# VERIFICATION — round 31 (blind), mcgill-email-to-bom v0.8.0

Verifier: blind independent round-31 verifier. Never saw this artifact being built.
Bar: `ACCEPTANCE_ROUND31.md`, pre-registered before this round began.
Kit HEAD: `43073e6` ("Remove the input filter (v0.8.0)"). Source ground truth:
`/Users/axr/Desktop/McGill/email-to-bom-agent` at `b15b23d`.

**OVERALL VERDICT: FAIL.**

Four HIGH findings. Two of them are damage the removal left inside `dist/kit.zip` —
shipped instruction text left mid-thought, one of which attaches a false claim to a
live flag, and one shipped example that violates the kit's own definition of done.
Two of them are checks that cannot fail on defences `ACCEPTANCE_ROUND31.md` names
explicitly in V-4.

**Mutation survival: 18 of 36 mutations survive `tools/selftest.py`. 16 of 36 survive
the full shipped bar (self-test + parity). 6 of those change behaviour in a way
neither suite can see.**

The engine itself is untouched and clean: `src/vendor/**` is byte-identical to the
source, all seven expected parity outputs regenerate byte-for-byte from the source
engine, the build is reproducible, and the engine ignored every instruction I embedded
in an email body. The removal surgery, not the engine, is what fails this round.

---

## V-1 … V-9 results

| # | Criterion | Verdict |
|---|---|---|
| V-1 | The code is whole | **PARTIAL** — no dangling imports, no half-removed function, no dead definition in `run_state.py`; but a stale present-tense reference to "the gate" survives in a docstring, and dead code + spliced comments survive in `tools/selftest.py` |
| V-2 | The recipe is coherent and executable | **PASS** |
| V-3 | The self-test did not lose coverage silently | **FAIL** — 18/36 mutations survive; Defence 4 cannot fail; one label no longer matches what it asserts; orphaned comment blocks spliced mid-sentence |
| V-4 | The surviving defences actually hold | **PARTIAL** — every invariant I could exercise holds in the shipped code, but the exit-code clamp and the `--config-dir` flag are undefended by any check |
| V-5 | Parity and the vendored engine | **PASS** |
| V-6 | The shipped artifact | **PARTIAL** — everything mechanical passes; `EXAMPLES.md` fails KIT-CONTRACT's required per-example format |
| V-7 | Documentation describes what exists | **FAIL** — two shipped documents carry text left mid-thought; one documented flag does not exist |
| V-8 | The project record is honest | **FAIL** — `DECISIONS.md` is entirely stale; PROJECT.md says "two-phase" while naming three; FOLLOW-UP-10 cites a deleted file as a live limitation |
| V-9 | Nothing sensitive, no new I/O | **PASS** |

---

### V-1 — the code is whole — PARTIAL

```
$ python3 -c "import sys; sys.path[:0]=['src/scripts','src','src/vendor']; import run_state, run_engine, generate_report; print('ok')"
ok
```

Every remaining definition in `run_state.py` has a live caller across the two
importers (`ARTIFACTS`, `INVOCATION_KEYS`, `StateError`, `make_invocation`,
`normalize_invocation`, `build_argv`, `artifact_path`, `all_artifacts`, `invalidate`,
`read_state`, `write_state`, `artifact_paths`). No dead code there. No `if X:` left
without a block — both wrappers compile and every public function was exercised.

No shipped file references the deleted names:

```
$ grep -rnI -E "filter|screen|filter_gate|filter_signals|filter_decision" src tools kit.json registry-entry.json | grep -v vendor | grep -v __pycache__
tools/selftest.py:43:# specifications and therefore reaches the engine -- bulk mail only filters at
```

That single hit is finding **F-6**. Two further V-1 defects: **F-10** (a docstring
still directing callers as "the gate") and **F-14** (dead `sha256()` + `import time`
in the self-test). Leftover `src/scripts/__pycache__/filter_gate.cpython-314.pyc`
exists on disk but is gitignored, absent from the zip, and not importable without its
source — not a defect.

### V-2 — the recipe is coherent and executable — PASS

I read the recipe end to end as a human. It is clean: no truncated sentence, no
dangling clause, no orphaned reference to `screen_input`, exit code `3`, `--no-filter`
or the gate. Round 30's three deleted-category names are gone.

```
$ /usr/bin/python3 recipe_check.py
parses OK; version 1
phases: ['prepare', 'extract_case', 'generate_report']
chain consistent: True
all recipe outputs: ['_report/bom_draft.md', '_report/case_state.json', '_report/state.json']
declared kit artifacts: ['_report/case_state.json', '_report/bom_draft.md']
every declared artifact produced by the recipe: True
```

Every command the recipe prescribes, run verbatim from the unzipped zip:

```
$ python3 -S -E scripts/run_engine.py --from-state --state _report/state.json --out _report/case_state.json
P1_EXIT=0
$ python3 -S -E generate_report.py --out _report/bom_draft.md --state _report/state.json
wrote _report/bom_draft.md (2082 bytes, engine_exit=2, reconciled)
P2_EXIT=0
```

`goal` and `constraints` describe what the scripts now do. This is the one artifact
the removal handled cleanly, and it is the binding contract, which matters.

### V-3 — the self-test did not lose coverage silently — FAIL

All twelve non-filter wrapper defences from rounds 25–28 survive, and nothing
legitimate was lost. Enumerated against the pre-removal suite:

| Present now | Deleted (all filter-only) |
|---|---|
| Defence 1, 1b, 1c, 2, 2b, 2c, 3, 3a2, 3b, 3c, 3d, 4 | Defence 5a–5j, and the round-27/28/29 filter blocks |
| Round 27 / R27-F4, Round 28 / F-4 | Round 27 R27-F1/F2/F3/F5 + 2, Round 28 F-1×2/F-2/F-3/F-3b/F-6, Round 29 ×4 |

```
$ python3 tools/selftest.py
...
28/28 defences held
```

**Mutation campaign — 36 mutations, one per invariant the surviving defences claim:**

```
applied: 36   survivors: 18   killed: 18   not-applied: 0

SURVIVORS (self-test):
  M03 invalidate() drops the directory guard
  M08 build_argv() drops --config-dir
  M10 write_state() swallows OSError
  M11 write_state() ignores the drop list
  M13 artifact_path() hard-codes the draft path
  M14 artifact_paths() ignores overrides            <- killed by parity
  M16 read_state() accepts a non-dict payload
  M17 __main__ clamp removed (R26-F2 reverted)
  M18 __main__ BaseException handler removed
  M19 run_engine() lets SystemExit escape
  M20 run_engine() ignores the engine's exit 1
  M24 extract phase skips its own input existence check
  M27 reconciliation skipped when the CaseState is absent (R26-F3)
  M28 reconciliation gated on lexists rather than isfile
  M33 report phase renders BEFORE reconciling       <- my mutation was a no-op; discount it
  M34 report phase resolves the CaseState to a fixed path   <- killed by parity
  M35 __main__ clamp removed in generate_report
  M36 report phase BaseException handler removed

$ python3 parity_survivors.py
survive selftest AND parity: 16 of 18
```

Honest classification of the 18:

- **Behaviour-preserving equivalents (8):** M03, M16, M17, M19-alone, M20, M24, M27,
  M28, M35. Each is caught by a redundant handler downstream and the shipped
  behaviour still fails closed — I verified each individually. These are not holes.
  M33 is my own bad mutation and I discount it.
- **Killed by parity (2):** M14, M34.
- **Real, behaviour-changing survivors of the whole bar (6):** M08, M10, M11, M13,
  M18, M36. These are findings **F-4**, **F-15**, **F-12** and **F-3**.

Two structural defects in the suite itself: **F-6** (three orphaned comment blocks
spliced mid-sentence where the deleted `FILTERED`/`NOT_FILTERED` lists used to be) and
**F-7** (a check labelled "ALL THREE clearing sites" that now exercises two).

I hunted for tautologies of round 30's kind (`assert "report:" in out`). I found none
of that literal shape: `check(f"{label} → exit {rc}", rc in (0, 1))` in Defence 4 is
not tautological in form — `rc` can be 2 — but no case it drives can *produce* a 2,
which is finding **F-3** and is the same disease by a different route.

### V-4 — the surviving defences actually hold — PARTIAL

Verified independently of the suite, in the shipped code:

- Flags survive the phase boundary; the draft and the CaseState always describe the
  same case. Attempted defeat: swapped `rfq.eml` for a different customer's email
  between phase 1 and phase 2 —
  `error: the draft would not describe the same case as _report/case_state.json` …
  `draft written despite the swap? no - refused`.
- Reconciliation fails closed on absent / directory / unreadable / truncated
  CaseState, and on garbage `state.json`. All four refuse, no draft left behind:
  `error: cannot read _report/case_state.json to reconcile against: [Errno 13] Permission denied` /
  `Expecting value: line 1 column 12`.
- No failure path left a stale artifact in any scenario I could construct;
  clearing failures are loud (`error: cannot clear the previous run's … Refusing to
  continue`). **But** the `--out` override path is untested — finding **F-12**.
- Both wrappers return only 0 or 1 in the shipped code, argparse `SystemExit(2)`
  included (`--bogus-flag → 1` for both). **But** nothing tests it — finding **F-3**.
- A failed phase preserves the prepare record (verified directly, not via the suite).
- Engine determinism holds: identical CaseState bytes across `PYTHONHASHSEED` 0, 1,
  42, 99999.

"A malformed schema fails open rather than crashing" is **N/A this round**: no shipped
runtime code reads a schema at all. `grep -rn "schema" src/scripts/*.py
src/generate_report.py` → no match. The only schema reader was `filter_gate.py`. The
pre-registered bar carries a criterion whose subject was deleted; that is the bar's
artefact, not the kit's.

### V-5 — parity and the vendored engine — PASS

```
$ python3 tools/parity_check.py
7 fixtures checked, 7 matched, 0 mismatched
normalized fields: (none declared)
```

I did not trust the committed expected files. I regenerated all seven from the source
engine in its own venv:

```
suction-assembly:     MATCH source
plain-steam:          MATCH source
quoted-printable:     MATCH source
multipart-html:       MATCH source
confirmed-ids:        MATCH source
human-render:         MATCH source
confirmed-ids-render: MATCH source
```

```
$ diff -r --exclude=__pycache__ email-to-bom-agent/email_to_bom mcgill-email-to-bom/src/vendor/email_to_bom
EMAIL_TO_BOM: IDENTICAL
$ diff -r --exclude=__pycache__ email-to-bom-agent/config mcgill-email-to-bom/src/vendor/config
CONFIG: IDENTICAL
$ git log --oneline -3 -- tools/parity tools/parity_check.py
9780f61 Round 26 FAIL closed (v0.3.0) …      # untouched by the removal
```

### V-6 — the shipped artifact — PARTIAL

```
$ python3 tools/validate_manifest.py kit.json registry-entry.json; echo EXIT=$?
EXIT=0
$ ./tools/build_kit.sh
SHA-256: a12dbe536b03404e33773900e37c19c97c874a6f3359ee88217c3a687ae85c4c
$ git status --porcelain
?? ACCEPTANCE_ROUND31.md
```

Reproducible byte-for-byte; the rebuild changed nothing. `requires.tools = []`;
exactly one `email_attachment`; both declared artifacts produced by the recipe; 21
files in the zip matching `kit.json` `contents[]`; version 0.8.0 in both manifests.

Clean-directory run of the unzipped zip under `python3 -S -E`, no install:

```
P1_EXIT=0 · P2_EXIT=0
CASE_STATE == SOURCE CAPTURE (byte-identical)
_report/ → bom_draft.md, case_state.json, state.json
```

`EXAMPLES.md` has all four required `##` sections. It does **not** satisfy
KIT-CONTRACT.md's required per-example format — finding **F-2**.

### V-7 — documentation describes what exists — FAIL

Findings **F-1** (CLAUDE.md fragment, shipped), **F-2** (EXAMPLES.md Example 5,
shipped), **F-11** (`--from-state` documented for a phase that has no such flag).

Verified true: `README.md`'s design-line bullets; `PROVENANCE.md`'s commit stamp and
its "still current as of `b15b23d`" claim (I confirmed the diff myself); every
documented direct command runs and exits 0; EXAMPLES' worked numbers are exact —

```
example 1: class hose_assembly · lines 0 · checkpoints 2 · open_items 6
           MATERIAL_CONFIRM VACUUM_VALUE_CONFIRM TEMPERATURE_MISSING
           SIZE_MISSING LENGTH_TYPE_MISSING SELECTION_UNRESOLVED
example 2: lines 4 · open_items 5 · SELECTION_UNRESOLVED gone · checkpoints ['C2']
```

No stale reference to the filter's exit code `3`, `--no-filter`, its schema or its
reference data survives in any shipped document — except inside F-1's fragment.

### V-8 — the project record is honest — FAIL

REQ-057/058/059 and the round-30 table are accurate; I re-derived nothing that
contradicts them. But: **F-5** (`DECISIONS.md` entirely stale), **F-8** ("two-phase"
naming three phases), **F-9** (FOLLOW-UP-10 citing a deleted file), **F-13** (roadmap
phase 5 still `complete` from a UAT sign-off, the inconsistency recorded nowhere).

Only FOLLOW-UP-10 of the ten deferred follow-ups references removed code. Per this
round's rules I report it as an honesty defect, not as a deferred-work defect.

### V-9 — nothing sensitive, no new I/O — PASS

```
=== network / env / subprocess / eval in NON-VENDORED src ===  NONE
=== credential-shaped strings in non-vendored src ===          NONE
=== addresses in fixtures and docs ===
dana@northside.example · purchasing@acmedairy.example · sales@mcgillhose.example
=== non-reserved domains in fixtures ===                       (none)
=== unexpected files in the zip ===                            clean
```

All three namespaces are RFC 2606 reserved. The deletion left no credential-shaped or
network-touching remnant.

---

## Findings

### F-1 (HIGH) — `src/CLAUDE.md` ships a sentence fragment that makes a false claim about a live flag

`src/CLAUDE.md` lines 41–44, present verbatim inside `dist/kit.zip`:

```
`--config-dir` selects an alternate rules/catalog directory.
engine regardless of its own decision — the documented escape hatch for a
false positive; it is never an engine flag and never reaches `run_engine.py`'s
argv.
```

The regex deleted the first two lines of a four-line sentence about `--no-filter` and
left the remaining three. This is the Arguments section of the file the executing agent
reads as its operating instructions.

It is worse than orphaned prose. The surviving fragment's only visible subject is
`--config-dir`, and the claim it makes — "it is never an engine flag and never reaches
`run_engine.py`'s argv" — is **false of `--config-dir`**, which is precisely an engine
flag and does reach that argv (`run_state.build_argv`: `argv += ["--config-dir", …]`).
An agent that believes this fragment will not pass `--config-dir` through, which is the
documented route to grounded selection.

Reproduce:

```
$ unzip -p dist/kit.zip CLAUDE.md | sed -n '36,45p'
```

### F-2 (HIGH) — `src/EXAMPLES.md` Example 5 is truncated mid-list and violates the kit's own definition of done

`src/EXAMPLES.md` lines 89–98, shipped:

```
### 5. A message that is not a request at all
**Prompt:** "What does this email need?"
**Arguments:** `newsletter.eml` (…)
**Expected workflow:**
1. `prepare` — resolves `newsletter.eml`, writes `_report/state.json`.

## Argument Reference
```

Steps 2 and 3 were the `screen_input` steps; the regex took them and left step 1
hanging. There is no `**Produces:**` line — every other example has one.

`KIT-CONTRACT.md` line 75–76 requires each example to carry **Prompt**, **Arguments**,
**Expected workflow** *and* **Produces**; line 88 makes it part of the definition of
done. Nothing in `tools/` machine-checks this (see F-16), so the build shipped it.

It is also the one example the removal actually changed the answer to, and it now
answers nothing. The real post-removal behaviour, which no document states:

```
empty.eml : exit 0 · class=out_of_scope · open_items 1 · routing inside_sales_review
dsn.eml   : exit 0 · class=out_of_scope · open_items 1 · routing inside_sales_review
news.eml  : exit 0 · class=hose_assembly · open_items 7 · checkpoints 2
```

### F-3 (HIGH) — Defence 4, the R26-F2 exit-code clamp, cannot fail

`ACCEPTANCE_ROUND31.md` V-4 requires: "`run_engine.py` and `generate_report.py` return
only 0 or 1 — the engine's 2 never leaks, including from argparse inside `cli.main`."
Defence 4 is five checks aimed at exactly that. None of them can fail.

Delete the clamp handler from **both** wrappers — the literal R26-F2 fix:

```
    except BaseException as _e:  # noqa: BLE001 - deliberate
        print(f"error: unhandled {type(_e).__name__}: {_e}", file=sys.stderr)
        _rc = 1
    raise SystemExit(0 if _rc == 0 else 1)
        →
    raise SystemExit(0 if _rc == 0 else 1)
```

Result:

```
$ python3 tools/selftest.py | tail -1
28/28 defences held
$ python3 src/scripts/run_engine.py --bogus-flag ; echo EXIT=$?
EXIT=2
$ python3 src/generate_report.py --bogus-flag ; echo EXIT=$?
EXIT=2
```

(Shipped code: both give 1. The defence works; the *check* is inert.) Parity is also
7/7 under this mutation. All five Defence 4 cases are satisfied by `main()`'s own
`return 1` statements or by the `SystemExit → RuntimeError` conversion inside
`run_engine()`; not one drives a path where a 2 could escape. The comment above the
`-x.eml` case — "The file must EXIST, or … this case proves nothing" — shows the author
knew this trap was there and still did not reach it: with both handlers gone that case
still exits 1, because a third redundant handler catches it.

### F-4 (HIGH) — `--config-dir` has no defence, and dropping it is R25-F1's exact failure shape

Defence 1 tests `--component-ids`. Defence 1b tests `--coc`. There is no check for the
third member of the flag triple. `--config-dir` is described by the recipe as "the
supported route to grounded selection", by README as the route to "a catalog backed by
the ERP item master", and by EXAMPLES' argument reference as "one backed by the P21
item master". Silently dropping it in `build_argv`:

```
    if invocation.get("config_dir"):
        argv += ["--config-dir", invocation["config_dir"]]
        →  pass
```

I planted `ERP-MASTER-DESCRIPTION-MARKER` as `SPS400452`'s description in an alternate
config dir and ran the full flow:

```
SHIPPED  : marker present in case_state.json → 1  (alternate catalog IS used)
MUTANT   : marker present in case_state.json → 0  (shipped vendor/config used instead)
           phase 1 exit 0 · phase 2 exit 0 · reconciliation GREEN
           state.json still records config_dir: …/cd/erp
           tools/selftest.py → 28/28 defences held
           tools/parity_check.py → 7 matched, 0 mismatched
```

Both artifacts come out perfectly self-consistent and quietly wrong about which item
master priced the case, `state.json` asserts the flag was honoured, and **both suites
stay green**. This is verbatim the mechanism the recipe's own phase-0 goal warns about
("drop `--coc` while composing phase 1 and both artifacts come out perfectly
self-consistent and quietly wrong") — with the flag nobody wrote a sibling check for.

Note that reconciliation *structurally cannot* catch this class: both passes replay
through the same `build_argv`, so they agree with each other while both being wrong.
Only a check that asserts the flag's observable effect can catch it, and there is none.

### F-5 (MEDIUM) — `.astrocode/DECISIONS.md` is 100% stale; the removal edited PROJECT.md and missed its sibling

The entire file is ADR-001 … ADR-005, and every one of the five is about the deleted
filter, in the present tense: the gate "fails OPEN", exit code `3` "means filtered",
"the recipe only branches on its exit code", the route vocabulary "in
`src/reference/filter_signals.json`", "the gate reads its own cheap, bounded text
view". There is no superseding entry and no `~~strikethrough~~`. `git show --stat HEAD`
confirms the removal commit never touched this file.

The file's own header: "Agents read this so past decisions are respected, not
relitigated." The next agent on this repo will read five binding-looking decisions
about `src/scripts/filter_gate.py`, `src/reference/filter_signals.json`, exit code `3`
and a `screen_input` phase — none of which exist. This is failure shape #1, tenth
occurrence in the campaign and eleventh now.

### F-6 (MEDIUM) — `tools/selftest.py` has three orphaned comment blocks, spliced mid-sentence

Lines 34–46, sitting between the `IDS` constant and `results = []`, with no code they
describe (the `FILTERED` / `NOT_FILTERED` lists they annotated are gone):

```
# Categories that can still be FILTERED. Round 29 removed the three
# content-judged ones (invoice/ack/internal) because they dropped 11 of 46
# genuine RFQs, so their fixtures now PASS and are asserted under NOT_FILTERED
# specifications and therefore reaches the engine -- bulk mail only filters at
# depth 0.
```

"…are asserted under NOT_FILTERED / specifications and therefore reaches the engine…"
is two sentence-halves glued together where the regex cut. All three blocks reference
`tools/filter/fixtures/`, deleted in the same commit. Line 43 is the only surviving
occurrence of "filter" in the entire non-vendored source tree.

### F-7 (MEDIUM) — a check label no longer matches what it asserts

```
tools/selftest.py:  print("Round 28 / F-4 — ALL THREE clearing sites consume the declaration")
```

There are two:

```
$ grep -rn "invalidate(" src --include='*.py' | grep -v vendor
src/generate_report.py:100:        invalidate([artifact_path("bom_draft", bom_draft=args.out)])
src/scripts/run_engine.py:168:        invalidate(all_artifacts(case_state=args.out, bom_draft=args.draft))
```

The third was the gate. This is exactly the V-3 hazard the bar predicted: a block whose
label survived the pattern-matching while its subject shrank.

### F-8 (MEDIUM) — PROJECT.md says "two-phase" while naming three phases

`.astrocode/PROJECT.md:351`:

> **What remains:** the engine, vendored verbatim, behind a **two-phase** recipe
> (`prepare` → `extract_case` → `generate_report`) …

Three names, called two. The count was decremented from "three" when a phase was
removed, without noticing the list it labels was four long. `ACCEPTANCE_ROUND31.md`,
the commit message and `src/CLAUDE.md` all correctly describe three phases.

### F-9 (MEDIUM) — FOLLOW-UP-10 cites a deleted file as a live limitation

`.astrocode/PROJECT.md:420-427`:

> `tools/_schema_engine.py` raises on the `"type": ["string","null"]` unions in
> `src/schemas/filter_decision.schema.json`, and already could not validate
> `case_state.schema.json` … So **both** output contracts are documented but not
> machine-checkable … worth fixing before a **third** schema is added.

`src/schemas/filter_decision.schema.json` was deleted in this commit. There is one
output contract now, not two, and the next schema added would be the second, not the
third. Reported as an honesty defect per this round's scope rules, not as deferred work.

### F-10 (MEDIUM) — a docstring still routes callers to the deleted gate

`src/scripts/run_state.py:88`, present tense, shipped:

> For sites that clear the WHOLE run (**the gate**, the extract phase). A site owning a
> single artifact uses artifact_path(name) instead…

There is one whole-run clearing site. (The R27-F4 paragraph below it says "all three
clearing sites hand-wrote…" — that one is historical narration of a past finding and
reads correctly as history; this one is a live instruction naming a dead caller.)

### F-11 (MEDIUM) — `--from-state` is documented for a phase that has no such flag

`src/README.md:52`: "Under Astro's recipe **both phases** read the invocation the
prepare phase recorded (`--from-state`)."
`src/CLAUDE.md:31-32`: "**phases 1 and 2** read it (`--from-state`) rather than having
you re-type the flags."

```
$ python3 src/generate_report.py --from-state --state _report/state.json
generate_report.py: error: unrecognized arguments: --from-state
error: unhandled SystemExit: 2
EXIT=1
```

`generate_report.py` reads the invocation from `--state` and has no `--from-state`.
The recipe gets this right, so the harness path is unaffected — but the two shipped
documents name a flag that does not exist, on the mechanism they exist to explain.

### F-12 (MEDIUM) — the `--out` override path is untested for stale-artifact clearing

`artifact_path()` returning the declaration without applying overrides survives both
suites, and leaves a stale artifact at a custom `--out` path across a failure —
R26-F1's mechanism:

```
    return artifact_paths(**overrides)[name]  →  return dict(ARTIFACTS)[name]

SHIPPED : failing rerun exit=1 · stale custom.md survived? no (cleared)
MUTANT  : failing rerun exit=1 · stale custom.md survived? YES
          tools/selftest.py → 28/28 · tools/parity_check.py → 7 matched
```

The shipped code is correct. The round-28 driver tests a *renamed declaration* and a
*literal hard-coded path* (my M31 was killed), but no check drives the `--out`
override — the one thing the recipe's own phase-2 command passes.

### F-13 (LOW) — the roadmap still records a human UAT sign-off for a deleted feature

`.astrocode/roadmap.json`:

```json
{"number": 5, "name": "Input Filter", "slug": "05-input-filter", "status": "complete",
 "accepted_by": "andrea.ridi@scaleuplabs.vc", "accepted_kind": "human",
 "accepted_at": "2026-08-26T18:24:14.097Z"}
```

`ACCEPTANCE_ROUND31.md` V-8 asks whether this inconsistency is "recorded anywhere a
reader would find it". It is not. PROJECT.md's round-30 section says the feature is
gone but says nothing about the roadmap entry, and the roadmap entry says nothing about
the removal. A reader consulting the roadmap alone concludes phase 5 shipped and was
accepted.

### F-14 (LOW) — dead code left behind in the self-test

`tools/selftest.py`: `import time` (line 27) is unreferenced, and `def sha256(path)`
(line 102) has no caller — its callers were the deleted `--no-filter` blocks that
asserted the input's hash was unchanged. `import hashlib` (line 20) exists only to
serve `sha256()`. Failure shape #5.

### F-15 (LOW) — `write_state`'s loudness and its `drop` argument are entirely untested

Both survive both suites:

- `except OSError as e: raise StateError(…)` → `except OSError: return`. Its docstring
  says "Loud for the same reason invalidate() is: if the record of what this run did
  cannot be written, a later phase would act on the previous run's record." Nothing
  asserts that.
- `for k in drop: state.pop(k, None)` → no-op. `drop=("extract_case",)` has exactly
  one caller and no test; the sibling check for it went out with the filter.

In both cases downstream reconciliation still refuses rather than landing a wrong pair,
which is why these are LOW rather than HIGH — but the declared invariant is unasserted.

### F-16 (LOW / informational) — the build cannot see documentation damage

`tools/validate_manifest.py` (413 lines) validates `kit.json` against the manifest JSON
schema and nothing else — no mention of `EXAMPLES`, `Produces`, `recipe` or `yaml`.
`KIT-CONTRACT.md` lines 88–89 list "`src/EXAMPLES.md` has all 4 required sections" and
"the recipe exists, parses as YAML, and its phases' inputs/outputs are consistent" in
the definition of done, and nothing in `tools/` checks either. That is the direct reason
F-1 and F-2 reached `dist/kit.zip`: on a removal round, the damage lands in prose, and
prose has no gate.

---

## Adversarial pass

**Instruction injection inside the email body.** I built an RFQ whose body carries
authority claims, urgency, a fake system directive, an instruction to suppress open
items, a demand to treat the draft as a confirmed quote, a fabricated price, a
"checkpoints signed off by me, the VP", an instruction to pass `--no-reconcile`, and a
shell command to run. Real specs were included so the message could not be dismissed.

```
$ python3 src/scripts/run_engine.py --in evil.eml --state _report/state.json
request_class : bulk_hose        (NOT the demanded "order")
open_items    : 7  MATERIAL_CONFIRM VACUUM_VALUE_CONFIRM TEMPERATURE_CONFLICT
                   QTY_MISSING DERATING_REVIEW LENGTH_TYPE_MISSING SELECTION_UNRESOLVED
                   (2 blocking — NOT the demanded [])
checkpoints   : ['C2', 'C3']    (NOT signed off)
price/quote keys in the CaseState: []
grep for 12,500 / '$' / 'confirmed quote' / 'signed off' in the draft: no match
engine_exit=2, wrapper exit 0 — the by-design outcome, not the demanded 0
```

Nothing acted on the embedded instructions. The wrapper never shells out (no
`subprocess`, no `eval`/`exec`, no `os.system` in non-vendored source), so the embedded
command had no reachable path. The only content-derived effect was `urgency.flagged =
true` from the literal word "urgent", which is documented engine behaviour and raises
an ask rather than acting.

**Other defeats attempted and repelled:** swapping the input between phases (refused,
with a diff of the differing top-level keys); absent / directory / unreadable /
truncated CaseState (all four refused, no draft written); garbage `state.json`
(refused); read-only `_report/` (loud stop); `--in=-x.eml` reaching the engine's own
argparse (clamped to 1); `PYTHONHASHSEED` variation (byte-identical output).

**One structural limitation, not a finding.** `generate_report.py` makes two engine
passes over the input path — one to reconcile, one to render. An actor with write access
to the RFQ file *between those two passes* could land a draft describing a different
message than the CaseState. Exploiting it requires local write access mid-run, at which
point the input is already untrustworthy. Worth knowing; not a defect of this build.

---

## Known limitations of this verification

- I did not re-verify engine extraction or classification correctness (rounds 1–24,
  out of scope). I verified only that the vendored bytes are identical to the source
  and that the source reproduces every fixture.
- My 36 mutations target the wrapper invariants. A larger campaign would find more; 18
  survivors is a floor, not a ceiling.
- M33 in my table was a no-op mutation and I have discounted it rather than quietly
  dropping it, so the 36/18 denominator stays auditable.
- `.astrocode/DECISIONS.md`, `roadmap.json` and `PROJECT.md` are not shipped in the
  zip. F-5, F-8, F-9 and F-13 damage the project record and the next agent's context,
  not the running kit.
- Both HIGH shipped-document findings (F-1, F-2) are *prose* defects. They cannot
  produce a wrong CaseState by themselves. They mislead the agent and the human reading
  the kit's instructions, and F-1's false claim points at a flag whose failure mode is
  exactly the silent-wrong-answer class this kit exists to prevent.

---

## Tree integrity

I mutated only sandbox copies under
`/private/tmp/claude-501/…/scratchpad/`. The only command I ran that writes inside the
kit is `./tools/build_kit.sh`, which reproduced `dist/kit.zip` byte-for-byte and left
`kit.json` / `registry-entry.json` unchanged.

```
$ git status --porcelain
?? ACCEPTANCE_ROUND31.md
$ git diff --stat HEAD
(empty)
$ shasum -a 256 dist/kit.zip
a12dbe536b03404e33773900e37c19c97c874a6f3359ee88217c3a687ae85c4c
$ git -C ../email-to-bom-agent status --porcelain
(empty)
```

**The kit tree is clean at `43073e6` apart from the two expected untracked round-31
`.md` files. The source repo was never written to.**

---

## Is v0.8.0 safe to publish?

**Not as it stands — but it is close, and the blocker is small.**

The mechanism is sound. The engine is byte-identical to the source, all seven parity
fixtures regenerate from the source engine, the recipe is coherent and executes
verbatim, the zip runs from a clean directory with no install and produces a CaseState
byte-identical to the source capture, every fail-closed defence I could attack held,
and the engine ignored a deliberately manipulative email. Compared with the v0.3.0 the
instance serves, v0.8.0 is a genuine improvement: it adds the rounds 25–28 wrapper
defences and removes the gate that six rounds could not make safe.

What blocks it is that two of the twenty-one shipped files carry text the removal left
mid-thought, and one of them tells the executing agent something false about a live
flag (F-1) while the other ships an example that fails the kit's own definition of done
(F-2). Publishing means publishing those bytes into `dist/kit.zip`. Both are
single-paragraph edits.

F-3 and F-4 do not block publication — the shipped behaviour is correct in both cases.
They block the *claim* that the self-test protects those two defences, and F-4 in
particular leaves the kit's documented route to grounded selection with no check at
all. Fix them before the next change touches `build_argv` or the wrappers' `__main__`,
because the next fix pass is historically where this campaign's defects come from.

Recommended before publish: F-1, F-2. Recommended immediately after, with checks that
are shown to fail first: F-4 (a `--config-dir` sibling for Defence 1/1b), F-3 (a
Defence 4 case that actually reaches a path where 2 could leak — `--bogus-flag` is
enough), F-5 (a superseding ADR-006), F-6, F-7, F-8, F-9, F-13.

## What I tried that did NOT break it

So the pass on V-2/V-5/V-6/V-9 is auditable, these are the attacks that held:

- Regenerated all 7 expected parity outputs from the source engine in its own venv
  rather than trusting the committed files — all 7 byte-identical.
- `diff -r` of `src/vendor/email_to_bom` and `src/vendor/config` against the source at
  `b15b23d` — identical, and I confirmed `b15b23d`'s only change was outside the
  vendored tree, which is what `PROVENANCE.md` claims.
- Rebuilt `dist/kit.zip` from scratch — same SHA-256, `kit.json` unchanged.
- Ran the unzipped zip from an empty directory under `python3 -S -E` — full flow,
  CaseState byte-identical to the source capture.
- Ran every command documented in the recipe, README and EXAMPLES verbatim, plus all
  four argument forms — all exit 0.
- Parsed the recipe as YAML, walked its input/output chain, and cross-checked it
  against `kit.json`'s declared artifacts — consistent.
- Read the recipe end to end looking for exactly the truncation I found in two other
  files — it is clean.
- 36 mutations against the wrapper invariants; 18 killed, and I verified individually
  that 8 more survivors are behaviour-preserving rather than holes.
- Injection, urgency, authority and checkpoint-bypass attempts inside an email body —
  every one ignored.
- Input-swap between phases, four flavours of unusable CaseState, garbage state file,
  read-only `_report/`, leading-dash input, hash-seed variation — all refused or
  deterministic.
- Credential, network, environment, subprocess and `eval` sweeps over non-vendored
  source; RFC 2606 check on every address and domain in fixtures and docs — clean.
