# mcgill-email-to-bom — Examples

## Quick Start

Ask Astro for the kit with the RFQ as its argument:

```
rfq.eml
```

Reads one RFQ email and produces `_report/case_state.json` (the machine contract,
attached to email replies) plus `_report/bom_draft.md` (the readable draft).

Directly, without Astro (the kit ships no console script):

```
python3 scripts/run_engine.py --in rfq.eml --out _report/case_state.json --state _report/state.json
python3 generate_report.py --out _report/bom_draft.md --state _report/state.json
```

## Examples

### 1. Quote an inbound RFQ

**Prompt:** "Draft a BOM for the attached RFQ."

**Arguments:** `rfq.eml`

**Expected workflow:**
1. `prepare` — resolves `rfq.eml`, writes `_report/state.json`.
2. `extract_case` — `scripts/run_engine.py` writes `_report/case_state.json`.
   The engine exits 2 (a draft with open items — the normal outcome).
3. `generate_report` — `generate_report.py` writes `_report/bom_draft.md`, then
   the request is summarised: what was understood, what must be answered, where
   to route it.

**Produces:** `_report/case_state.json`, `_report/bom_draft.md`

For the shipped sample (a 4in EPDM suction hose assembly, couplers named but no
size/temperature stated) the engine classifies it `hose_assembly`, drafts no BOM
lines because no selection rule is grounded, raises 2 harness-held checkpoints
and 6 open items — `MATERIAL_CONFIRM`, `VACUUM_VALUE_CONFIRM`,
`TEMPERATURE_MISSING`, `SIZE_MISSING`, `LENGTH_TYPE_MISSING`,
`SELECTION_UNRESOLVED`.

### 2. Draft with Component IDs an operator already confirmed

**Prompt:** "The operator confirmed these part numbers — draft the BOM."

**Arguments:** `rfq.eml --component-ids "OPW 633C A" "OPW 633E A" "SPS400452" "HOS-064 300 EPDM"`

**Expected workflow:** as above, but the confirmed IDs are matched against the
catalog and become real BOM lines. `SELECTION_UNRESOLVED` disappears (a human has
made the selection) and the catalog checkpoint closes. IDs that do not match the
catalog become blocking asks rather than silently vanishing.

**Produces:** `_report/case_state.json` with 4 populated BOM lines,
`_report/bom_draft.md` with the rendered table. 5 open items remain — the
engine still will not assume a size, temperature or length convention.

### 3. RFQ requiring a Certificate of Conformance

**Prompt:** "This customer needs a C of C — draft the BOM."

**Arguments:** `rfq.eml --coc`

**Expected workflow:** as example 1, plus the Certificate-of-Conformance line and
the Certs class. (The engine also detects a C-of-C request from the email text
itself, so the flag is a belt-and-braces override, not the only route.)

**Produces:** `_report/case_state.json`, `_report/bom_draft.md`, both including
the C-of-C line.

### 4. A request that is not a hose assembly

**Prompt:** "What does this email need?"

**Arguments:** `component_request.eml` (e.g. "need 12 camlock gaskets")

**Expected workflow:** `extract_case` classifies the request — one of
`hose_assembly`, `bulk_hose`, `component_rfq`, `order`, `stocking_lead`,
`out_of_scope` — and only the fields belonging to that class are asked about. A
gasket order is **not** pushed through hose-assembly questions like length
convention or hose selection.

**Produces:** `_report/case_state.json` with `request_class` set and a routing
recommendation; `_report/bom_draft.md`.

### 5. A message that is not a request at all

**Prompt:** "What does this email need?"

**Arguments:** `newsletter.eml` (e.g. a bulk mailing, an auto-reply, a delivery-status
bounce, an invoice/statement, a bare "thanks, got it.", or internal chatter)

**Expected workflow:**
1. `prepare` — resolves `newsletter.eml`, writes `_report/state.json`.
2. `screen_input` — `scripts/filter_gate.py` decides BEFORE the engine runs,
   without invoking it, and exits `3`: nothing to quote. **The run STOPS
   here.** Read the `filter` record `screen_input` wrote into
   `_report/state.json` and report its `code` (one of
   `DELIVERY_STATUS_NOTIFICATION`, `AUTO_REPLY`, `BULK_MAILING`,
   `INVOICE_OR_STATEMENT`, `BARE_ACKNOWLEDGEMENT`, `INTERNAL_CHATTER`), its
   `route` and the `input` path, in plain language. Mention `--no-filter` as
   the override if the requester believes this is a false positive.
3. `extract_case` and `generate_report` never run.

**Produces:** nothing new under `_report/` beyond `state.json`'s `filter`
record — no `_report/case_state.json`, no `_report/bom_draft.md`. If a
previous run's artifacts existed in this directory, they are gone too (a
filtered run is never left sitting beside a stale draft).

## Argument Reference

| Argument | Type | Default | Description |
|---|---|---|---|
| RFQ path | path (positional, required) | — | The inbound email to read: `.eml` (MIME, quoted-printable/base64, HTML) or `.txt`. Read as raw bytes. |
| `--component-ids` | list of strings | none | Component IDs an operator has already confirmed. Matched case-insensitively against the catalog; hits become BOM lines, misses become blocking asks. Also forces `hose_assembly` classification. |
| `--coc` | flag | off | The customer requires a Certificate of Conformance. |
| `--config-dir` | path | shipped `vendor/config/` | An alternate rules/catalog/citations directory — e.g. one backed by the P21 item master. |
| `--no-filter` | flag | off | Force the input filter (`screen_input`, `scripts/filter_gate.py`) to pass this message through to the engine regardless of its own decision — the documented escape hatch for a false positive. Never edit the message or kit source to get past the gate; use this flag. |

## Common Patterns

- **Exit code 2 is success.** The engine returns 2 whenever a draft has open
  items, which is essentially every real RFQ. Treat 2 as "draft produced, human
  input needed". Only the wrapper scripts' own non-zero exit is a failure. Exit 0
  is reserved and in practice unreachable.
- **`case_state.json` is the contract; `bom_draft.md` is a view.** The rendering
  drops `fields`, `routing`, `knowledge` and `supersedes`, and keeps only the code
  and ask from each open item. Anything programmatic must read the JSON — which is
  why the JSON is the email attachment.
- **`reading` ≠ captured.** A field with status `reading` means the engine saw a
  value but refuses to commit to it (ambiguous units like bare `bar`, or a bare
  `F`/`C`). It must be confirmed, never assumed. Same for `assumed`.
- **It never assumes a size from a bare dimension.** `4 in ID` captures; a bare
  `4in` or `4"` does not, because it could be ID or OD — the engine asks instead.
  This is the deliberate fail-safe direction, not a gap.
- **Every open item has a stable `code`.** Route and template on the code, not on
  the English text of the ask — the wording may change, the codes are the
  contract (`schemas/case_state.schema.json`).
- **It drafts, it does not quote.** No prices, lead times or stock positions are
  ever produced. Stock and pricing questions are acknowledged and routed to a
  human. Do not present the output as a quote.
- **One email per run.** Point it at a single RFQ; run it again for the next one.
- **Large threads are slow, and a run costs three engine passes.** A single pass
  is ~0.1 s at 8 KB, ~5 s at 134 KB, ~80 s at 538 KB — superlinear past roughly
  100 KB. A full kit run makes **three** passes (one in `extract_case`; two in
  `generate_report`, which re-derives the CaseState to reconcile before
  rendering), so budget roughly **3x** those figures: ~4 minutes end to end at
  538 KB, not 80 s. Both scripts warn on stderr above 100 KB. The per-pass cost is
  inherited from the engine and truncating input would be worse than being slow,
  so trim quoted history if you need speed.
- **Two schema values the engine cannot emit.** `schemas/case_state.schema.json`
  declares `status: "superseded"` and `knowledge.lookups[].op: "ratings_for"`, and
  neither is reachable: supersede results appear as a top-level `supersedes` array
  plus `superseded_from` inside the field, and `ratings_for()` records the
  `resolve_component` op. Do not build a branch for either. The schema is kept
  byte-identical to the source's contract rather than corrected here, so the fix
  belongs upstream.
- **The filter gate runs before the engine and has its own exit codes — `3`
  is not an error.** `scripts/filter_gate.py` (phase `screen_input`) exits
  `0` (not filtered — continue), `3` (filtered — nothing to quote, STOP the
  run) or `1` (the gate's own failure: bad usage, unreadable input,
  unwritable state). The gate never emits the engine's own `2`; treat `3`
  the same way you treat the engine's `2` — a normal, expected outcome, not
  a failure.
- **The filter fails toward running the engine.** Everything the gate cannot
  resolve confidently — no text obtained, a parse defect, an HTML-only body
  over its scan budget, an unrecognised or undecodable part, an undeclared
  code/route, unreadable reference data — resolves to *not filtered*, so a
  real RFQ is never silently dropped for being ambiguous. Only a hard input
  error (the path itself missing or unreadable) is loud and stops the run.
- **Direct, without Astro, the documented sequence runs the gate first.**
  ```
  python3 scripts/filter_gate.py --in rfq.eml --state _report/state.json
  ```
  Exit `0` → continue with `run_engine.py` then `generate_report.py` as in
  Quick Start. Exit `3` → stop; nothing else runs. Pass `--no-filter` on the
  `filter_gate.py` command to force pass-through for a message you know is a
  real request.
- **Multi-kit workflows:** feed `case_state.json` to a conversation layer to run
  the customer dialogue (it is designed for exactly that — every open item carries
  a priority and a route), and keep the raw JSON with the case record for audit.
