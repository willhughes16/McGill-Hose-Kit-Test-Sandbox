# McGill Email to BOM — Kit Instructions

Read an inbound customer RFQ email and produce a deterministic CaseState plus a
draft bill of materials, with every missing, ambiguous or unsafe item raised as an
explicit open item. Drafts only — a human reviews and commits in the ERP.

## Mission

This kit turns one inbound RFQ email into a complete, structured picture of the
case: every field with a status and the evidence behind it, every missing or
unsafe item as a machine-readable open item, the request classified, and a routing
recommendation. It exists so an inside-sales rep — or a conversational layer
running the customer dialogue — never has to guess what the customer asked for and
never re-asks something already answered. The deterministic engine doing the work
is vendored verbatim under `vendor/`; the kit wraps it, it does not reimplement it.
The reply carries **no attachment**: the whole case goes in the message body, so
`_report/reply.md` is what you send. `_report/case_state.json` remains the
machine-readable contract on disk for a conversation layer to consume, and
`_report/run_manifest.json` records who produced it and whether it needs a human.

One thing the engine does NOT do is read what the customer attached. It sees
"Subject + best body part" and nothing else, so an RFQ whose dimensions are in
the attached drawing yields a case that correctly reports them missing and knows
nothing about the drawing. The kit therefore names every attached file it finds,
in the reply and in the manifest, without opening any of them.

## How to run

1. Read `recipes/mcgill-email-to-bom.yaml` — it is the execution contract. Execute its
   phases **in order** — `prepare` → `extract_case` → `generate_report`. Each
   phase's `goal`, `constraints`, `input` and `output` are binding.
2. Stay in the current working directory. All runtime output goes under
   `_report/` — never scatter files elsewhere.
3. Track progress in `_report/state.json` so an interrupted run can resume.
4. Deliverables are produced by the kit's scripts (`scripts/run_engine.py`,
   `generate_report.py`, `scripts/render_reply.py`) — if a script fails, debug and
   fix it; do NOT create the artifact by hand.
5. **Write the run's arguments down once.** The prepare phase records an
   `invocation` object in `_report/state.json`; phases 1 and 2 read it
   (`--from-state`) rather than having you re-type the flags. Re-typing them is how
   a run ends up with two self-consistent artifacts that are both wrong about what
   the customer asked for.

## Arguments

`$ARGUMENTS` must contain the **path to one RFQ email** (`.eml` or `.txt`).
Optional: `--component-ids A B ...` for Component IDs an operator has already
confirmed, and `--coc` when the customer requires a Certificate of Conformance.
`--config-dir DIR` selects an alternate rules/catalog directory — e.g. one backed
by the ERP item master, which is the supported route to grounded selection. It IS
passed through to the engine.

If no RFQ path is given, print usage and STOP. If the path does not exist, print
the path you tried and STOP — never guess at another file and never invent email
content.

## What this kit must never do

These are not style preferences. The engine is built so that being silently wrong
is structurally impossible, and the surrounding narration has to hold the same
line:

- **Never answer, drop, reword or re-prioritize an open item.** Report them
  faithfully, highest priority first. They are the whole point of the output.
- **Never invent a part number, price, lead time or stock position.** The engine
  produces none of these. Pricing and stock questions are acknowledged and routed
  to a human.
- **Never present the output as a quote, a confirmed BOM, or an order.** It is a
  draft. A human commits it in the ERP.
- **Never treat exit code 2 as a failure.** It means "a draft was produced and it
  has open items" — the normal outcome for essentially every real RFQ. Only the
  wrapper scripts' own non-zero exits are failures.
- **Never report a `reading` or `assumed` field as confirmed.** `reading` means the
  engine saw a value and deliberately refused to commit to it (ambiguous units).
  Say it needs confirming.
- **Never edit `vendor/`** to change an outcome. It is a stamped verbatim copy; see
  `vendor/PROVENANCE.md` before touching it.
- **Never bypass a reconciliation failure.** `generate_report.py` AND
  `render_reply.py` both re-derive the CaseState and refuse if it differs. If
  either refuses, re-run the extract phase. Do NOT pass `--no-reconcile` to
  either one and do NOT write the artifact by hand — the refusal is the safety
  net doing its job, and for the reply it is the only thing standing between an
  operator and a confident document describing a different case.
- **Never attach a file to the reply.** The kit declares no `email_attachment`:
  the case goes in the body. Attaching `case_state.json` would send an operator to
  read JSON for information the reply already states in words.
- **Never summarise `reply.md` down.** It is already the summary, and every line in
  it is something the engine refused to assume. Send it, or frame it lightly.
- **Never open, read or summarise an attachment.** The engine reads the message
  TEXT only — there is no attachment handling in it at all. The kit NAMES the
  files the customer sent (EVIDENCE NOT READ in the reply, `evidence_not_read` in
  the run manifest) and stops there. Reading one yourself would put case data
  into the answer from outside the engine, with none of its guarantees, and every
  open item below it was derived without that file. Tell the operator to open it.
- **Never read `outcome: complete` as "ready to send".** It means only that
  nothing BLOCKS a quote. Every case this kit produces is a draft a human
  reviews; `complete` versus `needs_human_input` is a routing distinction, not an
  approval.
- **Never treat a missing artifact as equivalent to a stale one.** The scripts delete
  a previous run's artifacts before doing anything that can fail, on purpose: no
  artifact is an honest error, a leftover one is a silent wrong answer.

## Deliverables

| Path | Role |
|---|---|
| `_report/reply.md` | **What you send, as the message body.** The whole case inline: request class and urgency, open items grouped by priority (with a `route` on the items that carry one — it is optional and most do not), every field with its status and evidence, the draft BOM, harness-held checkpoints, corrections found in the thread, and knowledge provenance. |
| `_report/case_state.json` | The machine contract a conversation layer consumes. Conforms to `schemas/case_state.schema.json`. **Not attached** — cite it, do not send it. |
| `_report/bom_draft.md` | The engine's own verbatim rendering, byte-identical to what the source engine prints. A **lossy** view kept for parity, not for sending. |
| `_report/run_manifest.json` | **The run record** a conversation layer reads: which kit version and which engine commit produced this case, the input's sha256 and an `idempotency_key` derived from it, the `outcome` (`complete` / `needs_human_input`), and `evidence_not_read` — the files the customer attached that the engine never opened. Written by the extract phase. |
| `_report/state.json` | The run's `invocation` record (written by prepare, read by the later phases) plus the extract result. Not a deliverable. |

## Reference material

- `schemas/case_state.schema.json` — the CaseState contract: the full open-item
  code vocabulary, the request classes, and the field status/kind/route enums.
  Consult it whenever you need to know what a code means or what values are legal.
- `vendor/` — the vendored engine and its `config/` (all domain vocabulary lives in
  `config/rules.json`). Read-only. `vendor/PROVENANCE.md` records the exact source
  commit and how to refresh it.
- `vendor/config/citations.json` — maps each rule id to the McGill work instruction
  or test-report item it came from, so any behaviour can be traced to its source.
