# ACCEPTANCE — mcgill-email-to-bom kit, round 37

Pre-registered before the round-37 blind verification. Written against v0.20.0
(`d9ccc11`), which is **already published** — the operator shipped it deliberately
without this round, so a blocker here means a rollback, not a delayed release.

Rounds 25–36 all returned FAIL, every defect introduced by the previous fix pass,
with the numbers converging: mutation survival 65% → 39% → 32% → 25%, CaseState
fidelity 10/17 → 16/17 shipped-path.

**Round 37 is not another fix-pass audit.** Since round 36 the kit gained more new
surface than any round has ever examined at once, and none of it has been seen by a
verifier:

- **Two engine re-vendors.** Rounds 25–36 all ran against `b15b23d`. The kit now
  vendors `6b0a897`, whose behaviour is that of `ae4411f` ("size is not a length",
  scored on 140 real threads) plus a freshness change that left parity byte-identical.
- **Five new shipped scripts**: `attachments.py`, `answers.py`, `apply_answers.py`,
  `routing.py`, `render_review.py`, plus `config/routing.json` and
  `schemas/correction.schema.json` and the kit-side `tools/correction_check.py`.
- **A changed outcome contract** (REQ-097) and a second reader (`review_request.md`).

A check FAILS if it cannot be demonstrated by running something.

---

## Read this first: the author's conflict, stated plainly

**The same session wrote the code, the tests, and this bar.** That has been true of
earlier rounds too, and it is the single biggest reason to distrust what follows.
Concretely, today's work was checked only by its author, and the author's own
mutation runs caught **three of the author's checks that could not fail**:

1. a filename test that matched the `Outcome:` line four rows above the section it
   claimed to assert;
2. a tampered-CaseState test that the *reply* guard was satisfying, not the guard it
   named;
3. a freshness test that crashed the suite on a KeyError, which the mutation harness
   reported as "defence uncovered" because it counts FAIL lines and the suite never
   reached them.

**Assume more exist.** Three were found by the author looking; the ones that matter
are the ones the author did not think to look for.

---

## Part A — the new surface, in order of how badly it could hurt a customer

### K-1 — CW-6: can an operator's words be read as the customer's?

This is the sharpest risk in the kit and the author said so before building it.
`apply_answers.py` appends a reviewer's out-of-thread answer to the case text; the
engine reads it as a later message. Everything after the FIRST `answers.MARKER` is
operator-supplied by definition.

Attack it:

- **The marker in customer text.** `apply_answers.py` refuses if the RFQ already
  contains the marker. But `split()` is also called by `render_reply`, `render_review`
  and `run_engine` on ANY input. Send an RFQ whose body contains the marker and run
  the ordinary pipeline with no addendum at all. Does the reply claim an operator
  addendum that does not exist? Does it label the customer's own later sentences as
  an operator's? Either is a fabrication, in the opposite direction from the one the
  feature was built to prevent.
- **Attribution soundness.** `classify()` folds whitespace and case, and returns
  `OPERATOR` only when a span is absent from the customer's region. Construct a case
  where an operator-supplied value's evidence span ALSO appears in the customer's text
  (the customer wrote "not 150 psi", the operator wrote "150 psi") — is it reported as
  `SOURCE UNCLEAR`, and is that good enough for a reviewer?
- **`UNATTRIBUTABLE` is silent in the table.** Fields with no evidence span are named
  once in the banner and carry no row mark. Is the banner list complete? Can a field
  the operator supplied end up there instead of marked `OPERATOR-STATED`?
- The round-trip guard exists because the author found a real forwarded-thread case
  that breaks it. Find another shape it misses.

### K-2 — CW-1: which attachments does the classifier fail to report?

`attachments._classify` decides by disposition, filename, `Content-ID` and text
subtype. The author believes two specific holes may exist and did not close them:

- **A real drawing sent `Content-Disposition: inline` WITH a `Content-ID`** is
  classified `embedded` — named only on the headline, no `EVIDENCE NOT READ` block,
  and, since REQ-097 reads `attachments` only, **it does not force
  `needs_human_input`**. Build that message. Is a customer's dimensioned drawing
  demoted to signature-logo treatment?
- **A second inline `text/plain` part** that is not a multipart/alternative sibling is
  treated as a body candidate and never flagged, while the engine reads only one of
  them. The docstring admits this. Is it reachable with a realistic message?
- Nested multipart, `message/rfc822` attachments, a part whose headers raise while
  being inspected, zero-byte and undecodable parts.

### K-3 — CW-4/CW-5: the reviewer's document

- The review request embeds the reply verbatim, and the author documented that its
  CaseState reconciliation is **defence-in-depth with no check that can kill it** —
  two attempts to write one both ended up exercising the reply guard. **Find a pair
  that slips past BOTH guards**, or demonstrate that none exists.
- `config/routing.json` ships with every address `null`, so every real case renders
  `NOT ROUTABLE`. The routable branch is exercised only by a synthetic table in the
  selftest. Is the feature usable, and does anything downstream mistake NOT ROUTABLE
  for "no owner"?
- `routing.keys_in` walks `routing.recommendation`, `open_items[].route` and
  `checkpoints[].owner`. Is there a fourth site in the CaseState that names an owner?

### K-4 — CW-2/CW-3: the run contract

- `idempotency_key` hashes content + flags, not path. Two genuinely different cases
  that collide, or one case that should be a retry and is not?
- `outcome` is derived from blocking items and unread attachments. Construct a case
  that needs a human for a reason **neither** ground catches.
- A failed run writes no manifest — "absence is the failure signal". Find a failure
  path that leaves one, or a success path that does not.
- `KIT_VERSION` is a second copy of `kit.json`'s version, guarded by one assertion.

### K-5 — CW-7 and CW-8

- `correction_check.py` compares `original` byte-for-byte against the artifact. Can a
  correction be made replayable that should not be, or refused that should not be?
- The freshness contract **ships dormant** — no real run produces a lookup. Is the
  kit-side check exercising the shipped module, or a copy? Does `_freshness` have a
  path that reports something as fresher than it is?

---

## Part B — the standing bar

### K-6 — the rounds 25–36 defences still hold

Flags survive the phase boundary including `--config-dir`; every reconciliation fails
closed; no failure path leaves a stale artifact (now SIX: `case_state.json`,
`bom_draft.md`, `reply.md`, `run_manifest.json`, `review_request.md`, and
`augmented_input.txt` which is deliberately NOT cleared — confirm that is right);
clearing failures are loud; every clearing site resolves through `ARTIFACTS`; all
wrappers return only 0 or 1; a failed phase preserves the prepare record; falsy values
survive the backstop; whitespace folds rather than vanishing; untrusted text cannot
forge the document's structure — **including the new banner, block and separator
lines**, which are new forgeable structures.

### K-7 — coverage, and report the number

Suites: selftest 224, parity 7, golden 2, completeness 184.

- Mutate every defence and **report survival across the COMBINED suites**. The
  sequence is 65% → 39% → 32% → 25%. Say whether your figure is comparable, given the
  engine changed underneath it.
- Report **CaseState fidelity** against the 17-key standard.
- Hunt tautologies and coincidence-matches. Three were found today by the author; the
  new checks in `tools/selftest.py` after line ~400 are the least-reviewed code here.
- The golden suite covers `reply.md` only — **no golden fixture renders a review
  request or an addendum case**, so rendering changes there are invisible to it.

### K-8 — parity, vendor, shipped artifact, docs

Parity 7/7 with expecteds regenerated from the source engine yourself; `src/vendor/**`
byte-identical to `ScaleUpLabs/McGill-Core` at `6b0a897` (now on that repo's `main` as
`270f32b`); `validate_manifest.py` exits 0; the published package is the publisher's
own build (29 `src/` files + `kit.json`, sha `852edc2f`) — confirm nothing unintended
ships; **zero** `email_attachment` tags; every declared artifact produced by the
recipe; the unzipped zip runs all phases from a clean dir under `python3 -S -E`.

**Every factual claim in the shipped docs true.** All twelve rounds found false ones,
and today one had been false for three weeks (the "instance serves v0.3.0" line). The
docs grew by ~700 lines today.

### K-9 — nothing sensitive, nothing acts on message content

No credential in repo or zip; fixtures in RFC 2606 namespaces; non-vendored source
makes no network call, no environment read, no subprocess, no `eval`/`exec` —
**re-check this: `apply_answers.py` and `correction_check.py` are new and read files
named on the command line.** Plant injections in an email, in an answers file, and in
a correction record, and confirm nothing acts on them.

---

## The question to answer

**Should v0.20.0 stay published, or be rolled back?**

It is live now. The operator's stopping rule is: *ship when no finding would give a
customer a wrong answer.* So:

- A finding whose consequence is a **wrong or missing answer reaching a customer**
  means roll back. Name it as the single blocker.
- A finding that breaks a **stated guarantee** without changing what a customer
  receives does not.
- A **coverage gap** — a defence a mutation removes undetected while the shipped code
  is correct — does not. Log it.

If nothing blocks, say so without hedging and list what you tried that did not break
it, so the pass is auditable. After twelve FAILs an earned PASS is as valuable as an
honest FAIL — do not manufacture a finding to keep the streak, and do not soften one
to end it.

## Out of scope

- Engine extraction/classification correctness (rounds 1–24) except where the two
  re-vendors changed it.
- The no-attachment decision, the filter removal, the unread-attachment outcome rule,
  and publishing without this round — all the operator's decisions.
- Roadmap phases 1–4.
