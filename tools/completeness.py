#!/usr/bin/env python3
"""Property check: every non-empty CaseState key must appear in the reply.

Round 36 (K-3) established why this has to exist. The golden suite compares
BYTES, so it can only notice a change to a branch it already exercises — it
froze the *absence* of a branch (`lines == []`) and therefore could not see that
`bom_columns` vanished. A property check does not care which branch ran: it
asserts a relationship between the input and the output, over as many inputs as
you can generate.

That is also why this is not just another selftest case. The self-test checks
named behaviours the author thought of; this checks a universal sentence the
design actually claims:

    "A key cannot be silently absent."

Round 35's blocker and round 36's blocker both falsified exactly that sentence,
one screen apart in the same file, by the same mechanism: a section marks a key
consumed via `take()` and then renders nothing for it on some branch. The
backstop cannot help, because `take()` has already eaten the key.

Run from the kit root:  python3 tools/completeness.py
Exit 0 = every key of every generated CaseState reached the reply.
Exit 1 = a key was silently absent; the offending key and case are named.
"""
from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPLY = os.path.join(ROOT, "src", "scripts", "render_reply.py")

# Keys deliberately not represented as themselves, with the reason. Anything NOT
# listed here must appear. Keep this list tiny and justified: it is the only
# escape hatch, and every entry is a place the property does not hold.
EXEMPT = {
    # `questions` is the engine's legacy twin of `open_items`; its own section
    # renders text + rule_id, so the KEY NAME never appears and need not.
    "questions": "rendered as 'RULES THAT FIRED', not by key name",
    "extraction": "rendered field-by-field under 'EXTRACTED, NOT IN THE FIELD TABLE'",
    "fields": "rendered as the 'WHAT THE EMAIL SAID' table",
    "open_items": "rendered as 'WHAT WE NEED BEFORE QUOTING'",
    "checkpoints": "rendered as the 'CHECKPOINTS' section",
    "lines": "rendered as the BOM table rows",
    "urgency": "rendered as the URGENT marker and an 'urgency:' line",
    "routing": "rendered as the 'Route to:' line",
    "classes": "rendered as the 'Applies:' line",
    "class_evidence": "rendered as 'Why this request class'",
    "notes": "rendered as the 'NOTES' section",
    "supersedes": "rendered as the 'CORRECTIONS IN THE THREAD' section",
    "logged_attempts": "rendered as 'OUT-OF-CLASS ATTEMPTS'",
    "knowledge": "rendered as the 'PROVENANCE' section",
    "request_class": "rendered as 'Request type:'",
    "schema_version": "rendered under PROVENANCE",
    "bom_columns": "rendered as the BOM table HEADER",
}


def _values(obj):
    """Every scalar LEAF of a CaseState value, as strings worth searching for.

    Leaf values only -- nested dict KEY NAMES are deliberately not collected.
    The distinction is the whole basis of this check, so it is worth stating: a
    nested key name is schema VOCABULARY, and the reply legitimately expresses
    `{"recommendation": "inside_sales_review"}` as `Route to: inside_sales_review`
    without printing the word "recommendation". Demanding the vocabulary would
    force the reply to print raw JSON everywhere, which is exactly what it exists
    not to do. A leaf value is CONTENT, and content going missing is the defect
    this check hunts -- rounds 35 and 36 were both content, not vocabulary.

    TOP-LEVEL key names are still required (see EXEMPT in main()): those are what
    the completeness backstop prints, and a top-level key vanishing is precisely
    the round-35/36 failure mode.
    """
    out = []
    if isinstance(obj, dict):
        for v in obj.values():
            out += _values(v)
    elif isinstance(obj, list):
        for v in obj:
            out += _values(v)
    elif obj is not None and obj is not True and obj is not False:
        s = str(obj)
        if s.strip():
            out.append(s)
    return out


def _present(needle, haystack_norm):
    """Whether a leaf value reached the page, allowing only the two transforms
    the renderer demonstrably applies to labels: upper-casing and turning
    underscores into spaces (`must_acknowledge` -> `MUST ACKNOWLEDGE`).

    Kept deliberately narrow. Every normalization added here weakens the check,
    so it is limited to transformations that exist in the renderer's own source
    rather than anything that merely makes a red run green -- which is how this
    campaign's vacuous checks were born.
    """
    return needle.lower().replace("_", " ") in haystack_norm


def _norm(text):
    return text.lower().replace("_", " ")


def render(case):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "_report"), exist_ok=True)
    cp = os.path.join(d, "_report", "case_state.json")
    with open(cp, "w", encoding="utf-8") as fh:
        json.dump(case, fh)
    out = os.path.join(d, "_report", "reply.md")
    p = subprocess.run([sys.executable, REPLY, "--case-state", cp,
                        "--no-reconcile", "--out", out],
                       capture_output=True, text=True, timeout=120, cwd=d)
    body = ""
    if os.path.isfile(out):
        with open(out, encoding="utf-8") as fh:
            body = fh.read()
    return p.returncode, body, d


BASE = {
    "schema_version": "2.0",
    "request_class": "hose_assembly",
    "bom_columns": ["COL-ALPHA", "COL-BETA"],
    "knowledge": {"source": "none"},
}

# The axes whose COMBINATIONS matter. Round 36's blocker lived in the cell
# (bom_columns present, lines empty) -- a branch no fixture exercised.
AXES = {
    "lines": [[], [{"COL-ALPHA": "LINEVAL-1"}]],
    "open_items": [[], [{"code": "OI-CODE", "priority": "blocking",
                         "ask": "OI-ASK", "route": "OI-ROUTE"}]],
    "fields": [{}, {"FLD-NAME": {"value": "FLD-VALUE", "status": "captured"}}],
    "checkpoints": [[], [{"id": "CP-ID", "status": "PENDING",
                          "owner": "CP-OWNER", "rule_id": "CP-RULE"}]],
    "classes": [[], ["CLS-ONE"]],
    "notes": [[], ["NOTE-ONE"]],
    "supersedes": [[], [{"field": "SUP-FIELD", "to": "SUP-TO"}]],
    "logged_attempts": [[], ["LOG-ONE"]],
    "urgency": [{"flagged": False}, {"flagged": True, "phrases": ["URG-PHRASE"]}],
    "routing": [{}, {"recommendation": "RTG-REC", "reasons": ["RTG-WHY"]}],
    "class_evidence": [None, "CLSEV-TEXT"],
    "extraction": [{}, {"end_fittings": ["EXT-BARB"], "material_recognized": False}],
    "questions": [[], [{"text": "Q-TEXT", "rule_id": "Q-RULE"}]],
    "a_future_key": [None, "FUTURE-VALUE"],
}


def main():
    names = list(AXES)
    violations = []
    combos = 0
    # Full cross-product is 2^14; walk the pairwise+all-on/all-off frontier,
    # which is where a branch-gated omission lives, and keep it fast.
    profiles = [dict.fromkeys(names, 0), dict.fromkeys(names, 1)]
    for i, j in itertools.combinations(range(len(names)), 2):
        for a, b in ((0, 1), (1, 0)):
            prof = dict.fromkeys(names, 1)
            prof[names[i]], prof[names[j]] = a, b
            profiles.append(prof)
    for prof in profiles:
        case = dict(BASE)
        for n in names:
            v = AXES[n][prof[n]]
            if v is not None:
                case[n] = v
        combos += 1
        rc, body, d = render(case)
        if rc != 0:
            violations.append((combos, "<render failed>", f"rc={rc}"))
            continue
        body_norm = _norm(body)
        for key, value in case.items():
            if value in (None, "", [], {}):
                continue
            key_shown = key in EXEMPT or key in body
            missing_leaves = [v for v in _values(value)
                              if len(v) > 3 and not _present(v, body_norm)]
            if not key_shown:
                violations.append((combos, key, "key name absent"))
            if missing_leaves:
                violations.append((combos, key,
                                    f"values absent: {missing_leaves[:3]}"))
    print(f"COMBINATIONS RUN: {combos}")
    seen = set()
    uniq = []
    for c, k, why in violations:
        sig = (k, why)
        if sig in seen:
            continue
        seen.add(sig)
        uniq.append((c, k, why))
    print(f"VIOLATIONS: {len(uniq)} distinct ({len(violations)} total)")
    for c, k, why in uniq:
        print(f"  case {c}: {k} -> {why}")
    return 1 if uniq else 0


if __name__ == "__main__":
    raise SystemExit(main())
