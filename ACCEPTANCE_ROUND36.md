# ACCEPTANCE — mcgill-email-to-bom kit, round 36

Pre-registered before the round-36 blind verification.

Rounds 25–35 **all returned FAIL** — eleven for eleven, every defect introduced by the
previous fix pass. But the numbers converge: mutation survival 65% → 39% → 32% → **25%**
(round 35: 14/55, honest real-regression subset 6/55 = 11%), CaseState fidelity
10/17 → **13/17 strict, 15/17 shipped-path**, and rounds 33, 34 and 35 each **refuted** a
weakness the author named.

Round 35's verdict was "the narrowest of the campaign" and its closing line was that
v0.12.0 was "one honest pass from the campaign's first PASS". v0.13.0 is that fix plus
round 35's three MEDIUMs.

A check FAILS if it cannot be demonstrated by running something.

---

## Part A — round 35's fixes, and two items carried forward under protest

### K-1 — the sixteenth sibling, and every remaining falsy filter

Round 35's blocker: the `extraction` section's filter still contained `False` in its
drop-tuple after round 34 fixed the identical one in the backstop. Casualty:
`extraction.material_recognized: False` vanished entirely — hidden from the backstop by
`take("extraction")` and swallowed by the filter.

- Confirm the fix, then **sweep for the seventeenth**. Every place the renderer filters a
  collection: are there other `not in (None, "", [], {}, False)` or truthiness tests
  where a falsy value is real information? Check `_open_item`'s per-key loop, the
  checkpoint extras loop, the off-column BOM loop, `long_values`, `_urg_extra`,
  `_know_extra`, `extra_ex`, and the backstop itself.
- Two of these were fixed as *latent* siblings in the same pass (`class_evidence`,
  `knowledge` extras). Were they fixed correctly, and is anything else latent?

### K-2 — CARRIED FORWARD: two checks verified by inspection, not by execution

**The author could not execute the full mutation loop.** A sandbox classifier blocked shell
commands mid-pass. Four of six round-35 fixes were confirmed by executed mutation; the two
latent-sibling checks (falsy `class_evidence`, `knowledge` extras) were verified falsifiable
**by reading the code** — each mutation removes exactly the line its token lives on — which
is weaker than this campaign's standard.

**Re-verify them by execution.** Mutate each and confirm the suite fails. If either cannot
fail, that is a finding, and the inspection-based reasoning was wrong.

### K-3 — what else has the golden suite enshrined?

Round 35's sharpest finding generalises beyond its instance. The golden suite's expected
files are captured from the kit's own output, so **it will bake in a live defect** — and
then *fixing* that defect turns the suite red, which pressures a fix pass into re-capturing
rather than fixing. That is exactly what happened with `material_recognized: False`.

- Audit both golden fixtures against the CaseState they render. Is anything else in those
  expected files wrong-but-frozen?
- Is `tools/golden/README.md`'s framing (change-detector, not correctness proof; re-capture
  is deliberate; read the diff) adequate protection, or does the suite need a structural
  guard — e.g. a check that every non-empty CaseState key appears in the golden reply?
- Can `capture.py` be run accidentally as part of a normal workflow?

### K-4 — M-2's fix: artifact paths and the suites

Round 35 found suite runs deleting a real run's `_report/bom_draft.md` and `reply.md`,
because fixture commands set only `--out` and sibling defaults resolved to the CWD. Siblings
now follow `--out`'s directory.

- Verify with sentinels, from several working directories.
- Is the fix complete? `generate_report.py` and `render_reply.py` also have `--out`
  defaults — do their siblings resolve safely?
- The parallel-run race on the shared fixture `_report/` that round 35 noted: still there?

### K-5 — M-3's fix: ordering, and other unasserted behaviour

Reversing `PRIORITY_ORDER` used to pass every check. Now asserted.

- What other *ordering or arrangement* is unasserted? Section order in the reply, field-row
  ordering, `sorted()` calls whose stability matters, the order of open items within a
  priority group.
- Round 35 noted `knowledge` renders a fixed 3-key subset (fixed) — is anything else
  rendering a subset that looks complete?

---

## Part B — the standing bar

### K-6 — the rounds 25–35 defences

Flags survive the phase boundary including `--config-dir`; both reconciliations fail
closed; no failure path leaves a stale `case_state.json`, `bom_draft.md` or `reply.md`;
clearing failures are loud; every clearing site resolves through `ARTIFACTS`; all three
wrappers return only 0 or 1; a failed phase preserves the prepare record; a malformed schema
fails open; the `UNCONFIRMED` set is complete; falsy values survive the backstop; whitespace
folds rather than vanishing; untrusted text cannot forge the document's structure.

### K-7 — coverage, and report the number

Suites: selftest 106, parity 7, golden 2.

- Mutate every defence and **report survival across the COMBINED suites**. The sequence is
  65% → 39% → 32% → 25%.
- Hunt tautologies and coincidence-matches. Round 34 found a check passing via a fallback
  line rather than the table it named; round 35 found a golden fixture with no second
  priority group.

### K-8 — parity, vendor, shipped artifact, docs

Parity 7/7 with expected outputs regenerated from the source engine yourself; `src/vendor/**`
byte-identical to `b15b23d`; `validate_manifest.py` exits 0; `build_kit.sh` reproducible;
`requires.tools` `[]`; **zero** `email_attachment` tags; every declared artifact produced by
the recipe; the unzipped zip runs all phases from a clean dir under `python3 -S -E`. Every
factual claim in the shipped docs true — all eleven rounds found false ones.

### K-9 — nothing sensitive, nothing acts on message content

No credential in repo or zip; fixtures in RFC 2606 namespaces; non-vendored source makes no
network call, no environment read, no subprocess, no `eval`/`exec`. Plant injections and
confirm nothing acts on them.

---

## The question to answer

**Is v0.13.0 safe to publish?** The instance serves v0.3.0, which predates every wrapper
defence and the inline reply — so the cost of another FAIL is that users keep the older,
weaker build.

If the answer is no, **name the single blocker**. If the answer is yes, say so without
hedging and list what you tried that did not break it, so the pass is auditable. After
eleven FAILs an earned PASS is as valuable as an honest FAIL — do not manufacture a finding
to keep the streak, and do not soften one to end it.

## Out of scope

- Engine extraction/classification correctness (rounds 1–24).
- The no-attachment decision and the filter removal — both the operator's.
- Roadmap phases 1–4.
