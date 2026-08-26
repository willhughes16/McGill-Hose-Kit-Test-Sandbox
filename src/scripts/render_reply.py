#!/usr/bin/env python3
"""Render the whole case as an inline reply email for inside sales.

The kit's reply carries NO attachment. Everything an operator needs is in the
message body, including the parts `bom_draft.md` deliberately drops: every field
with its status and evidence, the routing recommendation, supersede history and
knowledge provenance.

This reads `_report/case_state.json` and nothing else. That is deliberate and
different from `generate_report.py`, which re-runs the engine to reproduce its
verbatim rendering: there is no upstream text to be byte-identical to here, so
re-running would buy nothing and cost a third engine pass. The CaseState IS the
contract, and it was already reconciled against a replayed extraction by
`generate_report.py`.

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
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from run_state import (  # noqa: E402
    ARTIFACTS, StateError, artifact_path, invalidate, read_state,
)

# Field statuses that are NOT a confirmed value. Named here so the wording can
# never quietly imply certainty the engine refused to claim.
UNCONFIRMED = {"reading", "assumed", "needs_unit", "missing", "conflict",
               "missing_gender", "missing_spec", "size_confirm",
               "configuration_confirm", "superseded"}

PRIORITY_ORDER = ("blocking", "confirm", "must_acknowledge")


def _table(rows, headers):
    if not rows:
        return None
    widths = [max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    out = [" | ".join(str(headers[i]).ljust(widths[i]) for i in range(len(headers))),
           "-|-".join("-" * w for w in widths)]
    for r in rows:
        out.append(" | ".join(str(r[i]).ljust(widths[i]) for i in range(len(headers))))
    return "\n".join(out)


def render(case):
    """Build the reply body. Pure function of the CaseState."""
    L = []
    cls = case.get("request_class") or "unclassified"
    urgent = bool((case.get("urgency") or {}).get("flagged"))
    items = case.get("open_items") or []
    lines = case.get("lines") or []

    L.append("DRAFT — not a quote, and not entered in the ERP. A human reviews and "
             "commits this.")
    L.append("")
    L.append(f"Request type: {cls}" + ("   ** URGENT **" if urgent else ""))
    blocking = sum(1 for i in items if i.get("priority") == "blocking")
    L.append(f"Open items: {len(items)}"
             + (f" ({blocking} blocking a quote)" if blocking else ""))
    L.append(f"Draft BOM lines: {len(lines)}")
    routing = case.get("routing") or {}
    if routing:
        who = routing.get("recommendation")
        why = routing.get("reasons") or []
        L.append("Route to: " + (str(who) if who else "(none recommended)")
                 + (f" — {', '.join(str(r) for r in why)}" if why else ""))
        # Never drop a routing key the engine adds later: show anything unread
        # rather than silently omitting it. Round 31's lesson in miniature.
        extra = {k: v for k, v in routing.items()
                 if k not in ("recommendation", "reasons")}
        if extra:
            L.append(f"  routing (other): {json.dumps(extra)}")
    L.append("")

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
                L.append(f"    [{it.get('code')}] {it.get('ask') or it.get('quote') or ''}")
                route = it.get("route")
                if route:
                    L.append(f"        route: {route}")
            L.append("")
        leftover = [i for i in items if i.get("priority") not in PRIORITY_ORDER]
        for it in leftover:      # never silently omit an item with a new priority
            L.append(f"    [{it.get('code')}] {it.get('ask') or it.get('quote') or ''}"
                     f"   (priority: {it.get('priority')!r})")
        if leftover:
            L.append("")

    # ---- what the engine understood, with evidence ---------------------------
    fields = case.get("fields") or {}
    if fields:
        rows = []
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
                value = str(shown["value"])
            elif shown:
                value = ", ".join(f"{k}={v}" for k, v in sorted(shown.items()))
            else:
                value = "—"
            mark = "" if status not in UNCONFIRMED else "  <-- NOT CONFIRMED"
            rows.append([name, value, status + mark,
                         str(f.get("evidence") or "")[:48]])
        L.append("WHAT THE EMAIL SAID")
        L.append("")
        L.append(_table(rows, ["Field", "Value", "Status", "Evidence"]))
        L.append("")
        L.append("  A status other than 'captured' is NOT a confirmed value. The engine")
        L.append("  deliberately refuses to commit to an ambiguous one.")
        L.append("")

    # ---- the draft BOM -------------------------------------------------------
    cols = case.get("bom_columns") or []
    if cols:
        L.append("DRAFT BILL OF MATERIALS")
        L.append("")
        if lines:
            L.append(_table([[str(l.get(c, "")) for c in cols] for l in lines], cols))
        else:
            L.append("  (no lines — nothing is grounded enough to draft; see the open "
                     "items above)")
        L.append("")

    # ---- checkpoints, notes, supersedes, provenance --------------------------
    cps = case.get("checkpoints") or []
    if cps:
        L.append("CHECKPOINTS — each requires a human, and none can be actioned here")
        L.append("")
        for c in cps:
            L.append(f"  {c.get('id')} [{c.get('status')}] owner={c.get('owner')} "
                     f"({c.get('rule_id')})")
        L.append("")
    notes = case.get("notes") or []
    if notes:
        L.append("NOTES")
        L.append("")
        for n in notes:
            L.append(f"  - {n}")
        L.append("")
    sup = case.get("supersedes") or []
    if sup:
        L.append("CORRECTIONS IN THE THREAD — a later message overrode an earlier value")
        L.append("")
        for sp in sup:
            L.append(f"  - {json.dumps(sp) if not isinstance(sp, str) else sp}")
        L.append("")
    logged = case.get("logged_attempts") or []
    if logged:
        L.append("OUT-OF-CLASS ATTEMPTS (logged, not acted on)")
        L.append("")
        for a in logged:
            L.append(f"  - {a}")
        L.append("")

    know = case.get("knowledge") or {}
    L.append("PROVENANCE")
    L.append("")
    L.append(f"  schema_version: {case.get('schema_version')}")
    L.append(f"  knowledge source: {know.get('source')}"
             + (f" (revision {know.get('revision')})" if know.get("revision") else ""))
    lookups = know.get("lookups") or []
    L.append(f"  knowledge lookups: {len(lookups)}")
    for lk in lookups:
        L.append(f"    - {json.dumps(lk)}")
    L.append("")
    L.append("No price, lead time or stock position appears above: the engine produces "
             "none.")
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

    body = render(case)
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
