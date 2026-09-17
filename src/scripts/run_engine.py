#!/usr/bin/env python3
"""Run the vendored McGill email->BOM engine over one RFQ and persist its CaseState.

This is a THIN WRAPPER, deliberately. It does not re-derive, re-order or
re-interpret anything: it calls the vendored CLI's own ``main()`` with
``--json`` and writes the bytes that come back. The engine's logic carries 529
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
import datetime
import io
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_VENDOR = os.path.join(os.path.dirname(_HERE), "vendor")
for _p in (_VENDOR, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from email_to_bom import cli  # noqa: E402  (needs the sys.path lines above)
import answers as answers_mod  # noqa: E402
import attachments  # noqa: E402  (kit-side: the engine reads none of them)
from run_state import (  # noqa: E402
    ARTIFACTS, KIT_NAME, KIT_VERSION, StateError, all_artifacts, artifact_paths,
    build_argv, derive_outcome, engine_commit, idempotency_key, input_sha256,
    invalidate, make_invocation, normalize_invocation, read_state, write_state,
)

# Past this size the engine's runtime grows superlinearly, and a kit run makes
# FOUR engine passes in total (one here, two in generate_report.py, one in
# render_reply.py's reconciliation), so the real cost is ~4x a single pass. We warn rather than refuse: refusing would change
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


def build_manifest(case, invocation, paths, engine_exit, started, elapsed_ms):
    """The run record: who produced this case, from what, and what it needs.

    This is the kit's half of the Body/Compute contract (CW-2/CW-3). Nothing
    here is a second expression of the CaseState -- `outcome` is derived from it
    by ``run_state.derive_outcome`` and the counts come from the same summary the
    extract phase already prints. `case_state.json` stays the engine's verbatim
    contract and is NOT touched: new information about a run goes in a new
    artifact, never by forking the contract.

    SCOPE, stated so nobody reads more into it than it says: this records the
    EXTRACT phase. It is written when a CaseState exists, before the renders run,
    so a manifest does not promise that `reply.md` was produced -- the render
    wrappers report that themselves, with their own exit codes.

    `idempotency_key` hashes the input's CONTENT plus the flags, deliberately not
    the input's path: the same email saved under a second name is the same case,
    and Body must be able to recognise a retry without inventing an identity for
    it.
    """
    commit, commit_error = engine_commit()
    input_sha = input_sha256(invocation["input"])
    evidence = attachments.scan(invocation["input"])
    _customer_text, _operator_text = answers_mod.read_case_text(invocation["input"])
    _operator_addendum = {
        "present": _operator_text is not None,
        "lines": answers_mod.addendum_lines(_operator_text),
    }
    # The outcome reads BOTH grounds: the engine's blocking items and the files
    # the engine could not see (REQ-097). The engine cannot raise an item about
    # an attachment it never opened, so the outcome has to carry it.
    outcome, outcome_reason = derive_outcome(case, evidence)
    try:
        size = os.path.getsize(invocation["input"])
    except OSError:
        size = None
    return {
        "manifest_kind": "run",
        "manifest_kind_version": 1,
        "kit": {"name": KIT_NAME, "version": KIT_VERSION},
        "engine": {"source_commit": commit,
                   "source_commit_error": commit_error,
                   "provenance": "vendor/PROVENANCE.md"},
        "input": {"path": invocation["input"], "sha256": input_sha, "bytes": size},
        "invocation": invocation,
        "idempotency_key": idempotency_key(invocation, input_sha),
        "case_state": {"path": paths["case_state"],
                       "schema_version": case.get("schema_version")},
        "engine_exit": engine_exit,
        "outcome": outcome,
        "outcome_reason": outcome_reason,
        "open_items_by_priority": {
            prio: sum(1 for it in case.get("open_items") or []
                      if (it or {}).get("priority") == prio)
            for prio in ("blocking", "confirm", "must_acknowledge")},
        "request_class": case.get("request_class"),
        # Whether an operator's words were folded into the case text (CW-6).
        # DERIVED from the input the engine actually read, not from the state
        # record that apply_answers.py wrote: the marker is in that file or it
        # is not, and a record of it could go stale while the file did not.
        "operator_addendum": _operator_addendum,
        # What the customer sent that the engine never opened (CW-1). Carried
        # here as well as rendered in the reply so Body can route on it without
        # parsing prose.
        "evidence_not_read": evidence,
        "started_utc": started,
        "elapsed_ms": elapsed_ms,
    }


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

    # A run's artifacts live TOGETHER. Round 35 (M-2): a fixture command that
    # set only --out left the draft and reply defaults resolving to the CURRENT
    # directory, so running the parity or golden suite from the kit root deleted
    # a real run's _report/bom_draft.md and _report/reply.md. Undeclared siblings
    # now default to --out's own directory, never to the CWD.
    # A run is identified by BOTH --out and --state, so its artifacts may live in
    # either directory and every one of them must be cleared. Round 35 (M-2)
    # scoped clearing to --out's directory, which stopped the suites deleting the
    # kit root's _report/ -- and round 36 (H-2) then found the other half: with
    # --out redirected, the run's OWN _report/reply.md (named by --state's
    # directory) survived beside a new CaseState. R26-F1, reintroduced by its own
    # fix. Clearing the union closes both: a suite passes both flags into its
    # fixture directory and never reaches the CWD, while a real run clears
    # everything it owns.
    _dirs = []
    for _p in (args.out, args.state):
        if _p:
            _d = os.path.dirname(_p) or "."
            if _d not in _dirs:
                _dirs.append(_d)
    # Every undeclared sibling resolves into --out's OWN directory, never the
    # CWD (round 35, M-2). The manifest is a sibling like any other: a suite run
    # from the kit root must not drop a run record into a real run's _report/.
    paths = artifact_paths(case_state=args.out,
                           bom_draft=args.draft or os.path.join(
                               _dirs[0], os.path.basename(ARTIFACTS["bom_draft"])),
                           manifest=os.path.join(
                               _dirs[0], os.path.basename(ARTIFACTS["manifest"])))
    # EVERY DECLARED artifact, in EVERY directory this run touches. Both halves
    # are load-bearing and a previous attempt at this lost one of them:
    #
    #   * driven by ARTIFACTS (not a hand-written name list) so a newly declared
    #     artifact is cleared with no call site edited -- R27-F4 / REQ-047, which
    #     the first cut of this fix silently broke;
    #   * across --out's AND --state's directories so nothing the run owns is
    #     left behind -- round 36 H-2 / R26-F1, which the round-35 fix broke.
    #
    # Iterating the declaration over the directories satisfies both; picking
    # either one alone has now failed once each.
    #
    # `case_state` is NOT excluded here, and that exclusion was a real defect
    # (found while adding the manifest, 2026-09-17 — the EIGHTEENTH instance of
    # this campaign's missed-sibling shape, and the one key that had been
    # exempted BY NAME). With --out redirected, the previous customer's
    # CaseState survived at the conventional `_report/case_state.json` while the
    # new one was written elsewhere: a consumer reading the default path got
    # customer A's case back after customer B's run. Verified before the fix and
    # asserted below it. Re-clearing --out costs nothing: invalidate() treats a
    # missing file as fine, so naming the same path twice is harmless, and an
    # exemption "because --out names it" is precisely how the sibling gets
    # missed.
    _sibling_paths = []
    for _d in _dirs:
        for _name in ARTIFACTS:
            _cand = os.path.join(_d, os.path.basename(ARTIFACTS[_name]))
            if _cand not in _sibling_paths:
                _sibling_paths.append(_cand)
    for _explicit in (args.draft,):
        if _explicit and _explicit not in _sibling_paths:
            _sibling_paths.append(_explicit)

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
        invalidate([args.out] + _sibling_paths)
        if args.state:
            write_state(args.state, {"invocation": invocation},
                        drop=("extract_case",))
    except StateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if not os.path.isfile(invocation["input"]):
        print(f"error: no such RFQ file: {invocation['input']}", file=sys.stderr)
        return 1
    warn_if_slow(invocation["input"], passes=1)

    started = datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="seconds")
    t0 = time.monotonic()
    try:
        payload, engine_exit = run_engine(invocation, as_json=True)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    try:
        os.makedirs(os.path.dirname(os.path.abspath(paths["case_state"])),
                    exist_ok=True)
        with open(paths["case_state"], "w", encoding="utf-8") as fh:
            fh.write(payload)          # verbatim -- byte parity with `--json`
    except OSError as e:
        print(f"error: cannot write {paths['case_state']}: {e}", file=sys.stderr)
        return 1

    case = json.loads(payload)
    summary = summarize(case, paths["case_state"], engine_exit)
    try:
        # The invocation is recorded WHOLE. generate_report.py replays it.
        write_state(args.state, {"invocation": invocation, "extract_case": summary})
    except StateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    # The run record (CW-2/CW-3). Written LAST, so it exists only for a run that
    # produced a CaseState: absence is the failure signal, and a half-written
    # record can never claim a case that was not extracted.
    manifest = build_manifest(case, invocation, paths, engine_exit, started,
                              elapsed_ms)
    try:
        os.makedirs(os.path.dirname(os.path.abspath(paths["manifest"])),
                    exist_ok=True)
        with open(paths["manifest"], "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
            fh.write("\n")
    except OSError as e:
        print(f"error: cannot write {paths['manifest']}: {e}", file=sys.stderr)
        return 1
    if manifest["engine"]["source_commit_error"]:
        print(f"warning: the run manifest cannot attribute the engine: "
              f"{manifest['engine']['source_commit_error']}", file=sys.stderr)
    _unread = attachments.total(manifest["evidence_not_read"])
    if _unread:
        print(f"warning: the customer sent {_unread} file(s) the engine does not "
              "read; see EVIDENCE NOT READ in the reply", file=sys.stderr)

    print(json.dumps(dict(summary, input=invocation["input"],
                          outcome=manifest["outcome"],
                          manifest=paths["manifest"]), indent=2))
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
