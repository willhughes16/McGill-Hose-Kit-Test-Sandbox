# Conventions — mcgill-email-to-bom

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
  is named after the kit id: `src/recipes/mcgill-email-to-bom.yaml`.
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

- Two harnesses, and they cover different things. `tools/parity_check.py` proves
  OUTPUT parity with the source; `tools/selftest.py` proves the DEFENCES still work
  (exit codes, which artifacts survive a failure, whether the two artifacts agree).
  Parity cannot see a failure path — round 26 removed two defences and parity stayed
  green. Both must pass.
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
- **The engine invocation is ONE contract in ONE place.** Any script that invokes the
  engine builds its argv through `run_engine.build_argv` and, if it runs across a
  phase boundary, replays the invocation recorded in `state.json`. Never re-list the
  flags at a second call site. Round 25's F-1 was exactly this: phase 2 rebuilt the
  call and silently dropped half of it, so the human draft contradicted the machine
  contract. Adding an argument means adding it to the recorded invocation, not to a
  command string.
- **A derived artifact must be reconcilable against its source artifact.** If a script
  produces something downstream of the CaseState, it must be able to prove they
  describe the same case, and must FAIL rather than emit a mismatch. Consistency you
  cannot check is consistency you do not have.
- **Never let a failure leave a plausible artifact behind.** Clear stale outputs before
  work that can fail. A missing file is an honest error; a stale valid-looking one is
  a silent wrong answer. Clear them via `run_state.ARTIFACTS` — never by naming files
  at the call site, which is how round 26's R26-F1 happened.
- **Declare categories, not instances.** Artifacts, invocation keys and argv live in
  `run_state.py` as single declarations. When a review names one broken item, fix the
  category it belongs to and check every sibling — five of this project's findings
  across rounds 21–26 were the same shape: the named instance fixed, the sibling
  missed.
- **Never enumerate exception types at a boundary you do not own.** `cli.main` can
  raise `SystemExit` from its own argparse; round 26's R26-F2 was an enumeration that
  missed it and leaked the engine's success code. Catch broadly, and clamp the exit
  code so a failure cannot look like a success.
- **Guards fail CLOSED.** If a safety check cannot run — the thing it compares against
  is missing, unreadable, not a regular file — that is an error, not a skip. Opting
  out must be explicit and must say so on stderr.
- **A failure must not destroy inputs.** Invalidate results, never the record of what
  was asked for.
