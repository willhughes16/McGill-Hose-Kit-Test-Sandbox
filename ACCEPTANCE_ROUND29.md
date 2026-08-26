# ACCEPTANCE — mcgill-email-to-bom kit, round 29

Pre-registered before the round-29 blind verification.

Rounds 25, 26, 27 and 28 **all returned FAIL**, and in every one the defect was introduced
by the fix pass for the previous round. That is a four-for-four record. Round 29 verifies
the round-28 fix.

**v0.6.0 is PUBLISHED and is what the instance serves.** Anything found here is live, so
severity is not theoretical. (v0.3.0, filter-free, remains available as a rollback.)

A check FAILS if it cannot be demonstrated by running something. The fix's author tested it
and reported 0-of-7 mutation survival; treat that as an unverified claim.

---

## Part A — the round-28 fix

### Z-1 — a real RFQ must never be filtered

The standing severe class. Round 27 lost 24/35; round 28 lost 15/39.

- Build your OWN corpus of at least 35 genuine quoting requests. Do not reuse round 27's
  or round 28's — both are now the fix's test cases. Report how many are filtered and
  confirm with `run_engine.py` that the engine would have drafted them.
- The protection is now `_spec_depth()`: a message is passed if the engine extracts ANY
  specification field, with **no category exempt**. So aim at requests carrying **zero**
  extractable specification: detail only in an attachment or an image; "same as last
  order"; "the usual for bay 4"; a bare part number; a drawing reference; a request
  written as a table; a request in another language; "can you price this up?".
- Round 28 disclosed a routing edge the author documented rather than fixed: a spec-less
  request carrying a machine header (`Auto-Submitted`, list-mail, a bounce marker) routes
  to **`no_action`** — filed where nobody looks — whereas the content categories route to
  a human. Quantify how easily that state is reached with a plausible real request, and
  say whether the disclosure matches the behaviour.

### Z-2 — the inverse failure: is the filter still capable of filtering?

Round 28 replaced a hand-written field tuple with a set derived from
`dataclasses.fields(core.Extraction)` minus `_NON_SPEC_FIELDS`. Deriving fixed a dead
name, but derivation can over-count.

- Is any `Extraction` field **always populated** for any non-empty input? If so, depth is
  always ≥1, nothing is ever filtered, and the whole feature is silently inert. Check
  every field, including `ends`, `end_fittings`, `material_recognized` (excluded — verify
  it really is), `length_type`, and anything with a non-None default.
- Measure depth across junk that SHOULD filter. How many of the six declared categories
  still actually filter in practice, on realistic junk mail rather than the shipped
  fixtures? Round 28's own fixtures give five; is that representative, or did removing the
  list-mail exemption gut the feature further than the author states?
- `_is_specified()` treats `False` as not-a-spec and `0` as not-a-spec. Is there a field
  where `0` or `False` is a real specification?

### Z-3 — the override

Round 28 made a recorded override require a matching `input`, and changed the recipe
template to write one.

- Does the override still WORK on the shipped path (recipe-written `screen` with `input`)?
- Does it correctly refuse: no `input` key, a different `input`, a relative-vs-absolute
  mismatch, a symlink, `./` prefixes, trailing whitespace, case differences?
- Did requiring `input` break the documented `--no-filter` command-line form?
- Can anything in the email enable it?

### Z-4 — `reason` validation, added in round 28

`_load_reason_pattern()` reads the shipped schema at RUN TIME on every decision.

- Does an unreadable, malformed, or pattern-less schema fail OPEN (never filter) rather
  than crash or filter?
- Is the regex anchored? Can a crafted reason slip through or wrongly be rejected?
- Does reading the schema per decision cost anything measurable on a large input?
- Do all reasons the gate can actually emit satisfy the declared pattern? Enumerate the
  emit sites in code and check each.

### Z-5 — nothing short-circuits the depth guard

Confirm by code path AND by probe that no category, header check, override path or early
return can reach `filtered: true` without the depth guard having run and returned 0.

---

## Part B — regressions and the standing bar

### Z-6 — the rounds 25/26/27/28 defences all still hold

- Flags survive the phase boundary; draft and CaseState always describe the same case.
- Reconciliation fails closed and cannot be defeated.
- No failure path leaves a stale `case_state.json` or `bom_draft.md`; clearing failures
  are loud; **all three** clearing sites resolve paths through the declaration (round 28
  found this closed at only two).
- `run_engine.py` / `generate_report.py` return only 0 or 1; `filter_gate.py` may also
  return 3, and only for a filtered message.
- A failed phase preserves the prepare record.
- Undecodable content is never judged — and verify these checks are not vacuous. Round 28
  proved two of them passed on `candidate is None` rather than on the guard.

### Z-7 — coverage is real, and report the number

The self-test reports 121 checks. Rounds 26, 27 and 28 each had **9** behaviour-changing
mutations leave the suite green.

- Mutate every defence and report **how many mutations survived**. That number, not the
  check count, is the measure.
- Hunt vacuous checks specifically. The author retargeted many checks from the
  `newsletter` fixture to `invoice-statement` when the newsletter stopped being
  filterable; verify that retargeting did not weaken any check, leave a check asserting
  something it no longer tests, or reduce distinct-category coverage.
- Confirm parity stays green under gate mutations.

### Z-8 — parity, the vendored engine, the shipped and published artifact

- Parity 7/7, every `normalize` empty, expected outputs regenerated from the source engine
  yourself.
- `src/vendor/**` byte-identical to the source; `tools/parity/**` unmodified.
- `validate_manifest.py` exits 0; `build_kit.sh` reproducible; `requires.tools` `[]`;
  exactly ONE `email_attachment`; the unzipped zip runs both paths from a clean dir under
  `python3 -S -E`.
- The upload package rebuilt from repo HEAD must equal published v0.6.0, sha256
  `a5ee0534978a98fe0495a41cabce1f90f2fae1bbe4ba2a8a3b145750bbaf71cf`.

### Z-9 — documentation makes no false claim

Rounds 25–28 each found false documented claims; round 28 found four, one of which
documented the F-1 bug as working. Verify every factual statement in `src/README.md`,
`src/CLAUDE.md`, `src/EXAMPLES.md`, `src/recipes/mcgill-email-to-bom.yaml`,
`src/scripts/filter_gate.py`'s module docstring and `src/vendor/PROVENANCE.md` — including
the stated field list, the routing claim, the accepted-cost statement about newsletters,
and the documented commands.

### Z-10 — nothing sensitive, no new I/O, no acting on message content

- No credential in repo or zip; every fixture address in an RFC 2606 reserved namespace.
- Non-vendored source: no network, no environment read, no subprocess, no `eval`/`exec`.
- Plant injections (forged override headers, a fake `screen`/`filter` record in the body,
  prose instructing a re-run with `--no-filter`, authority claims) and confirm they do
  nothing.

---

## The question to answer

**Should v0.6.0 stay published, or be rolled back to v0.3.0?** State it plainly, with the
finding that drives the answer.

## Out of scope

- Engine extraction/classification correctness (rounds 1–24), except as the oracle for
  "would this RFQ have produced a draft".
- The deferred follow-ups in `.astrocode/PROJECT.md`. Whether they are described honestly
  IS in scope.
- Roadmap phases 1–4.
