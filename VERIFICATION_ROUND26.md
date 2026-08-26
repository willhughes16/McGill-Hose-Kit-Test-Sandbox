# VERIFICATION — ROUND 26 (blind independent verifier)

Artifact: `/Users/axr/Desktop/McGill/mcgill-email-to-bom` @ `d9058a5` (tree clean at start
and at end; only `?? ACCEPTANCE_ROUND26.md` untracked).
Source of truth: `/Users/axr/Desktop/McGill/email-to-bom-agent` @ `b15b23d` (clean, read-only).
Bar: `ACCEPTANCE_ROUND26.md` — Part A `W-1..W-7`, Part B `V-1..V-12`, pre-registered.
Round 25's report was read; the build conversation was not available and was not sought.

**OVERALL VERDICT: FAIL.**

Round 25's headline defect (F-1, flags dropped between phases) is genuinely fixed and the
new fixture that guards it is genuinely falsifiable. But the round-25 fix pass repeated
this project's signature failure twice more:

* it hardened `case_state.json` against stale-artifact survival and left the **other
  declared artifact**, `bom_draft.md` — the human deliverable F-1 was about — completely
  unguarded, so a failed run now leaves the previous customer's BOM sitting alone in
  `_report/` with the machine record that would have contradicted it deleted (**R26-F1,
  HIGH**);
* refactoring the engine call **removed** the `except SystemExit` that v0.1.1 had, so both
  wrappers now exit **2** with empty stdout, empty stderr and no artifact — exit 2 being
  the one code every document in the kit tells the reader to treat as normal success
  (**R26-F2, MEDIUM-HIGH**, and it is a regression, proven against `0119689`).

Two of the three new defences also have zero regression coverage: I deleted the
reconciliation guard and the stale-clearing call, one at a time, and the full 7-fixture
suite stayed green.

Every mutation I made was restored; `git status --porcelain` is back to
`?? ACCEPTANCE_ROUND26.md`, `git diff --stat` empty, `dist/kit.zip` sha256 unchanged at
`3db7a61946f9cbca58ca5633ecb0805027f420373db0f906a18e68e3ef6b5bfb`, and
`src/vendor/` re-diffed byte-clean against the source afterwards.

---

## Results table

| # | Check | Verdict |
|---|---|---|
| W-1 | F-1 invocation contract | **PARTIAL** — flag plumbing genuinely fixed across 12 permutations; artifacts can still describe different cases by other routes |
| W-2 | Reconciliation guard | **FAIL** — fires correctly and names the diverging keys, but fails open (exit 0) whenever the CaseState path is not a regular file |
| W-3 | F-4 stale artifacts | **FAIL** — `bom_draft.md` is never cleared; clearing failures are silently swallowed |
| W-4 | New fixture is falsifiable | **PASS** — proven two independent ways |
| W-5 | Did the fixes introduce new defects | **FAIL** — silent exit-2 regression; undisclosed 3x runtime |
| W-6 | The fixes are honestly described | **FAIL** — REQ-025 and "unshippable" are false; stale fixture counts; schema byte-identity claim is TRUE |
| W-7 | Rename left nothing dangling | **PASS** |
| V-1 | Parity real and falsifiable | **PASS** (7/7, no normalization, 3 mutations) |
| V-2 | Parity not circular | **PASS** (all 7 regenerated from the source venv) |
| V-3 | Vendored engine verbatim | **PASS** |
| V-4 | No second copy of an engine rule | **PASS** (upgrade from round 25's PARTIAL — see below) |
| V-5 | Self-contained and offline | **PASS** |
| V-6 | Exit-code contract | **FAIL** — see R26-F2 |
| V-7 | Kit contract compliance | **PASS** |
| V-8 | Documentation makes no false claim | **FAIL** — runtime table + "unshippable" |
| V-9 | Determinism | **PASS** |
| V-10 | Nothing sensitive ships | **PASS** |
| V-11 | Published package matches repo | **PASS** (sha reproduced exactly; server side unverifiable without credentials) |
| V-12 | Recipe constraints coherent | **PARTIAL** |

---

# PART A

## W-1 — the invocation contract — PARTIAL

**The recipe's own two-phase path, phase 2 flagless exactly as written.** Run against the
unzipped `dist/kit.zip` from an unrelated working directory:

```
$ python3 $Z/scripts/run_engine.py --in raw/rfq.eml --out _report/case_state.json \
      --state _report/state.json --component-ids "OPW 633C A" "OPW 633E A" "SPS400452" "HOS-064 300 EPDM"
{ "case_state": "_report/case_state.json", "engine_exit": 2, "request_class": "hose_assembly",
  "open_items": 5, "checkpoints": 1, "bom_lines": 4, "knowledge_source": "none" }
EXIT=0

$ cat _report/state.json
{ "invocation": { "input": "raw/rfq.eml",
                  "component_ids": ["OPW 633C A","OPW 633E A","SPS400452","HOS-064 300 EPDM"],
                  "coc": false, "config_dir": null },
  "extract_case": { ... "bom_lines": 4 ... } }

$ python3 $Z/generate_report.py --out _report/bom_draft.md --state _report/state.json
wrote _report/bom_draft.md (2196 bytes, engine_exit=2, reconciled against _report/case_state.json)
EXIT=0
```

The draft now carries all **4 BOM lines**, **1 checkpoint (C2)** and **5 open items** — no
empty table, no phantom `SELECTION_UNRESOLVED`. Round 25's F-1 is closed on this path.

**Attack — 12 invocation permutations, comparing draft vs CaseState mechanically** (BOM row
count, ordered open-item code list, checkpoint ids, presence of the `Classes:` line):

```
empty --component-ids (flag, no values)      AGREE  cs(lines=0 items=6) draft(lines=0 items=6)
non-matching IDs ("NOPE-1","ZZZ 999")        AGREE  cs(lines=0 items=7) draft(lines=0 items=7)
unusual flag order, --coc last->first        AGREE  cs(lines=3 items=5) draft(lines=3 items=5)
absolute --in, same cwd, --coc               AGREE  cs(lines=1 items=6) draft(lines=1 items=6)
IDs containing a quote and non-ASCII         AGREE  cs(lines=1 items=7) draft(lines=1 items=7)
--config-dir <alternate dir> + ids           AGREE  cs(lines=1 items=5) draft(lines=1 items=5)
--config-dir relative + phase 2 other cwd    exit 1, loud: "cannot load config from cfg"
absolute --in + phase 2 from another cwd     exit 0 but UNRECONCILED (see W-2); draft correct
relative --in + phase 2 from another cwd     exit 1, loud: "no such RFQ file"
phase 2 given --in only (flags dropped)      exit 1, guard fires, names the keys
old-format state.json (real v0.1.1 specimen) exit 1, "no usable invocation recorded"
state.json invocation.component_ids a string exit 1, guard fires, shows the mangled argv
state.json invocation.input = 42             exit 1, "no such RFQ file: 42"
```

`--config-dir` is now genuinely plumbed end to end and recorded in `state.json` — round
25's F-6 is closed. The engine CLI accepts exactly four inputs (`email`,
`--component-ids`, `--coc`, `--config-dir`, plus `--json`), all four of which the recorded
invocation carries, so there is no *fourth flag* left to drop.

**Why PARTIAL.** The bar asks for *any* invocation where the two artifacts still disagree.
Flag drop is fixed, but I produced a divergent pair twice by other routes — R26-F1 (stale
draft survives a failure) and R26-F3 (guard fails open) — and one residual place where the
invocation is still expressed twice with nothing reconciling it: the phase-0 → phase-1
boundary (R26-F6).

## W-2 — the reconciliation guard — FAIL

**It fires, and it names the diverging keys.** Genuine divergence, phase 2 handed `--in`
without the flags phase 1 used:

```
error: the draft would not describe the same case as _report/case_state.json.
       Replaying the recorded invocation produced a DIFFERENT CaseState, ...
       invocation replayed: {"input": "raw/rfq.eml", "component_ids": [], "coc": false, ...}
       differing top-level keys: ['checkpoints', 'lines', 'open_items', 'questions', 'routing']
EXIT=1   (no draft written)
```

It also fires on a hand-edited `case_state.json` (`differing top-level keys: ['lines']`) and
on the input file changing between phases (`['checkpoints','classes','extraction','fields',
'lines','open_items','questions','routing']`). The comparison is structural JSON, so
whitespace and key order cannot fool it.

**Fail-open hunt — six states of `case_state.json`:**

```
absent                     -> warning on stderr, DRAFT WRITTEN, EXIT=0
a directory in its place   -> warning on stderr, DRAFT WRITTEN, EXIT=0
--case-state /dev/null     -> warning on stderr, DRAFT WRITTEN, EXIT=0
empty (0 bytes)            -> EXIT=1  "cannot read ... Expecting value"
truncated mid-file         -> EXIT=1  "Unterminated string starting at: line 122"
not JSON at all            -> EXIT=1  "Expecting value"
unreadable (chmod 000)     -> EXIT=1  "[Errno 13] Permission denied"
```

The four "not a regular file" states fail open. `generate_report.py:132` gates the whole
defence on `os.path.isfile(case_path)`; the `else` branch prints a warning and continues.
Rated as **R26-F3, MEDIUM** — with a demonstrated case where it emits a draft describing a
different email than the CaseState on disk.

**False positives:** none found. Across ~20 legitimate invocations (every permutation
above, repeated phase-2 runs, alternate config dirs, `PYTHONHASHSEED` variation, an empty
environment) the guard never fired wrongly. It is exact-equality against a deterministic
engine, which is the right construction.

## W-3 — stale artifacts — FAIL

`case_state.json` and `state.json` are handled. The **other declared artifact is not**:

```
run 1  (email A, flagged)  -> _report/{case_state.json, state.json, bom_draft.md}
run 2  phase 1, typo'd path:
       error: no such RFQ file: raw/steam_rfq.eml           EXIT=1
       _report/ now: bom_draft.md (2210 B, email A) + state.json == {}
       case_state.json: correctly gone
run 2  phase 2 (recipe command):
       error: no RFQ input given and no usable invocation recorded    EXIT=1
       _report/bom_draft.md: STILL email A, untouched
```

See **R26-F1** for the sharper reproduction (a `case_state.json` for one customer sitting
beside a `bom_draft.md` for another).

**Hostile environments:**

```
read-only _report/ (chmod 555), then a failing run:
   unlink of the stale case_state.json fails -> swallowed by `except OSError: pass`
   -> stale case_state.json SURVIVES; state.json emptied; EXIT=1
read-only state.json (chmod 444), then a failing run:
   case_state.json deleted, but the state.json rewrite fails -> swallowed
   -> state.json STILL points at raw/rfq.eml with extract_case intact
   -> phase 2 then: warning: _report/case_state.json not found ... EXIT=0
      *** a successful-looking phase 2 emitting the PREVIOUS email's draft ***
case_state.json is a directory:      failing run EXIT=1; good run EXIT=1 "Is a directory"
two phase-1 runs racing (5 trials):  state.json and case_state.json agreed every time;
                                     phase 2 reconciled clean. Could not break it.
```

Failure *during* the write: both wrappers build the payload fully in memory and write once,
so there is no partial-artifact window; the unwritable-output cases all exit 1 with nothing
on disk (see V-6).

## W-4 — the new fixture is falsifiable — PASS

Three mutations, each restored immediately with `git checkout`/backup copies.

**M1 — reintroduce F-1** (`state["invocation"] = {"input": invocation["input"]}`):

```
confirmed-ids-render: MISMATCH missing-output
7 fixtures checked, 6 matched, 1 mismatched     EXIT=1
```

**M3 — reintroduce F-1 *and* neuter the guard** (`if False and on_disk != replayed:`) — this
is the important one, because it proves the fixture catches the *defect*, not merely the
guard's exit code:

```
confirmed-ids-render: MISMATCH render
7 fixtures checked, 6 matched, 1 mismatched     EXIT=1
```

**M2 — neuter the guard ONLY:**

```
7 fixtures checked, 7 matched, 0 mismatched     EXIT=0
```

**M4 — remove the stale-clearing call** (`_discard_stale(args.out)` -> `pass`):

```
7 fixtures checked, 7 matched, 0 mismatched     EXIT=0
```

So W-4 itself passes — `confirmed-ids-render` is a real regression guard for F-1 — but M2
and M4 are **R26-F4**: two of the three round-25 defences can be deleted outright with the
suite fully green, in a project whose own `CONVENTIONS.md` says "A fixture that has never
failed has proven nothing."

## W-5 — did the fixes introduce new defects — FAIL

**The exit-code contract regressed.** `run_engine.run_engine()` used to catch `SystemExit`
(the round-25 code at `0119689` did `except SystemExit as e: print(...); return 1`). The
refactor replaced it with a `RuntimeError`, and only `RuntimeError` is caught now — so an
`argparse` rejection *inside* `cli.main` escapes, and because the call is wrapped in
`contextlib.redirect_stderr`, the usage message is swallowed too. Side-by-side, same input,
a file whose name begins with `-`:

```
ROUND-25 wrapper (0119689):  EXIT=1   stderr: [error: 2]
CURRENT  wrapper (d9058a5):  EXIT=2   stderr: []   stdout: []   artifact: absent
```

Both wrappers do it (`generate_report.py --in=-x.eml` also exits 2 in silence). See
**R26-F2**.

**The extra invocation has an undocumented cost.** Phase 2 now runs the engine twice (once
to reconcile, once to render), so a kit run is three engine passes:

```
  8 KB  input: phase1=0.13s  phase2=0.14s  total=0.27s
 34 KB  input: phase1=0.22s  phase2=0.38s  total=0.61s  (p2/p1 = 1.74)
134 KB  input: phase1=0.73s  phase2=1.41s  total=2.14s  (p2/p1 = 1.93)
134 KB  HTML : phase1=0.6s   phase2=1.1s   total=1.7s
268 KB  HTML : phase1=1.1s   phase2=2.2s   total=3.2s
```

`EXAMPLES.md` still publishes single-pass figures ("~0.1 s at 8 KB, ~5 s at 134 KB, ~80 s at
538 KB") as if they were the kit's runtime. See **R26-F7**. Also note `run_engine.py`'s
100 KB warning lives in `main()`, so the two heavier passes in phase 2 emit no warning at
all.

**State-shape break.** `extract_case` lost its `input` key and `blocking_open_items` became
`open_items_by_priority`. Nothing in the kit reads either, and a v0.1.1 `state.json` fails
loudly rather than silently, so this is clean — verified against a real v0.1.1 specimen
found in the repo's (gitignored) local `_report/`.

**Doubled side effects:** none. Three `cli.main` calls in one process produce identical
output (the `confirmed-ids-render` fixture compares the twice-run render against a
single-run source capture and matches byte-for-byte), so there is no leaked module state.

## W-6 — are the fixes honestly described — FAIL

| Claim | Where | True? |
|---|---|---|
| REQ-023 invocation recorded whole, replayed via one `build_argv` | PROJECT.md:88 | **TRUE** of argv assembly (`build_argv` is the only site); see R26-F6 for the residual copy |
| REQ-024 "on any difference it exits 1" / "the structural defence" | PROJECT.md:95 | **MISLEADING** — skipped entirely when the file is not a regular file |
| "Two structural defences now make that class of divergence unshippable" | generate_report.py:22 | **FALSE** — I shipped that class of divergence twice (R26-F1, R26-F3) |
| REQ-025 "A failed run leaves no artifact" | PROJECT.md:103 | **FALSE** — `bom_draft.md` always survives; `case_state.json` survives a read-only `_report/` |
| REQ-026 fixture mutation-tested | PROJECT.md:106 | **TRUE** — independently reproduced (M1, M3) |
| REQ-027 documented invocations exist | PROJECT.md:108 | **TRUE** — README/EXAMPLES now say "the kit ships no console script" and give the real `python3` commands |
| REQ-028 fixtures in reserved namespaces | PROJECT.md:112 | **TRUE** — only `northside.example`, `acmedairy.example`, `mcgillhose.example` |
| FOLLOW-UP-8: schema deliberately not patched, "kept byte-identical to the source's contract" | PROJECT.md:174, EXAMPLES.md:126 | **TRUE** — `src/schemas/case_state.schema.json` == `email-to-bom-agent/docs/case_state.schema.json`, sha256 `ba0f4acb1903…` on both sides |
| FOLLOW-UP-6/7 "Six fixtures, five distinct inputs" | PROJECT.md:162,167 | **FALSE** — 7 fixtures, and only **4** distinct `input.eml` files (four fixtures share one) |
| FOLLOW-UP-9 duration claim corrected | registry-entry.json | **TRUE as far as it goes** — "seconds for a typical email; minutes for a very large thread" is honest; the 3x multiplier is not disclosed (R26-F7) |

Round 25's F-5/V-4 finding is worth correcting on the record: the shipped schema is **not**
a kit-authored duplicate of the engine vocabulary, it is a verbatim copy of a source
artifact I had not been told existed. That reclassifies it and is described honestly here.

## W-7 — the rename — PASS

```
kit.json name : mcgill-email-to-bom
registry id   : mcgill-email-to-bom
directory     : mcgill-email-to-bom
recipe file   : src/recipes/mcgill-email-to-bom.yaml   (name: mcgill-email-to-bom)
CLAUDE.md     : "Read recipes/mcgill-email-to-bom.yaml"
git remote    : github.com/ScaleUpLabs/McGill-email-to-bom-kit.git
```

A repo-wide grep for `email-to-bom` excluding the three legitimate forms
(`mcgill-email-to-bom`, `email-to-bom-agent`, `McGill-email-to-bom-kit`) returns **nothing**.
The source path and the GitHub repo name were not mangled.

---

# PART B

## V-1 — parity real and falsifiable — PASS

```
$ python3 tools/parity_check.py --manifest tools/parity/parity.json
suction-assembly: matched / plain-steam: matched / quoted-printable: matched
multipart-html: matched / confirmed-ids: matched / human-render: matched
confirmed-ids-render: matched
7 fixtures checked, 7 matched, 0 mismatched
normalized fields: (none declared)
EXIT=0
```

Every `normalize` block is `{}` (read directly from `parity.json`). The harness keeps its C1
guarantee — it unlinks `{output}` before every run, reports `missing-output` if nothing
appears (I saw that fire for real under M1), and raises a usage error on a zero-fixture
manifest. Falsifiability proven by M1/M3 above.

## V-2 — parity is not circular — PASS

Ignoring the kit entirely and regenerating from the source repo's own venv:

```
$ cd email-to-bom-agent && ./.venv/bin/python -m email_to_bom.cli <fixture>/input.eml --json | diff - expected_output.json
V2 MATCH suction-assembly / plain-steam / quoted-printable / multipart-html
V2 MATCH confirmed-ids            (with the 4 --component-ids from parity.json)
V2 MATCH human-render             (source render, wrapped by wrap_text.py)
V2 MATCH confirmed-ids-render     (NEW FIXTURE — source render WITH the 4 ids)
$ ./.venv/bin/python -m pytest -q   ->  507 passed in 2.07s
```

The new fixture's expected output is a real source capture, not the kit grading itself. The
507-test claim in `PROVENANCE.md` and `README.md` is exact.

## V-3 — vendored engine verbatim — PASS

```
$ diff -r --exclude=__pycache__ src/vendor/email_to_bom ../email-to-bom-agent/email_to_bom  -> identical
$ diff -r src/vendor/config ../email-to-bom-agent/config                                    -> identical
```

Re-diffed after every mutation in this round; still identical at the end. `PROVENANCE.md`'s
`b1f9950`-stamp-plus-`b15b23d`-note remains accurate.

## V-4 — no second copy of an engine rule — PASS

`build_argv` (`run_engine.py:52`) is the **only** place an engine argv is assembled — grep
for `"--json" | "--coc" | "--component-ids" | "--config-dir"` in `src/**.py` returns
`build_argv` plus `argparse` declarations and nothing else. `generate_report.py` re-runs the
engine rather than re-rendering the CaseState. Engine-style `CAPS_WITH_UNDERSCORES`
vocabulary in non-vendor code: `run_engine.py` 0, `generate_report.py` 1
(`SELECTION_UNRESOLVED`, in a comment explaining F-1), `CLAUDE.md` 0, recipe 0,
`parity_check.py` 2 (its own constants). The 37 codes in the schema are a byte-identical
copy of a **source** artifact, so they are not a kit-authored second copy — round 25's
PARTIAL upgrades to PASS.

One residual, filed as R26-F6: the invocation *dict* is built in three places
(`run_engine.py:138`, `generate_report.py:66`, `generate_report.py:81`), the third being a
4-key whitelist that silently drops anything it does not recognise.

## V-5 — self-contained and offline — PASS

```
$ unzip dist/kit.zip -> 20 files, no __pycache__, no .pyc, no kit.json
$ env -i /usr/bin/python3 .../scripts/run_engine.py --in raw/rfq.eml ... --coc   -> EXIT=0
$ env -i /usr/bin/python3 .../generate_report.py --out ... --state ...           -> EXIT=0
$ PYTHONPATH=<sitecustomize with a sys.addaudithook trapping socket.connect,
  socket.getaddrinfo, urllib.Request, http.client.connect>
  phase 1 -> "knowledge_source": "none"   EXIT=0
  phase 2 -> wrote _report/bom_draft.md   EXIT=0
  knowledge: {'source': 'none', 'revision': None, 'lookups': []}
$ grep -rn "os.environ|getenv" <unzipped kit>   ->  none in the shipped zip
```

`requires.tools` is `[]`; nothing beyond system `python3` (3.14.6) was needed; the run works
from a directory unrelated to the kit; no environment variable is read; no credential is
present. Not one network event was attempted with the audit hook armed.

## V-6 — exit-code contract — FAIL

Engine exit 2 is never treated as failure — phase 1 prints `"engine_exit": 2` and returns 0,
phase 2 prints `engine_exit=2` and returns 0. Genuine failures, no partial artifacts:

```
input is a directory        EXIT=1  "no such RFQ file: raw/adir"                 no artifact
unreadable input            EXIT=1  "engine could not read its input: ..."       no artifact
bad --config-dir            EXIT=1  "cannot load config from /nonexistent"       no artifact
unwritable --out directory  EXIT=1  "cannot write ro/cs.json: [Errno 13]"        no artifact
empty file / random binary   EXIT=0  valid CaseState (engine's design, source-identical)
```

But **R26-F2**: an input path beginning with `-` makes both wrappers exit **2** with empty
stdout and empty stderr. "Fail loudly (exit 1) on genuine failures" is the pre-registered
criterion; this fails silently, with the success code. FAIL.

## V-7 — kit contract compliance — PASS

```
$ python3 tools/validate_manifest.py kit.json                    EXIT=0
$ ./tools/build_kit.sh
  SHA-256: 3db7a61946f9cbca58ca5633ecb0805027f420373db0f906a18e68e3ef6b5bfb   (20 files)
  == kit.json .sha256   and the rebuild left git clean (byte-reproducible)
```

Exactly one `email_attachment` (`_report/case_state.json`). Both declared artifacts are
produced by the recipe. `EXAMPLES.md` has all four required sections (`## Quick Start`,
`## Examples`, `## Argument Reference`, `## Common Patterns`) and each example carries
Prompt / Arguments / Expected workflow / Produces. Recipe phase dependencies are acyclic and
nothing is read before it is produced: phase 0 → `state.json`; phase 1 reads `state.json`,
writes `state.json` + `case_state.json`; phase 2 reads both, writes `bom_draft.md`.

## V-8 — documentation makes no false claim — FAIL

Verified true, by running it:

```
example 1 (no flags)   -> 0 BOM lines, 2 checkpoints (C2,C3), 6 open items,
                          exactly the 6 codes EXAMPLES.md lists
example 2 (4 ids)      -> 4 BOM lines, 5 open items, SELECTION_UNRESOLVED gone, C3 closed
example 3 (--coc)      -> "Classes: Certs Required" in BOTH artifacts (round 25's F-1 half)
example 4 (gasket)     -> request_class=component_rfq, no hose-assembly questions
"4 in ID captures"     -> size {'status':'captured','value':'4 ID'}
"bare 4in / 4\" does not" -> size {'status':'missing'}, SIZE_MISSING raised     (also 4 in OD)
"misses become blocking asks" -> ('COMPONENT_ID_UNRESOLVED','blocking')
"forces hose_assembly"        -> gasket email: component_rfq -> hose_assembly with ids
"matched case-insensitively"  -> lowercase ids give 2 BOM lines, kit == source
"two unreachable schema values" -> schema byte-identical to the source's, claim honest
README "the kit ships no console script"  -> true (round 25's F-3 closed)
```

False: `EXAMPLES.md:121-125` presents single-engine-pass runtimes as the kit's runtime when
the kit now runs the engine three times (R26-F7), and `generate_report.py:22`'s "unshippable"
is falsified by R26-F1 and R26-F3. FAIL.

## V-9 — determinism — PASS

Six full two-phase runs across `PYTHONHASHSEED` 0, 1, 42, 12345, random, random:

```
case_state.json  1e8f23620a72   x6      bom_draft.md  bdbfbbfa196f   x6
```

One distinct hash per artifact. No absolute path (`grep -c <scratch prefix>` = 0 in both)
and no ISO timestamp in either artifact, including when fed an absolute input path.

## V-10 — nothing sensitive ships — PASS

Zip scanned for `api[_-]?key|secret|passwd|password|bearer|PRIVATE KEY|aws_|xox[baprs]-|ghp_|sk-…`:
two hits, both in the dormant `vendor/email_to_bom/knowledge.py` — `auth_scheme: str = "Bearer"`
(a default header name) and a comment "so no password touches this code". No values.
Email addresses extracted from every file in the zip: **none**. Fixture addresses are all in
RFC 2606 reserved space (`northside.example`, `acmedairy.example`, `mcgillhose.example`) —
round 25's F-7 closed.

## V-11 — the published package matches the repo — PASS

Rebuilt from repo HEAD, not trusting the publisher's output:

```
$ python3 tools/publish_kit.py --base https://astro.twyd.cloud --dry-run --out upload.zip
Package built — 21 files, 69653 bytes, sha256 6cdfd8364c50…
$ shasum -a 256 upload.zip
6cdfd8364c509f991518dc0648f6a05d819856cf987abb80250dff62876e9cad
```

Exactly the pre-registered sha256. **Limitation:** `GET https://astro.twyd.cloud/api/kit-packages`
and `.../mcgill-email-to-bom` both return `401 {"error":"unauthorized"}`; I hold no
credentials and did not seek any, so I confirmed reproducibility against the bar's
pre-registered hash, not against the server's stored bytes.

## V-12 — the recipe's constraints are coherent — PARTIAL

Nothing declared is left unproduced, no constraint contradicts the engine's behaviour, and
the reconciliation-failure instruction is actionable (re-running phase 1 does fix every
divergence I induced). Three coherence defects:

1. The guard's own remediation text says "or pass the same flags to both phases", which the
   recipe forbids ("you do not repeat the flags there") and the README precludes ("The
   second command needs no flags") — see R26-F9.
2. Phase 0 is told to write "`_report/state.json` with the resolved input path and the
   optional flags, so later phases and any resumed run read the same inputs", but no script
   reads that record, and phase 1 unconditionally `pop`s `invocation` and `extract_case`
   before it can fail — so a failed phase 1 empties exactly the file phase 0 wrote (observed:
   `state.json` -> `{}`), against `CLAUDE.md`'s "Track progress in `_report/state.json` so an
   interrupted run can resume". See R26-F10, R26-F6.
3. `kit.json` declares two artifacts; only one is protected from stale survival (R26-F1).

---

# Findings

## R26-F1 — HIGH — the stale-artifact fix covers one of the two declared artifacts; `bom_draft.md` survives a failed run, and now nothing is left to contradict it

**What breaks.** `run_engine.py` clears `--out` and invalidates `state.json` before it can
fail (REQ-025). Nothing clears `_report/bom_draft.md` — not `run_engine.py`, and not
`generate_report.py`, which writes its output only at the very end and therefore leaves the
previous run's draft in place on every one of its own failure paths. `bom_draft.md` is the
artifact a human reads before quoting a customer, and it is the exact artifact round 25's
F-1 was about.

**Reproduction** (unzipped `dist/kit.zip`, one working directory, two customers):

```
phase 1, email B (plain-steam) — succeeds:
  request_class=hose_assembly  open_items=4  bom_lines=1
the .eml is cleaned up between phases (a mail fetcher, a tmpdir, a retry):
  mv raw/steam.eml raw/steam.eml.gone
phase 2 (the recipe's command, verbatim):
  error: no such RFQ file: raw/steam.eml            EXIT=1

### what _report/ now contains ###
case_state.json : class=hose_assembly  bom_lines=1  open_items=4
                  codes=['PRESSURE_MISSING','TEMPERATURE_MISSING','LENGTH_CONFIRM','SELECTION_UNRESOLVED']
bom_draft.md    : 4 BOM rows -> ['OPW 633C A','OPW 633E A','SPS400452','HOS-064 300 EPDM']
                  codes=['MATERIAL_CONFIRM','VACUUM_VALUE_CONFIRM','TEMPERATURE_MISSING',
                         'SIZE_MISSING','LENGTH_TYPE_MISSING']
```

A `case_state.json` for one customer's RFQ sitting beside a `bom_draft.md` for a completely
different customer's RFQ, both schema-valid, both looking fresh. That is round 25's F-1
outcome — "the human deliverable silently contradicts the machine contract" — reached
through a door the fix left open.

**And the F-4 fix made the failure mode worse in one respect.** In the typo'd-path variant,
`case_state.json` is now *deleted* and `state.json` is reduced to `{}`, so `_report/` holds
the stale draft **alone**:

```
run 2 phase 1, typo'd path:   error: no such RFQ file: raw/steam_rfq.eml   EXIT=1
_report/ ->  bom_draft.md  (2210 B, email A, 4 BOM lines)
             state.json    ({})
             case_state.json: gone
```

Round 25 at least left the contradicting CaseState on disk for someone to notice. Now the
only surviving artifact is the wrong one, and nothing in `_report/` records which run it
belongs to (phase 2 never writes to `state.json` at all).

**Why it matters.** This is failure class #2 — fixing the named instance, missing the
duplicate copy — for the sixth time in this project, and it lands on the deliverable the
whole kit exists to make trustworthy. It also makes REQ-025 ("A failed run leaves no
artifact") and `CONVENTIONS.md` ("Never let a failure leave a plausible artifact behind.
Clear stale outputs before work that can fail") false as written. The fix is symmetric with
the one already made: `generate_report.py` should discard `--out` before it can fail, and
`run_engine.py` should discard the downstream draft along with the CaseState.

## R26-F2 — MEDIUM-HIGH — both wrappers exit **2** silently on an argparse rejection inside the engine; this is a regression the fix introduced, and 2 is the code the docs call success

**What breaks.** Round 25's `run_engine.py` wrapped the engine call in
`except SystemExit as e: print(f"error: {e}"); return 1`. The refactor replaced the raised
`SystemExit` with a `RuntimeError` and now catches only `RuntimeError`
(`run_engine.py:75-77`, `147-149`; `generate_report.py:127-129`, `163-165`). `argparse`
inside `cli.main` raises `SystemExit(2)`, which is no longer caught — and because the call
runs inside `contextlib.redirect_stderr`, argparse's usage message is captured into a buffer
that is then discarded.

**Reproduction** (same input file, same engine, two wrapper versions):

```
$ cp raw/rfq.eml ./-x.eml
$ python3 <0119689 run_engine.py> --in=-x.eml --out cs.json    EXIT=1   stderr: [error: 2]
$ python3 <d9058a5 run_engine.py> --in=-x.eml --out cs.json    EXIT=2   stderr: []  stdout: []
$ python3 <d9058a5 generate_report.py> --in=-x.eml --state /dev/null    EXIT=2   stderr: []
```

**Why it matters.** Exit 2 is the single most overloaded code in this kit. `CLAUDE.md`:
"**Never treat exit code 2 as a failure.** It means 'a draft was produced and it has open
items' … Only the wrapper scripts' own non-zero exits are failures." The recipe repeats it;
so do `README.md` and `EXAMPLES.md`. An agent following those instructions literally sees
exit 2, no stderr, no stdout — and concludes the phase succeeded normally. `run_engine.py`'s
own docstring documents only 0 and 1 for the wrapper. The class is broader than the one
trigger: any `SystemExit` from inside `cli.main` now escapes silently.

## R26-F3 — MEDIUM — the reconciliation guard fails open, and I used it to ship a divergent pair

**What breaks.** `generate_report.py:132` gates the entire defence on
`os.path.isfile(case_path)`; when the path is absent, a directory, or `/dev/null`, the
`else` branch prints a stderr warning and writes the draft with **exit 0**.

**Reproduction** — same working directory, the input rewritten between phases (a re-fetched
thread, an overwritten temp file), with the CaseState momentarily out of the way:

```
phase 1 on email A -> case_state.json (6 open items, MATERIAL_CONFIRM…SELECTION_UNRESOLVED)
input replaced with email B; case_state.json moved aside
phase 2 (recipe command):
  warning: _report/case_state.json not found — writing the draft without reconciling ...
  wrote _report/bom_draft.md (1666 bytes, engine_exit=2, reconciled against nothing)  EXIT=0

case_state codes: ['MATERIAL_CONFIRM','VACUUM_VALUE_CONFIRM','TEMPERATURE_MISSING',
                   'SIZE_MISSING','LENGTH_TYPE_MISSING','SELECTION_UNRESOLVED']
draft      codes: ['PRESSURE_MISSING','TEMPERATURE_MISSING','LENGTH_CONFIRM','SELECTION_UNRESOLVED']
=> DIVERGENT ARTIFACTS IN _report/: True
```

The read-only-`state.json` variant in W-3 reaches the same exit-0 outcome with no manual
file moves at all: phase 1 deletes the CaseState, fails to invalidate `state.json`, and
phase 2 then cheerfully re-renders the *previous* email as the current deliverable.

**Why it matters.** The stated contract is "Before writing anything, this script re-derives
the CaseState … and asserts it equals the `case_state.json` on disk", and REQ-024 calls it
"the structural defence". A defence that is skipped on a missing file is advisory. Recipe
phase 2 declares `_report/case_state.json` as a required *input*; the script should treat a
missing one as the error it is (exit 1), not as permission to skip the check. Note the
guard's fail-*closed* behaviour on corrupt content is correct and well-messaged — this is
specifically the not-a-regular-file branch.

## R26-F4 — MEDIUM — two of the three new defences have no regression coverage at all

`if False and on_disk != replayed:` (guard removed) → **7/7 matched, exit 0**.
`_discard_stale(args.out)` → `pass` (REQ-025 removed) → **7/7 matched, exit 0**.

Only REQ-023 (the shared `build_argv`) is fenced by a fixture. REQ-024 and REQ-025 can be
deleted by any future edit and every check in the repo stays green — the "check that has
never been able to fail" pattern, applied to the fixes themselves, in a project whose
`CONVENTIONS.md` says "Before trusting a new fixture, confirm it can *fail*." A fixture that
runs phase 2 against a deliberately mismatched `case_state.json` and asserts exit 1, and one
that asserts `_report/` is empty after a failed run, would close both.

## R26-F5 — MEDIUM — stale-clearing failures are swallowed silently, reproducing F-4 in hostile environments

`run_engine.py:89-94` (`except OSError: pass`) and `:125-126`
(`except (OSError, json.JSONDecodeError): pass`) discard every error from the clearing step.

```
read-only _report/ (555) + failing run  -> stale case_state.json SURVIVES, no warning
read-only state.json (444) + failing run -> state.json still points at the OLD run, no warning
                                            (and then phase 2 exits 0 — see R26-F3)
```

"Better no artifact than a confidently wrong one" is the stated rationale; when the clearing
cannot be done, the run should say so, not proceed as if it had. Contrived environments, but
the swallow is unconditional and the consequence is exactly the defect REQ-025 claims to
have closed.

## R26-F6 — LOW-MEDIUM — the invocation contract still lives in two places at the phase-0 → phase-1 boundary, and the record's key set is copied three times

Round 25's F-1 was the phase-1 → phase-2 boundary, and that is now mechanically closed. The
phase-0 → phase-1 boundary is not: the recipe has the agent parse `$ARGUMENTS`, write "the
resolved input path and the optional flags" into `state.json` (phase 0), and then **re-type
the flags onto phase 1's command line** ("Pass through `--component-ids` / `--coc` /
`--config-dir` exactly as given in phase 0"). No script reads phase 0's record and nothing
compares the two. If the agent drops `--coc` while composing phase 1's command, both
artifacts are perfectly self-consistent, the guard is silent, and the run is simply wrong
about what the customer asked for. REQ-023's "ONE contract in ONE place" is true of argv
assembly only.

Secondarily, the invocation *record* is constructed at three sites — `run_engine.py:138`,
`generate_report.py:66` (the `--in` branch) and `generate_report.py:81` (the normaliser) —
and the third is an explicit 4-key whitelist, so a fifth key recorded by a future
`run_engine.py` is silently dropped by phase 2. `build_argv` reads through `.get`, so it
would not notice. The guard would catch the resulting divergence loudly, which is why this
is LOW-MEDIUM rather than higher.

## R26-F7 — LOW — the published runtime figures are single-pass; the kit now runs the engine three times

`EXAMPLES.md:121-125` — "~0.1 s at 8 KB, ~5 s at 134 KB, ~80 s at 538 KB" — is presented as
the kit's runtime. Measured phase-2/phase-1 ratio is 1.74–1.93 (2 engine passes vs 1), so a
kit run costs ≈3x a single pass; on round 25's own 538 KB measurement that is ≈4 minutes end
to end, not 80 s. `FOLLOW-UP-9` repeats the same single-pass numbers. Also, the 100 KB
"engine runtime grows superlinearly" warning is emitted only by `run_engine.py`'s `main()`,
so the two most expensive passes of the run happen with no warning at all.

## R26-F8 — LOW — the fixture counts in `PROJECT.md` are wrong in both directions

`FOLLOW-UP-6`/`FOLLOW-UP-7` say "Six fixtures, five distinct inputs" and "Parity covers the
six fixtures". There are **7** fixtures, and `shasum` on the seven `input.eml` files yields
only **4** distinct files — `suction-assembly`, `confirmed-ids`, `human-render` and the new
`confirmed-ids-render` all share `e52deb28bc31…`. The "five distinct inputs" claim was
already wrong before this round, and the round-25 fix pass that corrected other doc counts
did not correct it. Given the honest framing of that follow-up ("thin and partly
synthetic"), overstating the corpus by 3 fixtures' worth of inputs cuts against its purpose.

## R26-F9 — LOW — the reconciliation error tells the operator to do something the recipe forbids

`generate_report.py:149-150` — "Re-run the extract phase, **or pass the same flags to both
phases**." The recipe says "you do not repeat the flags there", the README says "The second
command needs no flags", and phase 2's command is fixed, so the second half of the advice is
unactionable through the shipped recipe and, if followed, is the very drift the message
exists to prevent.

## R26-F10 — LOW — phase 1 destroys phase 0's `state.json` record before it can fail

`run_engine.py:116-126` pops `invocation` and `extract_case` unconditionally at startup.
Observed: after a failed phase 1, `state.json` is `{}`. Phase 0's stated purpose ("so later
phases and any resumed run read the same inputs") and `CLAUDE.md`'s "Track progress in
`_report/state.json` so an interrupted run can resume" are therefore not delivered in the
one case where resuming matters. Phase 0's record is also unused by any script, so its shape
is unspecified and unverified.

---

## Adversarial pass — what I tried that did NOT break it

**Differential fuzz against the source engine, 14 new inputs** (deliberately disjoint from
round 25's list), kit run from the unzipped zip in an unrelated cwd vs source in its own
venv, byte-diffed:

```
attachment-only multipart/mixed with base64 PDF   IDENTICAL
duplicate Subject headers (conflicting sizes)     IDENTICAL
one 90 KB line with no newline                    IDENTICAL
RFC 2047 encoded-word Subject (=?utf-8?B?…)       IDENTICAL
Content-Transfer-Encoding: 8bit + UTF-8 degree    IDENTICAL
nested message/rfc822 forward                     IDENTICAL
charset=iso-2022-jp                               IDENTICAL
whitespace-only .txt                              IDENTICAL
lone UTF-8 surrogate bytes (ED A0 80)             IDENTICAL
800-deep <div> nesting                            IDENTICAL
obs-fold header continuation                      IDENTICAL
CRLF header with no body separator                IDENTICAL
conflicting units (150 psi and 10 bar, C and F)   IDENTICAL
lowercase --component-ids                         IDENTICAL
```

14 of 14. Combined with round 25's 24, I could not find any input where the kit's output
differs from the source engine's.

**Invocation permutations** — 13 of them (W-1 table). The flag plumbing held every time; the
argv is genuinely assembled once.

**Guard defeat attempts** — hand-edited `case_state.json`, corrupt/empty/truncated/
unreadable CaseState, a mangled `component_ids` string in `state.json`, a numeric `input`, a
real v0.1.1-format `state.json`, `--case-state` pointed elsewhere: every one either failed
closed with a named diverging key or refused loudly. The only defeat is the
not-a-regular-file branch (R26-F3).

**Guard false positives** — none in ~20 legitimate runs, including repeated phase-2 runs,
alternate config dirs, absolute paths, and 6 `PYTHONHASHSEED` values.

**Races** — five trials of two concurrent phase-1 runs on the same `_report/`; `state.json`
and `case_state.json` agreed every time and phase 2 reconciled clean.

**Reproducibility and publication** — `build_kit.sh` re-run left git clean and hit
`3db7a619…` again; the upload package rebuilt from HEAD hit the pre-registered
`6cdfd8364c50…` exactly.

**Offline / secrets** — audit-hook network trap armed: zero network events. Empty
environment: both phases exit 0. No credential, no email address, no real identity in the
zip.

**Vendoring** — byte-identical, re-verified after every mutation; the shipped schema turned
out to be byte-identical to the source's `docs/case_state.schema.json` too.

## Known limitations of this round

- Parity still covers a small slice of the engine's 37 open-item codes (pre-declared
  FOLLOW-UP-6/7); a regression in an unreached code would pass. Reported as measurement.
- `V-11`'s server side is unverifiable without credentials I do not have and did not seek;
  I verified byte-reproduction against the pre-registered sha256 instead.
- I could not reproduce round 25's absolute 80 s@538 KB figure — my synthetic padding does
  not hit the superlinear path — so R26-F7 rests on the measured 1.74–1.93x phase-2/phase-1
  ratio and the count of engine passes, not on a re-measured 538 KB number.
- The dormant `McpKnowledge` / `TwydIngestion` paths were only proven unreached, not
  exercised (pre-declared FOLLOW-UP-1/2).
- Engine extraction/classification correctness remains out of scope (rounds 1-24).
- The nine deferred follow-ups were assessed for honesty only, per the bar.

## Verdict

**FAIL** — on W-2, W-3, W-5, W-6, V-6 and V-8.

What is genuinely good, and I attacked all of it hoping it would not be: F-1 is really
fixed, and the fixture that guards it fails for the right reason when the defect is
reintroduced with the guard disabled; `--config-dir` is now plumbed end to end; the argv is
assembled in exactly one place; the guard fires precisely and names the diverging keys, with
no false positive I could construct; the vendoring, the schema, parity (7/7 regenerated from
the source), the 507 tests, determinism, offline operation, the byte-reproducible build and
the published sha all hold exactly as claimed; and 14 more adversarial inputs produce output
byte-identical to the source engine.

It fails because the fix pass reproduced the failure class it was closing. `bom_draft.md` —
the artifact F-1 was about — is the one declared artifact the new stale-artifact guard does
not cover, so a failed run still leaves one customer's BOM in `_report/` for another
customer's case, and now with the contradicting CaseState deleted so nothing can catch it.
The reconciliation "structural defence" is skipped silently whenever the CaseState file is
absent, and I used that to write a divergent pair with exit 0. And the refactor that
unified the engine call dropped the `except SystemExit` that v0.1.1 had, so both wrappers can
now fail with no message at all and the exit code every document in this kit defines as
success.

Fixing R26-F1 and R26-F2 is small and local. What should not be small is the response to the
pattern: three rounds running, the defect has been *one rule expressed in N places with one
copy missed*, and this round it was the fix itself. Both R26-F1 and R26-F3 would have been
caught by the two fixtures R26-F4 says are missing.
