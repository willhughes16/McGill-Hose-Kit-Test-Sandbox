"""Request triage: normalization, classification, question/urgency detection, supersede.

Everything here is deterministic and config-driven (rules.json). The classifier decides
WHICH fields the engine asks about (ENGINE_V2_SPEC WP-2, TESTREPORT-2.10): hose fields are
never asked of a non-hose request. Question and urgency detection exist so the conversation
layer never drops a customer question (TESTREPORT-2.7) or an urgency flag (TESTREPORT-2.12).
"""
from __future__ import annotations

import re
from typing import Any

# Unicode forms that defeated earlier extraction rounds: vulgar fractions, the U+2044
# fraction slash, NBSP, fullwidth digits (verification round 12, known limitations).
_FRACTIONS = {"¼": "1/4", "½": "1/2", "¾": "3/4", "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8"}
_FULLWIDTH = {ord(c): ord(c) - 0xFEE0 for c in "０１２３４５６７８９"}

FABRICATION_CLASSES = ("hose_assembly", "bulk_hose", "component_rfq")
HOSE_CLASSES = ("hose_assembly", "bulk_hose")


def normalize_text(text: str) -> str:
    for k, v in _FRACTIONS.items():
        text = text.replace(k, v)
    text = text.replace("⁄", "/").replace(" ", " ")
    # Unicode minus and en-dash fold to ASCII "-" so signed values and ranges
    # parse identically whatever the mail client typed (V2 round 9).
    for dash in "\u2212\u2013\u2014\u2010\u2011\u2012\u2015\uff0d\ufe63\u2e3a\u2796\u02d7":
        text = text.replace(dash, "-")
    return text.translate(_FULLWIDTH)


def classify(low: str, rules: dict[str, Any],
             component_ids: list[str] | None = None) -> tuple[str, str]:
    """Classify the request BEFORE field selection (WP-2). Returns (class, evidence).
    Precedence: order > stocking_lead > component_rfq > bulk_hose > hose_assembly >
    out_of_scope. Operator-supplied component IDs mean an assembly BOM is being built."""
    for pat in rules["order_patterns"]:
        m = re.search(pat, low)
        if m:
            return "order", m.group(0)
    for phrase in rules["stocking_phrases"]:
        if phrase in low:
            return "stocking_lead", phrase

    # Any conveyance product word suppresses the component shortcut — "EPDM suction
    # tubing with camlock fittings" is a hose-class request, not a fittings order
    # (blind verification V2: classification-bypass class). Fitting/coupling words are
    # excluded here because they ARE the component nouns.
    hose_context = re.search(rules["hose_context_pattern"], low) is not None
    if not hose_context and not component_ids:
        for noun in rules["component_nouns"]:
            m = re.search(rf"\b{re.escape(noun)}\b", low)
            if m:
                return "component_rfq", m.group(0)

    if hose_context:
        for phrase in rules["bulk_phrases"]:
            if phrase in low:
                return "bulk_hose", phrase

    product = re.search(rules["product_word_pattern"], low)
    media = any(re.search(rf"\b{re.escape(kw)}\b", low) for kw in rules["media_keywords"])
    fitting = any(re.search(rf"\b{re.escape(kw)}\b", low) for kw in rules["fitting_keywords"])
    size = re.search(r"\d+(?:-\d+/\d+|[./]\d+)?\s*(?:in|inch|\"|')\s*id\b", low) is not None
    descriptor = any(a in low for aliases in rules["length_descriptors"].values() for a in aliases)
    if component_ids or product or media or fitting or size or descriptor:
        ev = (product.group(0) if product else
              "component_ids" if component_ids else "product signal")
        return "hose_assembly", ev
    return "out_of_scope", ""


def detect_questions(text: str, rules: dict[str, Any]) -> list[dict[str, str]]:
    """Customer questions by '?' AND cue phrases (WP-4, TESTREPORT-2.7). Each detected
    question carries its verbatim quote, a topic tag, and a routing suggestion."""
    out = []
    seen: set[str] = set()
    for sentence in re.split(r"(?<=[.?!])\s+|\n+", text):
        s = sentence.strip()
        if not s or len(s) < 4:
            continue
        low = s.lower()
        is_q = s.endswith("?") or "?" in s
        if not is_q:
            is_q = any(re.search(rf"\b{re.escape(cue)}\b", low) for cue in rules["question_cues"])
        if not is_q:
            continue
        topic = "other"
        for name, kws in rules["question_topics"].items():
            if any(kw in low for kw in kws):
                topic = name
                break
        quote = s if len(s) <= 120 else s[:117] + "..."
        if quote in seen:
            continue
        seen.add(quote)
        route = "catalog_lookup" if topic == "capability_rating" else "inside_sales"
        out.append({"quote": quote, "topic": topic, "route": route})
    return out


def detect_urgency(low: str, rules: dict[str, Any]) -> dict[str, Any]:
    hits = []
    for p in rules["urgency_phrases"]:
        for m in re.finditer(rf"\b{re.escape(p)}\b", low):
            lead = low[max(0, m.start() - 12):m.start()]
            if re.search(r"\b(?:no|not|without)\b(?:\s+\w+){0,2}\s*$", lead):
                continue                     # "No rush" is the opposite of urgent
            hits.append(p)
            break
    return {"flagged": bool(hits), "phrases": hits}


def find_supersede(low: str, rules: dict[str, Any]) -> int | None:
    """Position just past the LAST supersede marker (WP-5, TESTREPORT-2.9), or None."""
    last = None
    for marker in rules["supersede_markers"]:
        for m in re.finditer(re.escape(marker), low):
            if last is None or m.start() > last:
                last = m.start()
    return last
