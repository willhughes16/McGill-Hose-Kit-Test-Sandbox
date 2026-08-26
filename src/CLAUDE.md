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
The final deliverable is `_report/case_state.json`, the integration contract, with
`_report/bom_draft.md` as the readable companion.

## How to run

1. Read `recipes/email-to-bom.yaml` — it is the execution contract. Execute its
   phases **in order**; each phase's `goal`, `constraints`, `input`, and `output`
   are binding.
2. Stay in the current working directory. All runtime output goes under
   `_report/` — never scatter files elsewhere.
3. Track progress in `_report/state.json` so an interrupted run can resume.
4. Deliverables are produced by the kit's scripts (`scripts/run_engine.py`,
   `generate_report.py`) — if a script fails, debug and fix it; do NOT create the
   artifact by hand.

## Arguments

`$ARGUMENTS` must contain the **path to one RFQ email** (`.eml` or `.txt`).
Optional: `--component-ids A B ...` for Component IDs an operator has already
confirmed, and `--coc` when the customer requires a Certificate of Conformance.
`--config-dir` selects an alternate rules/catalog directory.

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

## Deliverables

| Path | Role |
|---|---|
| `_report/case_state.json` | **The email attachment.** The machine contract: fields with statuses and evidence, open items with codes/priorities/routes, request class, routing, knowledge provenance. Conforms to `schemas/case_state.schema.json`. |
| `_report/bom_draft.md` | Readable draft: BOM table, harness-held checkpoints, operator questions, open items. A **lossy** view of the CaseState — cite the JSON as authoritative. |
| `_report/state.json` | Run state for resumability. Not a deliverable. |

## Reference material

- `schemas/case_state.schema.json` — the CaseState contract: the full open-item
  code vocabulary, the request classes, and the field status/kind/route enums.
  Consult it whenever you need to know what a code means or what values are legal.
- `vendor/` — the vendored engine and its `config/` (all domain vocabulary lives in
  `config/rules.json`). Read-only. `vendor/PROVENANCE.md` records the exact source
  commit and how to refresh it.
- `vendor/config/citations.json` — maps each rule id to the McGill work instruction
  or test-report item it came from, so any behaviour can be traced to its source.
