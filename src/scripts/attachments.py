#!/usr/bin/env python3
"""What the customer sent that the ENGINE never reads.

`vendor/email_to_bom/mail.py` reduces a MIME message to "Subject + best body
part": headers, encodings and HTML markup never reach the rules, and neither
does any attachment. There is no `walk()`, no `Content-Disposition` inspection
and no filename capture anywhere in the engine. So an RFQ whose dimensions are
in the attached drawing produces a CaseState that correctly reports the
dimensions missing -- and says nothing at all about the drawing.

That silence is the defect. The case reads as complete while the document the
customer considered the answer was never opened. This module exists to name the
files so the reply can say so.

What it does NOT do, deliberately:

  * it never opens, decodes or extracts an attachment's content. Naming a file
    is a fact about the message; reading one would be a second source of case
    data, outside the engine, with none of the engine's guarantees;
  * it never adds an open item. `open_items[]` is the engine's, and the kit may
    not write to it. The correct home for this is an `ATTACHMENT_NOT_READ` item
    in `ScaleUpLabs/McGill-Core`, beside `HTML_SOURCE_REVIEW` and
    `HIDDEN_CONTENT_DETECTED`, which already exist for "I saw something I could
    not safely read". This module is the kit-side interim;
  * it never decides an attachment is unimportant. Everything found is reported.

Failure degrades, never silences -- the rule `vendor/email_to_bom/knowledge.py`
states for its transport, applied here. An unreadable file, a malformed message
or a part that raises while being inspected all produce a record SAYING so. The
one outcome this module must never produce is a confident "no attachments" for a
message it could not actually read.
"""
from __future__ import annotations

import hashlib
import os
from email import policy
from email.parser import BytesParser

# Parts that are body candidates rather than evidence: the engine reads exactly
# one text part as the message body, so a text/plain or text/html part that is
# not explicitly an ATTACHMENT was almost certainly the thing it read.
#
# Known limit, stated rather than hidden: a message carrying a SECOND inline
# text/plain part -- not an alternative of the body, but additional prose -- goes
# unread by the engine and unflagged here. Multipart/alternative siblings carry
# the same content, so this is rare; a `Content-Disposition: attachment` text
# file is flagged normally.
_BODY_SUBTYPES = frozenset({"plain", "html"})


def _payload(part):
    """Decoded bytes, or None when the part will not decode."""
    try:
        return part.get_payload(decode=True)
    except Exception:             # noqa: BLE001 - a malformed part must not raise
        return None


def _size(part):
    """Decoded byte count, or None when the part will not decode."""
    payload = _payload(part)
    return len(payload) if payload is not None else None


def _sha256(part):
    """Hash of the attachment's own bytes, or None.

    Added for CW-9: a transcript names the file it claims to describe, and this is
    what pins that claim to the actual bytes the customer sent. Also lets a
    consumer recognise the same attachment across two messages.
    """
    payload = _payload(part)
    return hashlib.sha256(payload).hexdigest() if payload is not None else None


def _classify(part):
    """('attachments' | 'embedded' | None, record) for one non-multipart part.

    The returned name is the KEY in scan()'s record, not a prose label, so a
    caller cannot file a part under a bucket that does not exist.
    """
    try:
        filename = part.get_filename()
        disposition = part.get_content_disposition() or ""
        content_type = part.get_content_type()
        content_id = part.get("Content-ID")
        maintype, _, subtype = content_type.partition("/")
    except Exception as e:        # noqa: BLE001 - see module docstring
        # A part we cannot even describe is still a part the engine did not read.
        return "attachments", {"filename": "(part could not be inspected)",
                              "content_type": "unknown",
                              "disposition": "unknown",
                              "bytes": None,
                              "error": f"{type(e).__name__}: {e}"}
    if disposition != "attachment" and not filename:
        return None, None
    record = {"filename": filename or "(unnamed)",
              "content_type": content_type,
              "disposition": disposition or "(none)",
              "bytes": _size(part),
              "sha256": _sha256(part)}
    if disposition == "attachment":
        return "attachments", record
    if content_id:
        # Inline with a Content-ID: a signature logo or a body image. Reported,
        # but separately -- a block that cries wolf on every footer logo is a
        # block reviewers learn to skip, and then the drawing goes unread too.
        return "embedded", record
    if maintype == "text" and subtype in _BODY_SUBTYPES:
        return None, None         # the body the engine read
    return "attachments", record


def scan(path):
    """Inspect an RFQ file for parts the engine does not read.

    Returns a record that is ALWAYS truthful about its own reliability:

        {"status": "scanned" | "unreadable" | "not_checked",
         "attachments": [{filename, content_type, disposition, bytes}, ...],
         "embedded":    [... same shape ...],
         "error": str | None}

    `scanned` with two empty lists is the only form that means "there is nothing
    the engine missed". `unreadable` means we do not know, and the reply must say
    so rather than imply none. A plain-text RFQ parses cleanly and scans empty.
    """
    empty = {"status": "unreadable", "attachments": [], "embedded": [], "error": None}
    if not path or not os.path.isfile(path):
        return dict(empty, error=f"no such file: {path}")
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        return dict(empty, error=str(e))
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
        parts = list(message.walk())
    except Exception as e:        # noqa: BLE001 - see module docstring
        return dict(empty, error=f"{type(e).__name__}: {e}")

    found = {"status": "scanned", "attachments": [], "embedded": [], "error": None}
    for part in parts:
        try:
            if part.get_content_maintype() == "multipart":
                continue
        except Exception:         # noqa: BLE001
            pass                  # cannot tell -- fall through and classify it
        where, record = _classify(part)
        if where:
            found[where].append(record)
    return found


def not_checked(reason):
    """The record for a render that had no input file to look at.

    Used when a reply is produced from a CaseState in isolation. It must never
    be confused with a clean scan: the reply says the attachments were not
    checked, which is the truth, instead of silently omitting the subject.
    """
    return {"status": "not_checked", "attachments": [], "embedded": [],
            "error": reason}


def total(record):
    """How many unread files this record names. Embedded parts count too."""
    record = record or {}
    return len(record.get("attachments") or []) + len(record.get("embedded") or [])
