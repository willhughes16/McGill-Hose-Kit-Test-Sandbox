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
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from run_engine import run_engine  # noqa: E402  (ONE argv builder)
from run_state import (  # noqa: E402
    ARTIFACTS, StateError, artifact_path, invalidate, normalize_invocation,
    read_state,
)

# Field statuses that are NOT a confirmed value. Named here so the wording can
# never quietly imply certainty the engine refused to claim.
UNCONFIRMED = {"reading", "assumed", "needs_unit", "missing", "conflict",
               "missing_gender", "missing_spec", "size_confirm",
               "configuration_confirm", "superseded"}

PRIORITY_ORDER = ("blocking", "confirm", "must_acknowledge")

# Characters a customer must never be able to put into the reply. Round 32 (C-1)
# showed an email line beginning "\x1b[2K\x1b[G" erases the attribution prefix in
# any terminal or pager and renders customer text byte-identically to the kit's
# own checkpoint lines -- a customer could show a checkpoint as CLEARED. Control
# characters are stripped and newlines folded, so untrusted text can never start
# a line, erase one, or open a section.
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-Z\\-_]")

_CONTROL = {c: None for c in range(0x20)}
_CONTROL.update({c: None for c in range(0x7F, 0xA0)})
_CONTROL.pop(ord("\t"), None)


def _safe(value, limit=None):
    """Render an untrusted value as a single inert line of text.

    Everything the engine echoes back -- evidence spans, ask text, the captured
    customer name, notes -- originates in an email. It is DATA. This strips
    control characters (including ANSI escapes), folds newlines and tabs to
    spaces, and collapses runs, so a rendered value occupies exactly one line and
    cannot imitate the document's own structure.
    """
    text = "" if value is None else str(value)
    # Strip WHOLE escape sequences, not just the ESC byte. Removing only the
    # ESC leaves the printable residue ("[2K[G") in the page: harmless but
    # confusing noise that still reads as though the kit emitted it.
    text = _ANSI.sub("", text)
    text = text.replace("\t", " ").translate(_CONTROL)
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


def _open_item(it):
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
    L.append(f"Request type: {_safe(cls)}" + ("   ** URGENT **" if urgent else ""))
    blocking = sum(1 for i in items if i.get("priority") == "blocking")
    L.append(f"Open items: {len(items)}"
             + (f" ({blocking} blocking a quote)" if blocking else ""))
    L.append(f"Draft BOM lines: {len(lines)}")
    # `classes` carries requirements the operator must honour — Certs Required
    # from a C-of-C request is the one that matters. Round 32 pre-flight found it
    # dropped entirely, which for a certificate requirement is exactly the kind
    # of silent omission this kit exists to prevent.
    classes = case.get("classes") or []
    if classes:
        L.append("Applies: " + _safe(", ".join(str(c) for c in classes)))
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
            L.append("  (OTHER PRIORITY)")
            for it in leftover:  # never silently omit an item with a new priority
                L.extend(_open_item(it))
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
                value = _safe(shown["value"], 40)
            elif shown:
                value = _safe(", ".join(f"{k}={v}" for k, v in sorted(shown.items())), 40)
            else:
                value = "—"
            mark = "" if status not in UNCONFIRMED else "  <-- NOT CONFIRMED"
            rows.append([_safe(name), value, _safe(status) + mark,
                         _safe(f.get("evidence"), 48)])
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
            L.append(_table([[_safe(l.get(c, ""), 40) for c in cols] for l in lines],
                            [_safe(c) for c in cols]))
            # A BOM line may carry data outside the declared columns; show it
            # rather than letting bom_columns silently define what exists.
            for i, l in enumerate(lines, 1):
                extra = {k: v for k, v in l.items()
                         if k not in cols and v not in (None, "", [], {})}
                if extra:
                    L.append(f"    line {i} also carries: "
                             f"{_safe(json.dumps(extra, sort_keys=True))}")
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
            L.append(f"  {_safe(c.get('id'))} [{_safe(c.get('status'))}] "
                     f"owner={_safe(c.get('owner'))} ({_safe(c.get('rule_id'))})")
            # Same treatment as open_items: anything the engine adds later is
            # shown rather than dropped by a fixed key list (round 32, H-2).
            for k in sorted(k for k in c
                            if k not in ("id", "status", "owner", "rule_id")):
                if c[k] not in (None, "", [], {}):
                    L.append(f"      {_safe(k)}: {_safe(c[k])}")
        L.append("")
    notes = case.get("notes") or []
    if notes:
        L.append("NOTES")
        L.append("")
        for n in notes:
            L.append(f"  - {_safe(n)}")
        L.append("")
    sup = case.get("supersedes") or []
    if sup:
        L.append("CORRECTIONS IN THE THREAD — a later message overrode an earlier value")
        L.append("")
        for sp in sup:
            L.append("  - " + _safe(sp if isinstance(sp, str)
                                    else json.dumps(sp, sort_keys=True)))
        L.append("")
    logged = case.get("logged_attempts") or []
    if logged:
        L.append("OUT-OF-CLASS ATTEMPTS (logged, not acted on)")
        L.append("")
        for a in logged:
            L.append(f"  - {_safe(a)}")
        L.append("")

    know = case.get("knowledge") or {}
    L.append("PROVENANCE")
    L.append("")
    L.append(f"  schema_version: {case.get('schema_version')}")
    L.append(f"  knowledge source: {_safe(know.get('source'))}"
             + (f" (revision {_safe(know.get('revision'))})" if know.get("revision") else ""))
    lookups = know.get("lookups") or []
    L.append(f"  knowledge lookups: {len(lookups)}")
    for lk in lookups:
        L.append(f"    - {_safe(json.dumps(lk, sort_keys=True))}")
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
    p.add_argument("--no-reconcile", action="store_true",
                   help="render WITHOUT re-deriving the CaseState to check it. "
                        "Only for rendering a CaseState in isolation; never in a "
                        "real run, where the check is the safety net.")
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
