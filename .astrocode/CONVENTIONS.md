# Conventions — email-to-bom

> The rules new code MUST follow. Keep this short and current — every planning and
> execution agent reads it before touching code. Vague canon = inconsistent code.

Authoritative source: `KIT-CONTRACT.md` at the kit root (manifest v4). Where this
file and the contract disagree, the contract wins.

## Stack

- Language / runtime: Python 3 (`requires.runtime: ["python3"]`), **stdlib only**.
- Frameworks / key libraries: none. `requires.tools` is `[]` and must stay that way
  unless a genuinely new capability needs a tool — then it is an **exact pin**, and
  never one of the base-image allowlist (`bash coreutils grep sed awk jq git curl
  wget tar unzip`).
- Why this stack (one line): the vendored engine has zero runtime dependencies, so
  the kit installs and runs anywhere with no resolution step.

## Naming

- Files / modules: `snake_case.py`. Recipe phases are `snake_case`. The recipe file
  is named after the kit id: `src/recipes/email-to-bom.yaml`.
- Functions / variables: `snake_case`; module-private helpers prefixed `_`.
- Tests: fixture directories are `kebab-case` under
  `tools/parity/fixtures/<case>/`, each holding `input.eml`,
  `expected_output.json`, `actual_output.json`.

## Patterns

- Error handling: **the engine does not raise on ambiguity — it appends an ask.**
  Preserve that inversion. Kit scripts distinguish their own failure (non-zero exit)
  from the engine's exit 2, which means "a draft with open items" and is the normal
  outcome. Never treat 2 as an error.
- State / data flow: runtime output goes under `_report/` only. State travels
  through `_report/state.json`. Phases communicate through files, never through
  ambient state.
- Async / concurrency: none. One RFQ per run, synchronous.
- Config & secrets: **no secrets, ever.** The kit reads no environment variables and
  holds no keys. Engine vocabulary lives in `src/vendor/config/rules.json`; an
  alternate directory is supplied via `--config-dir`, never by editing the vendored
  copy.

## Testing

- Framework: `tools/parity_check.py` against `tools/parity/parity.json` — the
  golden-fixture parity harness. `python3 tools/parity_check.py --manifest
  tools/parity/parity.json` must exit 0 before any change is considered done.
- What must be tested: every capability change gets a fixture whose
  `expected_output.json` was **captured from the source engine**, never
  hand-written. Stamp the source commit and capture command in
  `tools/parity/parity.json`.
- Style: **structure, not vocabulary.** Assert on the shape and values of the
  CaseState, never on whether some word appears in the output — the source project
  lost several rounds to tests that checked phrasing instead of behaviour. Before
  trusting a new fixture, confirm it can *fail*: mutate the code, watch the fixture
  break, restore. A fixture that has never failed has proven nothing.
- **No normalization without justification.** `normalize` is empty for every
  fixture today. Adding an entry requires naming the specific benign
  nondeterminism it covers; it may never be widened to make a mismatch disappear.

## File layout

- Where new code goes:
  - `src/scripts/` — thin wrappers and helpers invoked by recipe phases.
  - `src/generate_report.py` — the deliverable generator. Deliverables are produced
    by scripts, **never hand-written**.
  - `src/schemas/` — output contracts.
  - `src/vendor/` — **read-only.** The verbatim engine copy. Do not edit it to
    change an outcome; refresh it per `src/vendor/PROVENANCE.md` and re-run parity.
  - `tools/` — build and parity scaffolding. Not shipped in the zip.
- Wrappers call the vendored engine's own entry point. **Never re-express an engine
  rule in kit code** — a second copy of a rule is the drift this project exists to
  avoid.
