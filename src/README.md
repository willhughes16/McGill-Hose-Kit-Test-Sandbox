# McGill Email to BOM

Turn an inbound customer RFQ email into a deterministic **CaseState** and a **draft
bill of materials**, with every missing, ambiguous or unsafe item raised as an
explicit open item.

It **drafts only**. A human reviews and commits in the ERP, and the engine
structurally cannot do otherwise — the checkpoints that would send a quote or sign
off on QC are harness-held and absent from its toolset.

## What it does

Given one `.eml` or `.txt` RFQ, it produces:

- **`_report/case_state.json`** — the contract. Every field with a status
  (`captured` / `reading` / `assumed` / `missing` / `conflict` / …) and the evidence
  behind it; every open item with a stable `code`, an `ask`, a `priority` and a
  `route`; the request classified (`hose_assembly`, `bulk_hose`, `component_rfq`,
  `order`, `stocking_lead`, `out_of_scope`); a routing recommendation; and
  knowledge provenance.
- **`_report/bom_draft.md`** — the readable draft: BOM table, harness-held
  checkpoints, operator questions, open items.

Two consumers, one contract: a person can read the draft, and a conversational
layer can consume the same CaseState to run the customer dialogue without guessing
or re-asking.

## Usage

As an Astro kit, you ask Astro for it and pass the RFQ plus any flags as the
kit's arguments — Astro executes `recipes/mcgill-email-to-bom.yaml`:

```
rfq.eml
rfq.eml --component-ids "OPW 633C A" "SPS400452"
rfq.eml --coc
rfq.eml --config-dir /path/to/erp-backed-config
```

To run it directly instead, the kit ships no console script — invoke the two
phase scripts with `python3` (no install, no dependencies):

```
python3 scripts/run_engine.py --in rfq.eml --out _report/case_state.json --state _report/state.json
python3 generate_report.py --out _report/bom_draft.md --state _report/state.json
```

The second command needs no flags: phase 1 records the whole invocation in
`_report/state.json` and phase 2 replays it.

See `EXAMPLES.md` for the full argument reference and worked examples.

## The design line

Everything about this engine points the same way: **it is better to ask than to be
quietly wrong.**

- Ambiguous units never capture. A bare `bar` or a bare `F` becomes a `reading`
  with a confirm ask — not a value.
- A bare `4in` is not read as a size, because it could be ID or OD. `4 in ID` is.
- Nothing is ever deleted from an email because of styling; HTML-derived drafts
  carry a provenance marker instead, so no hidden value can pass unflagged.
- No part number, price, lead time or stock position is ever invented. Pricing and
  stock questions are acknowledged and routed to a human.
- Exit code **2** — "a draft with open items" — is the normal outcome. Exit 0 is
  reserved and in practice unreachable. Treating 2 as an error upstream is a bug.

## What is inside

| Path | Role |
|---|---|
| `recipes/mcgill-email-to-bom.yaml` | The execution contract: `prepare` → `extract_case` → `generate_report`. |
| `scripts/run_engine.py` | Thin wrapper: runs the vendored engine, writes the CaseState verbatim. |
| `generate_report.py` | Thin wrapper: writes the human-readable draft verbatim. |
| `schemas/case_state.schema.json` | The CaseState contract, including the full open-item code vocabulary. |
| `vendor/` | The engine, **vendored verbatim** — see `vendor/PROVENANCE.md`. |

The wrappers call the engine's own entry point rather than re-expressing any of its
logic. That is deliberate: the engine carries 507 tests and 24 rounds of blind
adversarial verification, and a second expression of those rules is a copy that can
drift. Parity with the source is proven by
`tools/parity_check.py` against captured real outputs, not asserted.

## Limits worth knowing

- **Selection is not grounded.** Without an item master the engine will not choose
  a hose or fitting for you; it raises `SELECTION_UNRESOLVED` and asks an operator.
  Supply confirmed IDs with `--component-ids`, or point `--config-dir` at a catalog
  backed by the ERP item master.
- **No graph or network access.** The vendored engine ships offline: knowledge
  source is `none`. The live-knowledge adapter exists in `vendor/` but is dormant
  and not wired into this kit — see the deferred follow-ups in the project notes.
- **One email per run.**
