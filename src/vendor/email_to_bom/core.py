"""Deterministic core for the McGill email -> BOM agent.

Every output carries a rule_id resolvable to a source chunk via config/citations.json.
Nothing here selects hoses/couplings autonomously (G-1 waived) and nothing fabricates
part numbers (FR-11 / G-5): unmatched items become operator questions.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from . import fields as fx
from . import triage
from .knowledge import NullKnowledge, VERIFIED

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")

SCHEMA_VERSION = "2.0"


def load_config(config_dir: str = _CONFIG_DIR) -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    for name in ("rules", "catalog", "citations"):
        with open(os.path.join(config_dir, f"{name}.json"), encoding="utf-8") as fh:
            cfg[name] = json.load(fh)
    cfg["catalog_ids"] = {i["id"].upper() for i in cfg["catalog"]["items"]}
    cfg["catalog_by_id"] = {i["id"].upper(): i for i in cfg["catalog"]["items"]}
    return cfg


# ----------------------------- data structures -----------------------------

@dataclass
class Extraction:
    customer: str | None = None
    media: str | None = None
    size: str | None = None
    quantity: int | None = None
    end_fittings: list[str] = field(default_factory=list)
    material: str | None = None
    material_recognized: bool = False
    length_value: str | None = None
    length_type: str | None = None
    # v2 (ENGINE_V2_SPEC): structured pressure/temperature and per-end connection objects
    pressure: dict[str, Any] | None = None
    temperature: dict[str, Any] | None = None
    ends: list[dict[str, Any]] = field(default_factory=list)

    def missing_targets(self) -> list[str]:
        out = []
        for name in ("customer", "media", "size", "quantity", "material", "length_value"):
            if not getattr(self, name):
                out.append(name)
        if not self.end_fittings:
            out.append("end_fittings")
        return out


@dataclass
class Result:
    extraction: Extraction
    bom_columns: list[str]
    lines: list[dict[str, Any]] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    questions: list[dict[str, str]] = field(default_factory=list)   # {"text","rule_id"}
    checkpoints: list[dict[str, str]] = field(default_factory=list)  # {"id","owner","status"}
    notes: list[str] = field(default_factory=list)
    logged_attempts: list[str] = field(default_factory=list)
    # v2 CaseState (ENGINE_V2_SPEC §1) — data for the conversation layer
    request_class: str = "hose_assembly"
    class_evidence: str = ""
    urgency: dict[str, Any] = field(default_factory=lambda: {"flagged": False, "phrases": []})
    fields: dict[str, Any] = field(default_factory=dict)
    open_items: list[dict[str, Any]] = field(default_factory=list)
    supersedes: list[dict[str, Any]] = field(default_factory=list)
    routing: dict[str, Any] = field(default_factory=dict)
    knowledge: dict[str, Any] = field(default_factory=lambda: {
        "source": "none", "revision": None, "lookups": []})

    def ask(self, text: str, rule_id: str, code: str,
            priority: str = "confirm", **extra: Any) -> None:
        """Append a legacy question AND its machine-readable open-item twin."""
        self.questions.append({"text": text, "rule_id": rule_id})
        item: dict[str, Any] = {"code": code, "priority": priority, "ask": text}
        item.update(extra)
        self.open_items.append(item)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "extraction": self.extraction.__dict__,
            "request_class": self.request_class,
            "class_evidence": self.class_evidence,
            "urgency": self.urgency,
            "fields": self.fields,
            "open_items": self.open_items,
            "supersedes": self.supersedes,
            "routing": self.routing,
            "knowledge": self.knowledge,
            "bom_columns": self.bom_columns,
            "lines": self.lines,
            "classes": self.classes,
            "questions": self.questions,
            "checkpoints": self.checkpoints,
            "notes": self.notes,
            "logged_attempts": self.logged_attempts,
        }


# ----------------------------- the agent -----------------------------

class Agent:
    def __init__(self, config: dict[str, Any] | None = None, knowledge: Any = None):
        """`knowledge` supplies FACTS only (DD-3); rules always come from config.
        The default NullKnowledge makes the engine behave exactly as it does
        offline — a knowledge source can only add proposals and asks."""
        self.cfg = config or load_config()
        self.rules = self.cfg["rules"]
        self.knowledge = knowledge or NullKnowledge()

    # ---- R-EXTRACT (FR-2) ----
    # A number immediately followed by a unit is a dimension/rating, never a quantity
    # (pressure/temperature units added in WP-1: "need 150 psi hose" is not qty 150).
    _NOT_A_DIMENSION = (r"(?!\d)(?!\s*(?:(?:in|inch|inches|ft|foot|feet|id|mm|cm"
                        r"|psi|psig|bar|kpa|mpa|deg|degrees)\b|[\"'°]))")

    def extract(self, text: str, prefer_last: bool = False) -> Extraction:
        """prefer_last picks the LAST occurrence of size/length/pressure/temperature —
        used on correction segments (WP-5) where the superseding value comes after the
        superseded one it quotes ("disregard the 85°F ... the correct spec is 180°F")."""
        text = triage.normalize_text(text)
        low = text.lower()
        ex = Extraction()

        # ONE negation pre-pass feeding EVERY selector (V2 round 3, structural): values
        # inside negated clauses are masked out before any field extraction, so
        # "not 150 psi but 300 psi" / "was 85 F, is now 180 F" / "the 1/4 IN figure is
        # not correct" can never capture the retracted value in ANY field.
        neg_spans = [m.span() for pat in self.rules["negation_patterns"]
                     for m in re.finditer(pat, low)]

        # Every occurrence of the size (e.g. a repeated "1/2in ID") is excluded from the
        # length scan, not just the first (F-1, round 5). Mixed fractions ("1-1/2in ID")
        # are captured whole, not understated to their fractional part (round 6).
        size_matches = [
            mm for mm in re.finditer(r"(\.\d+|\d+(?:-\d+/\d+|[./]\d+)?)\s*(?:in|inch|\"|')\s*id\b", low)
            if not any(mm.start() < e and mm.end() > b for b, e in neg_spans)]
        if not size_matches:
            # CORPUS-2026-08-27 (F-1): the ID-anchored selector above captured the size on
            # 6 of 125 real threads, because customers write '3/4" metal hoses' and
            # "CS 1-1/2 inch MNPT", not "3/4in ID". Everything it missed fell through to
            # the ungated length scan below and was drafted as the LENGTH. A dimension
            # BOUND to the product or connection it describes is a size. Bounded four
            # ways so it can never eat a length: inch-family units only (feet are never
            # an ID), no punctuation and at most two words between dimension and noun, a
            # value no larger than the largest ID stocked (size_bind_max_inches), and a
            # tightly-bound length descriptor always wins ("4 in OAL hose assembly").
            nouns = "|".join(re.escape(n) for n in
                             sorted(self.rules["size_bind_nouns"], key=len, reverse=True))
            cap = self.rules["size_bind_max_inches"]
            desc_hits = self._length_types(low)
            size_matches = [
                mm for mm in re.finditer(
                    r"(\.\d+|\d+(?:-\d+/\d+|[./]\d+)?)[ \t-]*"
                    r"(in(?:ch(?:es)?)?\b|[\"”″])"
                    r"(?:[ \t]*(?:[a-z][a-z.\-/]*[ \t]+){0,2}?(?:" + nouns + r")\b"
                    # The industry's own shorthand: SIZE x LENGTH, both carrying a unit
                    # ('1/2" x 72”', '2"x24"', '3" x 15 foot'). Only the left operand is
                    # claimed here -- the span must END at the size's own unit, so a
                    # LOOKAHEAD, or the length scan would find its own operand excluded.
                    r"|(?=[ \t]*[x\u00d7][ \t]*"
                    r"(?:\.\d+|\d+(?:-\d+/\d+|[./]\d+)?)[ \t-]*"
                    r"(?:in(?:ch(?:es)?)?\b|f(?:oo|ee)?t\b|[\"”″'′])))", low)
                if not any(mm.start() < e and mm.end() > b for b, e in neg_spans)
                and (self._as_inches(mm.group(1)) or 0) > 0
                and self._as_inches(mm.group(1)) <= cap
                and not any(self._tightly_bound(low, (mm.start(1), mm.end(2)), span)
                            for _canonical, span in desc_hits)]
        if size_matches:
            pick = size_matches[-1] if prefer_last else size_matches[0]
            ex.size = pick.group(1) + " ID"
        size_spans = [mm.span() for mm in size_matches]

        # Material scans the FULL text, customer name included: a metal word anywhere may
        # only escalate (G-7 direction), so it is never masked out.
        ex.material, ex.material_recognized = self._detect_material(low)

        customer_span = None
        spec_keywords = self.rules["fitting_keywords"] + self.rules["media_keywords"]
        for mm in re.finditer(r"\b[Ff]or\s+([A-Z0-9][A-Za-z0-9&'.\- ]+?)(?:[.,\n]|$)", text):
            raw = mm.group(1)
            # An unpunctuated capture can run into spec prose ("Acme male NPT both ends");
            # cut at the first lowercase-in-original spec keyword (round 7). Title-case
            # keywords ("Camlock Industries", "Acme Dairy") are part of the name and stay.
            cut = len(raw)
            for kw in spec_keywords:
                for m2 in re.finditer(rf"\b{re.escape(kw)}\b", raw.lower()):
                    if raw[m2.start()].islower():
                        cut = min(cut, m2.start())
            # ...and at dimension tokens ("for Acme Dairy 36in seat to seat" — the length
            # is spec, not name; round 11). Bare numbers stay ("Area 51 Storage").
            for m2 in re.finditer(
                    r"\d+(?:-\d+/\d+|[./]\d+)?\s*(?:(?:in(?:ch(?:es)?)?|ft|foot|feet|mm|cm)\b|[\"'″′])",
                    raw.lower()):
                cut = min(cut, m2.start())
            cand = raw[:cut].strip(" -&'.").strip()
            # "for Hydraulic service" / "for Steam duty" is an APPLICATION, not a
            # customer — swallowing it as a name masks the media word and silently
            # suppresses the fluid-assumption ask (V2 round 5).
            core_words = [w for w in cand.lower().split()
                          if w not in self.rules["customer_generic_suffixes"]]
            if core_words and all(
                    w in self.rules["media_keywords"] for w in core_words):
                continue
            if cand and re.search(r"[A-Za-z]", cand) and not re.match(
                    r"\d+(?:[./]\d+)?\s*(?:in|inch|inches|ft|foot|feet|id)\b", cand, re.IGNORECASE):
                ex.customer = cand
                customer_span = (mm.start(1), mm.start(1) + cut)
                break

        # Media/fitting words inside the customer name describe the customer, not the hose
        # ("Acme Dairy" is not a dairy application) — mask them out (round 6). Negated
        # clauses are then masked on top: low_active is what every selector reads.
        low_masked = low
        if customer_span:
            s, e = customer_span
            low_masked = low[:s] + " " * (e - s) + low[e:]
        low_active = low_masked
        for b, e in neg_spans:
            low_active = low_active[:b] + " " * (e - b) + low_active[e:]

        # Quantity runs on the active text so a digit-initial customer ("quote for
        # 2 Brothers Plumbing") or a negated count is never a phantom qty (round 9 / V2).
        ex.quantity = self._find_quantity(low_active)

        # Pressure & temperature (WP-1) on the active text, excluding size spans; their
        # spans are excluded from the length scan below so "25 in Hg" never reads as a
        # 25-inch length and "1/2in ID" digits never read as pressure.
        ex.pressure, p_spans = fx.extract_pressure(
            low_active, size_spans, self.rules, prefer_last)
        ex.temperature, t_spans = fx.extract_temperature(
            low_active, size_spans + p_spans, self.rules, prefer_last)
        dim_exclude = size_spans + neg_spans + p_spans + t_spans

        # Vacuum words ESCALATE-ONLY and therefore scan the UNMASKED text, exactly
        # like material (V2 round 17: "for Acme Dairy vacuum service, rated 150 psi"
        # must conflict even when the customer capture swallowed the vacuum word).
        vac_hit = fx.vacuum_match(low, self.rules)
        if vac_hit is not None and any(
                m.start() <= vac_hit.start() < m.end()
                for pat in self.rules["negation_patterns"]
                for m in re.finditer(pat, low)):
            vac_hit = None          # "not a vacuum application" is not a vacuum (F-4)
        if vac_hit is not None:
            if ex.pressure is None:
                ex.pressure = {"kind": "vacuum", "value": None, "unit": None,
                               "status": "reading", "evidence": "vacuum/suction stated"}
            elif ex.pressure.get("kind") not in ("vacuum", "conflict"):
                # NEGATIVE condition (V2 round 18): any non-vacuum, non-conflict
                # pressure object beside a stated vacuum word conflicts — gauge,
                # range, whatever kind is added next
                stated = (ex.pressure.get("evidence")
                          or ", ".join(ex.pressure.get("candidates") or [])
                          or "a positive pressure")
                ex.pressure = {"kind": "conflict", "status": "conflict",
                               "candidates": ["vacuum/suction service stated",
                                              str(stated).strip()],
                               "value": None, "unit": None,
                               "evidence": "vacuum word beside a gauge pressure"}

        # Per-end connection objects (WP-3)
        ex.ends = fx.extract_ends(low_active, self.rules)

        for kw in self.rules["media_keywords"]:
            if re.search(rf"\b{re.escape(kw)}\b", low_active):
                ex.media = kw
                break

        # Longest keyword wins and claims its span, so "npt" cannot re-match inside an
        # already-claimed "male npt"; word boundaries stop "cam" firing inside "became".
        claimed: list[tuple[int, int]] = []
        for kw in sorted(self.rules["fitting_keywords"], key=len, reverse=True):
            spans = [mm.span() for mm in re.finditer(rf"\b{re.escape(kw)}\b", low_active)
                     if not any(s < mm.end() and mm.start() < e for s, e in claimed)]
            if not spans:
                continue
            claimed.extend(spans)
            label = kw.upper()
            count = 2 if re.search(rf"\b{re.escape(kw)}\b[^.,]*both ends", low_active) else 1
            ex.end_fittings.extend([label] * count)

        # Length is UNGATED (round 6): any dimension that is not a size is treated as a
        # candidate length so that G-4/AC-8 can always ask. Non-inch units (ft/mm/cm/m,
        # round 6/7) are recognized and kept in the value so they cannot read as inches.
        # Both the descriptor and the dimension scan run on the customer-masked text: a
        # descriptor token inside a customer name ("OAL Industries") must not phantom-label
        # the length and suppress the C2 must-ask (round 8).
        type_hits = self._length_types(low_active)
        candidates = []  # (match, normalized value)
        for mm in re.finditer(
                r"(\.\d+|\d+(?:-\d+/\d+|/\d+|\.\d+)?)[ \t-]*"
                r"((?:in(?:ch(?:es)?)?|ft|foot|feet|mm|cm|meters?|metres?)\b|[\"'″′]|[ \t]*m\b)", low_active):
            if any(mm.start() < e and mm.end() > s for s, e in dim_exclude):
                continue  # this number is (part of) a size/pressure/temperature, not the length
            # CORPUS-2026-08-27 (F-2), two structural gates. The unit must sit on the
            # SAME LINE as its number: "Vic 3153\nM: 0478..." and "T 203-303-3412\nM
            # 203-988-6243" were drafted as the lengths "3153 m" and "3412 m" -- a
            # postcode and a phone number, each borrowing the "M" of the line below.
            # And a material-grade token is never a dimension, the rule _find_quantity
            # has carried since round 8: "(304 in place of 316)" was drafted as 304 in.
            if mm.group(1) in self._digit_grades():
                continue
            unit = mm.group(2).strip()
            if unit in ("ft", "foot", "feet", "'", "′"):
                suffix = " ft"
            elif unit in ("mm", "cm"):
                suffix = f" {unit}"
            elif unit in ("m", "meter", "meters", "metre", "metres"):
                suffix = " m"
            else:  # in / inch(es) / " / ″ — inches are the implicit default
                suffix = ""
            candidates.append((mm, mm.group(1) + suffix))
        if candidates:
            first, value = candidates[-1] if prefer_last else candidates[0]
            ex.length_value = value
            # A descriptor labels the value only when TIGHTLY BOUND to it (F-1, round 9:
            # no intervening words — "36in seat-to-seat" yes, "24in for oal industries"
            # no) AND the dimensions are unambiguous: conflicting candidate values
            # ("2in OAL ... 50 ft long") leave the type unset so C2 still asks (round 7).
            unambiguous = len({v for _, v in candidates}) == 1
            if unambiguous:
                bound = {canonical for canonical, span in type_hits
                         if self._tightly_bound(low_active, first.span(), span)}
                # Conflicting bound descriptors ("36in OAL seat to seat") stay unset;
                # C2 asks (round 10).
                if len(bound) == 1:
                    ex.length_type = bound.pop()
        return ex

    def _detect_material(self, low: str) -> tuple[str | None, bool]:
        """Fail-safe metal detection. A named metal in the callout list -> (value, True).
        A metal-context term or an alloy-grade pattern with no listed match -> (token, False)
        so the QC checkpoint still fires for exotic metals (WI-031: 'specific metal ...
        Example 304 or 316' is non-exhaustive). No metal signal -> (None, False)."""
        for kw in self.rules["material_callouts"]:
            if re.search(rf"\b{re.escape(kw)}\b", low):
                if kw == "316":
                    return "316 SS", True
                if kw == "304":
                    return "304 SS", True
                return kw, True
        # heuristic fallback for unlisted specific metals (alloy grade designations)
        m = re.search(self.rules["material_grade_pattern"], low)
        if m:
            return m.group(0).strip(), False
        return None, False

    @staticmethod
    def _as_inches(raw: str) -> float | None:
        """Numeric value of a dimension token: '3/4', '1-1/2', '4', '.5'. None when it
        does not parse, which the size binder treats as 'not a size'."""
        m = re.fullmatch(r"(\d+)-(\d+)/(\d+)", raw)
        if m:
            return int(m.group(1)) + int(m.group(2)) / int(m.group(3))
        m = re.fullmatch(r"(\d+)/(\d+)", raw)
        if m:
            return int(m.group(1)) / int(m.group(2))
        try:
            return float(raw)
        except ValueError:
            return None

    def _digit_grades(self) -> set[str]:
        """Material-grade tokens that are bare digits (304, 316, ...). Never a quantity
        (round 8) and, since the 2026-08-27 corpus scoring, never a dimension either."""
        return {c for c in self.rules["material_callouts"] if c.isdigit()}

    def _find_quantity(self, low: str) -> int | None:
        """Grade-safe quantity detection (rounds 8-9). A number that is, or is the prefix
        of, a material-grade token (316, 904L, 17-4 PH, 254 SMO) is never a quantity;
        unresolvable cases return None so the draft ASKS instead of assuming."""
        digit_grades = self._digit_grades()
        for pat in (rf"(?:quote|need|want|qty|quantity)\D{{0,8}}(\d+){self._NOT_A_DIMENSION}",
                    rf"\b(\d+){self._NOT_A_DIMENSION}\s+(?:of|pieces?|pcs?|units?|assemblies)\b"):
            for m in re.finditer(pat, low):
                n = m.group(1)
                rest = low[m.end(1):]
                if n in digit_grades:
                    continue                       # "quote 316 stainless"
                if re.match(r"[a-z]|-\d", rest):
                    continue                       # grade-token prefix: 904L, 17-4
                if re.match(r"\s*mo\b", rest):
                    continue                       # spaced grade: "6 Mo" (round 10)
                if len(n) >= 2 and re.match(r"\s*(?:ss|smo|ph|stainless|steel|alloy|duplex)\b", rest):
                    continue                       # "12 stainless" is ambiguous -> ask
                return int(n)
        return None

    def _length_types(self, low: str) -> list[tuple[str, tuple[int, int]]]:
        """All recognized length-descriptor hits as (canonical, span). Word-bounded:
        'oal' must not match inside 'coal'/'goal' (round 7)."""
        hits = []
        for canonical, aliases in self.rules["length_descriptors"].items():
            for a in aliases:
                for m in re.finditer(rf"\b{re.escape(a)}\b", low):
                    hits.append((canonical, m.span()))
        return hits

    @staticmethod
    def _tightly_bound(low: str, a: tuple[int, int], b: tuple[int, int]) -> bool:
        """True when two spans are separated only by intra-phrase glue (spaces, ':', '-')
        — '36in seat-to-seat', 'OAL: 36in'. Words, sentence punctuation, parentheses, and
        newlines all break the bond ('24in for oal industries', '36in. OAL Industries',
        subject/body joins) so a descriptor outside the same phrase never labels the
        length (rounds 9-10). Since round 10 the label is advisory anyway: C2 fires on
        every stated length regardless."""
        if a[0] > b[0]:
            a, b = b, a
        if a[1] >= b[0]:
            return True
        between = low[a[1]:b[0]]
        return len(between) <= 4 and re.fullmatch(r"[ \t:\-]*", between) is not None

    # ---- R-CUSTOMER (FR-3) ----
    def customer_search(self, name: str) -> dict[str, Any]:
        spaced = re.sub(r"\.", " ", name)
        spaced = re.sub(r"\s+", " ", spaced).strip()
        return {"query": spaced, "mode": "Contains", "rule_id": "R-CUSTOMER"}

    # ---- R-CRIMP (FR-9 / AC-9) ----
    def crimp_response(self) -> str:
        r = self.rules
        return (
            "Crimp diameter is a STARTING POINT only and MUST BE PRESSURE TESTED to verify. "
            f"{r['crimp_manufacturer_attribution'].capitalize()}. [rule R-CRIMP]"
        )

    # ---- supersede pre-pass (WP-5 / TESTREPORT-2.9) ----
    _SUPERSEDABLE = ("size", "quantity", "media", "length_value", "length_type",
                     "pressure", "temperature")

    def _extract_with_supersede(self, text: str) -> tuple[Extraction, list[dict], bool]:
        """Extract; when the thread contains an explicit correction, values after the LAST
        marker overwrite the earlier ones (never re-asked, never silently kept)."""
        ex = self.extract(text)
        marker = triage.find_supersede(text.lower(), self.rules)
        if marker is None:
            return ex, [], False
        # Negated values are already excluded inside extract() (V2 round 2), so the
        # correction segment is parsed as-is with last-occurrence preference.
        corr = self.extract(text[marker:], prefer_last=True)
        history: list[dict] = []
        for name in self._SUPERSEDABLE:
            new = getattr(corr, name)
            if new in (None, "", []):
                continue
            old = getattr(ex, name)
            if old != new:
                history.append({"field": name, "old": old, "new": new})
            setattr(ex, name, new)
        if corr.material:
            if ex.material != corr.material:
                history.append({"field": "material", "old": ex.material, "new": corr.material})
            ex.material, ex.material_recognized = corr.material, corr.material_recognized
        resolved = any(getattr(corr, n) not in (None, "", []) for n in self._SUPERSEDABLE) \
            or bool(corr.material)
        # Only STRONG markers ("disregard", "correction:") escalate an unresolvable
        # correction; conversational "actually it's ..." prose with no field in it is
        # not an error to ask about (V2 round 2: spurious CORRECTION_UNRESOLVED).
        low_all = text.lower()
        strong = any(mk in low_all for mk in self.rules["supersede_markers"]
                     if mk not in self.rules["supersede_weak_markers"])
        return ex, history, (not resolved) and strong

    # ---- build the BOM + CaseState (FR-5,6,7,8,10,11; C1,C2,C3; ENGINE_V2_SPEC) ----
    def build(self, text: str, component_ids: list[str] | None = None,
              coc_requested: bool = False, lead_times: dict[str, str] | None = None) -> Result:
        text = triage.normalize_text(text)
        ex, supersedes, correction_unresolved = self._extract_with_supersede(text)
        res = Result(extraction=ex, bom_columns=list(self.rules["bom_columns"]))
        res.supersedes = supersedes
        low = text.lower()
        component_ids = component_ids or []
        lead_times = lead_times or {}

        # WP-2: classify BEFORE field selection — hose fields are never asked of a
        # non-hose request (TESTREPORT-2.10; Sofia R1 T6, R2 T14/18/21/29).
        res.request_class, res.class_evidence = triage.classify(low, self.rules, component_ids)
        hose_like = res.request_class in triage.HOSE_CLASSES
        fabrication = res.request_class in triage.FABRICATION_CLASSES
        res.urgency = triage.detect_urgency(low, self.rules)

        # adversarial temptation: never obey "skip QC" in any phrasing (AC-12; F-2 round 5).
        # A false positive here only adds a log note — escalation never depends on this.
        if re.search(
            r"(?:skip|bypass|ignore|forget|omit|waive)[^.,;]{0,25}\b(?:qc|qa|quality\s+(?:check|control|review)|certs?|certifications?|sign-?offs?)\b"
            r"|\b(?:qc|qa|quality\s+(?:check|control|review)|sign-?offs?)\b[^.,;]{0,20}(?:not\s+(?:needed|necessary|required)|unnecessary)"
            r"|\bno\s+qc\b|\bwithout\s+qc\b|don'?t\s+bother.*\bqc\b"
            r"|approve.*yourself|no\s+need.*\bqc\b", low):
            res.logged_attempts.append("Out-of-class instruction to bypass QC ignored (R-QC).")

        # R-CRIMP (FR-9 / AC-9) — never present a crimp spec as final
        if any(t in low for t in self.rules["crimp_triggers"]):
            res.notes.append(self.crimp_response())

        # R-OUT-OF-SCOPE price/stock (G-2 / AC-10) — decline, never invent a number
        if any(t in low for t in self.rules["price_stock_triggers"]):
            res.notes.append(self.rules["price_stock_decline"] + " [rule G-2]")

        # R-CMTR + C1 (FR-5 / AC-3 / AC-7). A RECOGNIZED grade escalates for EVERY request
        # class (an order of 316 parts still needs QC before fabrication); the fail-safe
        # confirmation question is scoped to fabrication classes (WP-2: never ask hose-ish
        # fields of an order/stocking/out-of-scope message — those get ROUTED_ACKNOWLEDGE).
        if ex.material:
            line = dict(self.rules["cmtr_line"])
            line["Qty Needed"] = str(ex.quantity) if ex.quantity else ""
            line["rule_id"] = "R-CMTR"
            res.lines.append(line)
            res.classes.append(self.rules["cmtr_classes"][0])
            res.checkpoints.append({"id": "C1", "owner": "QC Department",
                                    "status": "PENDING", "rule_id": "R-QC"})
            if not ex.material_recognized:
                res.ask(f"Material '{ex.material}' is a specific callout not in the known "
                        f"list. QC verification raised as a precaution — operator: confirm "
                        f"the exact grade and that CMTR/QC applies.",
                        "R-CMTR", "MATERIAL_UNLISTED_GRADE", priority="blocking",
                        field="material")
        elif fabrication:
            # Fail-safe (G-7): metal names are unbounded, so the absence of a specific metal
            # CANNOT be proven — never suppress. Any fabricated item without a recognized
            # grade gets a mandatory material-confirmation question. A co-occurring non-metal
            # is only surfaced as a hint. The only silent path is a recognized grade, which
            # fires CMTR+C1.
            nonmetals = [nm for nm in self.rules["non_metal_materials"] if nm in low]
            hint = f" (RFQ mentions non-metal '{nonmetals[0]}')" if nonmetals else ""
            res.ask(f"Material not confirmed as a specific grade{hint}. Operator: confirm the "
                    f"exact material of every component and whether CMTR/QC material "
                    f"verification (WI-031) applies before fabrication.",
                    "R-CMTR", "MATERIAL_CONFIRM", field="material")

        # R-COC (FR-6 / AC-4)
        if coc_requested or any(t in low for t in self.rules["coc_triggers"]):
            line = dict(self.rules["coc_line"])
            line["Qty Needed"] = ""
            line["rule_id"] = "R-COC"
            res.lines.append(line)
            if self.rules["cmtr_classes"][0] not in res.classes:
                res.classes.append(self.rules["cmtr_classes"][0])

        # R-CATALOG / R-BOM (FR-7/10/11 / AC-5/13/11)
        for cid in component_ids:
            item = self.cfg["catalog_by_id"].get(cid.upper())
            if item is None:
                # DD-3: a knowledge hit may only PROPOSE. Verified facts can be
                # grounded; candidates become an operator proposal carrying a
                # citation and never reach a BOM line.
                fact = self.knowledge.resolve_component(cid)
                if fact is not None and fact.groundable:
                    item = {"id": fact.id, "description": fact.description,
                            "component_type": fact.component_type,
                            "uom": fact.uom or "EA", "citation": fact.citation,
                            "provenance": "knowledge:verified"}
                elif fact is not None:
                    res.ask(f"'{cid}' appears in McGill knowledge but is not a "
                            f"verified stocked item \u2014 review the quoted context "
                            f"and confirm the correct Component ID before it goes on "
                            f"the BOM.",
                            "R-CATALOG", "COMPONENT_ID_CANDIDATE", priority="blocking",
                            component_id=cid, citation=fact.citation, tier=fact.tier,
                            context_text=fact.description)
                    continue
                else:
                    res.ask(f"No grounded catalog match for '{cid}'. Operator: confirm "
                            f"the correct Component ID before it goes on the BOM.",
                            "R-CATALOG", "COMPONENT_ID_UNRESOLVED", priority="blocking",
                            component_id=cid)
                    continue
            line = {
                "Component ID": item["id"],
                "Description": item["description"],
                "Component Type": item["component_type"],
                "Qty Needed": str(ex.quantity) if ex.quantity else "1",
                "Cut Length": "0.00",
                "Edited": "Unedited",
                "UOM": item["uom"],
                "lead_time_note": lead_times.get(item["id"], self.rules["default_lead_time_note"]),
                "rule_id": "R-BOM",
            }
            if item.get("provenance"):
                line["provenance"] = item["provenance"]
                line["citation"] = item.get("citation", "")
            res.lines.append(line)

        # A defaulted Qty Needed on real catalog lines is an assumption — ask (round 8).
        if ex.quantity is None and any(l.get("rule_id") == "R-BOM" for l in res.lines):
            res.ask("Quantity not stated in the RFQ. Confirm Qty Needed "
                    "(drafted as 1 on each catalog line).",
                    "R-EXTRACT", "QTY_CONFIRM_DEFAULT", field="quantity")

        # WP-1: pressure & temperature — same inversion as length. On a hose-class draft
        # a stated-but-unclear value is an open item, an expected-but-missing value is an
        # open item; nothing about P/T is ever silent (TESTREPORT-2.3/2.4).
        if hose_like:
            p = ex.pressure
            if p is None:
                res.ask("Working pressure not stated. Confirm pressure (psi/bar) — vacuum/"
                        "suction values are valid too (in Hg / mm Hg).",
                        "R-PRESSURE", "PRESSURE_MISSING", field="pressure")
            elif p["status"] == "needs_unit":
                res.ask(f"Pressure given as '{p['raw']}' with no unit — psi or bar?",
                        "R-PRESSURE", "PRESSURE_UNIT_MISSING", priority="blocking",
                        field="pressure")
            elif p["status"] == "conflict":
                res.ask("Both a vacuum value and a positive pressure appear ("
                        + " vs ".join(p["candidates"]) + ") — confirm which applies.",
                        "R-PRESSURE", "PRESSURE_CONFLICT", priority="blocking",
                        field="pressure")
            elif p["kind"] == "vacuum" and p["status"] == "reading":
                res.ask("Vacuum/suction service noted — confirm the vacuum level "
                        "(in Hg / mm Hg) or 'full vacuum'.",
                        "R-PRESSURE", "VACUUM_VALUE_CONFIRM", field="pressure")
            elif p["status"] == "reading":
                v = p["value"]
                shown = ("-".join("?" if x is None else f"{x:g}" for x in v)
                         if isinstance(v, list) else f"{v:g}")
                res.ask(f"Pressure read as {shown} {p['unit']} from context — "
                        f"confirm before fabrication.",
                        "R-PRESSURE", "PRESSURE_CONFIRM_READING", field="pressure")
            t = ex.temperature
            if t is None:
                res.ask("Operating temperature not stated. Confirm temperature "
                        "(°F or °C; a range is fine).",
                        "R-TEMPERATURE", "TEMPERATURE_MISSING", field="temperature")
            elif t["status"] == "needs_unit":
                res.ask(f"Temperature given as '{t['raw']}' with no unit — "
                        f"Fahrenheit or Celsius?",
                        "R-TEMPERATURE", "TEMPERATURE_UNIT_MISSING", priority="blocking",
                        field="temperature")
            elif t["status"] == "assumed":
                res.ask(f"Temperature {t['note']} — please advise if that's not correct.",
                        "R-TEMPERATURE", "TEMPERATURE_ASSUMPTION_CONFIRM", field="temperature")
            elif t["status"] == "conflict":
                res.ask("More than one operating temperature appears ("
                        + " vs ".join(t["candidates"]) + ") — confirm which applies.",
                        "R-TEMPERATURE", "TEMPERATURE_CONFLICT", priority="blocking",
                        field="temperature")
            elif t["status"] == "reading":
                v = t["value"]
                shown = (f"{v[0]:g}-{v[1]:g}" if isinstance(v, list) else f"{v:g}")
                res.ask(f"Temperature read as {shown}°{t['unit']} from context — "
                        f"confirm before fabrication.",
                        "R-TEMPERATURE", "TEMPERATURE_CONFIRM_READING", field="temperature")

            if not ex.size:
                res.ask("Hose size (inside diameter) not stated — confirm the ID.",
                        "R-EXTRACT", "SIZE_MISSING", field="size")
            if ex.quantity is None and not any(
                    l.get("rule_id") == "R-BOM" for l in res.lines):
                res.ask("Quantity not stated — confirm how many assemblies are needed "
                        "(footage alone is bulk stock, not an assembly count).",
                        "R-EXTRACT", "QTY_MISSING", field="quantity")

            # Industry default for hydraulic service (TESTREPORT-2.1): assume and confirm,
            # never ask an open "what is the material conveyed?" question.
            fluid = self.rules["fluid_defaults"].get(ex.media or "")
            if fluid:
                res.ask(f"We've assumed standard {fluid} — confirm, or tell us if this is a "
                        f"special fluid (e.g. Skydrol).",
                        "R-EXTRACT", "FLUID_ASSUMPTION_CONFIRM", field="fluid_detail")

        # WP-6: derating is inside sales' job — recognize and flag, never compute.
        # Armed only by captured/assumed temperatures, not unconfirmed readings
        # (V2 round 2: phantom readings must not spuriously arm it).
        # A temperature CONFLICT still arms derating from its maximum: ambiguity is a
        # reason to flag, never to skip (round 19 F-3). Unconfirmed readings stay out.
        # ONE source of truth for derating: fields sets max_f by the _armable rule
        # in every branch (marker/written-out unit, or a bare unit that does not run
        # into a word), so status no longer gates it — a bare "600 F" arms the flag
        # while "1250 F Street NW" cannot (rounds 19 F-3 / 22 F-2).
        t_max = fx.temp_max_f(ex.temperature)
        if (ex.pressure is not None and t_max is not None
                and t_max > self.rules["derating_threshold_f"]):
            res.open_items.append({
                "code": "DERATING_REVIEW", "priority": "blocking", "route": "inside_sales",
                "ask": f"Pressure at {t_max:.0f}°F needs a derating check by inside sales "
                       f"(engine never derates — TESTREPORT-2.5)."})

        # WP-3: per-end connection follow-ups (gender / flange class / tri-clamp size).
        # Hose classes always; component requests only when the item IS a fitting (a
        # 'camlock gasket' is a gasket for camlocks, not a camlock to gender).
        ends_apply = hose_like or (res.request_class == "component_rfq"
                                   and res.class_evidence in self.rules["component_nouns"]
                                   and res.class_evidence not in
                                   self.rules["component_noun_families"])
        if not ends_apply:
            for end in ex.ends:
                end.setdefault("note", "family word describes the component itself; "
                                       "per-end follow-ups not applicable")
        if ends_apply:
            for i, end in enumerate(ex.ends, start=1):
                fam = end["family"].replace("_", " ")
                if end["status"] == "missing_gender":
                    note = self.rules["connection_families"].get(
                        end["family"], {}).get("note", "male or female")
                    res.ask(f"End {i} ({fam}): confirm gender — {note}.",
                            "R-ENDS", "END_GENDER_MISSING", priority="blocking",
                            field=f"end_{i}")
                elif end["status"] == "missing_spec":
                    res.ask(f"End {i} (flange): confirm pressure class (150 lb / 300 lb / "
                            f"other) AND fixed or floating.",
                            "R-ENDS", "FLANGE_SPEC_MISSING", priority="blocking",
                            field=f"end_{i}")
                elif end["status"] == "size_confirm":
                    res.ask(f"End {i} (tri-clamp): confirm the clamp size — jump sizes are "
                            f"used, so it may not match the hose size.",
                            "R-ENDS", "TRI_CLAMP_SIZE_CONFIRM", field=f"end_{i}")
                elif end["status"] == "configuration_confirm":
                    res.ask(f"End {i} (Code 61/62 flange): confirm the configuration.",
                            "R-ENDS", "CODE6162_CONFIGURATION_CONFIRM", field=f"end_{i}")

        # C2 length checkpoint (FR-4 / AC-8) — the rounds-10/11 inversion, scoped by class:
        # on a hose-class draft, length is NEVER silent — detected -> confirmed, absent ->
        # asked. Non-hose classes never get hose-length questions (WP-2).
        if hose_like:
            if ex.length_value:
                if ex.length_type:
                    res.ask(f"Length read as {ex.length_value} {ex.length_type} — confirm "
                            f"value and convention before fabrication (WI-020).",
                            "R-LENGTH", "LENGTH_CONFIRM", field="length")
                else:
                    res.ask("Length given without a length type. Confirm convention: "
                            "overall length (OAL) / seat-to-seat / center-to-end / "
                            "cut length / live length.",
                            "R-LENGTH", "LENGTH_TYPE_MISSING", field="length")
            else:
                res.ask("No length detected in the RFQ. Confirm the required assembly length "
                        "and convention (overall length (OAL) / seat-to-seat / center-to-end "
                        "/ cut length / live length) before fabrication (WI-020).",
                        "R-LENGTH", "LENGTH_MISSING", field="length")
            res.checkpoints.append({"id": "C2", "owner": "Sales + Production Manager + Quality Team",
                                    "status": "PENDING", "rule_id": "R-LENGTH"})

        # C3 selection checkpoint when a hose/fitting is implied but not grounded (AC-11).
        if hose_like:
            has_hose_line = any(l.get("Component Type") == "Hose" for l in res.lines)
            if not has_hose_line and not component_ids:
                res.ask("Hose/coupling not resolved. No grounded selection rule exists (G-1 "
                        "waived) — operator must select/confirm the hose and end fittings.",
                        "R-CATALOG", "SELECTION_UNRESOLVED")
                # Proposals only: the G-1 waiver stands, the engine never selects.
                cands = self.knowledge.find_candidates(
                    {"media": ex.media, "size": ex.size}) or []
                if cands:
                    res.open_items.append({
                        "code": "SELECTION_CANDIDATES", "priority": "confirm",
                        "route": "inside_sales",
                        "candidates": [{"id": f.id, "description": f.description,
                                        "tier": f.tier, "citation": f.citation}
                                       for f in cands],
                        "ask": "Candidates found in McGill knowledge (proposals, not "
                               "selections \u2014 operator confirms each): "
                               + ", ".join(f.id for f in cands)})
                res.checkpoints.append({"id": "C3", "owner": "Inside Sales",
                                        "status": "PENDING", "rule_id": "R-CATALOG"})

        # WP-8: component requests ask their OWN field set, never the hose checklist.
        po_number = None
        referenced_ids: list[str] = []
        # A stated dimension is never silent on ANY class: whatever noun carried the
        # request ("suction line", "manifold", "spool") and however it classified, a
        # detected length/footage gets confirmed (V2 round 2: classification must not
        # be the only wall in front of the length rail).
        if not hose_like and ex.length_value:
            res.ask(f"A dimension ({ex.length_value}"
                    + (f" {ex.length_type}" if ex.length_type else "")
                    + ") appears in this request — confirm what it refers to "
                    "(length, size, or something else).",
                    "R-LENGTH", "DIMENSION_CONFIRM", field="length")

        if res.request_class == "component_rfq":
            family = self.rules["component_noun_families"].get(res.class_evidence, "_default")
            covered = {"item": res.class_evidence, "size": ex.size, "quantity": ex.quantity,
                       "media_or_service": ex.media,
                       "material_if_chemical_service": ex.material}
            for f_name in self.rules["component_field_sets"].get(
                    family, self.rules["component_field_sets"]["_default"]):
                if not covered.get(f_name):
                    res.ask(f"{res.class_evidence}: confirm {f_name.replace('_', ' ')}.",
                            "R-EXTRACT", "COMPONENT_FIELD_MISSING", field=f_name,
                            component=res.class_evidence)

        # WP-2: orders and stocking leads are ROUTED with acknowledgment, never
        # interrogated with a field checklist (TESTREPORT R2 T18/T21/T30).
        if res.request_class == "order":
            m = re.search(r"\bp\.?o\.?\s*#?\s*(\d+)", low)
            po_number = m.group(1) if m else None
            up = text.upper()
            referenced_ids = [cid for cid in self.cfg["catalog_ids"] if cid in up]
            res.open_items.append({
                "code": "ROUTED_ACKNOWLEDGE", "priority": "must_acknowledge",
                "route": "order_desk",
                "ask": "This is an order" + (f" (PO {po_number})" if po_number else "") +
                       " — acknowledge receipt and route to order entry; do not run the "
                       "RFQ checklist."})
        elif res.request_class == "stocking_lead":
            res.open_items.append({
                "code": "ROUTED_ACKNOWLEDGE", "priority": "must_acknowledge",
                "route": "account_owner",
                "ask": "Account-level stocking/relationship lead — route to the account "
                       "owner; not an RFQ."})
        elif res.request_class == "out_of_scope":
            res.open_items.append({
                "code": "ROUTED_ACKNOWLEDGE", "priority": "must_acknowledge",
                "route": "inside_sales",
                "ask": "No product request recognized — acknowledge and route to inside "
                       "sales for review."})

        # Hidden-content flag from the mail layer (V2 round 8): CSS-class hiding is
        # undecidable without a CSS engine, so the message is flagged for human review.
        if "[html-source]" in low:
            res.open_items.append({
                "code": "HTML_SOURCE_REVIEW", "priority": "confirm",
                "route": "inside_sales",
                "ask": "Extracted from an HTML email — rendering cannot be verified "
                       "here, so the ORIGINAL message is authoritative; open it before "
                       "fabrication (DD-1)."})
        if "[hidden-content-suspected]" in low:
            res.open_items.append({
                "code": "HIDDEN_CONTENT_DETECTED", "priority": "must_acknowledge",
                "route": "inside_sales",
                "ask": "This email contains style rules that can hide text — review the "
                       "original message; the extracted text may be incomplete."})

        # WP-4: never leave a customer question unanswered (TESTREPORT-2.7) — every
        # detected question is surfaced for acknowledgment, whatever the class.
        for q in triage.detect_questions(text, self.rules):
            item = {"code": "CUSTOMER_QUESTION_UNANSWERED", "priority": "must_acknowledge",
                    "quote": q["quote"], "topic": q["topic"], "route": q["route"],
                    "ask": "Acknowledge and route: " + q["quote"]}
            # WP-9: capability questions answered from the catalog when ratings exist —
            # as data for the conversation layer, still operator-confirmed (G-1 stands).
            if q["topic"] == "capability_rating":
                rated = [i for i in self.cfg["catalog"]["items"] if i.get("ratings")]
                if ex.media:
                    rated = [i for i in rated
                             if ex.media in [m.lower() for m in i.get("media_suitability", [])]
                             or not i.get("media_suitability")]
                if rated:
                    res.open_items.append({
                        "code": "CAPABILITY_ANSWER_READY", "priority": "confirm",
                        "quote": q["quote"],
                        "items": [{"id": i["id"], "ratings": i["ratings"]} for i in rated],
                        "ask": "Rated catalog matches found — propose these (operator-"
                               "confirmed) instead of re-asking."})
                    continue
                k_rated = [f for f in (self.knowledge.find_candidates(
                    {"media": ex.media}) or []) if f.ratings]
                if k_rated:
                    res.open_items.append({
                        "code": "CAPABILITY_ANSWER_READY", "priority": "confirm",
                        "quote": q["quote"],
                        "items": [{"id": f.id, "ratings": f.ratings, "tier": f.tier,
                                   "citation": f.citation} for f in k_rated],
                        "ask": "Rated matches found in McGill knowledge — propose these "
                               "(operator-confirmed) instead of re-asking."})
                    continue
                item["route"] = "inside_sales"
            res.open_items.append(item)

        # WP-5: a correction that cannot be resolved is asked, never dropped.
        if correction_unresolved:
            res.open_items.append({
                "code": "CORRECTION_UNRESOLVED", "priority": "blocking",
                "ask": "A correction ('disregard/correct value') was detected but could not "
                       "be applied to a specific field — confirm which value changed."})

        # Account background (TESTREPORT-2.6): known context is surfaced so the
        # conversation layer stops asking what McGill already knows.
        if ex.customer:
            ctx = self.knowledge.customer_context(ex.customer)
            if ctx:
                res.open_items.append({
                    "code": "CUSTOMER_CONTEXT_AVAILABLE", "priority": "confirm",
                    "route": "inside_sales", "citation": str(ctx.get("citation") or ""),
                    "tier": str(ctx.get("tier") or "candidate"),
                    "context_text": str(ctx.get("summary_text") or "")[:300],
                    "ask": f"Known context is on file for {ex.customer} \u2014 review "
                           f"the quoted context and confirm it still applies."})

        # Knowledge provenance: what was asked, what came back, from which revision
        res.knowledge = {"source": getattr(self.knowledge, "name", "unknown"),
                         "revision": getattr(self.knowledge, "revision", None),
                         "lookups": self.knowledge.log()}

        # ---- CaseState assembly (ENGINE_V2_SPEC §1) ----
        res.fields = self._case_fields(ex, res, po_number, referenced_ids)
        rec = {"order": "order_desk", "stocking_lead": "account_owner"}.get(
            res.request_class, "inside_sales_review")
        reasons = [c["id"] + " open" for c in res.checkpoints]
        if res.urgency["flagged"]:
            reasons.append("urgent: " + ", ".join(res.urgency["phrases"]))
        if any(i["code"] == "DERATING_REVIEW" for i in res.open_items):
            reasons.append("derating review")
        res.routing = {"recommendation": rec, "reasons": reasons}
        return res

    def _case_fields(self, ex: Extraction, res: Result,
                     po_number: str | None, referenced_ids: list[str]) -> dict[str, Any]:
        hose_like = res.request_class in triage.HOSE_CLASSES

        def f(value, status="captured", **kw):
            d = {"value": value, "status": status}
            d.update(kw)
            return d

        out: dict[str, Any] = {}
        if ex.customer:
            out["customer"] = f(ex.customer)
        if ex.media:
            out["media"] = f(ex.media)
        if ex.size:
            out["size"] = f(ex.size)
        elif hose_like:
            out["size"] = f(None, "missing")
        if ex.quantity is not None:
            out["quantity"] = f(ex.quantity)
        elif any(l.get("rule_id") == "R-BOM" for l in res.lines):
            out["quantity"] = f(1, "assumed", note="drafted as 1 — confirm")
        elif res.request_class in triage.FABRICATION_CLASSES:
            out["quantity"] = f(None, "missing")
        if ex.material:
            out["material"] = f(ex.material,
                                "captured" if ex.material_recognized else "reading")
        elif res.request_class in triage.FABRICATION_CLASSES:
            out["material"] = f(None, "missing")
        if ex.length_value:
            out["length"] = f(ex.length_value, "reading", type=ex.length_type)
        elif hose_like:
            out["length"] = f(None, "missing")
        if hose_like:
            out["pressure"] = ex.pressure or f(None, "missing")
            out["temperature"] = ex.temperature or f(None, "missing")
            fluid = self.rules["fluid_defaults"].get(ex.media or "")
            if fluid:
                out["fluid_detail"] = f(fluid, "assumed",
                                        note="industry default — confirm, or name the fluid")
        for i, end in enumerate(ex.ends, start=1):
            out[f"end_{i}"] = end
        if po_number:
            out["po_number"] = f(po_number)
        if referenced_ids:
            out["referenced_ids"] = f(sorted(referenced_ids))
        # Supersede provenance: the final value shows what it replaced (WP-5)
        remap = {"length_value": "length", "length_type": "length"}
        for s in res.supersedes:
            name = remap.get(s["field"], s["field"])
            if name in out and isinstance(out[name], dict):
                out[name]["superseded_from"] = s["old"]
        return out
