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

Run state -- the artifact set, the invocation record and the argv -- is owned by
``run_state.py``, not by this file. See its docstring for why.

Exit codes (the WRAPPER's, not the engine's) -- ONLY these two, enforced:
    0  CaseState written
    1  anything went wrong

The clamp in ``__main__`` is deliberate. Round 26 (R26-F2) found that swapping
one exception type for another let argparse's ``SystemExit(2)`` escape from
inside ``cli.main``, so the wrapper exited **2** -- the code every document here
defines as normal success -- with no artifact and no message. Enumerating which
exceptions to catch is what failed; the wrapper now catches broadly AND cannot
return a success-looking code on a failure path, whatever appears in future.

The ENGINE's own exit code is a different thing and is reported separately (on
stdout and in state.json) because 2 -- "a draft with open items" -- is its
normal, by-design outcome.
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
for _p in (_VENDOR, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from email_to_bom import cli  # noqa: E402  (needs the sys.path lines above)
from run_state import (  # noqa: E402
    ARTIFACTS, FILTER_KEY, StateError, all_artifacts, artifact_paths, build_argv, invalidate,
    make_invocation, normalize_invocation, read_state, write_state,
)

# Past this size the engine's runtime grows superlinearly, and a kit run makes
# THREE engine passes in total (one here, two in generate_report.py), so the real
# cost is ~3x a single pass. We warn rather than refuse: refusing would change
# behaviour and break parity with the source, which processes it regardless.
SLOW_INPUT_BYTES = 100 * 1024


def warn_if_slow(path, passes):
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    if size > SLOW_INPUT_BYTES:
        print(f"warning: input is {size / 1024:.0f} KB; engine runtime grows "
              f"superlinearly past ~100 KB and this step makes {passes} engine "
              f"pass(es), so a multi-hundred-KB thread can take minutes",
              file=sys.stderr)


def run_engine(invocation, as_json=True):
    """Invoke the vendored CLI. Returns (stdout_text, engine_exit).

    Catches broadly on purpose. ``cli.main`` can raise ``SystemExit`` from its own
    argparse, and round 26 showed that enumerating the expected exception types is
    the failure mode -- the same lesson the vendored engine's knowledge.py records
    for its transport. Anything that is not a clean engine return is an engine
    failure, reported as one.
    """
    buf, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            engine_exit = cli.main(build_argv(invocation, as_json))
    except KeyboardInterrupt:
        raise
    except SystemExit as e:
        raise RuntimeError(
            f"engine exited via SystemExit({e.code}) instead of returning; "
            f"stderr: {err.getvalue().strip() or '(none)'}")
    except BaseException as e:  # noqa: BLE001 - deliberate; see docstring
        raise RuntimeError(f"engine raised {type(e).__name__}: {e}")
    if engine_exit == 1:
        raise RuntimeError(
            f"engine could not read its input: {err.getvalue().strip()}")
    return buf.getvalue(), engine_exit


def summarize(case, out_path, engine_exit):
    return {
        "case_state": out_path,
        "engine_exit": engine_exit,
        "request_class": case.get("request_class"),
        "urgent": bool(case.get("urgency", {}).get("flagged")),
        "open_items": len(case.get("open_items", [])),
        # Broken down by priority rather than just counting "blocking": the
        # conversation layer routes on all three, and a bare total hides which
        # asks gate a quote.
        "open_items_by_priority": {
            prio: sum(1 for it in case.get("open_items", [])
                      if it.get("priority") == prio)
            for prio in ("blocking", "confirm", "must_acknowledge")
        },
        "checkpoints": len(case.get("checkpoints", [])),
        "bom_lines": len(case.get("lines", [])),
        "knowledge_source": case.get("knowledge", {}).get("source"),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--in", dest="inp", default=None,
                   help="path to the RFQ .eml/.txt; omit with --from-state")
    p.add_argument("--from-state", action="store_true",
                   help="take the whole invocation from --state (written by the "
                        "prepare phase) instead of re-typing the flags here")
    p.add_argument("--out", dest="out", default=ARTIFACTS["case_state"],
                   help="where to write the CaseState JSON")
    p.add_argument("--draft", default=None,
                   help="path of the human draft this run invalidates "
                        f"(default {ARTIFACTS['bom_draft']})")
    p.add_argument("--component-ids", nargs="*", default=[])
    p.add_argument("--coc", action="store_true")
    p.add_argument("--config-dir", default=None)
    p.add_argument("--state", default=None,
                   help="state.json to read the invocation from and record into")
    args = p.parse_args(argv)

    paths = artifact_paths(case_state=args.out, bom_draft=args.draft)

    # Resolve the invocation BEFORE clearing anything, so a usage error does not
    # destroy a previous run's artifacts.
    if args.from_state:
        invocation = normalize_invocation(read_state(args.state).get("invocation"))
        if not invocation:
            print(f"error: --from-state given but {args.state} records no usable "
                  "invocation; run the prepare phase first or pass --in",
                  file=sys.stderr)
            return 1
    elif args.inp:
        invocation = make_invocation(args.inp, args.component_ids, args.coc,
                                     args.config_dir)
    else:
        print("error: pass --in <rfq> or --from-state", file=sys.stderr)
        return 1

    # A new extraction invalidates BOTH artifacts: the old draft describes the
    # previous case and must not survive beside a new CaseState (R26-F1). Loud on
    # failure (R26-F5) -- if we cannot guarantee the old ones are gone, stop.
    # Note what is invalidated and what is NOT: the RESULT record
    # (extract_case) is dropped because it is about to be recomputed, but the
    # INVOCATION is preserved and rewritten. Round 26 (R26-F10) found phase 1
    # wiping the prepare phase's record before it could fail, leaving
    # state.json as {} in exactly the case where resuming matters. Inputs are
    # not invalidated by a failure to produce outputs.
    try:
        invalidate(all_artifacts(case_state=args.out, bom_draft=args.draft))
        if args.state:
            # Also drop any prior FILTER_KEY record: a record of a decision NOT
            # to run the engine can only mislead once the engine has actually
            # run (the sibling of R26-F1, in the new screen_input code path).
            write_state(args.state, {"invocation": invocation},
                        drop=("extract_case", FILTER_KEY))
    except StateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if not os.path.isfile(invocation["input"]):
        print(f"error: no such RFQ file: {invocation['input']}", file=sys.stderr)
        return 1
    warn_if_slow(invocation["input"], passes=1)

    try:
        payload, engine_exit = run_engine(invocation, as_json=True)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    try:
        os.makedirs(os.path.dirname(os.path.abspath(paths["case_state"])),
                    exist_ok=True)
        with open(paths["case_state"], "w", encoding="utf-8") as fh:
            fh.write(payload)          # verbatim -- byte parity with `--json`
    except OSError as e:
        print(f"error: cannot write {paths['case_state']}: {e}", file=sys.stderr)
        return 1

    summary = summarize(json.loads(payload), paths["case_state"], engine_exit)
    try:
        # The invocation is recorded WHOLE. generate_report.py replays it.
        write_state(args.state, {"invocation": invocation, "extract_case": summary})
    except StateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(json.dumps(dict(summary, input=invocation["input"]), indent=2))
    return 0


if __name__ == "__main__":
    # Clamp: this wrapper reports 0 or 1 and nothing else. 2 is the ENGINE's
    # "draft with open items" success code and must never leak from a failure
    # path here (R26-F2).
    try:
        _rc = main()
    except KeyboardInterrupt:
        _rc = 1
    except BaseException as _e:  # noqa: BLE001 - deliberate
        print(f"error: unhandled {type(_e).__name__}: {_e}", file=sys.stderr)
        _rc = 1
    raise SystemExit(0 if _rc == 0 else 1)
