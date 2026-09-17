# Coworker architecture doc vs. this kit — alignment, and the features it implies

Assessed 2026-09-17 against the kit at v0.15.0 (engine `ae4411f`), branch
`fix/corpus-size-length`.

The document describes a four-component product — **Body** (channels, cases,
delivery, audit), **Compute** (runs skills), **Memory** (TWYD), **Factory**
(builds and publishes skills). This kit is **one Compute skill**, the one the
document calls Evolution 1 (InboxQuoter).

So "aligned?" is really two questions, and they have different answers:

* **Does the kit contradict the document's design line?** No. On every point
  where the document states a safety rule, the kit already enforces it
  structurally rather than by intention.
* **Does the kit give Body what the document's Evolution 2 needs?** No. The kit
  produces one artifact for one audience with no execution identity, no
  resolvable assignee, and no way for an answer given outside the email thread
  to reach the case. Those are the gaps worth building.

---

## 1. Where the kit already is the document

These are not coincidences to be maintained by discipline — they are enforced.

| Document says | Kit does | Where |
|---|---|---|
| "We don't wanna just create a response out of the blue" | Every artifact opens `DRAFT — not a quote, and not entered in the ERP.` The kit may never present output as a quote, a confirmed BOM or an order. | `src/scripts/render_reply.py`, `src/CLAUDE.md` |
| "Compute never sends directly to Outside Sales or a customer" | The kit has no send path and no write key. A source-side test asserts `core.py` cannot even *reference* `TwydIngestion` or `publish`. | FOLLOW-UP-2, `.astrocode/PROJECT.md` |
| "states what is unknown" / "without Coworker inventing an answer" | Every missing, ambiguous or unsafe item is an `open_items[]` entry with a stable code, an ask and a priority. The kit may never answer, drop, reword or re-prioritize one. | `schemas/case_state.schema.json` (37 codes) |
| "Coworker shows the source and approval status of the knowledge used" | `knowledge{source, revision, lookups[]}` with per-lookup `tier` and `citation`; `verified` facts may reach a BOM line, `candidate` facts may only become proposals. Default-deny. | `src/vendor/email_to_bom/knowledge.py` |
| "asks only questions required by the application and risk context" | `request_class` gates which fields apply; a component or order request is never pushed through hose-assembly questions. | `src/vendor/email_to_bom/core.py` |
| "understands later answers or corrections" | `supersedes[]` — a later correction in the same thread text overrides the earlier value, and an unresolvable one becomes `CORRECTION_UNRESOLVED` (blocking). | `core.py::_extract_with_supersede` |
| "routes a precise question to a named expert or group" | `checkpoints[]` already carry an `owner` — "QC Department", "Sales + Production Manager + Quality Team", "Inside Sales". | `core.py` C1/C2/C3 |
| "idempotent so retries do not create duplicate cases" | The kit holds no state between runs. A run is a pure function of the input text plus the recorded invocation; re-running the whole accumulated thread is the supported way to continue a conversation. | `src/scripts/run_state.py` |

The last row is worth naming explicitly, because it looks like a limitation and
is actually the property the document asks for: **the kit continues a
conversation by replay, not by memory.** Body appends the new message to the
thread and re-runs; the engine re-derives everything including the corrections.
There is no accumulated state to corrupt and nothing to reconcile.

---

## 2. Where the document overstates what exists today

Four claims in Evolution 1 ("current capability") are not true of this kit.
Three of them belong to Body. One is a real hole in Compute.

**2.1 "keep the complete email thread and attachments together" — attachments are read by nobody.**
`mail.py` reduces a MIME message to *Subject + best body part*. There is no
attachment handling anywhere in the engine: no `walk()`, no
`Content-Disposition` inspection, no filename capture. An RFQ whose dimensions
are in the attached drawing produces a CaseState that correctly says the
dimensions are missing — and **never mentions that a drawing was attached and
ignored.** Body may well be storing the file; nothing tells the reviewer that
the evidence exists and was not read. This is the one gap in this section that
is ours. → **CW-1**.

**2.2 "filter incoming messages" — this kit tried that, and it was removed.**
An input filter shipped and was deleted after round 30 measured **54% of its
drops as real customer business**. Two published builds were rolled back for
dropping RFQs: v0.4.0 (24 of 35) and v0.6.0 (11 of 46). Six rounds failed to
make it safe. If Body implements filtering, it inherits that hazard wholesale.
The recommendation the campaign landed on: **filter to a review queue, never to
nothing**, and measure the drop set against real mail before trusting it. Not a
kit feature — a warning to the Body team, and the measurement is in
`VERIFICATION_ROUND30.md`.

**2.3 "connect a mailbox" / "read-only dashboard"** — Body, correctly. No kit gap.

**2.4 "Compute can report progress"** — there is no progress channel, and runtime
is superlinear: ~0.1 s at 8 KB, ~5 s at 134 KB, ~80 s at 538 KB, and a kit run
costs four engine passes. Body will see a long silent call on a big thread.
Either Body treats Compute as fire-and-poll, or an input ceiling gets agreed.
Inherited from the engine (FOLLOW-UP-9), so the fix is upstream.

---

## 3. Evolution 2 — what Body needs and the kit does not emit

This is the substance. The document's Evolution 2 asks for a supervised loop:
the reviewer gets a summary, the uncertainty and a proposed response, and can
approve / edit / reject / reassign / escalate from Teams or email. Today the
kit emits **one artifact, `reply.md`, for one audience**, with:

* no case or execution identity, and no record of which skill version produced it;
* no distinct reviewer view — the proposal and the decision are not separated;
* `route` as a four-value role enum, which Body cannot turn into an addressee;
* no way for an answer given in Teams to reach the case, so the next run re-asks
  a question a human already answered;
* no defined shape for a reviewer's correction, which Evolution 3 needs Factory
  to consume.

Each of those is a feature below.

---

## 4. Proposed features

Ordered by what unblocks Evolution 2 soonest. Every one respects the two
standing constraints: **`src/vendor/` is never edited to change an outcome**, and
**`case_state.json` stays the engine's verbatim contract** — new information goes
in new artifacts, never by forking the CaseState.

### CW-1 — Attachment awareness (honesty gap, ship first) — **SHIPPED v0.16.0**

*Problem.* An attached drawing or spec sheet is silently invisible. Under the
project's own stopping rule — *no finding would give a customer a wrong answer* —
this qualifies: the reviewer is shown a complete-looking case that omits the
document the customer considered the answer.

*Kit side, as built.* `scripts/attachments.py` inspects the `.eml` for parts
carrying a filename or an `attachment` disposition and records
`{filename, content_type, disposition, bytes}` under `evidence_not_read` in
**`run_manifest.json`** (not `state.json`, as this section originally proposed —
the manifest is the run record, and putting it there means Body can route on it
without parsing prose). `render_reply.py` derives the same list independently and
renders an **EVIDENCE NOT READ** block naming each file. It never guesses at
content and never adds an open item — the engine owns `open_items[]`. Since
v0.17.0 an unread attachment also forces `outcome: needs_human_input` (REQ-097).

*Upstream.* The correct long-term home is an `ATTACHMENT_NOT_READ` open item in
`ScaleUpLabs/McGill-Core`, exactly alongside `HTML_SOURCE_REVIEW` and
`HIDDEN_CONTENT_DETECTED`, which already exist for "I saw something I could not
safely read". The kit-side block is the interim.

*Verification.* A fixture `.eml` with a PDF part. Mutation: delete the block and
the check must fail. Round-33's lesson applies — the check must reference the
filename, not a substring that appears elsewhere on the page.

### CW-2 — Run manifest (`_report/run_manifest.json`) — **SHIPPED v0.16.0**

*Problem.* The document requires Body to "record which skill version produced
each proposal and correction", and a contract that is "versioned and idempotent".
The CaseState carries `schema_version` and nothing else: no kit version, no
engine commit, no input identity.

*Design.* A new artifact, declared in `run_state.ARTIFACTS` so invalidation picks
it up for free: kit name and version, engine source commit read from
`vendor/PROVENANCE.md`, `case_state` schema version, sha256 of the input,
the invocation record, engine exit code, wall time, and UTC timestamps.
`case_state.json` is untouched.

*Why it matters beyond bookkeeping.* `sha256(input) + invocation` is a natural
idempotency key: Body can recognise a retry of the same case without inventing
one, which is exactly the duplicate-suppression the contract section asks for.

### CW-3 — Explicit outcome, not an exit code — **SHIPPED v0.16.0, extended v0.17.0**

*Problem.* "Compute can report progress, request human input, propose a result,
complete or fail." The kit's boundary says 0 or 1, and the engine's `2` means
*draft produced, has open items* — a distinction `CLAUDE.md` has to spend a whole
bullet warning people not to read as failure. "Needs human input" is currently
implicit, buried inside the JSON.

*Design.* The manifest carries `outcome ∈ {complete, needs_human_input}`,
**derived** from what the run produced, never asserted independently. Derived,
because an independently-set flag is a second copy that can drift, which is
failure shape #1 of this campaign. `failed` is deliberately NOT in the
vocabulary: a failed run writes no manifest and the wrapper exits 1, so absence
is the failure signal and cannot be faked by a half-written record.

Two grounds force `needs_human_input`: a `blocking` open item, and **an
attachment the engine never read** (v0.17.0, REQ-097). The second was the
question v0.16.0 left open and the operator closed on 2026-09-17: an RFQ saying
"dimensions are on the attached drawing" was reporting `complete`, because the
engine's asks were all `confirm` and the drawing was invisible to it. The engine
cannot raise an item about a file it cannot see, so the outcome carries it. An
inline signature image does not force it — routing every footer logo to a human
is how a signal becomes noise.

### CW-4 — Split the audiences: `review_request.md` and `reply.md` — **SHIPPED v0.18.0**

*Problem.* The document splits one message into two: Inside Sales receives a
review request (summary, uncertainty, proposed response, and the decision to
make); Outside Sales receives the guidance once approved. The kit emits a single
document that tries to be both.

*Design.* `render_reply.py` grows a second projection, `_report/review_request.md`:
what the engine understood, **what it is uncertain about and why** (the
`reading` / `assumed` / `conflict` fields and the blocking items, stated as
uncertainty rather than as a list), the proposed response, and the decision —
approve / edit / reject / reassign / escalate. `reply.md` stays what gets sent
after approval.

*Constraint, and how it was met.* The proposal said "neither may contain a fact
the other lacks, proved by a completeness check over both". As built it is
stronger and simpler: the review request **embeds the reply verbatim**, so it is
a superset by construction and no completeness check is needed to prove it. The
check that matters instead is that the embedded bytes are THIS case's reply —
`render_reply.render` is re-run and compared, so a stale reply cannot be
approved.

### CW-5 — Resolvable owners (`config/routing.json`) — **SHIPPED v0.18.0**

*Problem.* `routing.recommendation` is one of three roles and `open_items[].route`
one of four; `checkpoints[].owner` is free text. Body cannot address a Teams
message to `inside_sales`.

*Design.* A kit-side directory mapping role and checkpoint-owner keys to an
addressee key (Teams group id or mailbox), **consulted, never invented**. An
owner with no mapping renders as explicitly *unrouted* rather than defaulting to
inside sales — a wrong assignee is worse than a visible gap. The kit stays
offline: it emits the key, Body resolves the address.

### CW-6 — Answers given outside the thread

*Problem.* The reviewer answers "it's 316 stainless" in Teams. That text never
enters the email thread, so the next run re-asks. The document's Evolution 2
requires that Coworker "understands later answers", and today it only does so
for answers that arrive as email text.

*Design — and this is the careful one.* Do **not** add a resolution path: the kit
may never answer an open item, and a second way for a value to enter the case is
a second way to be wrong. Instead, Body supplies the answer as an **operator
addendum appended to the case text**, and the engine reads it exactly as it reads
a later message in the thread — the `supersedes` machinery that already exists,
no new trust, no new code path in the engine.

*The risk to verify, stated up front:* this makes an operator's assertion
indistinguishable from the customer's in the extracted text. The addendum must
therefore be attributed in the rendered output (*answered by X, 2026-09-17,
not by the customer*), and the manifest must record that the input was
augmented. A reviewer must never read an operator's guess as a customer's
statement. This is the feature most likely to fail a verification round, and it
should get one of its own.

### CW-7 — Correction record (`schemas/correction.schema.json`)

*Problem.* Evolution 3 needs Factory to turn an approved correction into a test
or a proposed change. Nothing defines what a correction *is*.

*Design.* The kit defines the shape, because the kit owns what a case is:
the original proposal, the correction, the reason, the final response, the
reviewer, and — via CW-2's manifest — the input sha and skill version it applies
to. That last part is what makes a correction **replayable as a fixture**: a
correction that cannot be pinned to an input and a version cannot become a test.
The kit does not collect corrections (Body does); it defines the contract and can
consume one as a regression fixture. This is the direct answer to *"reviewed
corrections may become test cases, but never alter production behaviour
automatically."*

### CW-8 — Knowledge freshness (upstream)

Evolution 4 requires "each value includes its source and freshness". Today
`knowledge.lookups[]` logs op, argument, outcome, tier, citation and elapsed ms,
and `revision` pins the snapshot — there is no per-value freshness. Today this
costs nothing because `knowledge.source == "none"` on every run. The moment
FOLLOW-UP-1 wires the live graph, the document's promise is unmet. Raise against
`ScaleUpLabs/McGill-Core`; `knowledge.py` is vendored and must not be edited here.

---

## 5. What is not a kit feature

* Mailbox connection, the case store, Teams delivery, approval policy, audit,
  the admin panel, assignment and escalation — **Body**, per the document's own
  split, and the kit should not grow any of them.
* Grounded selection still needs the P21 item master and the ContiTech catalog
  (FOLLOW-UP-3). Evolution 4's "product identification, pricing and availability"
  is blocked on McGill supplying those, not on kit work.

---

## 6. Suggested order

**Status 2026-09-17: CW-1 through CW-5 are shipped.** CW-4 and CW-5 in v0.18.0
(REQ-098, REQ-099) — 13 further mutations, 12 caught, and the one survivor is a
defence-in-depth guard documented as non-observable rather than given a check
that passes for the wrong reason. Remaining: CW-6 (out-of-band answers), CW-7
(correction record), CW-8 (knowledge freshness, upstream).

**Earlier: CW-1, CW-2 and CW-3 are shipped** — v0.16.0 (REQ-092..REQ-096)
and v0.17.0 (REQ-097, the unread-attachment outcome), each mutation-proved: 16
mutations, 16 caught, 0 survivors. Adding the manifest to the invalidation loop
also surfaced REQ-096, a real stale-CaseState defect on the redirected-`--out`
path. CW-4 onwards are unbuilt.


1. **CW-1** — it is an honesty gap in shipped behaviour, and it is small.
2. **CW-2 + CW-3** — one artifact, and they unblock Body's side of the contract.
3. **CW-4** — the visible half of Evolution 2.
4. **CW-5**, then **CW-7**.
5. **CW-6** last, with its own verification round.

CW-1 through CW-3 are a v0.16.0. CW-4 and CW-5 are Evolution 2's minimum.
