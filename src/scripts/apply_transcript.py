#!/usr/bin/env python3
"""Fold a machine reading of an attachment into the case text (CW-9).

The engine reads "Subject + best body part" and nothing else, so when the request
IS the attachment — a purchase order as a PDF — the kit's honest answer is "1
attached file, and the engine opened none of them". Correct, and useless.

The capability to read it exists one layer ABOVE this kit: the runtime executing
the kit has a vision-capable host model and a tool for opening artifacts. The
kit's own scripts do not and must not — they are stdlib, offline, and that is
what makes the engine's output reproducible.

So the agent TRANSCRIBES and this script folds the transcript in. **The model
never extracts, classifies, answers or maps to fields.** The engine still applies
every rule and owns the CaseState; a transcript is simply more text for it to
read, in a region marked with a third author.

WHAT THIS BUYS, AND WHAT IT DOES NOT. Every human-facing document marks a
transcribed value, the run manifest lists them, and the outcome always demands a
human. But `case_state.json` — the machine contract — will still say `captured`
for a transcribed value: `fields{}` carries a status and no provenance, and
forking the engine's contract is the one thing this kit never does. A consumer
reading the CaseState alone cannot tell a transcribed value from a typed one. The
provenance lives in the manifest beside it. Closing that properly is an upstream
change in `ScaleUpLabs/McGill-Core`.

ORDER MATTERS. Run this BEFORE `apply_answers.py`: regions are chronological
(the attachment arrived with the email, an out-of-thread answer came after), and
`supersedes` is order-dependent. Running it after will refuse anyway, because by
then the invocation points at a text file with no attachments to match against.

Guards, all failing CLOSED:

1. **The file must be one the customer actually sent.** A transcript is accepted
   only for a filename the attachment scanner found in this run's input, and the
   attachment's own sha256 is recorded. A transcript for a file nobody sent is
   impossible.
2. **Neither marker may appear in the transcript** — a transcript that forges a
   boundary between authors is refused, exactly as an answer is.
3. **The augmented text must survive the engine's own reader unchanged**, the same
   round-trip guard `apply_answers.py` uses and for the same reason.
4. **A method must be named.** The kit cannot verify a transcript is faithful, and
   it cannot verify the method either — but "parsed a CSV" and "looked at a
   picture of a table" are different claims, and a reviewer is entitled to know
   which one they are being asked to trust.

Exit codes -- ONLY these two, enforced by the clamp in ``__main__``:
    0  the transcript was folded in and the invocation points at the result
    1  anything went wrong
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_VENDOR = os.path.join(os.path.dirname(_HERE), "vendor")
for _p in (_VENDOR, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from email_to_bom.mail import extract_rfq_text  # noqa: E402
import answers as answers_mod  # noqa: E402
import attachments  # noqa: E402
from run_state import (  # noqa: E402
    StateError, input_sha256, make_invocation, normalize_invocation, read_state,
    write_state,
)

DEFAULT_OUT = os.path.join("_report", "transcribed_input.txt")
REQUIRED = ("filename", "method", "text")


class TranscriptError(Exception):
    """A transcript that must not be folded into a case."""


def validate(records, found):
    """Return the transcripts to apply, or raise. `found` is the scanner's list."""
    by_name = {str(f.get("filename")): f for f in found}
    if not isinstance(records, list) or not records:
        raise TranscriptError(
            "no transcripts to apply: expected a non-empty 'transcripts' list")
    out = []
    for i, rec in enumerate(records, 1):
        if not isinstance(rec, dict):
            raise TranscriptError(f"transcript {i} is not an object")
        for key in REQUIRED:
            if not str(rec.get(key) or "").strip():
                raise TranscriptError(
                    f"transcript {i} has no '{key}'. Refusing: a transcript whose "
                    "source, method or content is unrecorded cannot be told from "
                    "the customer's own words later.")
        name = str(rec["filename"]).strip()
        if name not in by_name:
            raise TranscriptError(
                f"transcript {i} claims to be {name!r}, which is not among the "
                f"files this message carries ({sorted(by_name) or 'none'}). "
                "Refusing: a transcript of a file nobody sent is a fabrication "
                "with a filename on it.")
        text = str(rec["text"])
        for marker in (answers_mod.MARKER, answers_mod.TRANSCRIPT_MARKER):
            if marker in text:
                raise TranscriptError(
                    f"transcript {i} contains a region marker. Refusing rather "
                    "than embedding text that imitates the boundary between "
                    "authors.")
        out.append({"filename": name,
                    "method": str(rec["method"]).strip(),
                    "text": text.strip(),
                    "source_sha256": by_name[name].get("sha256"),
                    "source_bytes": by_name[name].get("bytes"),
                    "transcript_sha256": hashlib.sha256(
                        text.encode("utf-8")).hexdigest()})
    return out


def build_block(records):
    """The transcript region. Human-readable; no format to parse back."""
    lines = [answers_mod.TRANSCRIPT_MARKER, ""]
    for rec in records:
        lines.append(f"Transcribed from {rec['filename']} "
                     f"(read by: {rec['method']}):")
        lines.append(rec["text"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--transcripts", required=True,
                   help='JSON: {"transcripts": [{filename, method, text}, ...]}')
    p.add_argument("--state", default=os.path.join("_report", "state.json"))
    p.add_argument("--out", default=DEFAULT_OUT)
    args = p.parse_args(argv)

    invocation = normalize_invocation(read_state(args.state).get("invocation"))
    if not invocation:
        print(f"error: no usable invocation in {args.state}; run the prepare "
              "phase first", file=sys.stderr)
        return 1
    source = invocation["input"]
    if not os.path.isfile(source):
        print(f"error: no such RFQ file: {source}", file=sys.stderr)
        return 1

    try:
        with open(args.transcripts, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: cannot read {args.transcripts}: {e}", file=sys.stderr)
        return 1

    scan = attachments.scan(source)
    if scan.get("status") != "scanned":
        print(f"error: the attachments of {source} could not be read "
              f"({scan.get('error')}), so a transcript cannot be matched to one. "
              "Refusing.", file=sys.stderr)
        return 1
    found = (scan.get("attachments") or []) + (scan.get("embedded") or [])
    try:
        records = validate((payload or {}).get("transcripts"), found)
    except TranscriptError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    try:
        with open(source, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        print(f"error: cannot read {source}: {e}", file=sys.stderr)
        return 1
    customer_text = extract_rfq_text(raw, filename=source)
    for marker in (answers_mod.MARKER, answers_mod.TRANSCRIPT_MARKER):
        if marker in customer_text:
            print("error: the RFQ text already contains a region marker. "
                  "Refusing: a second\n       region would make the boundary "
                  "between authors ambiguous, which is the one\n       thing this "
                  "must never do.", file=sys.stderr)
            return 1
    augmented = (customer_text.rstrip("\n") + "\n\n" + build_block(records))

    reread = extract_rfq_text(augmented.encode("utf-8"), filename=args.out)
    if reread != augmented:
        print("error: the transcribed text does not survive the engine's own "
              "reader unchanged.\n"
              "       Written flat, this case re-parses as a MIME message, so the "
              "engine would\n"
              "       extract something other than what was transcribed. Refusing. "
              "Paste the\n"
              "       attachment's content into the email thread as text and re-run "
              "instead.", file=sys.stderr)
        return 1

    try:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(augmented)
    except OSError as e:
        print(f"error: cannot write {args.out}: {e}", file=sys.stderr)
        return 1

    new_invocation = make_invocation(args.out, invocation.get("component_ids"),
                                     invocation.get("coc"),
                                     invocation.get("config_dir"))
    try:
        write_state(args.state, {
            "invocation": new_invocation,
            "transcripts": {
                "original_input": source,
                "original_sha256": input_sha256(source),
                "transcribed_input": args.out,
                # The text is NOT duplicated here: it lives in the case file the
                # engine reads, and a second copy is a copy that can drift.
                "records": [{k: v for k, v in r.items() if k != "text"}
                            for r in records],
            },
        }, drop=("extract_case",))
    except StateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(json.dumps({"transcribed_input": args.out,
                      "original_input": source,
                      "transcripts_applied": len(records),
                      "note": "the engine reads these as part of the case text; "
                              "every value taken from them is marked TRANSCRIBED "
                              "and the outcome always requires a human"},
                     indent=2))
    return 0


if __name__ == "__main__":
    try:
        _rc = main()
    except KeyboardInterrupt:
        _rc = 1
    except BaseException as _e:  # noqa: BLE001 - deliberate
        print(f"error: unhandled {type(_e).__name__}: {_e}", file=sys.stderr)
        _rc = 1
    raise SystemExit(0 if _rc == 0 else 1)
