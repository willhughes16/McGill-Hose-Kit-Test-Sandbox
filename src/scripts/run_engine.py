#!/usr/bin/env python3
"""Run the vendored McGill email->BOM engine over one RFQ and persist its CaseState.

This is a THIN WRAPPER, deliberately. It does not re-derive, re-order or
re-interpret anything: it calls the vendored CLI's own ``main()`` with
``--json`` and writes the bytes that come back. The engine's logic carries 507
tests and 24 blind verification rounds; any second expression of it would be a
copy that can drift, so there is none here.

Because it goes through the real ``cli.main``, this wrapper inherits for free:
argument handling, ``.eml``/MIME decoding (including the ``[html-source]`` and
``[hidden-content-suspected]`` sentinels DD-2 depends on), the questions /
open_items duality, and the exit-code contract.

Exit codes (the WRAPPER's, not the engine's):
    0  CaseState written
    1  could not read the input, load config, or write the output

The ENGINE's own exit code is a different thing and is reported separately (on
stdout and in state.json) because 2 -- "a draft with open items" -- is its
normal, by-design outcome, not a failure. Treating 2 as an error anywhere
upstream would be a new bug.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_VENDOR = os.path.join(os.path.dirname(_HERE), "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

from email_to_bom import cli  # noqa: E402  (needs the sys.path line above)


def run(email_path, component_ids=None, coc=False, config_dir=None):
    """Invoke the vendored CLI and return (case_state_json_text, engine_exit)."""
    argv = [email_path, "--json"]
    if component_ids:
        argv += ["--component-ids"] + list(component_ids)
    if coc:
        argv.append("--coc")
    if config_dir:
        argv += ["--config-dir", config_dir]

    buf, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
        engine_exit = cli.main(argv)
    stderr_text = err.getvalue()
    if engine_exit == 1:
        # The engine's 1 means it could not read input/config -- a real failure.
        raise SystemExit(f"engine could not read its input: {stderr_text.strip()}")
    return buf.getvalue(), engine_exit


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--in", dest="inp", required=True,
                   help="path to the RFQ .eml/.txt")
    p.add_argument("--out", dest="out", default=os.path.join("_report", "case_state.json"),
                   help="where to write the CaseState JSON")
    p.add_argument("--component-ids", nargs="*", default=[],
                   help="operator-confirmed Component IDs, passed straight through")
    p.add_argument("--coc", action="store_true",
                   help="customer requires a Certificate of Conformance")
    p.add_argument("--config-dir", default=None,
                   help="alternate config dir (e.g. one backed by the P21 item master)")
    p.add_argument("--state", default=None,
                   help="optional state.json to update with the run's outcome")
    args = p.parse_args(argv)

    if not os.path.isfile(args.inp):
        print(f"error: no such RFQ file: {args.inp}", file=sys.stderr)
        return 1

    try:
        payload, engine_exit = run(args.inp, args.component_ids, args.coc, args.config_dir)
    except SystemExit as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    try:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload)          # verbatim -- byte parity with `--json`
    except OSError as e:
        print(f"error: cannot write {args.out}: {e}", file=sys.stderr)
        return 1

    case = json.loads(payload)
    summary = {
        "input": args.inp,
        "case_state": args.out,
        "engine_exit": engine_exit,
        "request_class": case.get("request_class"),
        "urgent": bool(case.get("urgency", {}).get("flagged")),
        "open_items": len(case.get("open_items", [])),
        # Broken down by priority rather than just counting "blocking": the
        # conversation layer routes on all three (blocking / confirm /
        # must_acknowledge), and a bare total hides which asks gate a quote.
        "open_items_by_priority": {
            prio: sum(1 for it in case.get("open_items", [])
                      if it.get("priority") == prio)
            for prio in ("blocking", "confirm", "must_acknowledge")
        },
        "checkpoints": len(case.get("checkpoints", [])),
        "bom_lines": len(case.get("lines", [])),
        "knowledge_source": case.get("knowledge", {}).get("source"),
    }

    if args.state:
        state = {}
        if os.path.isfile(args.state):
            try:
                with open(args.state, encoding="utf-8") as fh:
                    state = json.load(fh)
            except (OSError, json.JSONDecodeError):
                state = {}
        state["extract_case"] = summary
        os.makedirs(os.path.dirname(os.path.abspath(args.state)), exist_ok=True)
        with open(args.state, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
            fh.write("\n")

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
