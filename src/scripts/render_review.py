#!/usr/bin/env python3
"""Render the REVIEWER's document: the decision, its grounds, and who it goes to.

The Coworker architecture document splits one message in two. Outside Sales
receives the guidance; Inside Sales receives a review request carrying the
summary, the uncertainty and the proposed response, and decides -- approve, edit,
reject, reassign or escalate. Up to v0.17.0 this kit emitted one document trying
to be both: `reply.md` is written for the person who receives the answer, and a
reviewer had to infer the decision from it.

So this is a SECOND PROJECTION of the same case, for the other reader. What makes
it safe is that the proposed response is not re-described here -- it is EMBEDDED
VERBATIM. The reviewer approves the exact bytes that would be sent, and the two
documents cannot drift into disagreement, because one contains the other.

Three guards, each failing CLOSED:

1. **The CaseState is re-derived** and must equal `case_state.json`, exactly as
   `generate_report.py` and `render_reply.py` do it. Round 32 (H-1) is why: a
   script that trusts the file on disk will happily write a confident document
   about a case the engine no longer produces.

   **This docstring used to claim the guard could not be isolated by a test.
   Round 37 refuted that, and the claim was wrong.** The author had written that
   guard 2 refuses the same pairs, because a reply forged to match a tampered
   CaseState could not carry a scanned attachment record. It can: render the
   forged reply through `render_reply.render` with the REAL evidence and case
   text, and guard 2 is satisfied. The verifier built that pair, confirmed the
   shipped script refuses it, removed this guard in a scratch copy and watched the
   forged pair be accepted — with a `DERATING_REVIEW` blocking item silently
   absent from the reviewer's document.

   So this guard is load-bearing on its own, the test that isolates it exists,
   and the previous paragraph was false documentation of exactly the kind twelve
   rounds have found in shipped docs. It is left here, corrected, rather than
   deleted: what the author could not find a test for, someone else found in an
   afternoon.
2. **`reply.md` must equal what the renderer produces for THIS case right now.**
   A stale reply beside a fresh CaseState would mean the reviewer approves one
   text while a different one is on disk to send. Rather than comparing prose,
   the body is recomputed through `render_reply.render` -- the same function, not
   a second expression -- and compared byte for byte.
3. **Routing is resolved, never invented.** An owner with no configured address
   renders as NOT ROUTABLE and names the key. See `routing.py` for why a
   fallback to inside sales would be worse than a visible gap.

Cost: this adds a FIFTH engine pass to a full run (extract 1, generate_report 2,
render_reply 1, this 1). On a multi-hundred-KB thread that is not free -- see
FOLLOW-UP-9 -- and the size warning fires here too.

Exit codes -- ONLY these two, enforced by the clamp in ``__main__``:
    0  review request written
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

import answers as answers_mod  # noqa: E402
import attachments  # noqa: E402
import lineitems  # noqa: E402
import questions as questions_mod  # noqa: E402
import routing as routing_table  # noqa: E402  (not the CaseState's `routing` key)
import render_reply  # noqa: E402
from render_reply import _bytes, _safe, is_unconfirmed  # noqa: E402
from run_engine import build_delivery, run_engine, warn_if_slow  # noqa: E402
from run_state import (  # noqa: E402
    ARTIFACTS, StateError, artifact_path, derive_outcome, idempotency_key,
    input_sha256, invalidate, normalize_invocation, read_state, source_input,
)

RULE = "-" * 78


def _uncertainty(case, evidence, case_text, transcribed=(), line_items=None,
                 transcripts=None):
    """The grounds a human is needed, in the order they change the answer.

    Derived from the case, never asserted: the same two facts `derive_outcome`
    reads, plus the fields the engine refused to commit to. If this section is
    empty the outcome must be `complete`, and the self-test asserts exactly that
    relationship rather than the wording of either.
    """
    out = []
    _r = case_text or {}
    customer_text = _r.get(answers_mod.CUSTOMER) or ""
    operator_text = _r.get(answers_mod.OPERATOR)
    transcript_text = _r.get(answers_mod.TRANSCRIBED)
    items = case.get("open_items") or []
    blocking = [i for i in items if (i or {}).get("priority") == "blocking"]
    for item in blocking:
        out.append(f"  BLOCKING  [{_safe(item.get('code'))}] "
                   f"{_safe(item.get('ask') or item.get('quote'))}")
    # A transcribed attachment is NOT unread — it gets a MACHINE line below.
    # Listing it under both makes the page contradict itself, and a reviewer
    # resolves a contradiction by trusting whichever line they read last.
    _named = {str(t) for t in transcribed}
    for f in [f for f in ((evidence or {}).get("attachments") or [])
              if str(f.get("filename")) not in _named]:
        out.append(f"  UNREAD    {_safe(f.get('filename'))} — the customer sent it, "
                   "the engine never opened it, and every item below was derived "
                   "without it")
    if (evidence or {}).get("status") not in ("scanned", None):
        out.append("  UNKNOWN   the attachments could not be checked "
                   f"({_safe((evidence or {}).get('error'))}) — it is not known "
                   "whether the customer sent evidence this case does not contain")
    if (line_items or {}).get("multi_item") and (case.get("fields") or {}):
        # The sharpest ground there is: the fields may belong to no single product.
        for ground in line_items.get("grounds") or []:
            out.append(f"  MERGED    {_safe(ground)}")
        out.append("  MERGED    the specification below was built from across a "
                   "document describing several products, and may describe none "
                   "of them")
    if transcript_text is not None:
        # A reviewer approving a case built on a transcript is approving a
        # machine's reading of a document, and that is a ground in its own right.
        # The GROUND is short; the transcript itself is a section of its own
        # further down. Emitting one `MACHINE` line per transcribed line put
        # eighty rows of a purchase order between the reviewer and the decision
        # they were being asked to make -- the same unusability that made the
        # reply get ignored (phase 2).
        _count = len(answers_mod.addendum_lines(transcript_text))
        for rec in transcripts or []:
            out.append(f"  MACHINE   {_safe(rec.get('filename'))} was read by a "
                       f"model ({_safe(rec.get('method'))}) — "
                       f"{_count} lines, shown in full below")
        if not transcripts:
            out.append(f"  MACHINE   an attachment was read by a model — {_count} "
                       "lines, shown in full below")
        for name, verdict in answers_mod.sourced_fields(case, _r).items():
            if verdict == answers_mod.TRANSCRIBED:
                out.append(f"  MACHINE   {_safe(name)} was read off an attachment "
                           "by a model, not typed by the customer")
    if operator_text is not None:
        # Named as a ground in its own right: a reviewer approving a case that an
        # operator already part-answered is approving that operator's memory too.
        for line in answers_mod.addendum_lines(operator_text):
            out.append(f"  OPERATOR  {_safe(line)}")
        # Round 37 (H-1): this claimed "came from an operator's answer, not the
        # customer" for EVERY non-customer verdict — including `ambiguous` (the
        # words are in both) and `unattributable` (no evidence span to check).
        # Three of five such lines were false in one run, and a reviewer reading
        # them would discount values the customer really did state. Each verdict
        # now says what it actually means.
        _said = {answers_mod.OPERATOR:
                 "came from an operator's answer, not the customer",
                 answers_mod.AMBIGUOUS:
                 "appears in BOTH the customer's text and an operator's — the two "
                 "cannot be told apart here",
                 answers_mod.UNATTRIBUTABLE:
                 "records no evidence span, so it cannot be attributed to either"}
        for name, verdict in answers_mod.sourced_fields(case, _r).items():
            if verdict in _said:
                out.append(f"  OPERATOR  {_safe(name)} {_said[verdict]}")
    for name in sorted(case.get("fields") or {}):
        field = (case.get("fields") or {})[name] or {}
        status = field.get("status")
        if is_unconfirmed(status):
            out.append(f"  UNSURE    {_safe(name)} is `{_safe(status)}` — the engine "
                       "saw something and refused to commit to it")
    return out


def render(case, evidence, reply_body, invocation, addressees, table_error,
           case_text=None, transcripts=None, line_items=None, delivery=None,
           translations=None, record_body=""):
    """Build the review request. Pure function of what it is handed."""
    outcome, reason = derive_outcome(
        case, evidence,
        [r.get('filename') for r in transcripts or []], line_items)
    key = idempotency_key(invocation, input_sha256(invocation["input"])) \
        if invocation else None

    L = ["REVIEW REQUEST — a human decision is being asked for, and nothing has "
         "been sent.", ""]
    if key:
        # The case's identity, so a reviewer answering in Teams and a Body
        # resuming an execution are provably talking about the same run.
        L.append(f"Case: {key[:12]}   (idempotency key, first 12 of 64)")
    L.append(f"Outcome: {_safe(outcome)} — {_safe(reason)}")
    L.append("")
    L.append("DECISION: approve · edit · reject · reassign · escalate")
    L.append("")

    # ---- who it goes to (CW-5) ----------------------------------------------
    L.append("WHO THIS GOES TO")
    L.append("")
    if table_error:
        L.append(f"  the routing table could not be read: {_safe(table_error)}")
    pairs = routing_table.keys_in(case)
    if not pairs:
        L.append("  the case names no owner at all — decide who owns it before "
                 "anything else")
    for kind, key_name in pairs:
        record = routing_table.resolve(key_name, addressees, table_error)
        L.append(f"  {kind:11} {_safe(routing_table.describe(record))}")
    unroutable = [k for kind, k in pairs
                  if routing_table.resolve(k, addressees, table_error)["status"]
                  != routing_table.ROUTABLE]
    if unroutable:
        L.append("")
        L.append("  Nothing above with NOT ROUTABLE has an address. The kit will "
                 "not guess one:")
        L.append("  a wrong assignee is worse than a visible gap. Fill the key in "
                 "config/routing.json.")
    L.append("")

    # ---- why a human ---------------------------------------------------------
    grounds = _uncertainty(case, evidence, case_text,
                           [r.get('filename') for r in transcripts or []],
                           line_items, transcripts)
    L.append("WHY THIS NEEDS YOU")
    L.append("")
    if grounds:
        L.extend(grounds)
    else:
        L.append("  Nothing blocks a quote and no evidence went unread. This is a "
                 "draft for review,")
        L.append("  not an approval to send unread — every case this kit produces "
                 "is reviewed.")
    L.append("")

    # ---- what approving means ------------------------------------------------
    L.append("BEFORE YOU APPROVE")
    L.append("")
    L.append("  - The response below is sent UNCHANGED. Edit it in your reply, not "
             "here.")
    L.append("  - No open item below has been answered. The engine asks; it never "
             "guesses.")
    L.append("  - Nothing here is a price, a lead time or a stock position. Where a "
             "figure")
    L.append("    appears it is the customer's own words quoted back.")
    L.append("  - This is a draft. A human commits it in the ERP.")
    L.append("")

    # What should arrive WITH this review request. Named here as well as in the
    # manifest because a reviewer told to check a transcript against the original
    # needs to know whether they were sent the original.
    attach = ((delivery or {}).get("review_request") or {}).get("attach") or []
    if attach:
        L.append("SENT WITH THIS REVIEW — the customer's own files, so you can "
                 "check what a machine read")
        L.append("")
        for f in attach:
            L.append(f"  {_safe(f.get('filename'))}  ({_bytes(f.get('bytes'))})"
                     f" — {_safe(f.get('reason'))}")
        L.append("")
        L.append("  If these did not arrive, ask for them before approving: a "
                 "transcript nobody can")
        L.append("  check against its source is a claim, not evidence.")
        L.append("")

    # The transcript, verbatim, as its own section. Here and not in the reply
    # (phase 2): the reviewer is the one who checks a machine's reading against
    # the original document, and the customer's email is not the place for two
    # pages of someone else's purchase order.
    transcript_text = (case_text or {}).get(answers_mod.TRANSCRIBED)
    if transcript_text is not None:
        L.append("WHAT THE MACHINE READ — verbatim, for checking against the "
                 "original file")
        L.append(RULE)
        for line in answers_mod.addendum_lines(transcript_text):
            L.append(f"  {_safe(line)}")
        L.append(RULE)
        L.append("")

    # The translation, side by side. This is what makes rewording an open item
    # permissible at all: the reviewer sees the engine's EXACT words next to the
    # sentence the customer will read, and approves the change rather than
    # inheriting it. EVERY item appears, including the ones not asked.
    if translations:
        L.append("QUESTIONS PROPOSED TO THE CUSTOMER — approve the wording, or "
                 "correct it in your reply")
        L.append("")
        for t in translations:
            if t["audience"] == questions_mod.INTERNAL:
                L.append(f"  [{_safe(t['code'])}]  NOT ASKED — ours to resolve")
            elif t["untranslated"]:
                L.append(f"  [{_safe(t['code'])}]  NOT TRANSLATED — the customer "
                         "would see our internal wording")
            else:
                L.append(f"  [{_safe(t['code'])}]")
            L.append(f"      engine asks : {_safe(t['ask'])}")
            if t["question"] is not None:
                L.append(f"      customer sees: {_safe(t['question'])}")
        L.append("")
        L.append("  The left line is the engine's own words and is never edited. "
                 "The right line is")
        L.append("  from config/questions.json. If a translation changes what is "
                 "being asked, that is")
        L.append("  a defect — say so rather than approving it.")
        L.append("")

    # The COMPLETE case record. It used to BE reply.md; now the reply is the
    # customer's email and this is where every field, every open item in the
    # engine's own words, the checkpoints and the backstop live. Anything the
    # CaseState carries and no section above renders appears here, which is what
    # tools/completeness.py checks.
    L.append("THE COMPLETE CASE RECORD — everything the engine produced")
    L.append(RULE)
    L.append(record_body.rstrip("\n"))
    L.append(RULE)
    L.append("")

    L.append("PROPOSED RESPONSE — the exact text that would be sent, embedded "
             "verbatim")
    L.append(RULE)
    L.append(reply_body.rstrip("\n"))
    L.append(RULE)
    return "\n".join(L).rstrip() + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--case-state", default=None,
                   help="CaseState to render; defaults to the one named in --state")
    p.add_argument("--reply", default=None,
                   help=f"the proposed response to embed (default "
                        f"{ARTIFACTS['reply']})")
    p.add_argument("--out", dest="out", default=ARTIFACTS["review_request"])
    p.add_argument("--state", default=os.path.join("_report", "state.json"))
    p.add_argument("--questions", default=None,
                   help="question translation table (default config/questions.json)")
    p.add_argument("--routing", default=None,
                   help="routing table (default config/routing.json)")
    p.add_argument("--no-reconcile", action="store_true",
                   help="render WITHOUT re-deriving the CaseState or checking the "
                        "reply against it. Only for rendering in isolation.")
    args = p.parse_args(argv)

    out = args.out or ARTIFACTS["review_request"]
    try:
        invalidate([artifact_path("review_request", review_request=out)])
    except StateError as e:
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

    reply_path = args.reply or ARTIFACTS["reply"]
    try:
        with open(reply_path, encoding="utf-8") as fh:
            reply_body = fh.read()
    except OSError as e:
        print(f"error: cannot read the proposed response at {reply_path}: {e}.\n"
              "       The review request embeds the reply VERBATIM so a reviewer "
              "approves the exact\n"
              "       bytes that would be sent. Run scripts/render_reply.py first.",
              file=sys.stderr)
        return 1

    # Same rule as the reply (REQ-093): the input file may only be read once the
    # invocation is PROVEN to describe this CaseState.
    evidence = attachments.not_checked(
        "the review request was rendered without reconciliation, so the recorded "
        "invocation is not proven to describe this case")
    case_text = {}
    invocation = normalize_invocation(read_state(args.state).get("invocation"))
    if args.no_reconcile:
        print("warning: --no-reconcile — neither the CaseState nor the embedded "
              "reply is being checked", file=sys.stderr)
    else:
        if not invocation:
            print(f"error: no invocation recorded in {args.state}, so neither the "
                  "CaseState nor the\n       embedded reply can be checked. Run the "
                  "extract phase, or pass --no-reconcile.", file=sys.stderr)
            return 1
        warn_if_slow(invocation["input"], passes=1)
        try:
            replayed = json.loads(run_engine(invocation, as_json=True)[0])
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        if replayed != case:
            differing = sorted(k for k in set(case) | set(replayed)
                               if case.get(k) != replayed.get(k))
            print(f"error: {case_path} does not match a re-derived CaseState, so the "
                  "review request would\n       ask a human to approve a response "
                  "about a different case. Refusing.\n"
                  f"       differing top-level keys: {differing}", file=sys.stderr)
            return 1
        evidence = attachments.scan(source_input(read_state(args.state)))
        case_text = answers_mod.read_regions(invocation["input"])

        # The embedded reply must be THIS case's reply. Recomputed through the
        # renderer itself rather than compared as prose: a second expression of
        # the reply's content is exactly what this file exists to avoid.
        _table, _table_error = questions_mod.load(args.questions)
        expected = render_reply.render_customer(
            case, questions_mod.for_case(case, _table), _table_error, evidence,
            lineitems.scan_file(invocation["input"]))
        if expected != reply_body:
            print(f"error: {reply_path} is not the reply for this case.\n"
                  "       A reviewer would approve one text while a different one "
                  "sits on disk to send.\n"
                  "       Re-run scripts/render_reply.py, then this.",
                  file=sys.stderr)
            return 1

    _qtable, _qerror = questions_mod.load(args.questions)
    _translations = questions_mod.for_case(case, _qtable)
    _line_items = (lineitems.scan_file(invocation["input"]) if invocation else None)

    addressees, table_error = routing_table.load(args.routing)
    if table_error:
        print(f"warning: {table_error}; every owner will render as NOT ROUTABLE",
              file=sys.stderr)

    body = render(case, evidence, reply_body, invocation, addressees,
                  table_error, case_text,
                  (read_state(args.state).get('transcripts') or {}).get('records'),
                  _line_items,
                  build_delivery(evidence,
                                 (read_state(args.state).get('transcripts') or {})
                                 .get('records')),
                  _translations,
                  render_reply.render(case, evidence, case_text,
                                      (read_state(args.state).get('transcripts')
                                       or {}).get('records') or [],
                                      _line_items))
    try:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(body)
    except OSError as e:
        print(f"error: cannot write {out}: {e}", file=sys.stderr)
        return 1

    outcome, _ = derive_outcome(case, evidence)
    print(f"wrote {out} ({len(body)} bytes, outcome={outcome})")
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
