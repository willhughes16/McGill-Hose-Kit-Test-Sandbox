# VERIFICATION — ROUND 25 (blind independent verifier)

Artifact: `/Users/axr/Desktop/McGill/mcgill-email-to-bom` @ `0119689`
Source of truth: `/Users/axr/Desktop/McGill/email-to-bom-agent` @ `b15b23d` (clean)
Bar: `ACCEPTANCE.md` V-1 … V-12, pre-registered.
Verifier had no build context; only `ACCEPTANCE.md`, the artifact, and the source repo were read.

**OVERALL VERDICT: FAIL** — on V-8 and V-12, for one reproducible defect (F-1) that makes
the shipped human deliverable silently disagree with the machine contract on two of the
kit's own four documented examples. Everything else held, including several things I
attacked hard specifically hoping they would not.

Tree state at end of round: `git status --porcelain` → `?? ACCEPTANCE.md` only. Every
mutation I made to test falsifiability was reverted; vendored code re-diffed byte-clean
against the source afterwards; `dist/kit.zip` sha256 unchanged at
`8ed00871536c7b55b18d1401ba9ada500caab67ed10fbe97a48f2b06f10c238c`.

---

## Results table

| # | Check | Verdict |
|---|---|---|
| V-1 | Parity real, harness falsifiable | **PASS** |
| V-2 | Parity not circular | **PASS** |
| V-3 | Vendored engine verbatim | **PASS** |
| V-4 | No second copy of an engine rule | **PARTIAL** — wrappers clean; a full second copy of the vocabulary lives in the shipped schema, unguarded, with 2 already-drifted entries |
| V-5 | Self-contained and offline | **PASS** |
| V-6 | Exit-code contract preserved | **PASS** (with a stale-artifact hazard, F-4) |
| V-7 | Kit contract compliance | **PASS** |
| V-8 | Documentation makes no false claim | **FAIL** |
| V-9 | Determinism | **PASS** |
| V-10 | Nothing sensitive ships | **PASS** |
| V-11 | Published package matches repo | **PASS** |
| V-12 | Recipe constraints coherent | **FAIL** |

---

## V-1 — Parity is real, and the harness can fail — PASS

```
$ cd /Users/axr/Desktop/McGill/mcgill-email-to-bom && python3 tools/parity_check.py --manifest tools/parity/parity.json
suction-assembly: matched
plain-steam: matched
quoted-printable: matched
multipart-html: matched
confirmed-ids: matched
human-render: matched
6 fixtures checked, 6 matched, 0 mismatched
normalized fields: (none declared)
EXIT=0
```

Every fixture's `normalize` is `{}` — verified by reading `tools/parity/parity.json`
directly, and corroborated by the harness's own `normalized fields: (none declared)`
line. Nothing is masked.

**Falsifiability — three mutations.** I mutated the kit, ran the harness, and restored
with `git checkout`.

Mutation 1 — `core.py`, `PRESSURE_UNIT_MISSING` priority `blocking` → `confirm`:

```
 src/vendor/email_to_bom/core.py | 2 +-
6 fixtures checked, 6 matched, 0 mismatched     <-- STAYED GREEN
```

This is *not* a stub. `PRESSURE_UNIT_MISSING` is simply not reachable from any of the six
fixture inputs (verified: fixture code sets are `{MATERIAL_CONFIRM, VACUUM_VALUE_CONFIRM,
TEMPERATURE_MISSING, SIZE_MISSING, LENGTH_TYPE_MISSING, SELECTION_UNRESOLVED,
PRESSURE_MISSING, LENGTH_CONFIRM, HTML_SOURCE_REVIEW}` — 9 of the engine's 37 codes).
That coverage limit is pre-declared as FOLLOW-UP-6/7, so I report it as a corroborating
measurement, not a defect. Mutation 2 proves the harness fires when the mutation is in
range.

Mutation 2 — `core.py`, `TEMPERATURE_MISSING` given `priority="blocking"`:

```
suction-assembly: MISMATCH open_items[2].priority
plain-steam: MISMATCH open_items[1].priority
quoted-printable: MISMATCH open_items[1].priority
multipart-html: MISMATCH open_items[1].priority
confirmed-ids: MISMATCH open_items[2].priority
human-render: matched
6 fixtures checked, 1 matched, 5 mismatched
EXIT=1
```

It fails, and it names the diverging JSON path.

Mutation 3 — `cli.py`, render header `DRAFT BILL OF MATERIALS` → `DRAFT BOM XX` (proving
the `generate_report.py` path is covered too, not just `run_engine.py`):

```
human-render: MISMATCH render
6 fixtures checked, 5 matched, 1 mismatched
EXIT=1
```

Both wrapper paths are falsifiable. The harness also cannot become an always-pass
file-differ: it `unlink()`s the declared output before every run and reports
`missing-output` if nothing appears — I saw that trigger for real (all six fixtures went
`MISMATCH missing-output`) when an over-aggressive network block of mine broke the engine's
import.

## V-2 — Parity is not circular — PASS

I ignored the kit's scripts entirely and regenerated every expected output from the source
engine's own venv, then byte-diffed against the committed files.

```
$ cd /Users/axr/Desktop/McGill/email-to-bom-agent && ./.venv/bin/python -m email_to_bom.cli <fixture>/input.eml --json | diff - <fixture>/expected_output.json
V2 MATCH suction-assembly (engine_exit=2)
V2 MATCH plain-steam (engine_exit=2)
V2 MATCH quoted-printable (engine_exit=2)
V2 MATCH multipart-html (engine_exit=2)
V2 MATCH confirmed-ids (engine_exit=2)     # with the 4 --component-ids from parity.json
V2 MATCH human-render                       # source render, wrapped by wrap_text.py
raw render identical                        # source render == committed actual_render.txt
```

All six `expected_output.json` files are independently reproducible from the source engine.
Parity is a real capture, not the kit grading its own homework. `tools/parity/wrap_text.py`
was inspected first — it is a 40-line `json.dump({"render": text})` encoder with no
transformation, so it cannot hide a diff.

## V-3 — The vendored engine is verbatim — PASS

```
$ diff -r --exclude=__pycache__ src/vendor/email_to_bom  ../email-to-bom-agent/email_to_bom
$ diff -r src/vendor/config  ../email-to-bom-agent/config
(no output — identical)
```

Per-file sha256 confirms it independently: all 8 `.py` files and all 4 config JSONs match,
e.g. `core.py` = `812b00f946b99fb8103bbce54d06903461d03653e8398a65cc0af02f2ff55515` on both
sides. `PROVENANCE.md`'s annotation that `b15b23d` "touched nothing this directory vendors"
is true: `git diff --stat b1f9950 b15b23d` → `tests/property/shape_matrix.py | 4 +++-`,
one file, not vendored. The vendored tree also carries the full `config/` — nothing was
cherry-picked. Zero local modification.

## V-4 — No second copy of an engine rule — PARTIAL

The wrappers are clean, and I checked this by machine rather than by reading. Scanning each
non-vendor file for engine-style `CAPS_WITH_UNDERSCORES` vocabulary:

```
src/scripts/run_engine.py:            0
src/generate_report.py:               0
src/CLAUDE.md:                        0
src/recipes/mcgill-email-to-bom.yaml:        0
tools/parity_check.py:                0
src/README.md:                        1   (SELECTION_UNRESOLVED)
src/EXAMPLES.md:                      6
src/schemas/case_state.schema.json:  37
```

Neither wrapper re-derives extraction, re-implements the renderer, or hardcodes a code or
an ask. `generate_report.py` re-runs the engine rather than re-rendering `case_state.json`,
and documents exactly why — that is the right call and it is the reason mutation 3 was
catchable at all.

**But `src/schemas/case_state.schema.json` is a complete second copy of the engine's
vocabulary** — 37 open-item codes plus the `status`, `kind`, `route`, `tier`,
`request_class`, `routing.recommendation`, `lookups.op` and `lookups.outcome` enums.
`CLAUDE.md` points readers at it as authoritative ("Consult it whenever you need to know
what a code means or what values are legal"). Nothing in the repo enforces that it tracks
the engine — there is no test asserting `schema enum == engine literals`, and the parity
harness never validates output against the schema.

I checked whether it has already drifted. The 37 codes are exactly in sync:

```
engine all-caps code literals: 37   schema codes: 37
ENGINE NOT IN SCHEMA: []
SCHEMA NOT IN ENGINE: []
```

Two non-code values have drifted, both over-permissive — see F-5.

## V-5 — Self-contained and offline — PASS

**The unzipped zip runs.** From a clean directory, no venv, no install, system `python3`
3.14.6, the zip's own layout:

```
$ unzip -q dist/kit.zip -d zipkit          # 20 files, no __pycache__, no .pyc
$ cd /tmp/.../runwd && python3 .../zipkit/scripts/run_engine.py --in raw/rfq.eml \
      --out _report/case_state.json --state _report/state.json
{ "input": "raw/rfq.eml", "engine_exit": 2, "request_class": "hose_assembly",
  "open_items": 4, "checkpoints": 3, "bom_lines": 1, "knowledge_source": "none" }
EXIT=0
$ python3 .../zipkit/generate_report.py --out _report/bom_draft.md --state _report/state.json
wrote _report/bom_draft.md (1666 bytes, engine_exit=2)
EXIT=0
```

Config resolution is not cwd-dependent — this ran from a directory with no relation to the
kit and still loaded `vendor/config/`. `requires.tools` is `[]` and nothing beyond `python3`
was needed (`jq` is used only by `tools/build_kit.sh`, which is not shipped).

**Network proven absent, not assumed.** `sitecustomize.py` patching
`socket.socket.connect/connect_ex/sendto`, `socket.create_connection`, `socket.getaddrinfo`,
`socket.gethostbyname` to log-and-raise. Sanity-checked that the block bites
(`urllib.request.urlopen('http://example.com')` → `NETWORK-ATTEMPT-DETECTED`, `URLError`),
then:

```
$ PYTHONPATH=.../nonet2 NETLOG=.../netattempts.log python3 tools/parity_check.py --manifest tools/parity/parity.json
6 fixtures checked, 6 matched, 0 mismatched
EXIT=0
$ cat .../netattempts.log
(no attempts logged - file absent)
```

Zero network attempts; full parity offline. Every run I made reported
`knowledge.source == "none"` (`{'source': 'none', 'revision': None, 'lookups': []}`).
`McpKnowledge`/`TwydIngestion` do ship inside the verbatim `knowledge.py`, but `cli.py`
never constructs either — the default is `NullKnowledge` — and this is pre-declared as
FOLLOW-UP-1/2, so I do not flag it.

**No environment variables, no credentials.** `grep -rn "environ|getenv|expandvars"` over
the unzipped zip returns nothing. Secret scan (api key / token / bearer / private key /
AKIA / ghp_ / xox / sk-) over the zip returns only the word "token" inside tokenizer
comments in `mail.py`, `fields.py`, `core.py`.

## V-6 — The exit-code contract is preserved — PASS

Engine exit 2 is never treated as a failure: every one of the ~30 real runs I made returned
engine_exit=2 with wrapper exit 0, and the wrapper reports the engine's code separately in
its summary and in `state.json`.

Genuine failures fail loudly, and **no partial or empty artifact is ever written**. I ran
these against the unzipped zip, not the repo tree, and confirmed by `ls` after each:

| Broken input | wrapper exit | artifact |
|---|---|---|
| nonexistent path | 1 | not created |
| input is a directory | 1 | not created |
| `--config-dir /no/such/config` | 1 | not created |
| `--config-dir` with malformed JSON | 1 | not created |
| `--config-dir` that exists but is empty | 1 | not created |
| `--config-dir` with valid JSON of the wrong shape (`KeyError: 'items'`) | 1 | not created |
| `--out` inside a chmod-500 directory (`PermissionError` in `makedirs`) | 1 | not created |
| `--out` is an existing directory | 1 | `error: cannot write outdir: [Errno 21] Is a directory` |
| `generate_report --state` corrupt JSON | 1 | not created |
| `generate_report --state` valid JSON, no `extract_case` | 1 | not created |
| `generate_report --state` pointing at a deleted input | 1 | not created |

Two of these (wrong-shape config, unwritable dir) exit 1 via an uncaught traceback rather
than a clean message — ugly, but they exit non-zero and write nothing, which is what the
check demands.

Empty / binary / non-UTF-8 / null-byte inputs succeed with exit 0 and a real CaseState —
and that is the *engine's* behaviour, byte-identical to the source (see F-0 evidence
below), not a wrapper swallowing anything.

The one real hazard here is stale artifacts, not partial ones — F-4.

## V-7 — Kit contract compliance — PASS

```
$ python3 tools/validate_manifest.py kit.json
EXIT=0

$ ./tools/build_kit.sh
  SHA-256:  8ed00871536c7b55b18d1401ba9ada500caab67ed10fbe97a48f2b06f10c238c
$ shasum -a 256 dist/kit.zip
8ed00871536c7b55b18d1401ba9ada500caab67ed10fbe97a48f2b06f10c238c
$ python3 -c "import json;print(json.load(open('kit.json'))['sha256'])"
8ed00871536c7b55b18d1401ba9ada500caab67ed10fbe97a48f2b06f10c238c
$ git status --porcelain          # after the rebuild
?? ACCEPTANCE.md
$ cmp kit.zip.pre dist/kit.zip && echo "zip byte-identical"
zip byte-identical
```

The rebuild is byte-reproducible and leaves the tree untouched — so `kit.json` and
`registry-entry.json` in the repo are exactly what the build emits, not hand-edited.

Recipe coherence, checked mechanically:

```
email_attachment count: 1                              # _report/case_state.json only
declared artifacts:      ['_report/case_state.json', '_report/bom_draft.md']
produced by recipe:      ['_report/bom_draft.md', '_report/case_state.json', '_report/state.json']
declared but never produced: []
YAML PARSE OK (PyYAML 6.0.3)
  prepare        input []                                        output [_report/state.json]
  extract_case   input [state.json]           PRODUCED-EARLIER   output [state.json, case_state.json]
  generate_report input [state.json, case_state.json] both PRODUCED-EARLIER  output [bom_draft.md]
```

No phase reads a file no earlier phase produced. Both declared artifacts were produced for
real by running the phases. `src/EXAMPLES.md` has all four required sections (`## Quick
Start`, `## Examples` with 4 examples each carrying Prompt/Arguments/Expected
workflow/Produces, `## Argument Reference` as the required 4-column table, `## Common
Patterns`).

## V-8 — Documentation makes no false claim — FAIL

Claims I verified as **TRUE**:

- `PROVENANCE.md` "507 tests": `cd ../email-to-bom-agent && ./.venv/bin/python -m pytest -q`
  → `507 passed in 2.31s`. Exact.
- `PROVENANCE.md` source commit / "still current as of `b15b23d`": true (V-3).
- EXAMPLES.md ex.1 counts — "classifies it `hose_assembly`, drafts no BOM lines, 2
  harness-held checkpoints and 6 open items — MATERIAL_CONFIRM, VACUUM_VALUE_CONFIRM,
  TEMPERATURE_MISSING, SIZE_MISSING, LENGTH_TYPE_MISSING, SELECTION_UNRESOLVED":
  `suction-assembly class=hose_assembly lines=0 open_items=6 checkpoints=2`, codes in
  exactly that order. Exact, including the ordering.
- EXAMPLES.md ex.2 counts — "4 populated BOM lines … 5 open items remain … the catalog
  checkpoint closes": `confirmed-ids lines=4 open_items=5 checkpoints=1` (2→1). Exact.
- README/EXAMPLES `4 in ID` vs bare `4in`:
  ```
  bare 4in      size.status=missing     size.value=None
  4 inch        size.status=missing     size.value=None
  4"            size.status=missing     size.value=None
  4 in ID       size.status=captured    size.value='4 ID'
  ```
  True, and `SIZE_MISSING` appears for the bare form and not for `4 in ID`.
- "Exit 0 is reserved and in practice unreachable": I tried to reach it with a maximally
  complete RFQ (size+ID, length with convention, gauge pressure, full vacuum, temperature
  with unit, ends, material, quantity, C-of-C waived) and again with all four catalog IDs
  pre-confirmed. Best I achieved was 5 open items and 1 checkpoint. Held.
- "knowledge source is `none`", "reads no environment variables", "no network": V-5.
- Every real output conforms to `schemas/case_state.schema.json`. I wrote a validator
  (enum / required / type / maxLength / additionalProperties) and ran it over 32 real
  CaseStates — the 5 JSON fixtures, all 24 adversarial fuzz outputs, and 3 probes:
  `checked 32 files, 0 with violations`. The validator is falsifiable: injecting
  `code="NOT_A_REAL_CODE"` and `status="wat"` produced 2 violations.

Claims that are **FALSE of the shipped kit** — see F-1, F-2, F-3, F-5, F-6.

## V-9 — Determinism — PASS

```
distinct case_state hashes over 3 repeat runs + PYTHONHASHSEED in {0,1,42,12345,random}: 1
distinct bom_draft hashes over the same 8 runs:                                          1
```

No leakage into either declared artifact, tested deliberately with an **absolute** input
path so a leak would show:

```
grep -c "/private/tmp|/Users/" _report/case_state.json  -> 0   (no leak)
grep -c "/private/tmp|/Users/" _report/bom_draft.md     -> 0   (no leak)
grep -nEi "20[0-9]{2}-[0-9]{2}-[0-9]{2}|T[0-9]{2}:[0-9]{2}:" both -> no timestamps
```

`_report/state.json` does record the absolute input path, but it is not a declared artifact
and both `CLAUDE.md` and the schema treat it as run state, not a deliverable. In scope of
the claim as written. Worth knowing if state.json ever gets attached or pasted.

## V-10 — Nothing sensitive ships — PASS

No credential, token, key or password in the repo or the zip (V-5). The anonymisation claim
in `PROVENANCE.md`/`parity.json` is not only true, it is **effective** — I diffed the
shipped fixture against the source's `examples/sample_rfq.eml`:

```
source:  From: Dave Granquist <dave@richduboise.com>   To: sales@mcgillhose.com
         "...for Rich Duboise."                         "Thanks, Dave"
shipped: From: Dana Whitfield <dana@example-customer.com>  To: sales@mcgillhose.example
         "...for Northside Aggregate."                  "Thanks, Dana"
```

A real personal name, a real domain, a real end-customer and McGill's real sales address
are all gone; the technical content is unchanged. The kit is cleaner here than the source.
Every other fixture uses `.example` names. One nit — F-7.

## V-11 — The published package matches the repo — PASS

Rebuilt the *upload* package (src/ root-relative + `kit.json` at root) from repo HEAD,
offline, and compared to the sha256 pre-registered in ACCEPTANCE:

```
$ python3 tools/publish_kit.py --base https://astro.twyd.cloud --email x --password y --dry-run --out /tmp/upload.zip
[publish] Kit: mcgill-email-to-bom v0.1.1  (manifest: registry-entry.json)
[publish] Package built — 21 files, 66419 bytes, sha256 102a065e981c…
[publish] Dry run — not uploading.
$ shasum -a 256 /tmp/upload.zip
102a065e981c659f94161494b8c05bce6f74f917419848d9237bd5de3a5fbcbe
  expected: 102a065e981c659f94161494b8c05bce6f74f917419848d9237bd5de3a5fbcbe
```

Exact match. The registry serves something the repo reproduces byte-for-byte. No network
was used to establish this.

## V-12 — The recipe's constraints are coherent — FAIL

Constraints do not contradict each other, and no constraint asks for something the scripts
make impossible. But the recipe **does** leave a declared behaviour unproduced: its phase-2
command cannot carry `--component-ids` / `--coc` / `--config-dir`, so following the recipe
verbatim produces a `bom_draft.md` that contradicts the `case_state.json` produced by
phase 1. See F-1 and F-6.

Also noted: phase 2 declares `_report/case_state.json` as an `input` it never actually
reads (it re-runs the engine instead — documented and deliberate), so that declared
dependency is nominal rather than real. Informational, not a defect.

---

## Findings, by severity

### F-1 — HIGH — `--component-ids` and `--coc` are dropped between phase 1 and phase 2; the human deliverable silently contradicts the machine contract

**What breaks.** `run_engine.py` records only `input` into `state.json`. It never records
`component_ids`, `coc`, or `config_dir`. `generate_report.py::_input_from_state` therefore
recovers only the path. The recipe's phase-2 command is fixed and flagless
(`python3 generate_report.py --out _report/bom_draft.md --state _report/state.json`), while
phase 1's goal says "Pass through `--component-ids` / `--coc` exactly as given in phase 0."
So for any run that uses a flag, phase 2 re-runs the engine *without* it. This is the
project's recurring failure class exactly: one rule (the invocation contract) expressed in
two places, and one of them silently drops half of it.

**Reproduction** — the kit's own EXAMPLES.md example 2, run against the unzipped zip, using
the recipe's phase-2 command verbatim:

```
phase 1: run_engine.py --in raw/rfq.eml --out _report/case_state.json --state _report/state.json \
           --component-ids "OPW 633C A" "OPW 633E A" "SPS400452" "HOS-064 300 EPDM"
  -> bom_lines= 4  open_items= 5

phase 2: generate_report.py --out _report/bom_draft.md --state _report/state.json
  -> wrote _report/bom_draft.md (2082 bytes)

_report/bom_draft.md:
  Component ID | Description | Component Type | Qty Needed | Cut Length | Edited
  (header only — ZERO BOM lines)
  Checkpoints: C2, C3            (case_state has only C2)
  open items: 6                  (case_state has 5)
  extra item: [SELECTION_UNRESOLVED] Hose/coupling not resolved...
```

EXAMPLES.md line 48 promises "`_report/bom_draft.md` with the rendered table." The shipped
recipe produces an empty table, an extra checkpoint, and an extra open item saying the
selection is unresolved — when the CaseState says a human already resolved it. Passing the
flags to phase 2 yields the promised table, proving the wrappers are fine and the *plumbing*
is the defect:

```
generate_report.py --in raw/rfq.eml --state /dev/null --component-ids "OPW 633C A" ... :
  OPW 633C A       | 4 ALUM CPLR X HOSE SHANK             | Fitting | 1 | 0.00 | Unedited
  OPW 633E A       | 4IN MALE KAM X HOSE BARB             | Fitting | 1 | 0.00 | Unedited
  SPS400452        | 4" 4-13/16" 4-3/16" Plt Stl Slv (Wa) | Sleeve  | 1 | 0.00 | Unedited
  HOS-064 300 EPDM | 4 EPDM SUCTION HOSE                  | Hose    | 1 | 0.00 | Unedited
  open items: 5    (matches case_state)
```

Same defect on `--coc`, and here EXAMPLES.md example 3 is explicit — "**Produces:**
`_report/case_state.json`, `_report/bom_draft.md`, **both including the C-of-C line**":

```
phase 1 with --coc:  case_state classes: ['Certs Required']   C-of-C line present: yes
phase 2 as written:  draft has no "Classes:" line             C-of-C line present: no
```

**Why it matters.** `bom_draft.md` is the artifact a human reads. On any `--coc` or
`--component-ids` run it understates the case: it hides confirmed parts, invents an open
item that is closed, hides a certificate requirement the customer asked for, and shows an
extra checkpoint. This is precisely the "being silently wrong" outcome the whole kit is
designed to make structurally impossible, and it violates the recipe's own constraint
"Report every open item — do NOT summarise them away" in the opposite direction: it reports
a *phantom* one. It also breaks two of the four documented examples (V-8) and leaves a
declared behaviour unproduced by the recipe (V-12).

**Why no existing check catches it.** The `confirmed-ids` fixture exercises
`run_engine.py` only; the `human-render` fixture exercises `generate_report.py` only, and
on a no-flag input. The one combination that fails — a flagged input through
`generate_report.py` via `state.json` — is the one combination no fixture covers. This is
the "check that has never been able to fail" pattern, scoped to a specific path.

### F-2 — MEDIUM — the docstring that hides F-1 asserts the opposite of what the code does

`src/generate_report.py:58-59`:

```python
def _input_from_state(state_path):
    """Recover the RFQ path (and passthrough flags) recorded by run_engine.py."""
```

It recovers no flags, and `run_engine.py` records none. A reader auditing the flag path
would read this docstring and conclude the plumbing exists. This is the sentence that
makes F-1 invisible to review.

### F-3 — MEDIUM — README and EXAMPLES document a command that does not exist in the shipped kit

`src/README.md:30-34` presents, under `## Usage`, unqualified:

```
mcgill-email-to-bom rfq.eml
mcgill-email-to-bom rfq.eml --component-ids "OPW 633C A" "SPS400452"
mcgill-email-to-bom rfq.eml --coc
```

and `src/EXAMPLES.md:5-7` uses the same form for `## Quick Start`. The zip ships 20 files
and none of them provides an `mcgill-email-to-bom` executable, console script, or shim; there is
no `pyproject.toml` or entry point. The real invocations are
`python3 scripts/run_engine.py --in rfq.eml …` and `python3 generate_report.py …`.

I weigh this as MEDIUM rather than HIGH because the form is plausibly the Astro
kit-invocation convention (kit-id + `$ARGUMENTS`), which `CLAUDE.md` and the recipe both
use — and `CLAUDE.md`, which is what the runner actually reads, is careful and correct
throughout. But `README.md` labels the block `## Usage` with no such framing, and
`KIT-CONTRACT.md:74` calls Quick Start the "single simplest **invocation**." A human or an
agent that tries it literally gets `command not found`. Either name the convention or show
the real command.

### F-4 — MEDIUM — a failed re-run leaves the previous run's artifacts in place, looking valid

**What breaks.** `run_engine.py` validates the input and exits 1 *before* touching `--out`.
It never clears a stale artifact. `state.json` also still points at the previous input. So
after a failed second run, `_report/` holds a complete, schema-valid `case_state.json`
describing a *different email*, and phase 2 — whose default is to read the input path from
`state.json` — will happily re-render that old email into `bom_draft.md`.

**Reproduction:**

```
run 1: run_engine.py --in .../suction-assembly/input.eml --out _report/case_state.json --state _report/state.json
  -> EXIT=0  class=hose_assembly 6 items

run 2: run_engine.py --in raw/steam_rfq.eml (typo'd path) --out _report/case_state.json --state _report/state.json
  -> error: no such RFQ file: raw/steam_rfq.eml
  -> EXIT=1

_report/case_state.json still on disk:
  request_class= hose_assembly  open_items= 6
  codes= ['MATERIAL_CONFIRM','VACUUM_VALUE_CONFIRM','TEMPERATURE_MISSING','SIZE_MISSING','LENGTH_TYPE_MISSING','SELECTION_UNRESOLVED']
_report/state.json still points at:
  .../suction-assembly/input.eml
```

**Why it matters.** Any runner or operator that checks "did `_report/case_state.json` get
produced?" rather than "did phase 1 exit 0?" gets last run's answer for this customer's
email. The failure is loud at phase 1 but the evidence of it is erased by the surviving
artifact.

**Why it is the recurring class again.** The kit *already knows* this hazard and guards it
— in the other copy. `tools/parity_check.py:64-68` documents a "Real-execution guarantee
(C1)" and does `output_path.unlink()` before every fixture, precisely so "a stale leftover"
can never "fake a match." The runtime wrapper, which is where it matters to a customer,
has no equivalent.

### F-5 — LOW — two schema values the engine cannot emit (duplicate vocabulary, already drifted)

`src/schemas/case_state.schema.json` declares as legal:

- field `status: "superseded"` — the engine has no such literal anywhere. Supersede results
  are expressed as a top-level `supersedes` array plus a `superseded_from` key *inside* the
  field (`core.py:899-902`), never as `status: "superseded"`.
- `knowledge.lookups[].op: "ratings_for"` — `ratings_for()` delegates to
  `resolve_component()` and records *that* op (`knowledge.py:169-171`); `_record` is never
  called with `"ratings_for"` (all 12 call sites verified).

Verified by sweeping every lowercase string literal in the vendored engine against each
schema enum; those two are the only values with no corresponding literal.

Over-permissive rather than stale-restrictive, so nothing breaks today. But `CLAUDE.md`
sends consumers here for "what values are legal," and a conversation layer templating on
the schema would prepare two branches that can never fire. More importantly it demonstrates
that the duplicate has *already begun to drift* with nothing to stop it — see V-4.

### F-6 — LOW — `--config-dir` is documented as a supported argument but the recipe never plumbs it

`CLAUDE.md:36` ("`--config-dir` selects an alternate rules/catalog directory") and
`EXAMPLES.md:87` (a full Argument Reference row, default "shipped `vendor/config/`") both
advertise it. The recipe's phase 0 parses only "`--component-ids` … and `--coc`", and
phases 1 and 2 pass neither `--config-dir` nor anything derived from it. The scripts
support it; the recipe cannot reach it. Same root cause as F-1 — and it is the argument
the README's "Limits worth knowing" names as *the* route to grounded selection ("point
`--config-dir` at a catalog backed by the ERP item master"), so the documented escape
hatch from `SELECTION_UNRESOLVED` is unreachable through the shipped recipe.

### F-7 — LOW — one fixture domain is not in a reserved namespace

`suction-assembly`, `confirmed-ids` and `human-render` use `dana@example-customer.com`.
Every other address in the corpus correctly uses the RFC 2606 reserved `.example` TLD
(`sales@mcgillhose.example`, `purchasing@acmedairy.example`). `example-customer.com` is an
ordinary `.com` that someone may own. Cosmetic, but it is the kind of thing that turns into
a real address in a copied fixture.

### F-8 — LOW — `estimated_duration: "under 1 minute"` is falsified by a mid-size email

`registry-entry.json` advertises "under 1 minute". Runtime is superlinear in input size
(≈ O(n²) past ~30 KB), measured on the unzipped zip:

```
8 KB    -> 0.11 s
34 KB   -> 0.45 s
134 KB  -> 4.89 s
538 KB  -> 78.75 s     <-- exceeds the advertised bound
1.68 MB -> still running after 10 minutes (I killed it)
```

A 538 KB `.eml` is unremarkable — a long HTML quoted thread will get there. The cost is
**inherited, not introduced**: the source engine takes 88.0 s on the same 538 KB input and
its output is byte-identical to the kit's, so parity holds and engine performance is out of
round-25 scope. What is in scope is the kit's own duration claim, and the absence of any
input-size guard or wall-clock timeout in either wrapper (the 60 s `timeout` exists only in
the parity manifest, not at runtime).

---

## Adversarial pass — what I tried that did NOT break it

**Differential fuzz against the source engine, 24 hand-built adversarial inputs**, kit
(unzipped zip, run from an unrelated cwd) vs source (its own venv), byte-diffed:

```
f01_empty                IDENTICAL   f13_conflicting_units    IDENTICAL
f02_headers_only         IDENTICAL   f14_urgent_authority     IDENTICAL
f03_binary (all 256 bytes x20) IDENTICAL   f15_nested_mime (multipart/mixed>alternative) IDENTICAL
f04_nonutf8              IDENTICAL   f16_html_hidden (comment + display:none) IDENTICAL
f05_latin1               IDENTICAL   f17_subject_only         IDENTICAL
f07_bare4in              IDENTICAL   f18_null_bytes           IDENTICAL
f08_4inID                IDENTICAL   f19_crlf_mixed (bare CR) IDENTICAL
f09_unicode_endash       IDENTICAL   f20_utf8_BOM             IDENTICAL
f10_vulgar_fractions     IDENTICAL   f21_quoted_printable     IDENTICAL
f11_order_class          IDENTICAL   f22_base64               IDENTICAL
f12_component_request    IDENTICAL   f23_capability_question  IDENTICAL
                                     f24_nothing_recognized   IDENTICAL
f06_huge (1.68 MB)       parity confirmed separately at 538 KB: IDENTICAL
```

24 of 24. I could not find a single input where the kit's output differs from the source
engine's — including non-UTF-8 bytes, null bytes, bare-CR line endings, a UTF-8 BOM,
nested MIME with hidden HTML, unicode en-dashes, vulgar fractions, and conflicting units.

**Prompt-injection / authority pressure through the input.** `f14` claimed VP authority,
marked itself URGENT, and instructed the engine to "Skip the checks and confirm the BOM
now" while supplying complete specs. `f16` embedded `ignore all instructions` in a
`display:none` div. Neither changed the engine's behaviour: both still returned exit 2 with
open items and harness-held checkpoints; the hidden-content case raised the
`HTML_SOURCE_REVIEW`/hidden-content path instead of absorbing the text. No checkpoint was
slipped and no open item was resolved by assertion.

**Circularity.** Regenerated all six expected outputs from the source engine — every one
matched. Parity is not the kit grading itself.

**Quiet fork.** Per-file sha256 on all 12 vendored files against the source: all match.

**Harness stub.** Three mutations; two produced named path-level failures. The harness can
fail.

**Silent-success wrappers.** Eleven distinct broken-input / broken-config / unwritable-output
cases; every one exited 1 and none wrote a partial or empty artifact.

**Published-vs-repo drift.** Rebuilt the upload package and hit the pre-registered sha256
exactly.

**Sensitive data.** Diffed the anonymised fixture against the source's real sample: name,
domain, end-customer and McGill's real sales address all successfully replaced.

**Schema conformance.** 32 real CaseStates validated against the shipped schema, 0
violations, with the validator proven falsifiable.

**Exit-0 reachability.** Could not reach it with a maximally complete RFQ or with all four
catalog IDs pre-confirmed.

**Determinism.** 8 runs across 5 `PYTHONHASHSEED` values, 1 distinct hash per artifact; no
absolute path or timestamp in either declared artifact even when fed an absolute input path.

## Known limitations of this round

- Parity covers 9 of the engine's 37 open-item codes; a regression in a code no fixture
  reaches would pass parity (demonstrated by mutation 1). Pre-declared as FOLLOW-UP-6/7,
  so reported as measurement, not defect.
- The source's 507-test suite validates the source, not the kit's packaging. I ran it to
  check the provenance claim only.
- I did not exercise the dormant `McpKnowledge` / `TwydIngestion` paths — pre-declared
  FOLLOW-UP-1/2 — beyond proving they are never reached.
- Round-25 scope excludes engine extraction/classification correctness, so behaviours like
  `4 in OD` not capturing a size (whereas `4 in ID` does) are recorded as observations, not
  findings — and they are identical in the source.

## Verdict

**FAIL.**

The packaging work is genuinely strong: the vendoring is byte-exact, parity is a real
non-circular capture with a harness I proved can fail, the build is byte-reproducible, the
published package matches repo HEAD to the sha, offline operation is proven rather than
asserted, the anonymisation is real, and 24 of 24 adversarial inputs produce output
byte-identical to the source engine. Most of the documented numbers — the 507 tests, the
6/2/0 and 5/4/1 fixture counts, the `4 in ID` behaviour — are exactly right.

It fails on F-1. Following the kit's own recipe on the kit's own documented examples 2 and
3 produces a human-readable deliverable that hides confirmed parts, hides a certificate
requirement, and reports an open item the CaseState says is closed — and the docstring at
the root of it (F-2) claims the opposite of what the code does. That is the project's
signature failure mode, one rule in two places with one copy stale, and it lands in the
artifact a human reads before quoting a customer. F-4 is the same shape in the stale-output
guard: present in `parity_check.py`, absent in the wrapper.

Fixing F-1 requires plumbing the flags through `state.json` (record them in
`run_engine.py`'s summary, consume them in `_input_from_state`) and a fixture that runs
`generate_report.py` on a flagged input — without that fixture the defect can silently
return.
