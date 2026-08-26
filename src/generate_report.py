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
deterministic, so re-running it is free of that risk.

Three defences keep this artifact from ever disagreeing with the CaseState:

1. **One invocation contract.** The engine call is replayed from ``state.json``
   through ``run_state.build_argv`` -- the same builder phase 1 used. Round 25
   (F-1) found the flags being re-typed and half-dropped here, which produced a
   draft with an empty BOM table and a phantom ``SELECTION_UNRESOLVED``.
2. **Reconciliation, and it FAILS CLOSED.** Before writing, this re-derives the
   CaseState and requires it to equal ``case_state.json``. Round 26 (R26-F3)
   found the check gated on ``os.path.isfile``, so an absent or non-regular
   CaseState skipped it and a divergent pair could be landed. A missing CaseState
   is now an error; skipping reconciliation requires saying ``--no-reconcile``
   out loud.
3. **Its own artifact is invalidated first.** Round 26 (R26-F1) found every
   failure path here leaving the *previous* customer's draft in place beside the
   new customer's CaseState. The draft is cleared before any work that can fail.

Note the rendering is deliberately LOSSY next to the CaseState: it drops
``fields``, ``routing``, ``knowledge``, ``supersedes`` and every open-item
attribute except the code and the ask. ``case_state.json`` -- not this file -- is
the integration contract and the kit's email attachment.

Exit codes -- ONLY these two, enforced by the clamp in ``__main__``:
    0  draft written and reconciled
    1  anything went wrong
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(_HERE, "vendor"), os.path.join(_HERE, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from run_engine import run_engine, warn_if_slow  # noqa: E402  (ONE argv builder)
from run_state import (  # noqa: E402
    ARTIFACTS, StateError, artifact_paths, invalidate, make_invocation,
    normalize_invocation, read_state,
)


def resolve_invocation(state_path, args):
    """Return the invocation to replay: explicit arguments, else the record."""
    if args.inp:
        return make_invocation(args.inp, args.component_ids, args.coc,
                               args.config_dir)
    return normalize_invocation(read_state(state_path).get("invocation"))


def resolve_case_state(state_path, explicit):
    if explicit:
        return explicit
    recorded = (read_state(state_path).get("extract_case") or {}).get("case_state")
    return recorded or ARTIFACTS["case_state"]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--in", dest="inp", default=None,
                   help="path to the RFQ; defaults to the invocation in --state")
    p.add_argument("--out", dest="out", default=ARTIFACTS["bom_draft"],
                   help="where to write the human-readable draft")
    p.add_argument("--component-ids", nargs="*", default=[])
    p.add_argument("--coc", action="store_true")
    p.add_argument("--config-dir", default=None)
    p.add_argument("--state", default=os.path.join("_report", "state.json"),
                   help="state.json written by scripts/run_engine.py")
    p.add_argument("--case-state", default=None,
                   help="CaseState to reconcile against; defaults to the one "
                        "named in --state")
    p.add_argument("--no-reconcile", action="store_true",
                   help="render WITHOUT checking the draft against a CaseState. "
                        "Only for rendering in isolation (e.g. a parity fixture); "
                        "never in a real run, where the check is the safety net.")
    args = p.parse_args(argv)

    paths = artifact_paths(bom_draft=args.out)

    # Clear our own artifact before anything that can fail, so no failure path
    # leaves the previous run's draft behind (R26-F1). Loud on failure (R26-F5).
    try:
        invalidate([artifact_paths(bom_draft=args.out)["bom_draft"]])
    except StateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    invocation = resolve_invocation(args.state, args)
    if not invocation:
        print(f"error: no RFQ input given and no usable invocation recorded in "
              f"{args.state}; pass --in", file=sys.stderr)
        return 1
    if not os.path.isfile(invocation["input"]):
        print(f"error: no such RFQ file: {invocation['input']}", file=sys.stderr)
        return 1
    warn_if_slow(invocation["input"], passes=2)

    # ---- Defence 2: reconcile, failing CLOSED -------------------------------
    if args.no_reconcile:
        print("warning: --no-reconcile — the draft is NOT being checked against a "
              "CaseState", file=sys.stderr)
    else:
        case_path = resolve_case_state(args.state, args.case_state)
        if not os.path.isfile(case_path):
            print(f"error: no CaseState to reconcile against at {case_path}. The "
                  "draft must be provably about the same case as the machine "
                  "contract, so refusing to render one that nothing can check. Run "
                  "the extract phase first, or pass --no-reconcile if you really "
                  "want an unchecked render.", file=sys.stderr)
            return 1
        try:
            with open(case_path, encoding="utf-8") as fh:
                on_disk = json.load(fh)
        except (OSError, json.JSONDecodeError) as e:
            print(f"error: cannot read {case_path} to reconcile against: {e}",
                  file=sys.stderr)
            return 1
        try:
            replayed = json.loads(run_engine(invocation, as_json=True)[0])
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        if on_disk != replayed:
            differing = sorted(k for k in set(on_disk) | set(replayed)
                               if on_disk.get(k) != replayed.get(k))
            print("error: the draft would not describe the same case as "
                  f"{case_path}.\n"
                  "       Replaying the recorded invocation produced a DIFFERENT "
                  "CaseState, so the\n"
                  "       human draft and the machine contract would disagree. "
                  "Refusing to write a\n"
                  "       draft that is silently wrong. Re-run the extract phase "
                  "so both artifacts\n"
                  "       come from one invocation.\n"
                  f"       invocation replayed: {json.dumps(invocation)}\n"
                  f"       differing top-level keys: {differing}",
                  file=sys.stderr)
            return 1

    # ---- Render, verbatim ---------------------------------------------------
    try:
        payload, engine_exit = run_engine(invocation, as_json=False)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    try:
        os.makedirs(os.path.dirname(os.path.abspath(paths["bom_draft"])),
                    exist_ok=True)
        with open(paths["bom_draft"], "w", encoding="utf-8") as fh:
            fh.write(payload)          # verbatim -- byte parity with the source
    except OSError as e:
        print(f"error: cannot write {paths['bom_draft']}: {e}", file=sys.stderr)
        return 1

    print(f"wrote {paths['bom_draft']} ({len(payload)} bytes, "
          f"engine_exit={engine_exit}, "
          f"{'NOT reconciled' if args.no_reconcile else 'reconciled'})")
    return 0


if __name__ == "__main__":
    # Clamp: 0 or 1 only. 2 is the ENGINE's success code (R26-F2).
    try:
        _rc = main()
    except KeyboardInterrupt:
        _rc = 1
    except BaseException as _e:  # noqa: BLE001 - deliberate
        print(f"error: unhandled {type(_e).__name__}: {_e}", file=sys.stderr)
        _rc = 1
    raise SystemExit(0 if _rc == 0 else 1)
