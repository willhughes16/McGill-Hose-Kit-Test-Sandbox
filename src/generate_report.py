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

Because it re-runs the engine, it must reproduce the SAME invocation phase 1
used -- every flag, not just the input path. Round 25 (F-1) found that it did
not: flags were dropped, so a ``--component-ids`` run produced a draft with an
empty BOM table and a phantom ``SELECTION_UNRESOLVED``, silently contradicting
the CaseState a human had already resolved.

Two structural defences now make that class of divergence unshippable:

1. The invocation is replayed from ``state.json`` through
   ``run_engine.build_argv`` -- the SAME argv builder phase 1 used. There is no
   second place for the argument contract to live.
2. Before writing anything, this script re-derives the CaseState from that
   invocation and asserts it equals the ``case_state.json`` on disk. If the two
   disagree the run FAILS loudly instead of emitting a draft that describes a
   different case. That check is exact (structural JSON comparison, no text
   parsing) and it catches any future invocation drift, including causes nobody
   has thought of yet.

Note the rendering is deliberately LOSSY next to the CaseState: it drops
``fields``, ``routing``, ``knowledge``, ``supersedes`` and every open-item
attribute except the code and the ask. ``case_state.json`` -- not this file --
is the integration contract and the kit's email attachment.

Exit codes: 0 = draft written; 1 = could not read input, replay the invocation,
write the output, or reconcile the draft with the CaseState.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_VENDOR = os.path.join(_HERE, "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)
sys.path.insert(0, os.path.join(_HERE, "scripts"))

from run_engine import run_engine  # noqa: E402  (shares ONE argv builder)


def load_invocation(state_path, cli_args):
    """Return the invocation to replay.

    Prefers the whole invocation recorded by run_engine.py; falls back to
    explicit CLI arguments when no state file is in play (parity fixtures, ad-hoc
    use). Returns None when neither supplies an input path.
    """
    if cli_args.inp:
        return {
            "input": cli_args.inp,
            "component_ids": list(cli_args.component_ids),
            "coc": bool(cli_args.coc),
            "config_dir": cli_args.config_dir,
        }
    try:
        with open(state_path, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    inv = state.get("invocation")
    if not isinstance(inv, dict) or not inv.get("input"):
        return None
    # Normalise so a state file written by an older kit cannot silently omit keys.
    return {
        "input": inv["input"],
        "component_ids": list(inv.get("component_ids") or []),
        "coc": bool(inv.get("coc")),
        "config_dir": inv.get("config_dir"),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--in", dest="inp", default=None,
                   help="path to the RFQ .eml/.txt; defaults to the invocation in --state")
    p.add_argument("--out", dest="out", default=os.path.join("_report", "bom_draft.md"),
                   help="where to write the human-readable draft")
    p.add_argument("--component-ids", nargs="*", default=[])
    p.add_argument("--coc", action="store_true")
    p.add_argument("--config-dir", default=None)
    p.add_argument("--state", default=os.path.join("_report", "state.json"),
                   help="state.json written by scripts/run_engine.py")
    p.add_argument("--case-state", default=None,
                   help="case_state.json to reconcile against; defaults to the one "
                        "named in --state, else _report/case_state.json")
    args = p.parse_args(argv)

    invocation = load_invocation(args.state, args)
    if not invocation:
        print(f"error: no RFQ input given and no usable invocation recorded in "
              f"{args.state}; pass --in", file=sys.stderr)
        return 1
    if not os.path.isfile(invocation["input"]):
        print(f"error: no such RFQ file: {invocation['input']}", file=sys.stderr)
        return 1

    # ---- Defence 2: reconcile with the CaseState phase 1 produced -----------
    case_path = args.case_state
    if case_path is None:
        try:
            with open(args.state, encoding="utf-8") as fh:
                case_path = (json.load(fh).get("extract_case") or {}).get("case_state")
        except (OSError, json.JSONDecodeError):
            case_path = None
        if case_path is None:
            case_path = os.path.join("_report", "case_state.json")

    try:
        replayed_json, engine_exit = run_engine(invocation, as_json=True)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    replayed = json.loads(replayed_json)

    if os.path.isfile(case_path):
        try:
            with open(case_path, encoding="utf-8") as fh:
                on_disk = json.load(fh)
        except (OSError, json.JSONDecodeError) as e:
            print(f"error: cannot read {case_path} to reconcile against: {e}",
                  file=sys.stderr)
            return 1
        if on_disk != replayed:
            print(
                "error: the draft would not describe the same case as "
                f"{case_path}.\n"
                "       Replaying the recorded invocation produced a DIFFERENT "
                "CaseState, so the\n"
                "       human draft and the machine contract would disagree. "
                "Refusing to write a\n"
                "       draft that is silently wrong. Re-run the extract phase, "
                "or pass the same\n"
                "       flags to both phases.\n"
                f"       invocation replayed: {json.dumps(invocation)}\n"
                f"       differing top-level keys: "
                f"{sorted(k for k in set(on_disk) | set(replayed) if on_disk.get(k) != replayed.get(k))}",
                file=sys.stderr)
            return 1
    else:
        print(f"warning: {case_path} not found — writing the draft without "
              "reconciling it against a CaseState", file=sys.stderr)

    # ---- Render, verbatim ---------------------------------------------------
    try:
        payload, engine_exit = run_engine(invocation, as_json=False)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    try:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload)          # verbatim -- byte parity with the source
    except OSError as e:
        print(f"error: cannot write {args.out}: {e}", file=sys.stderr)
        return 1

    print(f"wrote {args.out} ({len(payload)} bytes, engine_exit={engine_exit}, "
          f"reconciled against {case_path if os.path.isfile(case_path) else 'nothing'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
