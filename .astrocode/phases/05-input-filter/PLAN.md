# PLAN — Phase 05 Input Filter

Aims at every criterion in `CRITERIA.md` (C1–C8). Canon: `.astrocode/CONVENTIONS.md`,
`KIT-CONTRACT.md`, `.astrocode/DECISIONS.md`. No `CONTEXT.md` exists for this phase, so
the design decisions below are recorded as ADR entries by **t5** rather than assumed.

## Design the tasks implement (read this before touching a file)

**One gate, one place.** A new deterministic script `src/scripts/filter_gate.py` owns the
decision. The recipe gets a new phase that *runs the script and branches on its exit code*
— it never "decides" in prose. (The recipe is agent-interpreted text; a judgement call
there would be non-deterministic and unmutatable, failing C7.)

**Exit contract (new, non-overlapping):** `0` = not filtered, proceed to the engine ·
`3` = filtered, do NOT run the engine · `1` = the gate's own failure. Clamped in
`__main__` exactly like `run_engine.py` (R26-F2): never `2`, ever (REQ-007, C2).

**Two evidence tiers, and one universal veto.**
1. *Structural header tier* (cheap, `email.parser.BytesHeaderParser`, only when
   `mail.looks_like_mime(raw, filename)` says there are headers): DSN
   (`Content-Type: multipart/report; report-type=delivery-status` and/or a
   `message/delivery-status` part, `MAILER-DAEMON`/`postmaster` sender, null `Return-Path`),
   auto-reply (`Auto-Submitted` present and not `no`, RFC 3834), bulk
   (`List-Unsubscribe` **AND** (`Precedence: bulk|list|junk` **OR** `List-Id`) — never
   `List-Unsubscribe` alone).
2. *Content tier* for the three categories no protocol header marks: invoice/statement
   (positive invoice evidence in subject/body), bare acknowledgement (**dominance** test:
   after stripping quoted history and signature the remainder is under a declared char
   budget and matches an ack phrase — never bare substring presence), internal chatter
   (every `To`/`Cc` address shares the `From` domain).
3. *Quoting-request veto* — applies to **every** category except DSN: filter only if the
   message shows NO quoting request, where a quoting request is
   `product_signal AND request_act`:
   - `product_signal` = the **vendored** classifier's own verdict:
     `triage.classify(low, rules)[0] != "out_of_scope"`, with `rules` from
     `core.load_config(config_dir)` (honours `--config-dir`). We do NOT re-express any
     engine vocabulary in kit code (CONVENTIONS).
   - `request_act` = `"?" in text` OR a `rules["question_cues"]` hit OR class in
     (`order`, `stocking_lead`) OR a hit in the small kit-side `quote_request_cues` list
     declared in `src/reference/filter_signals.json`. ("Is this a request at all" is a
     genuinely new capability — the engine assumes yes — so it is new vocabulary, not a
     second copy of a rule.)
   This veto is what saves `bait-rfq` (bulk+auto-reply headers on a real RFQ),
   `ack-plus-rfq` and `invoice-plus-rfq` (C5 1–3), and it is why the newsletter (product
   words, no request act) and the internal chatter (a question, no product) still filter.

**Fail OPEN, deliberately — a named inversion of the kit's fail-closed idiom.** Anything
uncertain resolves to *not filtered*: no text obtained, a parse defect or exception,
HTML-only body above the declared HTML scan budget, an unrecognised/undecodable part that
could hide the request, a code or route not in the declared vocabulary, an unreadable
reference/schema file. Only a *hard input error* (missing/unreadable input path) is loud
and fails closed with exit 1 (that is not ambiguity). Recorded as an ADR by t5.

**Cost (C3).** The gate never calls `mail.extract_rfq_text` and never runs the
HTML/CSS-hiding pipeline on a large body: that is the engine-side superlinear cost the
gate exists to avoid. Text acquisition is a stdlib `BytesParser` walk taking decoded
`text/plain` parts; `mail.html_to_text` is used only for HTML-only messages under the
declared budget, else fail open. All signal checks are linear `re.search` passes, so the
~1 MB newsletter filters in well under a second with no truncation of the veto scan
(truncating it would bias toward filtering — the forbidden direction).

**Byte parity (C4).** The gate only ever *reads* the input file; it never rewrites,
copies, normalises or re-encodes it, and `run_engine.py` keeps passing the original path
to `cli.main`. The gate imports `core`/`triage`/`mail` — never `cli`, never `run_engine`
— so the C3 sentinel cannot fire from the gate, and nothing in `tools/parity/` changes.

**Parity harness untouched, on purpose.** `tools/parity/*` gets NO new fixture: parity
commands invoke `run_engine.py` directly, so a mutation of the gate can only break
`tools/selftest.py` — which is exactly what C7 requires ("the mutations break parity
instead of selftest" is a failure). The gated-path byte-identity check lives in
`selftest.py` instead (t10).

**Test strategy: TEST-AFTER, chosen deliberately.** The kit's only test harnesses are two
always-run gate scripts (`tools/selftest.py`, `tools/parity_check.py`); a RED selftest
landing before the gate exists would fail the wave-integration gate at the boundary
(ADR-020). So t10 depends on the implementation and carries C7's mutation proof as a
mandatory step — which is this project's own falsifiability discipline ("a fixture that
has never failed has proven nothing"). Test *data* is still first: t3 lands the fixtures
in wave 1. Any selftest check that imports `filter_gate` directly MUST do the import
inside that check's own function/try block so a missing symbol fails only that check, not
the whole file at module load (ADR-018).

---

## Tasks

### t1 — Declare the filter's signal vocabulary as shipped reference data
- **file:** `src/reference/filter_signals.json`
- **depends_on:** —
- New file. Mirrors `vendor/config/rules.json` style (leading `_note` keys; **list order
  is behaviour**, first match wins). Declares, once:
  - `categories`: ORDERED list of `{code, route, detector}` covering exactly six
    categories — `DELIVERY_STATUS_NOTIFICATION`/`no_action`,
    `AUTO_REPLY`/`no_action`, `BULK_MAILING`/`no_action`,
    `INVOICE_OR_STATEMENT`/`accounts_payable`, `BARE_ACKNOWLEDGEMENT`/`inside_sales_fyi`,
    `INTERNAL_CHATTER`/`internal_ops`. Codes are SCREAMING_SNAKE like `open_items[].code`;
    routes are deliberately DISJOINT from `open_items[].route` / `routing.recommendation`
    values so a consumer can never mistake a filtered message for a routed-but-undrafted
    case.
  - `quote_request_cues`, `invoice_phrases`, `ack_phrases`, `auto_reply_localparts`,
    `dsn_sender_localparts`, `bulk_precedence_values`, and thresholds
    `ack_max_chars`, `html_scan_bytes`.
  - A `_note` stating that absence of evidence is never grounds to filter.
- **Done when:** the file parses as JSON, every category has a code+route+detector, and
  no phrase list duplicates engine vocabulary from `rules.json` (product/media/fitting
  words are NOT copied here — the classifier supplies them).

### t2 — Declare the filter decision contract (closed enums)
- **file:** `src/schemas/filter_decision.schema.json`
- **depends_on:** —
- New sibling schema — `case_state.schema.json` is NOT edited (it is kept byte-identical
  to the source contract). Describes the `filter` record written into
  `_report/state.json`: `filtered` (bool, required), `input` (string path, required — C6
  replayability), `code` and `route` (`["string","null"]` with closed `enum`s that include
  `null` for the pass-through case), `evidence` (short verbatim signal string),
  `override` (bool), `reason` (short machine token for why a pass-through happened, e.g.
  `quoting_request_detected` / `no_evidence` / `parse_failed` / `override`).
  `additionalProperties: false`. Same enum style as `case_state.schema.json`.
- **Done when:** the schema parses, and its `code`/`route` enums are exactly the t1
  category codes/routes plus `null` (t10 asserts this mechanically).

### t3 — Land the filter fixture corpus
- **file:** `tools/filter/fixtures/<case>/input.eml` for cases:
  `auto-reply`, `delivery-status`, `newsletter`, `bare-ack`, `invoice-statement`,
  `internal-chatter`, `bait-rfq`, `ack-plus-rfq`, `invoice-plus-rfq`, `broken-mime`,
  `empty`
- **depends_on:** —
- `kebab-case` dirs holding `input.eml`, matching the existing
  `tools/parity/fixtures/<case>/` convention. The six junk cases reproduce the categories
  in `CRITERIA.md`'s scratch corpus; the five adversarial cases reproduce C5 1–5:
  `bait-rfq` = the `plain-steam` body with `Auto-Submitted: auto-replied`,
  `List-Unsubscribe`, `Precedence: bulk` and an `Out of Office: RE:` subject prefix;
  `ack-plus-rfq` = `Thanks, got it.` then the `plain-steam` request; `invoice-plus-rfq` =
  invoice subject + statement paragraph + a genuine 4in EPDM suction hose quote request;
  `broken-mime` = the `multipart-html` fixture with a corrupted boundary and
  `Content-Transfer-Encoding: x-nonsense`; `empty` = zero bytes.
- RFC 2606 `.example` domains ONLY (REQ-028). Data only — nothing imports these yet.
- **Done when:** all 11 `input.eml` files exist, `empty/input.eml` is 0 bytes, and
  `grep -rlE '\.(com|net|org)\b' tools/filter/fixtures` is empty.

### t4 — Declare the filter/screen state records in the single state owner
- **file:** `src/scripts/run_state.py`
- **depends_on:** —
- Additive only; `ARTIFACTS` is UNCHANGED (a filtered run produces no artifact — its
  record is a state key, which is what C1 requires). Add, as declarations beside
  `INVOCATION_KEYS`:
  - `FILTER_KEY = "filter"`, `FILTER_KEYS` and `make_filter_decision(...)` /
    `normalize_filter_decision(raw)` — one constructor, one normaliser, read through
    `FILTER_KEYS` (never a hand-written whitelist, R26-F6).
  - `SCREEN_KEY = "screen"`, `make_screen_request(override=False)` /
    `normalize_screen_request(raw)` — the prepare phase's record of the `--no-filter`
    override, kept OUT of the engine invocation so `INVOCATION_KEYS`/`build_argv` and
    therefore parity are untouched.
  - Docstring lines explaining both, in the file's existing voice.
- **Done when:** `python3 -c "import sys;sys.path.insert(0,'src/scripts');import run_state"`
  succeeds, `INVOCATION_KEYS`/`build_argv`/`ARTIFACTS` are byte-unchanged, and
  `python3 tools/parity_check.py --manifest tools/parity/parity.json` still exits 0.

### t5 — Record the phase's decisions as ADR entries
- **file:** `.astrocode/DECISIONS.md`
- **depends_on:** —
- Append (do not rewrite; the log is append-only) entries for: (a) **the filter fails
  OPEN** — a named, intentional inversion of the kit's fail-closed guard idiom, because
  filtering a real RFQ is far worse than passing a newsletter (rejected: fail closed);
  (b) **gate exit code `3`** for "filtered", never reusing the engine-adjacent `2`
  (rejected: overloading 2, and reusing 1); (c) **the gate is a deterministic script, the
  recipe only branches on its exit code** (rejected: judging in recipe prose);
  (d) **the filter's route vocabulary is disjoint from `open_items[].route`** (rejected:
  reusing `inside_sales`/`order_desk`); (e) **the gate reads its own cheap bounded text
  view and never `extract_rfq_text`**, and never hands text to the engine (rejected:
  reusing the full extraction pipeline for pre-screening).
- **Done when:** the entries exist with why + rejected alternatives, and no pre-existing
  content was modified.

### t6 — Implement the gate
- **file:** `src/scripts/filter_gate.py`
- **depends_on:** t1, t2, t4
- New script, shaped exactly like `run_engine.py`: module docstring stating the exit-code
  contract up front and WHY it fails open; argparse CLI (`--in`, `--from-state`,
  `--state`, `--no-filter`, `--config-dir`, plus artifact overrides mirroring
  `run_engine.py`); broad `except BaseException` in `__main__` with the clamp; JSON
  summary printed on stdout for the phase to read.
- Exposes ONE pure, importable decision function — `decide(raw, filename, rules, signals)`
  returning a decision record (or an equivalent single seam) — so `selftest.py` can call
  it directly as well as via subprocess, and so C7's two mutations have exactly one site.
- Sequence in `main()`: resolve the invocation (from `--in` or the recorded one) BEFORE
  clearing anything → hard-error (exit 1) if the input is missing/unreadable →
  `invalidate([paths["case_state"], paths["bom_draft"]])` via `run_state` (never naming
  files at the call site, R26-F1) on BOTH branches → read raw bytes → decide → write the
  `filter` record through `write_state(..., drop=("extract_case",))`, preserving
  `invocation` (REQ-035) → print the summary → return 0 or 3.
- Loads the closed vocabulary from `src/schemas/filter_decision.schema.json` +
  `src/reference/filter_signals.json` by `__file__`-relative path (works in the repo and
  in the unzipped kit, and under `python3 -S -E`), and refuses to emit a code/route that
  is not in the declared enum — such a bug fails OPEN with a loud stderr note.
- `--no-filter` (or a recorded `screen.override`) short-circuits to exit 0, says so on
  stderr (CONVENTIONS: opting out must be explicit and loud) and records
  `override: true, reason: "override"` — this is C6's no-code-edit escape hatch.
- Imports only `email_to_bom.core` (`load_config`), `email_to_bom.triage`,
  `email_to_bom.mail` (`looks_like_mime`, `html_to_text`) and `run_state`. NEVER
  `email_to_bom.cli`, never `run_engine`. Never writes to or copies the input file.
- **Done when:** each of the 11 t3 fixtures produces the intended outcome by hand
  (`6 filtered with 6 distinct codes / 5 passed through`), the same input twice yields an
  identical record, a 1 MB newsletter filters in < 2 s, and `python3 -S -E` runs it.

### t7 — Stop a stale filter record from sitting beside a fresh CaseState
- **file:** `src/scripts/run_engine.py`
- **depends_on:** t4
- Import `FILTER_KEY` from `run_state` and add it to the existing pre-work
  `write_state(..., drop=("extract_case",))` call, with a one-line comment: a record of a
  decision NOT to run the engine can only mislead once the engine has run — the sibling of
  R26-F1, in the new code path. No other behaviour changes; the engine invocation, argv
  and exit clamp are untouched.
- **Done when:** `parity_check.py` exits 0, `selftest.py` exits 0 (pre-t10 state), and a
  state file seeded with a `filter` record has it removed by a successful extract.

### t8 — Wire the gate into the recipe
- **file:** `src/recipes/mcgill-email-to-bom.yaml`
- **depends_on:** t6
- Add PHASE 0.5 `screen_input` between `prepare` and `extract_case`: run
  `python3 scripts/filter_gate.py --from-state --state _report/state.json`, then branch on
  the exit code ONLY — `0` continue, `3` STOP the run and report the `filter` record's
  `code`/`route`/`input` plus the documented `--no-filter` route to override, `1` a loud
  failure that stops the run. Explicit constraints: "NEVER decide yourself whether a
  message is a request — the script decides", "exit 3 is NOT an error and NOT a success —
  it means there was nothing to quote", "never treat 2 as anything (the gate cannot emit
  it)", "a filtered run produces NO case_state.json and NO bom_draft.md".
  `input: [_report/state.json]`, `output: [_report/state.json]`.
- Extend `prepare`: parse `--no-filter` and record it in state's `screen` record (it is
  NOT an engine flag — do not put it in `invocation`).
- Extend `extract_case`: constraint "if state.json records a filter decision with
  `filtered: true`, do NOT invoke run_engine.py — the run ended at screen_input".
- **Done when:** the recipe still loads the way the kit's own tooling loads it (whatever
  `tools/validate_manifest.py` / the build already do — do NOT add a YAML dependency,
  `requires.tools` stays `[]`), phase inputs/outputs stay consistent (REQ-013), and no
  phase re-types engine flags (REQ-034).

### t9 — Document the gate everywhere the kit describes itself
- **file:** `src/EXAMPLES.md`, `src/README.md`, `src/CLAUDE.md`
- **depends_on:** t2, t6
- One owner for all three so they cannot disagree.
  - `EXAMPLES.md`: keep all four required sections; add an Example ("a message that is
    not a request at all") with Prompt/Arguments/Expected workflow/Produces stating a
    filtered run produces NO artifacts; add a `--no-filter` row to the Argument
    Reference; add Common Patterns bullets for the gate's exit codes (`0/3/1`, and that
    `3` is not an error), for "the filter fails toward running the engine", and for the
    documented direct commands (`filter_gate.py` then `run_engine.py`).
  - `README.md`: add the gate to "What is inside", to the direct-invocation command
    block, and a "design line" bullet that the filter never silently discards.
  - `CLAUDE.md`: add the screen phase to "How to run", `--no-filter` to Arguments,
    "Never decide by hand whether a message is a request" + "Never treat the gate's 3 as
    a failure" to "What this kit must never do", the `filter` record to the deliverables
    table, and `schemas/filter_decision.schema.json` + `reference/filter_signals.json` to
    Reference material.
- Every documented command must run **verbatim** (REQ-027 / C6) — execute each one.
- **Done when:** each documented invocation was executed as written on `newsletter` and
  `bare-ack` fixtures and produced a CaseState + draft under `--no-filter`.

### t10 — Cover the gate's defences in the self-test, and mutation-prove them
- **file:** `tools/selftest.py`
- **depends_on:** t3, t6, t7
- Add `Defence 5…` sections in the existing flat style (`check()`, `sh()`, a `workdir()`
  sibling for `tools/filter/fixtures`, a small expectation table — no inline heredoc
  `.eml` bodies), covering:
  1. each of the six junk fixtures → gate exit 3, no `case_state.json`/`bom_draft.md` in
     `_report/`, a non-empty `code` and `route` (C1, C2);
  2. at least four (in practice six) DISTINCT codes across the six, and byte-identical
     records on a re-run (determinism, C2);
  3. all five adversarial fixtures → gate exit 0 and a CaseState produced by the normal
     path; `empty` → exit 0 or a loud non-zero, never "filtered" with a success-looking
     status (C5);
  4. three distinguishable outcomes: filtered = 3, drafted = 0, nonexistent input = 1,
     and the gate never returns 2 (C2, REQ-007);
  5. stale-artifact case: real RFQ to completion, then a newsletter in the SAME dir →
     both prior artifacts gone (C1, the R26-F1 category) and the `filter` record present;
  6. the sibling: a state file carrying a `filter` record, then a successful extract →
     the record is gone (t7);
  7. gated-path byte identity: gate then `run_engine.py` on `plain-steam` →
     `_report/case_state.json` byte-equal to
     `tools/parity/fixtures/plain-steam/expected_output.json`, and the input's sha256
     unchanged (C4 inside selftest, so parity stays blind to the gate);
  8. `--no-filter` on a junk fixture → CaseState + draft produced, input sha256 unchanged
     (C6);
  9. vocabulary consistency: the `code`/`route` enums in
     `schemas/filter_decision.schema.json` equal the t1 category codes/routes (plus
     `null`) — a mechanical drift check;
  10. cost: a generated ~1 MB newsletter (built in the temp dir, NOT committed) filters
      in well under the engine's cost at that size (C3).
- Any direct import of `filter_gate` happens INSIDE the check that needs it (ADR-018), so
  a missing symbol fails that check only.
- **Mutation proof (mandatory, C7):** mutate `filter_gate.decide` to (a) always pass
  through and (b) always filter; after EACH, `python3 tools/selftest.py` must exit
  non-zero AND `python3 tools/parity_check.py --manifest tools/parity/parity.json` must
  still exit 0; restore with `git checkout --` between, and leave
  `git status --porcelain` clean. Record in the task's commit message which named checks
  failed under each mutation.
- **Done when:** `python3 tools/selftest.py` exits 0, `parity_check.py` exits 0, and both
  mutations were observed to break selftest and NOT parity.

### t11 — Rebuild, revalidate and reship the kit
- **file:** `kit.json`, `registry-entry.json`, `dist/kit.zip`
- **depends_on:** t1, t2, t6, t8, t9
- Bump `version` (new capability, e.g. `0.4.0`), run
  `python3 tools/validate_manifest.py kit.json` then `./tools/build_kit.sh` (which
  regenerates `contents[]` — it must now list `scripts/filter_gate.py`,
  `schemas/filter_decision.schema.json`, `reference/filter_signals.json` — and `sha256`),
  and `git add -f dist/kit.zip`. `requires.tools` MUST stay `[]`.
- Then the C8 proof: unzip `dist/kit.zip` into an empty temp dir and, with no install
  step, run with `python3 -S -E` (a) the newsletter fixture → the same filtered decision
  and (b) `plain-steam/input.eml` → a CaseState byte-identical to its
  `expected_output.json`.
- **Done when:** validate + build exit 0, `contents[]` lists the three new shipped files,
  `requires.tools == []`, and both `-S -E` runs behave exactly as in the repo tree.

---

## Wave shape

| wave | tasks |
|---|---|
| 1 | t1, t2, t3, t4, t5 |
| 2 | t6, t7 |
| 3 | t8, t9, t10 |
| 4 | t11 |

No task deletes or renames a module or symbol, so no consumer fixups are pending at any
boundary; every task is additive or a self-contained edit and leaves
`python3 tools/parity_check.py --manifest tools/parity/parity.json` green on its own.
Every file has exactly one owning task: `run_state.py`→t4, `run_engine.py`→t7,
`filter_gate.py`→t6, recipe→t8, the three shipped docs→t9, `selftest.py`→t10,
`kit.json`/`registry-entry.json`/`dist/kit.zip`→t11. `src/vendor/**`,
`src/schemas/case_state.schema.json` and `tools/parity/**` are touched by NO task.
