# ACCEPTANCE — mcgill-email-to-bom kit, round 31

Pre-registered before the round-31 blind verification.

Rounds 25–30 **all returned FAIL**, and in every case the defect was introduced by the fix
pass for the previous round. Two builds were published before being verified and both were
dropping real customer requests (v0.4.0: 24/35 RFQs; v0.6.0: 11/46); both were rolled back.

Round 30 recommended deleting the input filter, and v0.8.0 does exactly that. This is
therefore a **removal** round, not a feature round, and the risk profile is different: the
danger is no longer a bad decision the code makes, but damage left behind by the surgery.

The removal was done largely with regular-expression edits across code, the recipe and the
docs. That is precisely the kind of edit that leaves subtle wreckage, and this author has
had three unasserted string replacements silently fail in this campaign. Assume the surgery
left damage and go looking for it.

A check FAILS if it cannot be demonstrated by running something.

---

## Part A — did the removal leave damage?

### V-1 — the code is whole

- `src/scripts/run_state.py`, `src/scripts/run_engine.py` and `src/generate_report.py`
  after the excisions: no dangling import, no reference to a deleted name, no function
  left half-removed, no unreachable or now-unused definition. Import each module cleanly
  and exercise every public function.
- Is every remaining definition in `run_state.py` actually used? A helper left behind
  after its only caller was deleted is dead code that will confuse the next change.
- Does anything still reference the deleted `filter`/`screen` state keys, `filter_gate`,
  `filter_signals.json`, `filter_decision.schema.json` or `tools/filter/`?

### V-2 — the recipe is coherent and executable

The recipe is the **binding execution contract** and it was edited by regex.

- Read it as a human would. Are there truncated sentences, dangling clauses, orphaned
  references to a phase that no longer exists, or constraints that reference removed
  behaviour? Round 30 found the deleted categories still named in this file.
- Does it parse as YAML, do its phases form a consistent input/output chain, and does
  every command it prescribes actually work when run verbatim?
- Do its `goal` and `constraints` describe what the scripts now do?

### V-3 — the self-test did not lose coverage silently

The suite went from 124 checks to 28. Most of that is legitimate — 96 checks tested a
deleted feature — but the blocks were removed by pattern matching.

- Was any block truncated mid-way, leaving a check that no longer asserts what its label
  says, or a `check(...)` whose setup was deleted?
- Are all twelve named wrapper defences from rounds 25–28 still present and still testing
  their invariant? Enumerate them against the round-26/27/28 reports.
- **Mutate every remaining defence and report how many mutations survive.** Rounds 26–28
  each had 9 survive; round 29 had 10 of 24; round 30 had 15 of 34 and found a tautology
  that had been reported closed twice. That number is the measure, not the check count.
- Hunt tautologies and checks that pass for the wrong reason.

### V-4 — the surviving defences actually hold

Independently, not by reading the suite:

- Flags survive the phase boundary; the draft and the CaseState always describe the same
  case.
- Reconciliation fails **closed** on an absent / directory / unreadable CaseState and
  cannot be defeated.
- No failure path leaves a stale `case_state.json` or `bom_draft.md`; clearing failures
  are loud; every clearing site resolves its path through the `ARTIFACTS` declaration
  (round 28 found this closed at only two of three sites; round 30 found the check for it
  tautological).
- `run_engine.py` and `generate_report.py` return only 0 or 1 — the engine's 2 never
  leaks, including from argparse inside `cli.main`.
- A failed phase preserves the prepare record.
- A malformed schema fails open rather than crashing.

---

## Part B — the standing bar

### V-5 — parity and the vendored engine

Parity 7/7 with every `normalize` empty, and regenerate all seven expected outputs from
the source engine yourself rather than trusting the committed files. `src/vendor/**`
byte-identical to the source at the commit `PROVENANCE.md` stamps; `tools/parity/**`
unmodified.

### V-6 — the shipped artifact

`validate_manifest.py` exits 0; `build_kit.sh` reproducible byte-for-byte;
`requires.tools` `[]`; exactly ONE `email_attachment`; every declared artifact produced by
the recipe; `EXAMPLES.md` still has all four required sections after the pruning; the
unzipped `dist/kit.zip` runs the full flow from a clean directory under `python3 -S -E`
with no install, and its `case_state.json` matches the source capture byte-for-byte.

### V-7 — documentation describes what exists

Every round from 25 to 30 found false documented claims; round 30 found nine. The docs
were just pruned by regex, so check for the opposite failure too — text that now
describes nothing, or a sentence left mid-thought.

- Every factual statement in `src/README.md`, `src/CLAUDE.md`, `src/EXAMPLES.md`, the
  recipe, and `src/vendor/PROVENANCE.md` must be true of the shipped kit.
- Every documented command must exist and work as written.
- No stale reference to the filter, its exit code `3`, its `--no-filter` override, its
  schema or its reference data.
- `EXAMPLES.md`'s examples must still be internally consistent: the stated open-item
  codes, BOM-line counts and exit codes must match what a real run produces.

### V-8 — the project record is honest

- `.astrocode/PROJECT.md`: are REQ-057/058/059 and the round-30 table accurate? Does any
  earlier requirement now describe deleted code as if it were live?
- The roadmap still marks phase 5 `complete` from a UAT sign-off, while the feature it
  delivered has been deleted. Is that inconsistency recorded anywhere a reader would find
  it?
- Do any of the ten deferred follow-ups now reference removed code?

### V-9 — nothing sensitive, no new I/O

No credential in repo or zip; every fixture address in an RFC 2606 reserved namespace;
non-vendored source makes no network call, no environment read, no subprocess, no
`eval`/`exec`. Confirm the deletion did not leave a credential-shaped or network-touching
remnant.

---

## The question to answer

**Is v0.8.0 safe to publish?** The instance currently serves v0.3.0, which predates the
rounds 25–28 wrapper defences, so a pass here means a genuine improvement can ship.

## Out of scope

- Engine extraction/classification correctness (rounds 1–24).
- Re-litigating the decision to remove the filter. It is removed on the operator's
  explicit instruction. Whether the removal was done *cleanly* is entirely in scope.
- Roadmap phases 1–4.
