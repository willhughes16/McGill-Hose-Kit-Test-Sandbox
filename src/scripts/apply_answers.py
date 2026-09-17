#!/usr/bin/env python3
"""Fold answers a human gave outside the thread into the case text (CW-6).

Run between the prepare phase and the extract phase, and only when a reviewer has
answered something in Teams or by phone -- text that never reaches the email
thread, so the next run would re-ask a question a human already answered.

What it does: takes the text the engine WOULD have read from the RFQ, appends an
operator addendum, writes the result as the run's new input, and points the
recorded invocation at it. From there the run is ordinary: the engine reads one
text file and treats the addendum exactly as a later message in the thread.

What it does NOT do is answer anything. See `answers.py` for why the addendum is
the whole design and a resolution path is not.

Two guards, both failing CLOSED:

1. **The augmented text must survive the engine's own reader unchanged.** The
   text is built from `mail.extract_rfq_text` and then read back through it: if
   the round trip is not byte-identical, this refuses. It matters for a forwarded
   thread whose body carries `From:`/`Subject:` lines -- written back out as a
   flat `.txt`, those can make the engine's MIME sniffer parse the file a second
   time and mangle it. Rather than reason about when that happens, the check
   asks. When it refuses, paste the answer into the email thread instead; that
   path always works, and this script is only a shortcut for it.
2. **The original is never modified.** The augmented text is a new file beside
   the run, and the original input's path and hash are recorded in `state.json`
   so a later phase can always get back to what the customer actually sent.

Exit codes -- ONLY these two, enforced by the clamp in ``__main__``:
    0  the augmented input was written and the invocation points at it
    1  anything went wrong
"""
from __future__ import annotations

import argparse
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
from run_state import (  # noqa: E402
    StateError, input_sha256, make_invocation, normalize_invocation, read_state,
    write_state,
)

DEFAULT_OUT = os.path.join("_report", "augmented_input.txt")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--answers", required=True,
                   help="JSON file: {\"answers\": [{answer, answered_by, "
                        "code?, answered_at?}, ...]}")
    p.add_argument("--state", default=os.path.join("_report", "state.json"))
    p.add_argument("--out", default=DEFAULT_OUT,
                   help=f"where to write the augmented case text (default "
                        f"{DEFAULT_OUT})")
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
        with open(args.answers, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: cannot read {args.answers}: {e}", file=sys.stderr)
        return 1
    try:
        records = answers_mod.validate((payload or {}).get("answers"))
    except answers_mod.AnswerError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    try:
        with open(source, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        print(f"error: cannot read {source}: {e}", file=sys.stderr)
        return 1
    # The text the engine WOULD read, produced by the engine's own reader rather
    # than by a second expression of it.
    customer_text = extract_rfq_text(raw, filename=source)
    if answers_mod.MARKER in customer_text:
        print("error: the RFQ text already contains the operator-addendum "
              "marker.\n       Refusing: a second addendum would make the "
              "boundary between the customer's\n       words and an operator's "
              "ambiguous, which is the one thing this must never do.",
              file=sys.stderr)
        return 1
    augmented = (customer_text.rstrip("\n") + "\n\n"
                 + answers_mod.build_addendum(records))

    # Guard 1: the engine must read back exactly what we wrote.
    reread = extract_rfq_text(augmented.encode("utf-8"), filename=args.out)
    if reread != augmented:
        print("error: the augmented text does not survive the engine's own reader "
              "unchanged.\n"
              "       Written flat, this case re-parses as a MIME message (a "
              "forwarded thread whose\n"
              "       body carries From:/Subject: lines does this), so the engine "
              "would extract\n"
              "       something different from what you just approved. Refusing.\n"
              "       Paste the answer into the email thread and re-run instead — "
              "that path always\n"
              "       works, and this script is only a shortcut for it.",
              file=sys.stderr)
        return 1

    try:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(augmented)
    except OSError as e:
        print(f"error: cannot write {args.out}: {e}", file=sys.stderr)
        return 1

    # The run now reads the augmented text. The ORIGINAL is recorded, never
    # overwritten: every later phase can still get back to what the customer sent.
    new_invocation = make_invocation(args.out, invocation.get("component_ids"),
                                     invocation.get("coc"),
                                     invocation.get("config_dir"))
    try:
        write_state(args.state, {
            "invocation": new_invocation,
            "answers": {
                "original_input": source,
                "original_sha256": input_sha256(source),
                "augmented_input": args.out,
                "records": records,
            },
        }, drop=("extract_case",))
    except StateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(json.dumps({"augmented_input": args.out,
                      "original_input": source,
                      "answers_applied": len(records),
                      "note": "the engine reads these as a later message in the "
                              "thread; no open item has been answered"}, indent=2))
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
