#!/usr/bin/env python3
"""Produce the human-readable draft BOM for a run.

Like ``scripts/run_engine.py`` this is a thin wrapper: it calls the vendored
CLI's own ``main()`` (this time WITHOUT ``--json``) and writes the bytes that
come back, verbatim. The result is byte-identical to what the source engine
prints, which is what makes parity provable rather than argued.

Why it re-runs the engine instead of rendering ``case_state.json`` itself: the
source's default rendering is a sequence of ``print`` statements inside
``cli.main``, not a reusable function, so reproducing it here would mean forking
~30 lines of formatting logic -- a second copy that can drift. The engine is
deterministic (verified byte-identical across runs and across PYTHONHASHSEED
values), so re-running it is free of that risk. It costs milliseconds.

Note the rendering is deliberately LOSSY next to the CaseState: it drops
``fields``, ``routing``, ``knowledge``, ``supersedes`` and every open-item
attribute except the code and the ask. ``case_state.json`` -- not this file --
is the integration contract and the kit's email attachment.

Exit codes: 0 = draft written; 1 = could not read input or write output.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_VENDOR = os.path.join(_HERE, "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

from email_to_bom import cli  # noqa: E402  (needs the sys.path line above)


def render(email_path, component_ids=None, coc=False, config_dir=None):
    """Return the engine's verbatim human rendering for one RFQ."""
    argv = [email_path]
    if component_ids:
        argv += ["--component-ids"] + list(component_ids)
    if coc:
        argv.append("--coc")
    if config_dir:
        argv += ["--config-dir", config_dir]

    buf, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
        engine_exit = cli.main(argv)
    if engine_exit == 1:
        raise SystemExit(f"engine could not read its input: {err.getvalue().strip()}")
    return buf.getvalue(), engine_exit


def _input_from_state(state_path):
    """Recover the RFQ path (and passthrough flags) recorded by run_engine.py."""
    try:
        with open(state_path, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    return (state.get("extract_case") or {}).get("input")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--in", dest="inp", default=None,
                   help="path to the RFQ .eml/.txt; defaults to the one recorded in --state")
    p.add_argument("--out", dest="out", default=os.path.join("_report", "bom_draft.md"),
                   help="where to write the human-readable draft")
    p.add_argument("--component-ids", nargs="*", default=[])
    p.add_argument("--coc", action="store_true")
    p.add_argument("--config-dir", default=None)
    p.add_argument("--state", default=os.path.join("_report", "state.json"),
                   help="state.json written by scripts/run_engine.py")
    args = p.parse_args(argv)

    email_path = args.inp or _input_from_state(args.state)
    if not email_path:
        print("error: no RFQ input given and none recorded in "
              f"{args.state}; pass --in", file=sys.stderr)
        return 1
    if not os.path.isfile(email_path):
        print(f"error: no such RFQ file: {email_path}", file=sys.stderr)
        return 1

    try:
        payload, engine_exit = render(email_path, args.component_ids,
                                      args.coc, args.config_dir)
    except SystemExit as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    try:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload)          # verbatim -- byte parity with the source
    except OSError as e:
        print(f"error: cannot write {args.out}: {e}", file=sys.stderr)
        return 1

    print(f"wrote {args.out} ({len(payload)} bytes, engine_exit={engine_exit})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
