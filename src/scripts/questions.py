#!/usr/bin/env python3
"""The engine asks an OPERATOR. A customer needs a different sentence.

The engine writes for the person who will build the thing:

    MATERIAL_CONFIRM — "Material not confirmed as a specific grade. Operator:
    confirm the exact material of every component and whether CMTR/QC material
    verification (WI-031) applies before fabrication."

That is correct, and it cannot be sent to a customer. Job `af54e714` showed what
happens when the kit offers it as the thing to send: the executing agent wrote
its own email instead, inventing wording nobody reviewed.

So `config/questions.json` maps each open-item CODE to a question a customer can
answer, and this module applies it.

**THIS IS THE ONE PLACE THE KIT MAY REWORD AN OPEN ITEM.** The standing rule is
never to answer, drop, reword or re-prioritize one, and translating is rewording.
Four things keep the guarantee where it bites:

  * `review_request.md` prints the engine's EXACT ask beside the proposed wording
    for EVERY item, so the reviewer approves a translation rather than inheriting
    it. The engine's text is read from the CaseState at render time and is never
    copied into the table -- a second copy of rule text is a copy that drifts.
  * priority ORDER is preserved exactly; nothing is re-ranked.
  * nothing is dropped from the REVIEW. An item marked `internal` is absent from
    the customer's email only, and the review request still lists it, marked.
  * a code with no entry falls back to the engine's own words and is flagged as
    untranslated, rather than vanishing. `tools/selftest.py` asserts every code
    the schema declares appears in the table, so a new engine code fails the
    suite instead of leaking a work-instruction number into a customer's inbox.

`internal` is the default-deny answer: under-asking costs a round trip the
reviewer can start themselves, mis-asking sends a customer a wrong question about
their own order.
"""
from __future__ import annotations

import json
import os

CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "config", "questions.json")

CUSTOMER = "customer"
INTERNAL = "internal"
UNTRANSLATED = "untranslated"


def load(path=None):
    """Load the translation table. Returns (table, error).

    A missing or malformed table is an error, not an empty one: every item then
    falls back to the engine's operator wording, which is ugly but true, and the
    renderers say the table could not be read.
    """
    path = path or CONFIG
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        return None, f"cannot read {path}: {e}"
    table = data.get("questions")
    if not isinstance(table, dict):
        return None, f"{path} has no 'questions' object"
    return table, None


def translate(item, table):
    """One open item as {code, audience, question, ask, untranslated}.

    `ask` is always the engine's own words, taken from the item itself. Callers
    render it beside `question` so a reviewer can see what was changed.
    """
    item = item or {}
    code = str(item.get("code") or "")
    ask = str(item.get("ask") or item.get("quote") or "")
    entry = (table or {}).get(code)
    if not isinstance(entry, dict):
        # Unknown code: the customer sees the engine's words rather than nothing,
        # and the page says they were not translated.
        return {"code": code, "audience": UNTRANSLATED, "question": ask,
                "ask": ask, "untranslated": True}
    audience = entry.get("audience")
    if audience == INTERNAL:
        return {"code": code, "audience": INTERNAL, "question": None,
                "ask": ask, "untranslated": False}
    question = str(entry.get("question") or "").strip()
    if not question:
        return {"code": code, "audience": UNTRANSLATED, "question": ask,
                "ask": ask, "untranslated": True}
    return {"code": code, "audience": CUSTOMER, "question": question,
            "ask": ask, "untranslated": False}


def for_case(case, table):
    """Every open item translated, in the engine's own order. Never re-ranked."""
    return [translate(i, table) for i in (case or {}).get("open_items") or []]
