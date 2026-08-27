# ACCEPTANCE — mcgill-email-to-bom kit, round 33

Pre-registered before the round-33 blind verification.

Rounds 25–32 **all returned FAIL**, and in every case the defect was introduced by the fix
pass for the previous round. Eight for eight.

v0.10.0 closes round 32: untrusted text is sanitised before rendering, every record is
rendered whole rather than through a key whitelist, and `render_reply.py` now reconciles
against a re-derived CaseState and fails closed.

**Three weaknesses the author already knows about are named below rather than hidden.**
Confirm or refute each, and then find what is not on this list — the pattern of this
campaign is that the next defect is one nobody named.

A check FAILS if it cannot be demonstrated by running something.

---

## Part A — the round-32 fixes, and their new surfaces

### Q-1 — `_safe()` and what it does not cover

`_safe()` strips whole ANSI sequences (`_ANSI` regex) and C0/C1 control characters, folds
whitespace, and truncates. **Known gap, unaddressed:** it does nothing about Unicode
format and bidi characters — RTL/LTR overrides (U+202E, U+202D, U+2066–U+2069),
zero-width space/joiner (U+200B–U+200D), soft hyphen, or homoglyphs.

- Can any of those make rendered customer text imitate the kit's own structure, reorder a
  line so a checkpoint reads as CLEARED, hide text from a reader, or make two visually
  identical lines carry different content? Judge how bad it is in a plain-text email body
  and in a viewer that honours bidi.
- Is the `_ANSI` regex complete for what a terminal acts on — 8-bit CSI (0x9B), OSC
  sequences, DCS, and escapes split across the values of two different fields that end up
  adjacent in the output?
- Does `_safe()` get applied at EVERY point untrusted text reaches the page? Enumerate the
  render sites and find one it misses. The author has already shipped two "I hardened the
  siblings but missed one" defects in this exact file.

### Q-2 — the reply's new reconciliation: false refusals and cost

`render_reply.py` now re-derives the CaseState and exits 1 on any difference.

- **Can a legitimate run be refused?** Anything non-deterministic, environment-dependent,
  or order-dependent between the extract pass and the reply pass would reject a correct
  case and stop an operator getting their draft. Try: an alternate `--config-dir`, a
  message near the HTML scan budget, unusual encodings, repeated runs, and different
  `PYTHONHASHSEED` values.
- A full run now makes **four** engine passes (recounted at pre-flight; the docs said
  three until `d33d3e6`). Is the fourth pass justified, and are the stated runtime figures
  now accurate?
- Is the reconciliation reachable-around? Does the recipe ever produce a `reply.md` from a
  CaseState that failed reconciliation in `generate_report.py`?

### Q-3 — the tested path is not the shipped path (known)

**Known weakness, unaddressed:** the synthetic-CaseState block in `tools/selftest.py`
renders with `--no-reconcile`, a flag the recipe never uses. That is the exact shape of
round 28's F-3 and round 31's finding, reintroduced inside the fix for round 32.

- Do the shipped-path checks cover what the synthetic block covers, or is whole-record
  rendering only ever exercised through a flag no real run passes?
- Are the `MUST-APPEAR-*` token checks meaningful, or satisfiable by coincidence? Round 32
  found one passing because its token also appeared in an unrelated line.

### Q-4 — completeness of the reply, again

Round 32 measured 10 of 17 CaseState keys faithful, 4 partial, 3 absent
(`class_evidence`, `questions`, `extraction`).

- Re-measure. Are the three absentees genuinely redundant (`questions` is the legacy twin
  of `open_items`; `extraction` overlaps `fields`), or does an operator lose something?
- Drive the field statuses that still have no fixture: `superseded`, `conflict`,
  `missing_gender`, `missing_spec`, `size_confirm`, `configuration_confirm`. Is the
  hand-written `UNCONFIRMED` set complete against the schema's enum? A status missing from
  it renders as though confirmed.
- Can the summary header disagree with the body — counts, urgency, `Applies:`?

---

## Part B — the standing bar

### Q-5 — the rounds 25–31 defences still hold

Flags survive the phase boundary; draft and CaseState describe the same case;
`generate_report.py` reconciliation fails closed; no failure path leaves a stale
`case_state.json`, `bom_draft.md` **or `reply.md`**; clearing failures are loud; every
clearing site resolves through the `ARTIFACTS` declaration; all three wrappers return only
0 or 1; a failed phase preserves the prepare record; a malformed schema fails open;
`--config-dir` survives the phase boundary.

### Q-6 — coverage, and report the number

The suite reports 69 checks. Mutation survival by round: 29 → 10/24, 30 → 15/34,
31 → 18/36, 32 → **33/51 (65%)**, of which 28 were in `render_reply.py`.

- Mutate every defence and **report how many survived**. That number is the measure.
- Hunt tautologies and checks that pass for the wrong reason. Round 32 found six, and
  three of the author's replacements still could not fail.
- Confirm parity stays green under renderer mutations — the renderer must not be entangled
  with what the engine sees.

### Q-7 — parity, vendor, shipped artifact, docs

Parity 7/7 with expected outputs regenerated from the source engine yourself; `src/vendor/**`
byte-identical; `validate_manifest.py` exits 0; `build_kit.sh` reproducible;
`requires.tools` `[]`; **zero** `email_attachment` tags; every declared artifact produced
by the recipe; the unzipped zip runs all phases from a clean dir under `python3 -S -E`.
Every factual claim in the shipped docs and the recipe true of the kit — rounds 25–32 each
found false ones, and the pass-count claim was wrong until pre-flight for this round.

### Q-8 — nothing sensitive, and nothing acts on message content

No credential in repo or zip; fixtures in RFC 2606 reserved namespaces; non-vendored
source makes no network call, no environment read, no subprocess, no `eval`/`exec`. Plant
injections and confirm nothing in the pipeline acts on them.

---

## The question to answer

**Is v0.10.0 safe to publish?** The instance serves v0.3.0, which predates every wrapper
defence and the inline reply.

## Out of scope

- Engine extraction/classification correctness (rounds 1–24).
- The no-attachment decision and the filter removal — both the operator's, already made.
- Roadmap phases 1–4.
