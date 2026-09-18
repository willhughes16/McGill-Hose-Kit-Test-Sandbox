#!/usr/bin/env python3
"""Render the whole case as an inline reply email for inside sales.

The kit's reply carries NO attachment. Everything an operator needs is in the
message body, including the parts `bom_draft.md` deliberately drops: every field
with its status and evidence, the routing recommendation, supersede history and
knowledge provenance.

It renders from `_report/case_state.json`, and it RECONCILES: before writing, it
re-derives the CaseState from the recorded invocation and refuses if the two
differ. Round 32 (H-1) found the earlier design -- read the file, trust it --
writing a confident reply from a CaseState `generate_report.py` had already
refused, complete with a fabricated price beneath this file's own footer stating
that no price appears. The reply is the ONLY artifact a human reads, so it needs
that guard more than the draft does, not less. The cost is one extra engine pass
(four per run in total); `--no-reconcile` skips it and is for rendering a
CaseState in isolation, never for a real run.

What this must never do, because the whole engine is built the other way:
  * never resolve, answer, drop or re-word an open item -- they are the point;
  * never state a price, a lead time or a stock position;
  * never present the draft as a quote, a confirmed BOM or an order;
  * never report a `reading` or `assumed` field as confirmed.

Exit codes -- ONLY these two, enforced by the clamp in ``__main__``:
    0  reply written
    1  anything went wrong
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import answers as answers_mod  # noqa: E402
import attachments  # noqa: E402
import lineitems  # noqa: E402
import questions as questions_mod  # noqa: E402
from run_engine import run_engine, warn_if_slow  # noqa: E402
from run_state import (  # noqa: E402
    ARTIFACTS, StateError, artifact_path, invalidate, normalize_invocation,
    read_state, source_input,
)

# The ONE status that means "the engine committed to this value".
CONFIRMED_STATUS = "captured"


def is_unconfirmed(status):
    """Whether a field status means the engine did NOT commit to the value.

    Inverted deliberately: anything that is not exactly `captured` is
    unconfirmed. Round 36 found the previous hand-written ten-member set had
    6 members deletable with the whole suite green -- one of them live on a plain
    camlock email -- so a future edit could quietly mark a field confirmed that
    the engine had refused to confirm.

    The set was CORRECT (exactly the schema's status enum minus `captured`);
    the problem was that a list can drift and nothing noticed. So the list is
    gone. There is nothing to delete, and a status the schema adds later is
    unconfirmed by default -- the safe direction, since the alternative is
    presenting a value as certain because we had not heard of its status yet.

    Same inversion as `_spec_field_names()` (derive, do not enumerate) and the
    `consumed` tracking (record, do not declare). Enumerations on the unsafe side
    of a decision have caused the majority of this campaign's findings.
    """
    return str(status) != CONFIRMED_STATUS


# Kept as a derived value for documentation and for tests that want the list.
# It is computed, never maintained.
UNCONFIRMED = frozenset(
    s for s in ("reading", "assumed", "needs_unit", "missing", "conflict",
                "missing_gender", "missing_spec", "size_confirm",
                "configuration_confirm", "superseded")
    if is_unconfirmed(s))

PRIORITY_ORDER = ("blocking", "confirm", "must_acknowledge")

# Characters a customer must never be able to put into the reply. Round 32 (C-1)
# showed an email line beginning "\x1b[2K\x1b[G" erases the attribution prefix in
# any terminal or pager and renders customer text byte-identically to the kit's
# own checkpoint lines -- a customer could show a checkpoint as CLEARED. Control
# characters are stripped and newlines folded, so untrusted text can never start
# a line, erase one, or open a section.
_ANSI = re.compile(
    # 7-bit CSI/OSC/DCS and single-character escapes, plus the 8-bit C1 forms
    # (0x9B CSI, 0x9D OSC, 0x90 DCS) a terminal acts on identically.
    r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?"
    r"|\x1b[P^_][^\x1b]*(?:\x1b\\)?"
    r"|\x1b\[[0-9;?]*[ -/]*[@-~]"
    r"|\x1b[@-Z\\-_]"
    r"|\x9b[0-9;?]*[ -/]*[@-~]"
    r"|[\x9d\x90][^\x9c]*\x9c?")

# Unicode categories that must never reach the page, stripped BY CATEGORY rather
# than by a list of code points. Round 33 (C-1) found the previous version
# handled ANSI and C0/C1 only, so a U+202E right-to-left override let a customer
# render arbitrary display text -- the demonstrated payload was "Can you confirm
# the price agreed at $9700?", forty lines above this file's own footer stating
# that no price appears. Enumerating code points is the failure mode that has
# recurred a dozen times in this campaign; a category test cannot go stale as
# Unicode adds characters.
#   Cc control · Cf format (bidi overrides, isolates, ZWJ/ZWNJ, soft hyphen,
#   BOM) · Cs surrogate · Co private use · Cn unassigned · Zl/Zp line and
#   paragraph separators.
_STRIP_CATEGORIES = frozenset({"Cf", "Cs", "Co", "Cn"})

# Categories that are WHITESPACE-LIKE and must fold to a space rather than
# vanish. Round 34 (C-1) found the round-33 rewrite deleting them: the category
# strip ran before the whitespace fold, and `\n` is `Cc`, so "temperature\n250"
# rendered as "temperature250" -- a token that appears in no email, printed in
# the Evidence column whose whole purpose is to be the customer's verbatim span.
# That FABRICATES rather than loses, with no marker, on a plain email with no
# hostile intent. Deleting a character that separates words is never safe;
# folding it is.
_FOLD_CATEGORIES = frozenset({"Cc", "Zl", "Zp"})


def _safe(value, limit=None):
    """Render an untrusted value as a single inert line of text.

    Everything the engine echoes back -- evidence spans, ask text, the captured
    customer name, notes -- originates in an email. It is DATA. This strips
    format/private/unassigned characters (including ANSI escapes and bidi
    overrides), FOLDS every whitespace-like character -- newlines, tabs, vertical
    tabs, line and paragraph separators -- to a space, and collapses runs. A
    rendered value occupies exactly one line and cannot imitate the document's
    own structure. Folding rather than deleting matters: round 34 found the
    delete-first version turning "temperature\n250" into "temperature250", a
    token present in no email.
    """
    text = "" if value is None else str(value)
    # Strip WHOLE escape sequences, not just the ESC byte. Removing only the
    # ESC leaves the printable residue ("[2K[G") in the page: harmless but
    # confusing noise that still reads as though the kit emitted it.
    text = _ANSI.sub("", text)
    text = text.replace("\t", " ")
    text = "".join(
        " " if unicodedata.category(ch) in _FOLD_CATEGORIES else ch
        for ch in text
        if unicodedata.category(ch) not in _STRIP_CATEGORIES)
    text = " ".join(text.split())
    if limit and len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def _table(rows, headers):
    if not rows:
        return None
    widths = [max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    out = [" | ".join(str(headers[i]).ljust(widths[i]) for i in range(len(headers))),
           "-|-".join("-" * w for w in widths)]
    for r in rows:
        out.append(" | ".join(str(r[i]).ljust(widths[i]) for i in range(len(headers))))
    return "\n".join(out)


# Keys already shown on an open item's headline. EVERY other key is printed
# underneath, so a key the engine adds later cannot be silently dropped.
_ITEM_HEADLINE = ("code", "ask", "quote", "priority")


def _open_item(it, show_priority=False):
    """One open item, with EVERY attribute the engine set.

    Round 32 (C-2/H-2) found this rendered through a hand-written three-key
    whitelist -- the exact shape `run_state.py` claims was structurally
    eliminated. A CAPABILITY_ANSWER_READY item lost both the customer's question
    (`quote`) and the catalog answer (`items`), leaving "propose these" with no
    referent; `tier`, `citation`, `candidates`, `context_text`, `field`, `topic`
    and `component_id` were dropped too. `fields` and `routing` had already been
    hardened against exactly this and open_items was the missed sibling.
    """
    out = []
    text = it.get("ask") or it.get("quote") or ""
    out.append(f"    [{_safe(it.get('code'))}] {_safe(text)}")
    if show_priority:
        # Round 33 (H-2): `priority` sits in the headline set, so it was excluded
        # from the all-other-keys loop AND never printed -- an unrecognised value
        # vanished entirely.
        out.append(f"        priority: {_safe(it.get('priority'))}")
    for k in sorted(k for k in it if k not in _ITEM_HEADLINE):
        v = it[k]
        if v in (None, "", [], {}):
            continue
        if isinstance(v, (list, dict)):
            out.append(f"        {_safe(k)}: {_safe(json.dumps(v, sort_keys=True))}")
        else:
            out.append(f"        {_safe(k)}: {_safe(v)}")
    # An item carrying BOTH a question and an ask must show both.
    if it.get("quote") and it.get("ask") and it["quote"] != it["ask"]:
        out.append(f"        quote: {_safe(it['quote'])}")
    return out


def _bytes(n):
    """A file size a human reads, or an honest admission that we do not know."""
    if not isinstance(n, int):
        return "size unknown"
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def _evidence_headline(evidence, transcribed=()):
    """One line, ALWAYS rendered, about what the customer attached.

    Always, because silence is what this feature exists to remove. If the block
    below appeared only when there were attachments, its absence would carry two
    meanings at once -- "none were sent" and "nobody looked" -- and a reviewer
    would have no way to tell which. A line that says NOT CHECKED is worth more
    than a page that says nothing.
    """
    evidence = evidence or attachments.not_checked("no attachment record")
    status = evidence.get("status")
    files = evidence.get("attachments") or []
    inline = evidence.get("embedded") or []
    if status != "scanned":
        return ("Attachments: NOT CHECKED — "
                + _safe(evidence.get("error") or status or "unknown reason")
                + ". Open the original message.")
    if files:
        # An attachment with a transcript WAS read -- by a machine, not by the
        # engine. Reporting it as "not read" beside a banner quoting its contents
        # makes the page contradict itself, and a reader resolves that by trusting
        # whichever line they saw last.
        named = {str(t) for t in transcribed}
        read_by_machine = [f for f in files if str(f.get("filename")) in named]
        unread = [f for f in files if str(f.get("filename")) not in named]
        parts = []
        if unread:
            parts.append(f"{len(unread)} the engine did NOT read")
        if read_by_machine:
            parts.append(f"{len(read_by_machine)} transcribed by a machine")
        if inline:
            parts.append(f"{len(inline)} inline")
        tail = (" — see EVIDENCE NOT READ below" if unread
                else " — see the transcript above; none was read by the engine")
        return "Attachments: " + ", ".join(parts) + tail
    if inline:
        return (f"Attachments: {len(inline)} inline part(s) only "
                + _safe(", ".join(str(f.get("filename")) for f in inline))
                + " — none read by the engine")
    return "Attachments: none in the source email"


def _evidence_block(evidence, transcribed=()):
    """The prominent block, for a message carrying real attachments.

    Deliberately NOT raised for inline parts alone. A block that fires on every
    signature logo is a block reviewers learn to scroll past, and then the
    drawing goes unread too -- so inline parts are named on the headline instead.
    Nothing is dropped either way.
    """
    named = {str(t) for t in transcribed}
    files = [f for f in ((evidence or {}).get("attachments") or [])
             if str(f.get("filename")) not in named]
    inline = (evidence or {}).get("embedded") or []
    if not files:
        return []
    plural = "" if len(files) == 1 else "s"
    out = [f"EVIDENCE NOT READ — {len(files)} attached file{plural}, and the "
           "engine opened none of them", ""]
    for f in files:
        out.append(f"    {_safe(f.get('filename'))}   "
                   f"{_safe(f.get('content_type'))}   {_bytes(f.get('bytes'))}"
                   + (f"   ({_safe(f.get('error'))})" if f.get("error") else ""))
    out += [
        "",
        "  The engine reads the message TEXT only — there is no attachment "
        "handling in it",
        "  at all. Anything the customer put in these files is NOT in this case, "
        "and the",
        "  open items below were derived without it. Open them before you answer. "
        "If they",
        "  carry specifications, put those into the thread as text and run the "
        "case again.",
    ]
    if inline:
        # Named, not merely counted. The headline counts them; if the block
        # showed only a number, a file the customer sent would appear NOWHERE by
        # name -- which is this campaign's most-repeated finding, and the exact
        # thing this whole block exists to stop.
        out += ["",
                "  Also present inline and equally unread (usually signature "
                "images): "
                + _safe(", ".join(str(f.get("filename")) for f in inline))]
    out.append("")
    return out


def _not_assessed_banner(case, evidence, customer_text):
    """Say so when the engine classified a case it never actually read.

    2026-09-17, production. A customer sent a purchase order as a PDF. The engine
    read 39 bytes of body text, captured NO fields, and classified the case
    `out_of_scope`; the reply led with "Request type: out_of_scope" and
    "No product request recognized". To a reviewer that reads as *we looked and
    there is nothing here* — while 118 KB of purchase order sat unopened and the
    message's real HTML body had not been read either (the engine prefers the
    plain alternative, which was a placeholder).

    The classification was not wrong about the text. It was wrong as an answer
    about the REQUEST, and the reply presented it as one. That is the wrong-answer
    shape this project exists to prevent, so the page now says outright that
    nothing was assessed, and shows how little was read.

    Derived, never asserted: no fields captured AND no BOM lines AND something the
    engine could not read (an unopened attachment, or a body so short it cannot be
    the request). It says nothing on an ordinary case.
    """
    fields = case.get("fields") or {}
    lines = case.get("lines") or []
    unread = (evidence or {}).get("attachments") or []
    body_bytes = len((customer_text or "").encode("utf-8"))
    if fields or lines:
        return []
    if not unread and body_bytes >= 200:
        return []
    out = ["** THIS CASE WAS NOT ASSESSED — do not read the request type as a "
           "finding **", ""]
    out.append(f"  The engine captured no fields at all from the {body_bytes} bytes "
               "of body text it read.")
    if unread:
        out.append(f"  {len(unread)} attached file(s) were never opened: "
                   + _safe(", ".join(str(f.get("filename")) for f in unread)) + ".")
    out += [
        "  `" + _safe(case.get("request_class") or "unclassified") + "` describes "
        "THAT TEXT. It is not a conclusion about what",
        "  the customer asked for — their request may be entirely in what was not "
        "read.",
        "  Open the message and the files yourself before answering.",
        "",
    ]
    return out


def _multi_item_banner(case, line_items):
    """Say when the single specification below may describe no real product.

    The engine assumes one text is one request. Handed a twenty-line purchase
    order it does not refuse: it builds ONE specification by taking the size and
    pressure off the hose line, the length off a barb fitting's THREAD SIZE, and
    the ends off the fittings — a product that appears nowhere in the document.
    Then the asks below invite a customer to confirm it.

    This does not fix the merge. Fixing it is per-line-item extraction, upstream.
    It refuses to let the merged spec be READ as a finding about what was ordered.
    """
    if not (line_items or {}).get("multi_item"):
        return []
    if not (case.get("fields") or {}):
        return []            # nothing was merged; the not-assessed banner covers it
    out = ["** THIS DOCUMENT DESCRIBES MORE THAN ONE PRODUCT — the specification "
           "below may describe none of them **", ""]
    for ground in line_items.get("grounds") or []:
        out.append(f"  - {_safe(ground)}")
    out += [
        "",
        "  The engine reads one text as one request. It has therefore built a "
        "SINGLE specification",
        "  out of values taken from across this document, and those values may "
        "belong to different",
        "  items — a length read off one product's thread size, a pressure off "
        "another's. Do not",
        "  ask anyone to confirm the fields below until you have checked them "
        "against the document",
        "  line by line. If this is a purchase order, what it needs is an "
        "acknowledgement and a ship",
        "  date, not a specification review.",
        "",
    ]
    return out


def _transcript_banner(transcript_text, records=()):
    """That a machine read an attachment -- NOT the transcript itself.

    The transcript is NOT repeated here, and that is phase 2 of PLAN_TURMOIL.md.
    Job `af54e714` produced a 9 KB `reply.md` whose first two hundred lines were a
    purchase order's transcript -- addresses, fax numbers, account numbers, unit
    prices -- with the questions somewhere underneath. The executing agent did
    what anyone would: it ignored the artifact and hand-wrote its own email,
    breaking the kit's own instruction to send this file unsummarised.

    **When the deliverable is unusable, the rule protecting it gets broken.** So
    the full text lives in the review request, where a reviewer checks it against
    the original, and this message says which file was read, how, and how much.

    Nothing is summarised: a summary of a transcript is a model's answer wearing a
    transcript's clothes. The choice is WHERE the verbatim text goes, not whether
    it stays verbatim.
    """
    lines = answers_mod.addendum_lines(transcript_text)
    if not lines:
        return []
    out = ["ATTACHMENT READ BY A MACHINE — not typed by the customer", ""]
    for rec in records or ():
        out.append(f"    {_safe(rec.get('filename'))}   read by: "
                   f"{_safe(rec.get('method'))}")
    if not records:
        out.append("    (the run records no transcript detail)")
    out.append(f"    {len(lines)} lines were transcribed and read by the engine")
    out += [
        "",
        "  A model read the attachment and the engine then read its output as part "
        "of this case.",
        "  Fields marked TRANSCRIBED below came from it. A transcription can "
        "transpose a quantity",
        "  or drop a digit from a part number and still look right, so NOTHING "
        "here is confirmed.",
        "  The full transcript is in the review request, verbatim, for checking "
        "against the",
        "  original file — this message does not repeat it. This case requires a "
        "human for that",
        "  reason alone.",
        "",
    ]
    return out


def _operator_banner(operator_text, unattributable=()):
    """The addendum, verbatim, under a banner saying whose words it is.

    Rendered high on the page and BEFORE the field table, because every value
    below it may have come from here. Each line goes through `_safe`: an operator
    wrote this text, which makes it no less untrusted as a source of control
    characters than the customer's.
    """
    lines = answers_mod.addendum_lines(operator_text)
    if not lines:
        return []
    out = ["OPERATOR ANSWERS WERE ADDED TO THIS CASE — the text below is NOT the "
           "customer's words", ""]
    out += [f"    {_safe(l)}" for l in lines]
    out += [
        "",
        "  The engine read the above as though it were a later message in the "
        "thread, which",
        "  is how it can supersede an earlier value. A field marked "
        "OPERATOR-STATED below came",
        "  from it, not from the customer. SOURCE UNCLEAR means the same words "
        "appear in both",
        "  and the two cannot be told apart. Nothing here has been confirmed BY "
        "THE CUSTOMER.",
    ]
    if unattributable:
        # Said once, here, rather than as a mark on most rows. These fields carry
        # no evidence span, so neither region can be checked -- the honest
        # statement is that they cannot be attributed, not that they are the
        # customer's.
        out += ["",
                "  These fields record no evidence span, so they cannot be "
                "attributed to either",
                "  author: " + _safe(", ".join(sorted(unattributable)))]
    out.append("")
    return out


def render_customer(case, translations, table_error=None, evidence=None,
                    line_items=None):
    """The email the CUSTOMER receives: their questions, in their language.

    Deliberately a SUBSET, and a small one. `render()` below still produces the
    complete case record -- every field, every open item in the engine's own
    words, the checkpoints, the rule ids, the backstop -- and that record now
    lives in `review_request.md`, where the reviewer reads it. This document is
    what gets sent once they approve.

    What is NOT here, and why: open-item codes, rule ids (`R-CATALOG`), work
    instructions (`WI-031`), checkpoint owners, knowledge provenance and the
    remainder backstop. All of it is true and none of it means anything to the
    person who sent the email. Job `af54e714` offered a 9 KB document full of it
    as the thing to send; the agent wrote its own email instead.

    The questions come from `config/questions.json` through `questions.py` -- the
    one place the kit may reword an open item -- and they stay in the engine's
    order. Items marked internal are COUNTED here and detailed in the review
    request; they are not silently absent.
    """
    L = []
    cls = (case.get("request_class") or "unclassified").replace("_", " ")
    urgent = bool((case.get("urgency") or {}).get("flagged"))

    L.append("Thank you for your enquiry — we have it and we are working on it.")
    L.append("")
    L.append("This is not a quote and nothing has been ordered. Before we can price "
             "and schedule")
    L.append("this accurately we need a few details confirmed.")
    L.append("")
    if urgent:
        L.append("We have noted that this is urgent.")
        L.append("")

    if table_error:
        L.append("  (the question wording could not be loaded: "
                 f"{_safe(table_error)} — the text below is our internal wording)")
        L.append("")

    asked = [t for t in translations
             if t["audience"] in (questions_mod.CUSTOMER, questions_mod.UNTRANSLATED)]
    internal = [t for t in translations if t["audience"] == questions_mod.INTERNAL]

    if asked:
        L.append("WHAT WE NEED FROM YOU")
        L.append("")
        for n, t in enumerate(asked, 1):
            L.append(f"  {n}. {_safe(t['question'])}")
            if t["untranslated"]:
                # Never silently send internal wording as though it were written
                # for the reader.
                L.append("     (our internal wording — we have not rephrased this "
                         "one)")
        L.append("")
    else:
        L.append("We do not need anything further from you at this point.")
        L.append("")

    if internal:
        _n = len(internal)
        L.append(f"  There {'is' if _n == 1 else 'are'} also {_n} "
                 f"point{'' if _n == 1 else 's'} for us to resolve internally, "
                 f"which need{'s' if _n == 1 else ''} nothing from you.")
        L.append("")

    # What we understood, in plain terms. Values only, no statuses or evidence
    # spans: a customer does not need to know the engine refused to commit.
    fields = case.get("fields") or {}
    shown = []
    for name in sorted(fields):
        f = fields[name] or {}
        if f.get("status") != CONFIRMED_STATUS:
            continue
        value = f.get("value")
        if value in (None, "", [], {}):
            # An ALLOW-list, not a deny-list. The engine attaches internal
            # commentary to a field (`note`: "family word describes the component
            # itself; per-end follow-ups not applicable") and a deny-list would
            # have to grow every time it adds one. A customer sees the attributes
            # that describe their product and nothing else; the complete record
            # still carries all of it for the reviewer.
            value = ", ".join(f"{k}={v}" for k, v in sorted(f.items())
                              if k in ("family", "gender", "type", "kind", "unit")
                              and v not in (None, "", [], {}))
        if value not in (None, "", [], {}):
            shown.append((name.replace("_", " "), _safe(value)))
    if shown:
        L.append("WHAT WE HAVE UNDERSTOOD SO FAR")
        L.append("")
        for name, value in shown:
            L.append(f"  {name}: {value}")
        L.append("")
        L.append("  Please correct anything above that is not right.")
        L.append("")

    if (line_items or {}).get("multi_item"):
        L.append("  Your message lists more than one item. We are treating the "
                 "details above as")
        L.append("  provisional until we have confirmed them against your document "
                 "line by line.")
        L.append("")

    unread = [f for f in (evidence or {}).get("attachments") or []]
    if unread:
        L.append("  We have your "
                 + _safe(", ".join(str(f.get("filename")) for f in unread))
                 + ". Anything in "
                 + ("it" if len(unread) == 1 else "them")
                 + " that answers the above is welcome as")
        L.append("  text in your reply — it saves us a round trip.")
        L.append("")

    L.append("Once we have these we will come back with a firm answer.")
    return "\n".join(L).rstrip() + "\n"


def render(case, evidence=None, case_text=None, transcripts=(),
           line_items=None):
    """Build the reply body. Pure function of the CaseState and the case text.

    `case_text` is the region map from `answers.regions()`; {} means the text was
    not available and nothing about authorship may be claimed.
    """
    _r = case_text or {}
    customer_text = _r.get(answers_mod.CUSTOMER) or ""
    operator_text = _r.get(answers_mod.OPERATOR)
    transcript_text = _r.get(answers_mod.TRANSCRIBED)
    L = []
    # Keys this run actually rendered. Round 34 (H-2) found the previous
    # hand-written `_consumed` list wrong in six places -- each of those keys was
    # both absent from the page AND excluded from the backstop, which is worse
    # than having no backstop. A section marks its own key as it renders it, so
    # the two cannot drift apart.
    consumed = set()

    def take(*keys):
        consumed.update(keys)
    take("request_class", "urgency", "open_items", "lines", "bom_columns")
    cls = case.get("request_class") or "unclassified"
    urgent = bool((case.get("urgency") or {}).get("flagged"))
    items = case.get("open_items") or []
    lines = case.get("lines") or []

    L.append("DRAFT — not a quote, and not entered in the ERP. A human reviews and "
             "commits this.")
    L.append("")
    urgency_rec = case.get("urgency") or {}
    _urg_extra = {k: v for k, v in urgency_rec.items()
                  if k != "flagged" and v is not None and v != "" and v != [] and v != {}}
    L.append(f"Request type: {_safe(cls)}" + ("   ** URGENT **" if urgent else ""))
    if _urg_extra:
        # Round 35 (M-1): urgency.phrases -- a required schema key -- was consumed
        # by take() and never rendered, reaching the page only by coincidence.
        L.append("  urgency: " + _safe(json.dumps(_urg_extra, sort_keys=True)))
    blocking = sum(1 for i in items if i.get("priority") == "blocking")
    L.append(f"Open items: {len(items)}"
             + (f" ({blocking} blocking a quote)" if blocking else ""))
    L.append(f"Draft BOM lines: {len(lines)}")
    # "0 bytes" and "we did not look" are different statements, and only one of
    # them is true of an unreconciled render. The region map is {} exactly when
    # the case text was not available, so say that instead of reporting a zero
    # the reader would take at face value.
    L.append("Body text the engine read: "
             + (f"{len((customer_text or '').encode('utf-8'))} bytes" if _r
                else "NOT CHECKED — rendered without the source text"))
    _transcribed_names = [r.get("filename") if isinstance(r, dict) else r
                          for r in (transcripts or ())]
    L.append(_evidence_headline(evidence, _transcribed_names))
    # `classes` carries requirements the operator must honour — Certs Required
    # from a C-of-C request is the one that matters. Round 32 pre-flight found it
    # dropped entirely, which for a certificate requirement is exactly the kind
    # of silent omission this kit exists to prevent.
    take("classes")
    classes = case.get("classes") or []
    if classes:
        L.append("Applies: " + _safe(", ".join(str(c) for c in classes)))
    take("routing")
    routing = case.get("routing") or {}
    if routing:
        who = routing.get("recommendation")
        why = routing.get("reasons") or []
        L.append("Route to: " + (_safe(who) if who else "(none recommended)")
                 + (f" — {_safe(', '.join(str(r) for r in why))}" if why else ""))
        # Never drop a routing key the engine adds later: show anything unread
        # rather than silently omitting it. Round 31's lesson in miniature.
        extra = {k: v for k, v in routing.items()
                 if k not in ("recommendation", "reasons")}
        if extra:
            L.append(f"  routing (other): {_safe(json.dumps(extra, sort_keys=True))}")
    L.append("")

    # FIRST of all the sections. If the case was never assessed, every line below
    # it — the class, the asks, the empty BOM — is about text that was not the
    # request, and a reviewer has to meet that before anything else. The
    # multi-item warning sits beside it for the same reason: both say the fields
    # below are not what they appear to be.
    L.extend(_not_assessed_banner(case, evidence, customer_text))
    L.extend(_multi_item_banner(case, line_items))

    # Before the attachments, and before every ask: if an operator's words are in
    # this case, that colours how each line below should be read.
    _sourced_all = (answers_mod.sourced_fields(case, _r)
                    if (operator_text is not None or transcript_text is not None)
                    else {})
    L.extend(_transcript_banner(transcript_text, transcripts))
    L.extend(_operator_banner(
        operator_text,
        [n for n, v in _sourced_all.items()
         if v == answers_mod.UNATTRIBUTABLE]))

    # The attachments come FIRST among the sections: an unread drawing changes
    # how every ask below should be read, so a reviewer must meet it before the
    # list of things the engine says are missing.
    L.extend(_evidence_block(evidence, _transcribed_names))

    # ---- what must be answered, highest priority first -----------------------
    if items:
        L.append("WHAT WE NEED BEFORE QUOTING")
        L.append("")
        for prio in PRIORITY_ORDER:
            group = [i for i in items if i.get("priority") == prio]
            if not group:
                continue
            L.append(f"  {prio.replace('_', ' ').upper()}")
            for it in group:
                L.extend(_open_item(it))
            L.append("")
        leftover = [i for i in items if i.get("priority") not in PRIORITY_ORDER]
        if leftover:
            L.append("  (PRIORITY NOT RECOGNISED — treat as blocking until "
                     "someone classifies it)")
            for it in leftover:  # never silently omit an item with a new priority
                L.extend(_open_item(it, show_priority=True))
            L.append("")

    # ---- what the engine understood, with evidence ---------------------------
    take("fields")
    fields = case.get("fields") or {}
    # Whose words each field came from. Empty when no addendum exists, so the
    # ordinary case renders exactly as before.
    sourced = _sourced_all
    if fields:
        rows = []
        long_values = []
        for name in sorted(fields):
            f = fields[name] or {}
            status = f.get("status", "")
            # `value` is not universal: an end connection carries family/gender
            # and no value at all, and round 31 caught this rendering "—" for a
            # CAPTURED field. Show every attribute the engine set rather than
            # guessing one key name.
            shown = {k: v for k, v in f.items()
                     if k not in ("status", "evidence")
                     and v not in (None, "", [], {})}
            if "value" in shown and len(shown) == 1:
                full = _safe(shown["value"])
            elif shown:
                full = _safe(", ".join(f"{k}={v}" for k, v in sorted(shown.items())))
            else:
                full = "—"
            value = full if len(full) <= 40 else full[:39] + "…"
            if value != full:
                # Round 33 (H-3): truncation silently dropped attributes,
                # including a truncated Component ID in a BOM. A shortened cell
                # is fine; losing the data is not.
                long_values.append((name, full))
            mark = "  <-- NOT CONFIRMED" if is_unconfirmed(status) else ""
            # Only the decidable verdicts get a mark. A span-less field is
            # listed once in the banner instead: marking most of the table
            # would bury the field an operator actually supplied, which is the
            # one thing a reader has to see.
            if sourced.get(name) == answers_mod.OPERATOR:
                mark += "  <-- OPERATOR-STATED"
            elif sourced.get(name) == answers_mod.TRANSCRIBED:
                # Not named per file: with several transcripts the row cannot say
                # which one without parsing the region back, and the banner above
                # lists them verbatim already.
                mark += "  <-- TRANSCRIBED"
            elif sourced.get(name) == answers_mod.AMBIGUOUS:
                mark += "  <-- SOURCE UNCLEAR"
            ev_full = _safe(f.get("evidence"))
            ev = ev_full if len(ev_full) <= 48 else ev_full[:47] + "…"
            if ev != ev_full:
                long_values.append((f"{name} evidence", ev_full))
            rows.append([_safe(name), value, _safe(status) + mark, ev])
        # The heading is a claim about authorship, and it stops being true the
        # moment an operator answer is folded in.
        if operator_text is None and transcript_text is None:
            L.append("WHAT THE EMAIL SAID")
        else:
            _authors = ["the customer's words"]
            if transcript_text is not None:
                _authors.append("text transcribed from an attachment")
            if operator_text is not None:
                _authors.append("operator answers")
            L.append("WHAT THE CASE TEXT SAID — " + " AND ".join(_authors))
        L.append("")
        L.append(_table(rows, ["Field", "Value", "Status", "Evidence"]))
        L.append("")
        for _n, _full in long_values:
            L.append(f"  {_safe(_n)} in full: {_full}")
        if long_values:
            L.append("")
        L.append("  A status other than 'captured' is NOT a confirmed value. The engine")
        L.append("  deliberately refuses to commit to an ambiguous one.")
        L.append("")

    # ---- the draft BOM -------------------------------------------------------
    cols = case.get("bom_columns") or []
    if lines and not cols:
        # Round 34 (H-4): an alternate --config-dir can supply no bom_columns,
        # and the header still counts the lines. Never claim a count and then
        # show nothing: fall back to every key the lines actually carry.
        cols = sorted({k for l in lines for k in l})
    if cols or lines:
        L.append("DRAFT BILL OF MATERIALS")
        L.append("")
        if lines:
            L.append(_table([[_safe(l.get(c, "")) for c in cols] for l in lines],
                            [_safe(c) for c in cols]))
            # A BOM line may carry data outside the declared columns; show it
            # rather than letting bom_columns silently define what exists.
            for i, l in enumerate(lines, 1):
                extra = {k: v for k, v in l.items()
                         if k not in cols and v not in (None, "", [], {})}
                if extra:
                    L.append(f"    line {i} also carries: "
                             f"{_safe(json.dumps(extra, sort_keys=True))}")
            # A BOM line is the closest this kit ever comes to an answer, so a line
            # drawn from a MACHINE's reading of a document is the sharpest hazard
            # CW-9 creates: a transposed part number that happens to match the
            # catalog becomes a real line. The kit cannot stop the engine drafting
            # it -- the transcript is just text by then -- so it says so, loudly,
            # per line.
            if transcript_text is not None:
                for i, l in enumerate(lines, 1):
                    from_transcript = sorted(
                        str(k) for k, v in l.items()
                        if answers_mod.classify(v, _r) == answers_mod.TRANSCRIBED)
                    if from_transcript:
                        L.append(f"    ** line {i} IS DRAWN FROM TRANSCRIBED TEXT "
                                 f"({_safe(', '.join(from_transcript))}) — a "
                                 "machine read these values off a")
                        L.append("       document. Check them against the original "
                                 "file before anyone quotes this. **")
        else:
            # Round 36 (C-1), the SEVENTEENTH missed sibling: `bom_columns` is a
            # required, always-populated key, marked consumed by take() and
            # rendered only inside _table(...). On the lines==[] branch its six
            # names appeared NOWHERE, and the backstop could not see the key
            # because take() had already eaten it -- the same mechanism as round
            # 35's blocker, one screen away. The columns are what the BOM WOULD
            # have, so say so rather than printing prose alone.
            if cols:
                L.append("  Columns this BOM would carry: "
                         + _safe(", ".join(str(c) for c in cols)))
            L.append("  (no lines — nothing is grounded enough to draft; see the open "
                     "items above)")
        L.append("")

    # ---- checkpoints, notes, supersedes, provenance --------------------------
    take("checkpoints")
    cps = case.get("checkpoints") or []
    if cps:
        L.append("CHECKPOINTS — each requires a human, and none can be actioned here")
        L.append("")
        for c in cps:
            L.append(f"  {_safe(c.get('id'))} [{_safe(c.get('status'))}] "
                     f"owner={_safe(c.get('owner'))} ({_safe(c.get('rule_id'))})")
            # Same treatment as open_items: anything the engine adds later is
            # shown rather than dropped by a fixed key list (round 32, H-2).
            for k in sorted(k for k in c
                            if k not in ("id", "status", "owner", "rule_id")):
                if c[k] not in (None, "", [], {}):
                    L.append(f"      {_safe(k)}: {_safe(c[k])}")
        L.append("")
    take("notes")
    notes = case.get("notes") or []
    if notes:
        L.append("NOTES")
        L.append("")
        for n in notes:
            L.append(f"  - {_safe(n)}")
        L.append("")
    take("supersedes")
    sup = case.get("supersedes") or []
    if sup:
        L.append("CORRECTIONS IN THE THREAD — a later message overrode an earlier value")
        L.append("")
        for sp in sup:
            L.append("  - " + _safe(sp if isinstance(sp, str)
                                    else json.dumps(sp, sort_keys=True)))
        L.append("")
    take("logged_attempts")
    logged = case.get("logged_attempts") or []
    if logged:
        L.append("OUT-OF-CLASS ATTEMPTS (logged, not acted on)")
        L.append("")
        for a in logged:
            L.append(f"  - {_safe(a)}")
        L.append("")

    # Round 33 (H-4) found the reply LOSING what bom_draft.md carries: all six
    # `questions[].rule_id`, `extraction.end_fittings` (a barb the customer named
    # explicitly), and `class_evidence` -- while three documents claimed the reply
    # was a superset. Rather than adding three named keys and waiting for round 34
    # to name the next, everything rendered above is tracked and ANY unconsumed
    # top-level key is printed below. A key cannot be silently absent.
    take("questions")
    qs = case.get("questions") or []
    if qs:
        L.append("RULES THAT FIRED (the engine's own question record)")
        L.append("")
        for q in qs:
            rid = q.get("rule_id") if isinstance(q, dict) else None
            txt = q.get("text") if isinstance(q, dict) else q
            L.append(f"  - {_safe(txt)}" + (f"   ({_safe(rid)})" if rid else ""))
        L.append("")
    take("class_evidence")
    ce = case.get("class_evidence")
    if ce is not None and ce != "" and ce != [] and ce != {}:
        L.append(f"Why this request class: {_safe(json.dumps(ce, sort_keys=True) if not isinstance(ce, str) else ce)}")
        L.append("")
    take("extraction")
    extraction = case.get("extraction") or {}
    # Round 35 (C-1): this filter still contained False after round 34 fixed the
    # identical one in the backstop -- the sixteenth fix-the-instance-miss-the-
    # sibling, and its casualty was round 34 H-3's own named example:
    # extraction.material_recognized: False vanished from the reply entirely,
    # hidden from the backstop by take("extraction") and swallowed here.
    extra_ex = {k: v for k, v in extraction.items()
                if v is not None and v != "" and v != [] and v != {}
                and k not in fields}
    if extra_ex:
        L.append("EXTRACTED, NOT IN THE FIELD TABLE")
        L.append("")
        for k in sorted(extra_ex):
            L.append(f"  {_safe(k)}: {_safe(json.dumps(extra_ex[k], sort_keys=True) if isinstance(extra_ex[k], (list, dict)) else extra_ex[k])}")
        L.append("")

    take("knowledge")
    know = case.get("knowledge") or {}
    L.append("PROVENANCE")
    L.append("")
    take("schema_version")
    L.append(f"  schema_version: {_safe(case.get('schema_version'))}")
    L.append(f"  knowledge source: {_safe(know.get('source'))}"
             + (f" (revision {_safe(know.get('revision'))})" if know.get("revision") else ""))
    lookups = know.get("lookups") or []
    L.append(f"  knowledge lookups: {len(lookups)}")
    _know_extra = {k: v for k, v in know.items()
                   if k not in ("source", "revision", "lookups")
                   and v is not None and v != "" and v != [] and v != {}}
    if _know_extra:
        L.append("  knowledge (other): " + _safe(json.dumps(_know_extra, sort_keys=True)))
    for lk in lookups:
        L.append(f"    - {_safe(json.dumps(lk, sort_keys=True))}")
    L.append("")
    # The completeness backstop. Anything the CaseState carries and the sections
    # above did not consume is printed verbatim, so "all the information" is a
    # property of the renderer rather than a claim about it.
    # `is None` and explicit empties only. Round 34 (H-3): `v not in (..., False)`
    # dropped every key valued False, and since 0 == False in Python, 0 and 0.0
    # as well -- `extraction.material_recognized: False` vanished on the shipped
    # path. A false value is information.
    leftover_keys = {k: v for k, v in case.items()
                     if k not in consumed and v is not None
                     and v != "" and v != [] and v != {}}
    if leftover_keys:
        L.append("")
        L.append("ALSO IN THE CASE RECORD (not covered by a section above)")
        L.append("")
        for k in sorted(leftover_keys):
            v = leftover_keys[k]
            L.append(f"  {_safe(k)}: "
                     f"{_safe(json.dumps(v, sort_keys=True) if isinstance(v, (list, dict)) else v)}")
    L.append("")
    # Round 34 (H-5): this used to assert absolutely that no price appears --
    # false whenever the customer's own words, echoed in an ask or an evidence
    # span, mention one. The engine produces none; the page may still quote the
    # customer asking. Say exactly that.
    L.append("The ENGINE produces no price, lead time or stock position, and none of the")
    L.append("above is one. Where a figure appears it is the customer's own words quoted")
    L.append("back — treat it as their claim, not as our number.")
    L.append("Pricing and availability questions are routed to a human, never answered "
             "here.")
    return "\n".join(L).rstrip() + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--case-state", default=None,
                   help="CaseState to render; defaults to the one named in --state")
    p.add_argument("--out", dest="out", default=ARTIFACTS.get("reply"),
                   help="where to write the reply body")
    p.add_argument("--state", default=os.path.join("_report", "state.json"))
    p.add_argument("--no-reconcile", action="store_true",
                   help="render WITHOUT re-deriving the CaseState to check it. "
                        "Only for rendering a CaseState in isolation; never in a "
                        "real run, where the check is the safety net.")
    p.add_argument("--record", action="store_true",
                   help="render the COMPLETE case record instead of the customer's "
                        "email — every open item in the engine's own words, the "
                        "checkpoints, the rule ids. This is what review_request.md "
                        "embeds and what tools/completeness.py checks.")
    p.add_argument("--questions", default=None,
                   help="question translation table (default config/questions.json)")
    args = p.parse_args(argv)

    out = args.out or os.path.join("_report", "reply.md")
    try:
        invalidate([artifact_path("reply", reply=out)])
    except (StateError, KeyError) as e:
        if isinstance(e, StateError):
            print(f"error: {e}", file=sys.stderr)
            return 1

    case_path = args.case_state
    if case_path is None:
        case_path = ((read_state(args.state).get("extract_case") or {}).get("case_state")
                     or ARTIFACTS["case_state"])
    if not os.path.isfile(case_path):
        print(f"error: no CaseState at {case_path}; run the extract phase first",
              file=sys.stderr)
        return 1
    try:
        with open(case_path, encoding="utf-8") as fh:
            case = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: cannot read {case_path}: {e}", file=sys.stderr)
        return 1

    # Reconcile, failing CLOSED. Round 32 (H-1): generate_report.py refuses an
    # edited CaseState and exits 1, and this script then exited 0 and wrote a
    # confident reply from the same file -- 0 open items, every checkpoint
    # CLEARED, a fabricated price -- beneath its own footer swearing no price
    # appears. The reply is the ONLY artifact a human reads, so it needs the
    # guard more than the draft does, not less.
    # What the customer attached (CW-1) is DERIVED from the input file, never
    # read from a record the extract phase wrote -- a second copy of a fact is a
    # copy that can drift, and this one would drift towards telling a reviewer
    # there was nothing to open.
    #
    # It is derived ONLY inside the reconciled branch, and that placement is the
    # point. `--state` defaults to `_report/state.json`; rendering a CaseState in
    # isolation (`--case-state X --no-reconcile`) would otherwise scan whatever
    # email an UNRELATED run happened to leave recorded there, and attribute one
    # customer's attachments to another customer's case. Reconciliation is
    # exactly the proof that the recorded invocation reproduces THIS CaseState,
    # so it is also the only ground on which its input may be read. Without that
    # proof the reply says NOT CHECKED, which is true, instead of a confident
    # answer about the wrong email.
    evidence = attachments.not_checked(
        "the reply was rendered without reconciliation, so the recorded "
        "invocation is not proven to describe this case")
    # An empty region map means "nothing but the customer", which is also what an
    # unreconciled render must assume: it has no proven input to look at, and
    # inventing a banner from an unrelated run's file would be worse than omitting
    # one.
    case_text = {}
    if args.no_reconcile:
        print("warning: --no-reconcile — the reply is NOT being checked against a "
              "re-derived CaseState", file=sys.stderr)
    else:
        invocation = normalize_invocation(read_state(args.state).get("invocation"))
        if not invocation:
            print(f"error: no invocation recorded in {args.state}, so the reply "
                  "cannot be checked against a re-derived CaseState. Run the "
                  "extract phase first, or pass --no-reconcile to render an "
                  "unchecked reply.", file=sys.stderr)
            return 1
        # The fourth engine pass of a run, and it had no size warning while the
        # other three did (round 33). An operator watching a large thread should
        # be told why this step is slow too.
        warn_if_slow(invocation["input"], passes=1)
        try:
            replayed = json.loads(run_engine(invocation, as_json=True)[0])
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        if replayed != case:
            differing = sorted(k for k in set(case) | set(replayed)
                               if case.get(k) != replayed.get(k))
            print(f"error: {case_path} does not match a re-derived CaseState, so "
                  "the reply would\n"
                  "       describe a different case than the engine produces. "
                  "Refusing to write a\n"
                  "       reply that is silently wrong. Re-run the extract phase.\n"
                  f"       differing top-level keys: {differing}", file=sys.stderr)
            return 1
        # Reconciled: this invocation provably produced this CaseState, so its
        # input file is provably this case's email.
        # Attachments come from the file the CUSTOMER sent; the regions come
        # from the text the ENGINE read. They are different files whenever the
        # case text has been augmented, and conflating them loses the
        # attachment report entirely.
        evidence = attachments.scan(source_input(read_state(args.state)))
        case_text = answers_mod.read_regions(invocation["input"])

    # Which attachments a machine read, from the run's own record. Resolved
    # here so render() stays a pure function of what it is handed.
    transcripts = ((read_state(args.state).get("transcripts") or {})
                   .get("records") or [])
    _inv = normalize_invocation(read_state(args.state).get("invocation"))
    _li = lineitems.scan_file(_inv["input"]) if _inv else None
    if args.record:
        # The COMPLETE case record: every field, every open item in the engine's
        # own words, the checkpoints, the backstop. The reviewer's document
        # embeds this; the customer's does not.
        body = render(case, evidence, case_text, transcripts, _li)
    else:
        _table, _table_error = questions_mod.load(args.questions)
        body = render_customer(case, questions_mod.for_case(case, _table),
                               _table_error, evidence, _li)
    try:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(body)
    except OSError as e:
        print(f"error: cannot write {out}: {e}", file=sys.stderr)
        return 1

    print(f"wrote {out} ({len(body)} bytes, {len(case.get('open_items') or [])} "
          f"open items, {len(case.get('lines') or [])} BOM lines)")
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
