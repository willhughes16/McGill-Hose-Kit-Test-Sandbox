#!/usr/bin/env python3
"""Answers a human gave OUTSIDE the email thread, and how they enter a case.

The reviewer answers "it's 316 stainless" in Teams. That text never reaches the
email thread, so the next run re-asks a question a human already answered. The
Coworker document's Evolution 2 requires Coworker to understand later answers;
today it only does so for answers that arrive as email text.

**What this deliberately is NOT: a resolution path.** The kit may never answer an
open item, and a second way for a value to enter a case is a second way to be
wrong. So an answer is not applied to the CaseState, mapped onto a field, or used
to silence an ask. It is APPENDED TO THE CASE TEXT as an operator addendum, and
the engine reads it exactly as it reads a later message in the thread -- the
`supersedes` machinery that already exists, carrying 529 tests. No new trust, no
new code path in the engine, and if the engine does not accept the answer the ask
stays open, which is the correct outcome for an answer the engine cannot parse.

**The risk this creates, stated first because it is the whole danger.** Appending
an operator's words to the customer's makes the two indistinguishable in the
extracted text: a reviewer could read "316 SS" as something the customer
confirmed when an operator supplied it from memory. Three things hold that line:

  * the addendum begins with `MARKER`, and everything after the first occurrence
    of it is operator-supplied BY DEFINITION -- not by parsing, not by heuristic;
  * the reply and the review request both render the addendum verbatim under a
    banner saying whose words it is, and mark every field whose evidence exists
    only in the addendum as OPERATOR-STATED;
  * a field whose evidence appears in BOTH regions is reported as ambiguous
    rather than as the customer's. Where the two cannot be told apart, the safe
    answer is "cannot be told apart".

`classify()` is sound in the direction that matters: it never calls something the
customer's words when an operator may have supplied them.
"""
from __future__ import annotations

import os
import sys

_VENDOR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

from email_to_bom.mail import extract_rfq_text  # noqa: E402

# The one thing separating two authors' words. Deliberately unmistakable, and
# deliberately matched by FIRST occurrence: if an operator pastes the marker into
# their own answer, everything after the first one is still operator-supplied, so
# the forgery buys nothing.
MARKER = ("===== OPERATOR ADDENDUM — the text below is NOT the customer's words "
          "=====")

CUSTOMER = "customer"
OPERATOR = "operator"
AMBIGUOUS = "ambiguous"
# A field the engine captured without recording a span it came from. Neither
# region can be checked, so it is not ambiguous between two readings -- it is
# unattributable, and kept distinct because the two call for different
# treatment on the page: an ambiguous field is worth a mark beside it, while
# marking every span-less field would bury the one that an operator really did
# supply. Most fields carry no evidence, so this is the common case.
UNATTRIBUTABLE = "unattributable"

REQUIRED = ("answer", "answered_by")


class AnswerError(Exception):
    """An answers file that must not be applied."""


def validate(records):
    """Return the answers to apply, or raise. Fails closed on anything odd.

    Every field is required to be present and non-empty rather than defaulted:
    an answer with no author is exactly the record that later cannot be told from
    the customer's own words, which is the failure this whole module is built
    around.
    """
    if not isinstance(records, list) or not records:
        raise AnswerError("no answers to apply: expected a non-empty 'answers' list")
    out = []
    for i, rec in enumerate(records, 1):
        if not isinstance(rec, dict):
            raise AnswerError(f"answer {i} is not an object")
        for key in REQUIRED:
            if not str(rec.get(key) or "").strip():
                raise AnswerError(f"answer {i} has no '{key}'. Refusing: an answer "
                                  "whose author is unrecorded cannot be told from "
                                  "the customer's own words later.")
        if MARKER in str(rec["answer"]):
            raise AnswerError(
                f"answer {i} contains the addendum marker itself. Refusing rather "
                "than embedding text that imitates the boundary between the "
                "customer's words and an operator's.")
        out.append({"code": str(rec.get("code") or "").strip() or None,
                    "answer": str(rec["answer"]).strip(),
                    "answered_by": str(rec["answered_by"]).strip(),
                    "answered_at": str(rec.get("answered_at") or "").strip()
                                   or "(time not recorded)"})
    return out


def build_addendum(records):
    """The text appended to the case. Human-readable; no format to parse back."""
    lines = [MARKER, ""]
    for rec in records:
        about = f" to {rec['code']}" if rec["code"] else ""
        lines.append(f"Operator answer{about} — from {rec['answered_by']} at "
                     f"{rec['answered_at']}:")
        lines.append(rec["answer"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def split(text):
    """(customer_text, operator_text | None) for a case's extracted text.

    By definition, not by parsing: everything before the FIRST marker is the
    customer's, everything after it is not.
    """
    text = text or ""
    if MARKER not in text:
        return text, None
    head, _, tail = text.partition(MARKER)
    return head, tail


def read_case_text(path):
    """(customer_text, operator_text | None) for the file the engine read.

    Read through the engine's OWN reader, so the regions compared against the
    evidence spans are the text the engine actually saw -- not a second
    expression of its MIME handling. An unreadable file yields ("", None), which
    renders as "no addendum" and is safe: the banner is additive, and a case with
    no operator answers is the ordinary case.
    """
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return "", None
    return split(extract_rfq_text(raw, filename=path))


def addendum_lines(operator_text):
    """The addendum as a list of lines, for rendering verbatim."""
    return [l for l in (operator_text or "").splitlines() if l.strip()]


def _norm(value):
    """Whitespace- and case-folded, for locating an evidence span in a region.

    Two normalisations, and only two. Whitespace because the engine re-wraps and
    trims spans on the way out; CASE because it lowercases them -- an email
    reading "male NPT both ends" yields the span `male npt`, so a case-sensitive
    test finds it in NEITHER region and the field ends up marked as though its
    authorship were in doubt. Both folds are applied to both sides, so neither
    can shift a span from one author to the other; what they change is whether a
    span can be located at all.

    Nothing else is folded. Punctuation, ordering and stemming stay untouched,
    because a looser comparison than this starts calling an operator's words the
    customer's -- and that is the one error this module exists to prevent.
    """
    return " ".join(str(value or "").casefold().split())


def classify(evidence, customer_text, operator_text):
    """Whose words a piece of evidence is: customer, operator, or ambiguous.

    Sound in the direction that matters. `operator` is returned only when the
    span is absent from the customer's text, and `customer` only when it is
    absent from the operator's; anything present in both is `ambiguous`, never
    attributed to the customer by default.
    """
    span = _norm(evidence)
    if operator_text is None:
        return CUSTOMER          # no addendum: every word is the customer's
    if not span:
        return UNATTRIBUTABLE
    in_customer = span in _norm(customer_text)
    in_operator = span in _norm(operator_text)
    if in_operator and not in_customer:
        return OPERATOR
    if in_customer and not in_operator:
        return CUSTOMER
    if not in_customer and not in_operator:
        # The span is in neither region: the engine reformatted it beyond a
        # whitespace-and-case fold, so it cannot be located. That is not the same
        # as appearing in both, and calling it AMBIGUOUS would tell a reader the
        # same words occur in both authors' text when nothing of the sort was
        # established.
        return UNATTRIBUTABLE
    return AMBIGUOUS


def operator_fields(case, customer_text, operator_text):
    """{field name: verdict} for every field whose evidence is not the customer's.

    Only the fields worth flagging are returned -- `customer` verdicts are left
    out -- so a caller cannot accidentally render a reassuring mark for a field
    this module never examined.
    """
    out = {}
    for name, field in sorted((case.get("fields") or {}).items()):
        verdict = classify((field or {}).get("evidence"), customer_text,
                           operator_text)
        if verdict != CUSTOMER:
            out[name] = verdict
    return out
