# mcgill-email-to-bom — Examples

## Quick Start

Ask Astro for the kit with the RFQ as its argument:

```
rfq.eml
```

Reads one RFQ email and produces `_report/case_state.json` (the machine contract,
not attached — the reply carries the case inline) plus `_report/bom_draft.md` (the readable draft).

Directly, without Astro (the kit ships no console script):

```
python3 scripts/prepare_input.py --body body.html --attachments-dir input/ --state _report/state.json
python3 scripts/run_engine.py --from-state --out _report/case_state.json --state _report/state.json
python3 generate_report.py --out _report/bom_draft.md --state _report/state.json
python3 scripts/render_reply.py --out _report/reply.md --state _report/state.json
python3 scripts/render_review.py --out _report/review_request.md --state _report/state.json
```

## Examples

### 1. Quote an inbound RFQ

**Prompt:** "Draft a BOM for the attached RFQ."

**Arguments:** `rfq.eml`

**Expected workflow:**
1. `prepare` — resolves `rfq.eml`, writes `_report/state.json`.
2. `extract_case` — `scripts/run_engine.py` writes `_report/case_state.json`
   and `_report/run_manifest.json`. The engine exits 2 (a draft with open items
   — the normal outcome); the manifest states that in words as
   `outcome: needs_human_input` or `complete`.
3. `generate_report` — `generate_report.py` writes `_report/bom_draft.md`, then
   the request is summarised: what was understood, what must be answered, where
   to route it.

**Produces:** `_report/review_request.md` (what the reviewer reads), `_report/reply.md` (what is sent once they approve), `_report/case_state.json`, `_report/bom_draft.md`, `_report/run_manifest.json`

For the shipped sample (a 4in EPDM suction hose assembly, couplers named but no
length or temperature stated) the engine classifies it `hose_assembly`, captures
the size as `4 ID`, drafts no BOM lines because no selection rule is grounded,
raises 2 harness-held checkpoints and 5 open items — `MATERIAL_CONFIRM`,
`VACUUM_VALUE_CONFIRM`, `TEMPERATURE_MISSING`, `LENGTH_MISSING`,
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

**Arguments:** `newsletter.eml` (a bulk mailing, an auto-reply, a bounce, an
invoice, a bare "thanks, got it.", internal chatter)

**Expected workflow:** the kit does not pre-judge whether a message deserves a
quote — it reads the whole thing and lets the engine classify it. All three phases
run normally. The engine returns `request_class: out_of_scope` with a single
`ROUTED_ACKNOWLEDGE` open item, and the reply says plainly that there is nothing
to quote and where the message should go instead.

**Produces:** `_report/case_state.json`, `_report/reply.md`, `_report/bom_draft.md`
— the same artifacts as any other run, with an empty BOM table.

A previous version screened such messages out before the engine ran. That was
removed: measured against a 45-message corpus it discarded 13 genuine RFQs, and
54% of everything it dropped was real customer business. Reading the message and
saying "nothing to quote" costs a few hundred milliseconds and cannot lose an
order.

## Argument Reference

| Argument | Type | Default | Description |
|---|---|---|---|
| RFQ path | path (positional, required) | — | The inbound email to read: `.eml` (MIME, quoted-printable/base64, HTML) or `.txt`. Read as raw bytes. |
| `--component-ids` | list of strings | none | Component IDs an operator has already confirmed. Matched case-insensitively against the catalog; hits become BOM lines, misses become blocking asks. Also forces `hose_assembly` classification. |
| `--coc` | flag | off | The customer requires a Certificate of Conformance. |
| `--config-dir` | path | shipped `vendor/config/` | An alternate rules/catalog/citations directory — e.g. one backed by the P21 item master. |

## Common Patterns

- **Exit code 2 is success.** The engine returns 2 whenever a draft has open
  items, which is essentially every real RFQ. Treat 2 as "draft produced, human
  input needed". Only the wrapper scripts' own non-zero exit is a failure. Exit 0
  is reserved and in practice unreachable.
- **`case_state.json` is the contract; `bom_draft.md` is a view.** The rendering
  drops `fields`, `routing`, `knowledge` and `supersedes`, and keeps only the code
  and ask from each open item. Anything programmatic must read the JSON — which is why
  the reply states it in words instead of attaching JSON.
- **The kit builds the message; the agent never does.** `scripts/prepare_input.py`
  takes the body file and everything in `input/` and writes one `.eml`: HTML as a
  `text/html` part so the engine's own HTML-to-text runs, every file as a real
  attachment so the scanner sees it, and NO `text/plain` placeholder — the engine
  prefers plain, and a placeholder is how a 39-byte "This message contains HTML."
  once became the whole case. A bare `.html` pointed at the engine is refused.
- **A model may transcribe an attachment; it may not answer.** When the request is
  the attachment — a PO as a PDF — `scripts/apply_transcript.py` folds a transcription
  into the case text and the ENGINE extracts from it as it would from any text. The
  model never classifies, never maps to fields and never decides what matters. Every
  transcribed value is marked, and the outcome is always `needs_human_input`: a
  transcription can transpose a quantity and still look right.
- **An operator's answer is text, not a value.** `scripts/apply_answers.py` folds a
  reviewer's out-of-thread answer into the case text as an addendum and re-points the
  invocation at it; the engine treats it as a later message in the thread, which is
  how it can supersede an earlier value. Nothing writes to the CaseState, so an
  answer the engine will not accept leaves the ask open — the correct outcome. Every
  document downstream marks the fields that came from the addendum `OPERATOR-STATED`,
  and says plainly that the added text is not the customer's words.
- **A correction has to pin to a run to be worth anything.**
  `schemas/correction.schema.json` is the shape Body fills in when a reviewer edits a
  proposal, and `tools/correction_check.py` (kit-side) refuses one that does not match
  a real run's idempotency key, kit version and engine commit, or whose `original` is
  not what the run actually produced. A correction that cannot be replayed is an
  anecdote, not a test.
- **Two documents, two readers.** `review_request.md` is for the Inside Sales
  reviewer: the decision, the grounds, the owners, and the proposed response
  embedded verbatim. `reply.md` is what gets sent once they approve. The review
  request is a superset by construction — it CONTAINS the reply — so a reviewer
  can never approve text they were not shown.
- **Owners are resolved, never invented.** `config/routing.json` ships with every
  key the engine emits and every address empty, on purpose. Until they are filled
  in, every owner renders NOT ROUTABLE and names the key. Inventing a Teams group
  would be fabrication, and a wrong assignee is worse than a visible gap.
- **The outcome is in the manifest, not in the exit code.**
  `_report/run_manifest.json` carries `outcome: needs_human_input` when a blocking
  open item exists **or the customer attached a file the engine never read**, and
  `complete` otherwise — plus the kit version, the engine commit, the input's
  sha256 and an `idempotency_key` for recognising a retry. `outcome_reason` says
  which, and names the files.
  `complete` does not mean sendable — every case here is a draft a human reviews.
  A run that FAILED writes no manifest at all: absence is the failure signal.
- **Attachments are named, never read.** The engine reads the message text only,
  so a drawing or spec sheet the customer attached is not in the case. The reply
  carries an `EVIDENCE NOT READ` block naming the files, and the manifest carries
  the same list under `evidence_not_read`. Every reply states the attachment
  position — including "none" — so silence never has to be interpreted. Do not
  open the files and answer from them: the open items were all derived without
  them, and reading one puts case data into the answer from outside the engine.
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
- **Large threads are slow, and a run costs four engine passes.** A single pass
  is ~0.1 s at 8 KB, ~5 s at 134 KB, ~80 s at 538 KB — superlinear past roughly
  100 KB. A full kit run makes **four** passes: one in `extract_case`, two in
  `generate_report` (it re-derives the CaseState to reconcile before rendering),
  and one in `render_reply` (which reconciles too, so the reply cannot describe a
  different case than the CaseState). Budget roughly **4x** the single-pass
  figures: ~5 minutes end to end at 538 KB, not 80 s. All three scripts warn on stderr above 100 KB. The per-pass cost is
  inherited from the engine and truncating input would be worse than being slow,
  so trim quoted history if you need speed.
- **Two schema values the engine cannot emit.** `schemas/case_state.schema.json`
  declares `status: "superseded"` and `knowledge.lookups[].op: "ratings_for"`, and
  neither is reachable: supersede results appear as a top-level `supersedes` array
  plus `superseded_from` inside the field, and `ratings_for()` records the
  `resolve_component` op. Do not build a branch for either. The schema is kept
  byte-identical to the source's contract rather than corrected here, so the fix
  belongs upstream.
- **Multi-kit workflows:** feed `case_state.json` to a conversation layer to run
  the customer dialogue (it is designed for exactly that — every open item carries
  a priority, and a route where one applies — `route` is OPTIONAL and absent on
  most items, so read it with a default rather than indexing it), and keep the
  raw JSON with the case record for audit.
