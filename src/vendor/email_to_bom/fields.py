"""Field extractors for pressure, temperature, and end connections (ENGINE_V2_SPEC WP-1/WP-3).

Field dicts follow the CaseState contract: {"status": captured|reading|assumed|needs_unit,
"value"/"raw", "unit", "kind", "evidence"}. A bare number NEVER reaches "captured"
(TESTREPORT-2.3); vacuum/suction is a first-class pressure value (TESTREPORT-2.4).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

Span = tuple[int, int]


def _overlaps(m: re.Match, exclude: list[Span]) -> bool:
    return any(m.start() < e and m.end() > s for s, e in exclude)


def _ev(m: re.Match) -> str:
    return m.group(0)[:80]


def _pick(matches: list[re.Match], prefer_last: bool) -> re.Match:
    return matches[-1] if prefer_last else matches[0]


def vacuum_match(low: str, rules: dict[str, Any]) -> re.Match | None:
    """THE vacuum-word matcher — one implementation, used by the pressure extractor
    and by the escalate-only pass in core.py. Round 21 driver 1: a stem fix applied
    to one of two copies left "for Acme Dairy vacuums, rated 150 psi" capturing a
    clean gauge with no ask. Stem- and separator-tolerant; escalate-only, so a
    generous match can add an ask but never remove one."""
    for w in rules["vacuum_words"]:
        stem = re.sub(r"(?:\\ |\\-|[ -])+", "[ -]+", re.escape(w))
        m = re.search(rf"\b{stem}(?:s|es|ed|ing)?\b", low)
        if m:
            return m
    return None


def _ctx_bound(context_words: list[str], low: str, start: int) -> bool:
    """A context word corroborates a value only when TIGHTLY BOUND to it — the word
    (plus an optional is/of/:/=) must END the window right before the number. 'temp is
    50 F' corroborates; 'our temp desk at 250 F' (temporary) and 'Bar Harbor Road'
    prose do not (V2 round 4: one binding rule for every context gate)."""
    alt = "|".join(re.escape(c) for c in context_words)
    window = low[max(0, start - 28):start]
    return re.search(rf"\b(?:{alt})\b\s*(?:is|of|:|=)?\s*$", window) is not None


# ---------------- ONE value model for both P and T (round 23) ----------------
#
# Rounds 19-23 all failed the same way: a gate claimed to be "unified" while
# enumerating the shapes the last report happened to name. So shapes are no longer
# enumerated per gate. Each extractor collects EVERY value it can see into one list
# of Claim objects — including the unit-less ones — and exactly one gate reads that
# list. A new shape is added in one place and every rule sees it.

_PSI_PER = {"psi": 1.0, "psig": 1.0, "bar": 14.5038, "kpa": 0.145038, "mpa": 145.038}

_NUMBER = r"(?:\d+(?:\.\d+)?|\.\d+)"
_DIM_UNITS = ("in", "inch", "inches", "ft", "foot", "feet", "mm", "cm", "m",
              "meter", "meters", "metre", "metres", "id", "od")


def unit_tokens(low: str, rules: dict[str, Any]) -> list[tuple[Span, str]]:
    """ONE tokenization pass over the text: every number that carries a recognized
    unit, paired with the family that OWNS it (round 24 driver).

    Ownership used to be decided by which extractor happened to run first and what
    each one's private lookahead happened to exclude — a one-directional guard meant
    'rated 350 F' was claimed as a unit-less PRESSURE and its span then hid the
    350 F from temperature entirely. Both families now consult this single map, so a
    value cannot be visible to one and invisible to the other."""
    fams: list[tuple[str, tuple[str, ...]]] = [
        ("vacuum", ("hg",)),
        ("pressure", tuple(rules["pressure_units"])),
        ("temperature", tuple(rules["temperature_units_f"]
                              + rules["temperature_units_c"])),
        ("dimension", _DIM_UNITS),
    ]
    out: list[tuple[Span, str]] = []
    for family, units in fams:
        if not units:
            continue
        alt = "|".join(sorted((re.escape(u) for u in units), key=len, reverse=True))
        pat = (rf"(-?{_NUMBER})[ \t]*(?:°[ \t]*|deg(?:ree|res)?s?\.?[ \t]*(?:of[ \t]+)?)?"
               rf"(?:(?:in(?:ch(?:es)?)?|mm)\.?[ \t]*(?:of[ \t]+)?)?({alt})\b")
        for m in re.finditer(pat, low):
            if not any(m.start() < e and m.end() > b for b, e in
                       (t[0] for t in out)):
                out.append((m.span(), family))
    return out


def _owned_elsewhere(span: Span, tokens: list[tuple[Span, str]], mine: str) -> bool:
    """True when this number already carries a unit — whoever owns it, it is not a
    unit-less value for anybody."""
    return any(span[0] < e and span[1] > b for (b, e), fam in tokens)


@dataclass(frozen=True)
class Claim:
    """One stated value: a point (hi is None) or a range, with its unit or None."""
    lo: float
    hi: float | None
    unit: str | None            # normalized unit, or None when unit-less
    span: Span
    evidence: str
    marked: bool = True        # an explicit marker/written-out unit was present

    def canon(self) -> tuple:
        """Comparable signature in a common unit (psi for pressure, °F for
        temperature); unit-less claims compare as their own kind so they can never
        be mistaken for a converted value."""
        if self.unit is None:
            return ("bare", self.lo, self.hi)
        return ("val", self._c(self.lo), None if self.hi is None else self._c(self.hi))

    def _c(self, v: float) -> float:
        if self.unit in _PSI_PER:
            return v * _PSI_PER[self.unit]
        return to_f(v, self.unit) if self.unit in ("F", "C") else v

    @property
    def top(self) -> float:
        """Highest stated value, in the unit it was stated in."""
        return self.hi if self.hi is not None else self.lo

    @property
    def top_f(self) -> float:
        """Highest stated value in °F (temperature claims only)."""
        return self._c(self.top)


def _distinct(claims: list[Claim]) -> list[Claim]:
    """Claims that restate one another (same kind, values within tolerance in the
    common unit) collapse to one; anything else is a separate statement."""
    out: list[Claim] = []
    for c in claims:
        k = c.canon()
        dup = False
        for d in out:
            kd = d.canon()
            if k[0] != kd[0] or (k[2] is None) != (kd[2] is None):
                continue
            tol = max(1.0, abs(k[1]) * 0.02)
            if abs(k[1] - kd[1]) <= tol and (
                    k[2] is None or abs(k[2] - kd[2]) <= max(1.0, abs(k[2]) * 0.02)):
                dup = True
                break
        if not dup:
            out.append(c)
    return out


def _conflict(claims: list[Claim], extra: list[str] | None = None) -> dict[str, Any]:
    seen: list[str] = list(extra or [])
    for c in claims:
        if c.evidence not in seen:
            seen.append(c.evidence)
    return {"kind": "conflict", "status": "conflict", "candidates": seen[:3],
            "value": None, "unit": None,
            "evidence": " / ".join(seen[:2])[:80]}


# ------------------------------- pressure -------------------------------

def extract_pressure(low: str, exclude: list[Span], rules: dict[str, Any],
                     prefer_last: bool = False) -> tuple[dict[str, Any] | None, list[Span]]:
    """ONE chokepoint gate for the whole wall: a captured value whose unit is an
    ambiguous English word ("bar") is downgraded to a reading whichever branch
    produced it (V2 round 5 — gating at the return boundary makes a branch that
    skips the gate structurally impossible)."""
    result, spans = _extract_pressure_raw(low, exclude, rules, prefer_last)
    if result is not None:
        vals = result.get("value")
        vals = vals if isinstance(vals, list) else [vals]
        if (result.get("status") == "captured"
                and any(v is not None and v < 0 for v in vals)):
            result["status"] = "reading"          # a negative is a vacuum statement
        if (result.get("status") == "captured"
                and result.get("unit") in rules["pressure_ambiguous_units"]):
            result["status"] = "reading"
    return result, spans


def _pressure_claims(low: str, exclude: list[Span], rules: dict[str, Any]
                     ) -> tuple[list[Claim], list[re.Match]]:
    """EVERY pressure shape the text states, unit-bearing and unit-less alike."""
    units = "|".join(rules["pressure_units"])
    num = r"(?:\d+(?:\.\d+)?|\.\d+)"

    def signed(txt: str, at: int, raw: float) -> float:
        lead = low[max(0, at - 12):at]
        if raw > 0 and re.search(r"(?:\bminus|\bnegative|\bneg\.?|(?<!\d)(?<!\d )-)\s*$",
                                 lead):
            return -raw
        return raw

    claims: list[Claim] = []
    vac = [m for m in re.finditer(
        rf"({num})[ \t]*(in(?:ch(?:es)?)?|mm)\.?[ \t]*(?:of[ \t]+)?hg\b", low)
        if not _overlaps(m, exclude)]

    rng = [m for m in re.finditer(
        rf"(?:between[ \t]+)?(?<![\d-])(-?{num})[ \t]*(?:{units})?[ \t]*"
        rf"(?:-|–|to|and)[ \t]*(-?{num})[ \t]*({units})\b", low)
        if not _overlaps(m, exclude)]
    for m in rng:
        claims.append(Claim(signed(low, m.start(1), float(m.group(1))),
                            signed(low, m.start(2), float(m.group(2))),
                            m.group(3), m.span(), _ev(m).strip()))
    upto = [m for m in re.finditer(rf"up[ \t]+to[ \t]+(-?{num})[ \t]*({units})\b", low)
            if not _overlaps(m, exclude)]
    for m in upto:
        if not any(m.start() >= r.start() and m.end() <= r.end() for r in rng):
            claims.append(Claim(signed(low, m.start(1), float(m.group(1))), None,
                                m.group(2), m.span(), _ev(m).strip()))
    single = [m for m in re.finditer(rf"(?<![\d-])(-?{num})[ \t]*({units})\b", low)
              if not _overlaps(m, exclude) and not _overlaps(m, [v.span() for v in vac])]
    for m in single:
        if not any(m.start() >= r.start() and m.end() <= r.end()
                   for r in rng + upto):
            claims.append(Claim(signed(low, m.start(1), float(m.group(1))), None,
                                m.group(2), m.span(), _ev(m).strip()))

    # unit-less values in pressure context are FIRST-CLASS claims (round 23 driver):
    # they were previously computed below every return, so any unit-bearing value
    # deleted them — adding information removed a blocking ask. Sign-aware, like
    # their temperature twin.
    ctx = "|".join(re.escape(c) for c in rules["pressure_context"])
    tokens = unit_tokens(low, rules)
    for m in re.finditer(rf"(?:{ctx})\s*(?:is|of|:|=)?\s*(-?{num})(?!\d)", low):
        # a number that carries ANY recognized unit is not unit-less for anyone
        if _owned_elsewhere(m.span(1), tokens, "pressure"):
            continue
        if _overlaps(m, exclude) or any(m.start(1) >= c.span[0] and m.end(1) <= c.span[1]
                                        for c in claims):
            continue
        claims.append(Claim(signed(low, m.start(1), float(m.group(1))), None, None,
                            m.span(), _ev(m).strip()))
    return claims, vac


def _extract_pressure_raw(low: str, exclude: list[Span], rules: dict[str, Any],
                          prefer_last: bool = False) -> tuple[dict[str, Any] | None, list[Span]]:
    """Precedence: ANY vacuum signal co-stated with ANY positive claim is a conflict;
    then distinct claims conflict; then the single remaining claim is returned."""
    spans: list[Span] = []
    claims, vac = _pressure_claims(low, exclude, rules)
    spans += [v.span() for v in vac]
    vac_word = vacuum_match(low, rules)

    if (vac or vac_word) and claims:
        vac_desc = (f"{_pick(vac, prefer_last).group(1)} "
                    + ("inHg" if _pick(vac, prefer_last).group(2).startswith("in")
                       else "mmHg") + " vacuum") if vac else \
            f"'{vac_word.group(0)}' (vacuum service)"
        spans += [c.span for c in claims]
        return _conflict(claims, [vac_desc]), spans

    if vac:
        m = _pick(vac, prefer_last)
        unit = "inHg" if m.group(2).startswith("in") else "mmHg"
        return {"kind": "vacuum", "value": float(m.group(1)), "unit": unit,
                "status": "captured", "evidence": _ev(m)}, spans

    distinct = _distinct(claims)
    if len(distinct) > 1:
        spans += [c.span for c in claims]
        return _conflict(distinct), spans

    if claims:
        c = claims[-1] if prefer_last else claims[0]
        spans.append(c.span)
        if c.unit is None:
            return {"kind": "gauge", "raw": f"{c.lo:g}", "value": None, "unit": None,
                    "status": "needs_unit", "evidence": c.evidence}, spans
        if c.hi is not None:
            return {"kind": "range", "value": [c.lo, c.hi], "unit": c.unit,
                    "status": "captured", "evidence": c.evidence}, spans
        if re.match(r"up[ \t]+to", c.evidence):
            return {"kind": "range", "value": [None, c.lo], "unit": c.unit,
                    "status": "captured", "evidence": c.evidence}, spans
        return {"kind": "gauge", "value": c.lo, "unit": c.unit,
                "status": "captured", "evidence": c.evidence}, spans

    if vac_word:
        return {"kind": "vacuum", "value": None, "unit": None,
                "status": "reading", "evidence": vac_word.group(0)[:80]}, spans
    return None, spans


# ------------------------------- temperature -------------------------------

def to_f(value: float, unit: str) -> float:
    """THE single Celsius->Fahrenheit conversion."""
    return value if unit == "F" else value * 9 / 5 + 32


def _t_unit(token: str, rules: dict[str, Any]) -> str:
    return "F" if token in rules["temperature_units_f"] else "C"


def _t_corroborated(deg_marker: str | None, unit_token: str,
                    low: str, start: int, rules: dict[str, Any],
                    end: int | None = None) -> bool:
    """Only an explicit marker (°/deg) or a written-out unit CAPTURES; a bare
    single-letter unit is always a reading with a confirm ask (V2 round 7)."""
    return bool(deg_marker) or len(unit_token) > 1


def _temperature_claims(low: str, exclude: list[Span], rules: dict[str, Any]
                        ) -> list[Claim]:
    """EVERY temperature shape the text states, in °F, unit-less ones included."""
    units = "|".join(sorted(rules["temperature_units_f"] + rules["temperature_units_c"],
                            key=len, reverse=True))
    num = r"(?:\d+(?:\.\d+)?|\.\d+)"
    mark = r"(°[ \t]*|deg(?:ree|res)?s?\.?[ \t]*(?:of[ \t]+)?)?"
    claims: list[Claim] = []

    rng = [m for m in re.finditer(
        rf"(-?{num})[ \t]*(?:-|–|to)[ \t]*(-?{num})[ \t]*{mark}({units})\b", low)
        if not _overlaps(m, exclude)]
    for m in rng:
        u = _t_unit(m.group(4), rules)
        claims.append(Claim(float(m.group(1)), float(m.group(2)), u,
                            m.span(), _ev(m).strip(),
                            marked=_t_corroborated(m.group(3), m.group(4), low,
                                                   m.start(), rules, m.end())))
    for m in re.finditer(rf"(-?{num})[ \t]*{mark}({units})\b", low):
        if _overlaps(m, exclude) or any(m.start() >= r.start() and m.end() <= r.end()
                                        for r in rng):
            continue
        u = _t_unit(m.group(3), rules)
        claims.append(Claim(float(m.group(1)), None, u, m.span(),
                            _ev(m).strip(),
                            marked=_t_corroborated(m.group(2), m.group(3), low,
                                                   m.start(), rules, m.end())))

    ctx = "|".join(re.escape(c) for c in rules["temperature_context"])
    tokens = unit_tokens(low, rules)
    for m in re.finditer(rf"(?:{ctx})\s*(?:is|of|:|=)?\s*(-?{num})(?!\d)", low):
        if _owned_elsewhere(m.span(1), tokens, "temperature"):
            continue
        if _overlaps(m, exclude) or any(m.start(1) >= c.span[0] and m.end(1) <= c.span[1]
                                        for c in claims):
            continue
        claims.append(Claim(float(m.group(1)), None, None, m.span(), _ev(m).strip()))
    return claims


def extract_temperature(low: str, exclude: list[Span], rules: dict[str, Any],
                        prefer_last: bool = False) -> tuple[dict[str, Any] | None, list[Span]]:
    spans: list[Span] = []
    claims = _temperature_claims(low, exclude, rules)
    distinct = _distinct(claims)

    if len(distinct) > 1:
        spans += [c.span for c in claims]
        out = _conflict(distinct)
        # Derating arms on the HIGHEST stated temperature, full stop (round 23):
        # two rounds of "is this an address or a spec" heuristics failed in both
        # directions, so the engine escalates instead of filtering. A spurious flag
        # on '1250 F Street' is accepted noise; a missed 600 F is not acceptable.
        armed = [c.top_f for c in claims if c.unit is not None]
        out["max_f"] = max(armed) if armed else None
        return out, spans

    if claims:
        c = claims[-1] if prefer_last else claims[0]
        spans.append(c.span)
        if c.unit is None:
            return {"kind": "point", "raw": f"{c.lo:g}", "value": None, "unit": None,
                    "status": "needs_unit", "evidence": c.evidence}, spans
        status = "captured" if c.marked else "reading"
        if c.hi is not None:
            return {"kind": "range", "value": [c.lo, c.hi], "unit": c.unit,
                    "status": status, "max_f": c.top_f, "evidence": c.evidence}, spans
        return {"kind": "point", "value": c.lo, "unit": c.unit, "status": status,
                "max_f": c.top_f, "evidence": c.evidence}, spans

    for term in rules["ambient_terms"]:
        m = re.search(rf"\b{re.escape(term)}\b", low)
        if m:
            lo_f, hi_f = rules["ambient_default_f"]
            return {"kind": "range", "value": [lo_f, hi_f], "unit": "F",
                    "status": "assumed", "max_f": hi_f, "evidence": _ev(m),
                    "note": f"'{m.group(0)}' read as {lo_f}-{hi_f}°F — confirm"}, spans
    return None, spans


def temp_max_f(temp: dict[str, Any] | None) -> float | None:
    """Highest stated temperature in °F, for the derating check (WP-6)."""
    if not temp:
        return None
    if "max_f" in temp:
        return None if temp["max_f"] is None else float(temp["max_f"])
    v = temp.get("value")
    if v is None:
        return None
    hi = max(x for x in (v if isinstance(v, list) else [v]) if x is not None)
    return to_f(hi, temp.get("unit") or "F")


# ------------------------------- end connections -------------------------------

def extract_ends(low: str, rules: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-end connection objects (WP-3, TESTREPORT-2.2). Longest keyword wins and claims
    its span; gender is read from the keyword itself or a short window before the match."""
    fams = rules["connection_families"]
    kw_map = [(kw, family) for family, kws in rules["connection_keywords"].items() for kw in kws]
    kw_map.sort(key=lambda p: len(p[0]), reverse=True)

    claimed: list[Span] = []
    hits: list[tuple[str, re.Match, str]] = []   # (family, match, keyword)
    for kw, family in kw_map:
        for m in re.finditer(rf"\b{re.escape(kw)}\b", low):
            if any(m.start() < e and m.end() > s for s, e in claimed):
                continue
            claimed.append(m.span())
            hits.append((family, m, kw))
    hits.sort(key=lambda h: h[1].start())

    ends: list[dict[str, Any]] = []
    for family, m, kw in hits:
        fam_cfg = fams.get(family, fams["_default"])
        end: dict[str, Any] = {"family": family, "evidence": _ev(m)}
        # A gender word binds to THIS end only when tightly bound to its keyword —
        # nothing but spaces/commas/hyphens between them. A window that crosses another
        # end's span ("male NPT to camlock") must never gender the second end (blind
        # verification V2: gender-phantom class).
        gender = None
        dual: tuple[str, str] | None = None
        ambiguous = False
        gw = "|".join(rules["gender_words"])
        # "male and female camlocks" states BOTH genders — end 1 / end 2, in order.
        # "male OR female camlocks" states a QUESTION — both ends stay missing_gender
        # (V2 rounds 2-3: never collapse either phrasing to one gender twice).
        dm = None
        for cand in re.finditer(rf"\b({gw})\s*(and|&|x|/|or)\s*({gw})\b", low[:m.start()]):
            glue = low[cand.end():m.start()]
            if len(glue) <= 3 and re.fullmatch(r"[ \t,-]*", glue):
                dm = cand
        if dm:
            g1 = rules["gender_words"][dm.group(1)]
            g2 = rules["gender_words"][dm.group(3)]
            if dm.group(2) == "or":
                ambiguous = True
            elif g1 != g2:
                dual = (g1, g2)
            else:
                gender = g1
        if not dual and not gender and not ambiguous:
            for word, g in rules["gender_words"].items():
                if re.match(rf"\b{word}\b", kw):
                    gender = g          # the keyword itself carries it ("male npt")
                    break
                for gm in re.finditer(rf"\b{word}\b", low[:m.start()]):
                    glue = low[gm.end():m.start()]
                    if len(glue) <= 3 and re.fullmatch(r"[ \t,-]*", glue):
                        gender = g
                        break
                if gender:
                    break
        both = re.search(rf"{re.escape(kw)}[^.,;]*(?:both ends|each end)", low) is not None

        if fam_cfg["gendered"]:
            end["gender"] = dual[0] if dual else gender
            end["status"] = "captured" if end["gender"] else "missing_gender"
        elif fam_cfg["ask"] == "configuration":
            end["status"] = "configuration_confirm"
        elif fam_cfg["ask"] == "pressure_class_and_fixed_or_floating":
            cls = re.search(rules["flange_class_pattern"], low)
            mount = next((w for w in rules["flange_mount_words"]
                          if re.search(rf"\b{w}\b", low)), None)
            end["pressure_class"] = cls.group(0) if cls else None
            end["mount"] = mount
            end["status"] = "captured" if (cls and mount) else "missing_spec"
        elif fam_cfg["ask"] == "size_confirm":
            end["status"] = "size_confirm"
        else:
            end["status"] = "captured"

        ends.append(end)
        if (both or dual) and len(ends) < 2:
            second = dict(end)
            if dual:
                second["gender"] = dual[1]
                second["status"] = "captured"
            ends.append(second)
        if len(ends) >= 2:
            break

    # "male camlock one end, female the other" — the second end is stated without
    # repeating the keyword; synthesize it rather than losing it (V2 round 2).
    if len(ends) == 1 and ends[0].get("gender"):
        gw = "|".join(rules["gender_words"])
        om = (re.search(rf"\b({gw})\b[^.,;]{{0,16}}\b(?:the\s+)?other(?:\s+end)?\b", low)
              or re.search(rf"\b(?:the\s+)?other(?:\s+end)?\b[^.,;]{{0,16}}\b({gw})\b", low))
        if om:
            g = rules["gender_words"][om.group(1)]
            second = dict(ends[0])
            second["gender"] = g
            second["status"] = "captured"
            second["evidence"] = om.group(0)[:80]
            ends.append(second)
    return ends
