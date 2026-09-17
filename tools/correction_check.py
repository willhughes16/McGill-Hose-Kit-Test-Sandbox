#!/usr/bin/env python3
"""Check a reviewer correction, and say whether it can become a regression test.

Evolution 3 of the Coworker document: "reviewed corrections may become test cases
or proposed changes, but never alter production behaviour automatically." For
Factory to turn a correction into a test, the correction has to be REPLAYABLE --
tied to an input and a skill version, with the kit's original proposal recorded
byte for byte. A correction that is merely a better paragraph is an anecdote.

So this asks three questions, in order, and stops at the first failure:

1. **Is it a correction?** Validated against `src/schemas/correction.schema.json`
   with the kit's own schema engine. The schema is deliberately written inside
   that engine's supported subset -- no union types, no general `oneOf` -- because
   a contract the kit cannot machine-check is a contract in name only
   (FOLLOW-UP-10 records the same limitation biting `case_state.schema.json`).
2. **Does it pin to a real run?** `correction_of` must match a run manifest's
   idempotency key, kit version and engine commit. A correction replayed against
   a different skill version can "pass" while telling you nothing.
3. **Did the kit really propose that?** `original` must equal the artifact the
   run actually produced, byte for byte. Without this a correction can claim the
   kit said something it never said, and the test built from it would enshrine a
   defect that never existed -- the same shape as the parity fixture that had
   enshrined the size/length bug.

It is a CHECKER, not a collector: Body gathers corrections from reviewers. This
tool is what lets the kit accept one as a fixture.

Usage:  python3 tools/correction_check.py CORRECTION.json --run _report/
Exit 0 = replayable. Exit 1 = not, and the reason is printed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from _schema_engine import validate  # noqa: E402

SCHEMA = os.path.join(ROOT, "src", "schemas", "correction.schema.json")
ARTIFACT_FILE = {"reply": "reply.md", "review_request": "review_request.md"}


def _load(path, what):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), None
    except (OSError, json.JSONDecodeError) as e:
        return None, f"cannot read {what} at {path}: {e}"


def check(correction_path, run_dir):
    """Return a list of reasons this correction is not replayable. [] = it is."""
    with open(SCHEMA, encoding="utf-8") as fh:
        schema = json.load(fh)
    correction, err = _load(correction_path, "the correction")
    if err:
        return [err]

    errors = validate(schema, correction)
    if errors:
        return [f"schema: {e.path or '(root)'} — {e.reason}" for e in errors]

    manifest, err = _load(os.path.join(run_dir, "run_manifest.json"),
                          "the run manifest")
    if err:
        return [err + ". A correction must pin to a run; without the manifest "
                      "there is nothing to pin it to."]

    pin = correction["correction_of"]
    problems = []
    for field, actual in (
            ("idempotency_key", manifest.get("idempotency_key")),
            ("kit_version", (manifest.get("kit") or {}).get("version")),
            ("engine_commit", (manifest.get("engine") or {}).get("source_commit") or ""),
            ("input_sha256", (manifest.get("input") or {}).get("sha256") or "")):
        if pin.get(field) != actual:
            problems.append(
                f"pin: {field} is {pin.get(field)!r} but the run says {actual!r}. "
                "Replaying this correction would test a different run than the "
                "reviewer was looking at.")
    if problems:
        return problems

    artifact = os.path.join(run_dir, ARTIFACT_FILE[correction["artifact"]])
    try:
        with open(artifact, encoding="utf-8") as fh:
            produced = fh.read()
    except OSError as e:
        return [f"cannot read {artifact} to check the original against: {e}"]
    if produced != correction["original"]:
        return [f"original: the correction's `original` is not what the run "
                f"produced in {ARTIFACT_FILE[correction['artifact']]}. A test "
                "built from it would enshrine a proposal the kit never made."]
    if correction["corrected"] == correction["original"]:
        return ["corrected: identical to the original — nothing was corrected, so "
                "there is no test to build."]
    return []


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("correction", help="the correction record to check")
    p.add_argument("--run", default="_report",
                   help="the run directory it claims to correct (default _report)")
    args = p.parse_args(argv)

    problems = check(args.correction, args.run)
    if problems:
        print(f"NOT REPLAYABLE — {args.correction}", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    with open(args.correction, encoding="utf-8") as fh:
        correction = json.load(fh)
    print(f"REPLAYABLE — {args.correction}")
    print(f"  corrects   {correction['artifact']} of run "
          f"{correction['correction_of']['idempotency_key'][:12]} "
          f"(kit {correction['correction_of']['kit_version']}, engine "
          f"{correction['correction_of']['engine_commit'][:7] or '(unattributed)'})")
    print(f"  reviewer   {correction['reviewer']} at {correction['at']}")
    print(f"  disposition {correction['disposition']}")
    if correction["disposition"] == "reusable_knowledge":
        print("  NOTE: proposed as company knowledge. That is a PROPOSAL — it "
              "requires approval\n        before Factory acts on it, and it never "
              "alters production behaviour on its own.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
