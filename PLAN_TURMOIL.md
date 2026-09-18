# Plan — the Turmoil PO run, and what it exposed

Written 2026-09-18 after job `af54e714` on kit v0.21.0. Operator decisions
recorded at the end; they shape every phase.

## What went wrong, in severity order

### 1. The kit invented a product that nobody ordered — BLOCKING

PO 24156 is a twenty-line purchase order: barb fittings, bushings, nipples, a
tee, elbows, adapters, hose clamps, and **one** hose. The engine reduced it to a
single `hose_assembly` and built its spec by mixing line items:

| Field | Value | Where it actually came from |
|---|---|---|
| `size` | `3/4 ID` | the HOSE line |
| `pressure` | `300 psi` | the HOSE line |
| `length` | `1` | `BARB FITTING, **1"** MNPT` — a THREAD SIZE |
| `end_1`, `end_2` | barb | the barb fittings |

`class_evidence` is the single word `hose`. Reproduced locally on a seven-line
excerpt; the merge is deterministic and repeats.

The kit then asked the customer to confirm the **quantity**, **length
convention**, **material** and **temperature** of that assembly — for an order
whose every line already carries a part number, a quantity and a price, and whose
only actual request was *"please acknowledge and provide best ship date"*.

Under the operator's stopping rule — ship when no finding would give a customer a
wrong answer — this blocks. It is the sharpest wrong answer the campaign has
produced, because the case is not merely incomplete: **the specification it
describes exists in no document.**

The engine has never been wrong here in 37 rounds because every fixture is one
request per text. The assumption was invisible until a real multi-item document
arrived.

### 2. `reply.md` is not a sendable email (CW-9, mine, v0.21.0)

9,004 bytes, opening with the entire two-page PO transcript — addresses, fax
numbers, account numbers, unit prices — before anything a reader needs. The
questions are below all of it. The executing agent responded exactly as anyone
would: it ignored the artifact and hand-wrote its own email (step 33), violating
the kit's own instruction to send `reply.md` and not summarise it down.

When the deliverable is unusable, the rule protecting it gets broken. That is a
design failure, not an operator failure.

### 3. The open items are addressed to an operator, not a customer

> `MATERIAL_CONFIRM` — "Operator: confirm the exact material of every component
> and whether CMTR/QC material verification (WI-031) applies before fabrication."

That is an internal instruction citing an internal work instruction. It cannot go
to Rachel as written, and `reply.md` is documented as "what you send".

### 4. Nothing rides with the reviewer's message

Inside Sales is asked to check a machine transcript against a document they have
not been given.

---

## The plan

### Phase 1 — Stop the wrong answer (kit, days)

Detect a multi-item document — repeated rows carrying a part number, a quantity
and a price — and refuse to present a merged single specification. The reply and
the review request say: *this document contains N line items; the engine built
ONE specification from across them and it may describe no real product.* Every
field derived that way is marked, exactly as transcribed fields already are.

This does not make a PO properly assessable. It stops the kit stating an invented
spec as fact while phase 4 is built, and it is the only phase that protects a
customer this week.

### Phase 2 — Make the reply sendable (kit, hours)

The full transcript moves to `review_request.md` only. `reply.md` names the file,
says a machine read it, and gets on with the questions. The transcript stays on
disk as its own artifact for anyone comparing it against the original.

### Phase 3 — Customer questions, with the reviewer approving the wording (kit, days)

`reply.md` becomes customer-facing: each open item is rendered as a question a
customer can answer, in their language, without internal rule ids.

**This is rewording an open item, which the kit currently forbids outright.** The
guarantee is preserved where it bites: `review_request.md` shows the engine's
EXACT ask beside the proposed customer wording, and the reviewer approves the
translation rather than inheriting it. A translation that drops an ask, or
changes what is being asked, is a defect and gets its own checks — one per open
item code, so a code whose translation is missing fails the suite rather than
silently sending the operator text.

### Phase 4 — Per-line-item extraction (McGill-Core, weeks)

The real fix, and the operator's choice. Today the engine is one text → one case:
one `fields{}`, one `request_class`, one BOM. A document with twenty line items
needs twenty.

Segmentation belongs in the ENGINE, not the kit: splitting a document is
extraction, and doing it kit-side would be a second source of case data outside
the engine with none of its guarantees — the thing this project exists to
prevent.

That means:

* a segmentation step in the engine that splits a document into line items;
* a per-item dimension in the CaseState — a contract change affecting every
  consumer, including the kit's schema, the renderers and every parity fixture;
* a corpus of REAL purchase orders to test against, which the project does not
  have (FOLLOW-UP-6 already records the fixture corpus as thin and partly
  synthetic — four distinct inputs);
* re-vendor, re-parity, and a verification round of its own.

Phases 1–3 are independent of this and should not wait for it.

### Phase 5 — Source files ride with the reviewer's message (kit + Body)

The kit does not send email; Body does. So the kit DECLARES what should be
attached to which message, and Body attaches it:

* the **customer reply** carries nothing — unchanged, and still the operator's
  standing decision;
* the **review request** declares the customer's original files (the PDF, the
  drawing) so Inside Sales can check the transcript against the source.

**This changes an invariant every acceptance bar has asserted:** "**zero**
`email_attachment` tags". It becomes "zero on the customer reply; the review
request declares the source files". That must be changed deliberately in
`CLAUDE.md`, the recipe and the next bar, not quietly.

---

## Decisions taken by the operator, 2026-09-18

1. **`reply.md` is for the CUSTOMER, in their words.** → phase 3.
2. **Multi-item documents get per-line-item extraction.** → phase 4, with phase 1
   as the interim guard.
3. **The transcript belongs in the review request only.** → phase 2.
4. **The reviewer's message carries the source files; the customer's carries
   nothing.** → phase 5.

## What I would do first

Phase 1, then 2, then 5 — they are days of work between them and they remove a
live wrong answer, an unusable deliverable, and a reviewer checking a transcript
blind. Phase 3 next. Phase 4 is a project and needs a real PO corpus before a
line of it is written.
