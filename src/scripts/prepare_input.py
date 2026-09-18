#!/usr/bin/env python3
"""Build the message the kit reads from what the runtime actually delivers.

The kit was written for an `.eml`. The Astro runtime does not deliver one: it
hands the agent the email BODY as text (usually HTML) and the ATTACHMENTS as
separate files under `input/`. Every successful run so far worked only because
the agent hand-assembled an `.eml` from those pieces, and job `2e07005c`
(2026-09-18) is what happened when it did not:

  * it wrote the HTML to a bare `rfq_email.html`. A bare file has no MIME parts,
    so the attachment scanner saw nothing — no EVIDENCE NOT READ, no
    `needs_human_input`, and `apply_transcript` would have refused. The purchase
    order that WAS the request vanished from the run. Outcome: `complete`.
  * a bare HTML file is not a message, so the engine's reader returned the RAW
    MARKUP. `DIMENSION_CONFIRM` fired on `font-size:16px`, and the customer was
    asked to clarify a measurement that does not exist in their email.

Both are one defect: the kit assumed a shape the runtime never produces, and
left the agent to bridge the gap by hand. This script closes it. The prepare
phase calls it; the agent never assembles a message again.

WHAT IT BUILDS. One RFC 5322 message: the body as a `text/html` part when it is
HTML (so the engine's own HTML-to-text path runs) or `text/plain` when it is
not, and every file in the attachments directory as a real attachment part with
its filename preserved. **No `text/plain` placeholder is added beside an HTML
body**: the engine prefers `plain` to `html`, and a placeholder is what produced
the 39-byte "This message contains HTML." case on 2026-09-17.

GUARDS, all failing CLOSED:

1. A body that is ALREADY a message (`looks_like_mime`) is used as-is. Wrapping a
   message in a message would hide its attachments one level down.
2. The built message is read back through the engine's own reader and refused if
   the extracted text still contains markup, or is empty. The wrapping must
   produce something the engine can actually read, and the check asks rather
   than assumes.
3. A body carrying a region marker is refused, exactly as an answer or a
   transcript is.

Exit codes -- ONLY these two, enforced by the clamp in ``__main__``:
    0  the message was written and the invocation points at it
    1  anything went wrong
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
from email.message import EmailMessage

_HERE = os.path.dirname(os.path.abspath(__file__))
_VENDOR = os.path.join(os.path.dirname(_HERE), "vendor")
for _p in (_VENDOR, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from email_to_bom.mail import extract_rfq_text, looks_like_mime  # noqa: E402
import answers as answers_mod  # noqa: E402
from run_state import (  # noqa: E402
    StateError, input_sha256, make_invocation, write_state,
)

DEFAULT_OUT = os.path.join("_report", "rfq.eml")
_HTML = re.compile(rb"^\s*(?:<!doctype\s+html|<html|<head|<body|<div|<span|<p\b)", re.I)
_MARKUP = re.compile(r"<\s*/?\s*(?:html|body|head|div|span|meta|br|p)\b", re.I)


def looks_like_html(raw):
    """Markup at the start, or an <html>/<body> tag anywhere in the head."""
    head = raw[:4096]
    return bool(_HTML.match(head)) or b"<html" in head.lower() or b"<body" in head.lower()


def build(body_raw, body_name, subject, sender, to, attachments):
    """Assemble the message. Returns (bytes, kind) where kind is html|plain."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    text = body_raw.decode("utf-8", errors="replace")
    if looks_like_html(body_raw):
        # HTML as the ONLY body part. See the docstring for why no placeholder.
        msg.set_content(text, subtype="html")
        kind = "html"
    else:
        msg.set_content(text)
        kind = "plain"
    for path in attachments:
        ctype, _ = mimetypes.guess_type(path)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        with open(path, "rb") as fh:
            msg.add_attachment(fh.read(), maintype=maintype, subtype=subtype,
                               filename=os.path.basename(path))
    return bytes(msg), kind


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--body", required=True,
                   help="the email body as the runtime delivered it: HTML, plain "
                        "text, or an existing .eml (used as-is)")
    p.add_argument("--attachments-dir", default=None,
                   help="every regular file here becomes an attachment part")
    p.add_argument("--attach", nargs="*", default=[],
                   help="individual files to attach, in addition to the directory")
    p.add_argument("--subject", default="RFQ")
    p.add_argument("--from", dest="sender", default="customer@unknown.invalid")
    p.add_argument("--to", default="sales@unknown.invalid")
    p.add_argument("--out", default=DEFAULT_OUT)
    p.add_argument("--state", default=os.path.join("_report", "state.json"))
    p.add_argument("--component-ids", nargs="*", default=[])
    p.add_argument("--coc", action="store_true")
    p.add_argument("--config-dir", default=None)
    args = p.parse_args(argv)

    if not os.path.isfile(args.body):
        print(f"error: no such body file: {args.body}", file=sys.stderr)
        return 1
    try:
        with open(args.body, "rb") as fh:
            body_raw = fh.read()
    except OSError as e:
        print(f"error: cannot read {args.body}: {e}", file=sys.stderr)
        return 1

    attachments = list(args.attach)
    if args.attachments_dir:
        if not os.path.isdir(args.attachments_dir):
            print(f"error: no such attachments directory: {args.attachments_dir}",
                  file=sys.stderr)
            return 1
        for name in sorted(os.listdir(args.attachments_dir)):
            path = os.path.join(args.attachments_dir, name)
            if os.path.isfile(path) and not name.startswith("."):
                attachments.append(path)
    for path in attachments:
        if not os.path.isfile(path):
            print(f"error: no such attachment: {path}", file=sys.stderr)
            return 1

    text_probe = body_raw.decode("utf-8", errors="replace")
    for marker in (answers_mod.MARKER, answers_mod.TRANSCRIPT_MARKER):
        if marker in text_probe:
            print("error: the body contains a region marker. Refusing: a customer's "
                  "message must not imitate the boundary between authors.",
                  file=sys.stderr)
            return 1

    # Guard 1: already a message -> use as-is, but only if there is nothing to add.
    if looks_like_mime(body_raw, args.body):
        if attachments:
            print("error: the body is already an .eml AND attachments were given. "
                  "Refusing to wrap a message inside a message — its own "
                  "attachments would sit one level down where the scanner does not "
                  "look. Either pass the .eml alone or pass the body text with the "
                  "files.", file=sys.stderr)
            return 1
        out_bytes, kind = body_raw, "mime"
    else:
        out_bytes, kind = build(body_raw, args.body, args.subject, args.sender,
                                args.to, attachments)

    # Guard 2: the engine must be able to READ what we built.
    extracted = extract_rfq_text(out_bytes, filename=args.out)
    if not extracted.strip():
        print("error: the engine extracts NOTHING from the message that was built. "
              "Refusing to hand it an empty case.", file=sys.stderr)
        return 1
    if kind != "mime" and _MARKUP.search(extracted):
        print("error: the engine's reader still sees raw markup in the built "
              "message — the HTML was not wrapped in a way it can read. Refusing: "
              "this is exactly how a CSS font size became a customer question.",
              file=sys.stderr)
        return 1

    try:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "wb") as fh:
            fh.write(out_bytes)
    except OSError as e:
        print(f"error: cannot write {args.out}: {e}", file=sys.stderr)
        return 1

    try:
        write_state(args.state, {
            "invocation": make_invocation(args.out, args.component_ids, args.coc,
                                          args.config_dir),
            "prepared_from": {
                "body": args.body,
                "body_kind": kind,
                "body_sha256": input_sha256(args.body),
                "attachments": [{"path": a, "sha256": input_sha256(a)}
                                for a in attachments],
            },
        }, drop=("extract_case", "answers", "transcripts"))
    except StateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(json.dumps({"message": args.out, "body_kind": kind,
                      "attachments": [os.path.basename(a) for a in attachments],
                      "engine_will_read_bytes": len(extracted.encode("utf-8"))},
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
