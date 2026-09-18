# Verification campaign runbook — read this first

You are continuing a blind-verification campaign on this kit. Rounds 25–36 all
returned FAIL, and in every case the defect was introduced by the fix pass for the
previous round. Full reports are `VERIFICATION_ROUND25.md` … `VERIFICATION_ROUND36.md`;
the requirement ledger is `.astrocode/PROJECT.md` (REQ-001…REQ-096).

The operator's standing instruction: **run rounds, fix findings, and publish when
ready.** They have twice authorised rolling a bad version back off the instance, and
both rollbacks worked.

> **READ THIS BEFORE PLANNING A ROUND: the repo and the instance disagree, on purpose.**
> `main` carries **v0.26.0**. The instance serves **v0.21.0**. Round 38 failed v0.26.0
> on a blocker in the customer-facing translation layer, and v0.26.0 and v0.25.0 were
> DELETED from the instance on 2026-09-18 (HTTP 204 each, read back between). Their code
> is intact on `main` at `2fae5e7` and `940e5e8` and can be re-published once the layer
> is fixed.
>
> So: **do not assume the shipped version is the published one**, and do not read a green
> suite as evidence that what customers receive is correct. Round 38's blocker passed
> every suite in this repo.
>
> (Historical, now settled: rounds 25–36 ran against the engine at `b15b23d`; the kit has
> vendored `6b0a897` since v0.20.0, and rounds 37 and 38 both tested it.)

---

## STATE AS OF THIS FILE (2026-09-18, after round 38)

| | |
|---|---|
| `main` | `5a406df` — clean, pushed |
| Repo version | **v0.26.0** (`kit.json` and `dist/kit.zip` current, not stale) |
| **Instance serves** | **v0.21.0** — rolled back after round 38 |
| Campaign | **round 38 FAIL — fourteenth consecutive** |

**Two rollbacks in one day.** Round 37 failed v0.20.0 (an operator answer erased the
customer's attachments from the whole run); it was fixed forward in v0.21.0 and v0.20.0
was deleted. Round 38 then failed v0.26.0 on a worse defect and v0.26.0 + v0.25.0 were
deleted, leaving v0.21.0 live.

**What the rollback reinstated**, and what will therefore happen again until it is
undone: the phantom assembly (a multi-line PO merged into one invented specification),
the 9 KB reply, and the bare-HTML failure — job `2e07005c`, where the PO vanished from
the run and the customer was asked to clarify a CSS font size.

**`prepare_input.py` and the phase 1–2 fixes are NOT implicated in round 38's blocker**,
which is confined to `config/questions.json` and `render_customer`. Rebuilding forward
from v0.24.0 — keeping the multi-item detector, the transcript relocation, the delivery
declaration and the input assembler, and redoing the customer email — is likely better
than fixing v0.26.0 in place. **That decision is not made; make it first.**

What landed since round 36, in order:

- **The engine was re-vendored at `ae4411f`** (commit `f6e8d38`) — "size is not a
  length", scored against **140 real McGill threads**. Size captured **6 → 68 of 131**;
  three phantom lengths eliminated (the extractor was reading a phone number as a hose
  length). It also found that this kit's own parity fixture had *enshrined* the defect,
  so four expecteds were re-captured with the diffs read. `src/vendor/**` is
  byte-identical to `~/Desktop/McGill/email-to-bom-agent` at `ae4411f`.
- **Round 36's backlog is closed** (commit `81006e7`), each item mutation-proved by
  execution: REQ-088 (`UNCONFIRMED` enumeration deleted — 6 of 10 members had been
  deletable with the suite green), REQ-089 (loud `write_state` failure), REQ-090 (no
  0-byte CaseState), REQ-091 (falsy knowledge-extras). Coverage 110 → 129.
- **v0.16.0 — CW-1..CW-3** (commit `0aa2932`), derived from the Coworker architecture
  document; the assessment and the five unbuilt features are in
  `COWORKER_ALIGNMENT.md`. New: `src/scripts/attachments.py` names every file the
  engine never read (it has no attachment handling at all), `_report/run_manifest.json`
  records kit version / engine commit / input sha256 / `idempotency_key` /
  `evidence_not_read`, and `outcome` states `complete` vs `needs_human_input` in words,
  **derived** from `open_items[]`. REQ-092…REQ-096.
- **REQ-096**, found while doing the above: with `--out` redirected, the previous
  customer's CaseState survived at the conventional `_report/case_state.json`. The
  **eighteenth** missed sibling, on the one key that had been exempted *by name*.

- **v0.17.0 — REQ-097**: an unread attachment forces `outcome: needs_human_input` on
  its own. The operator's decision on the question v0.16.0 left open. An inline
  signature image does not force it; a scan that did not complete does.
- **v0.26.0 — REQ-119/120**: `scripts/prepare_input.py` builds the `.eml` from what the
  runtime ACTUALLY delivers — a body file plus `input/` attachments — and `run_engine.py`
  refuses a bare HTML input. Fixes job `2e07005c`, where the PO vanished from the run and
  a CSS font size became a customer question. **Not implicated in round 38's blocker.**
- **v0.25.0 — REQ-116..118 (phase 3)**: `reply.md` became the CUSTOMER's email;
  `config/questions.json` rewords open items (the ONE place that is permitted);
  completeness moved to `--record`. **This is the layer round 38 failed.**
- **v0.24.0 — REQ-114/115 (phase 5)**: `run_manifest.deliver` declares the customer's
  source files for the REVIEWER's message; the customer reply still carries nothing. A
  declaration only — Body must implement the attaching, and has not.
- **v0.23.0 — REQ-112/113 (phase 2)**: the machine transcript moved out of the reply into
  the review request; the reviewer's grounds became grounds rather than a document dump.
- **v0.22.0 — REQ-111 (phase 1)**: `scripts/lineitems.py` — a document describing many
  products is no longer presented as one specification. Two MEASURED thresholds
  (`ROW_MIN=3` because a subtotal line matches the item pattern; `DIM_MIN=5` because a
  hose-plus-reducer honestly names 3). **Known false negative, since confirmed by the
  external review as D04:** a two-item list naming four dimensions is NOT flagged, and
  the engine then captures quantity `1` from the list number.
- **v0.21.0 — REQ-105..110**: four defects from a real production run (a PO sent as a
  PDF), three of them introduced the same day — including a recipe phase that forced an
  agent to hand-write a kit artifact, and a v0.19.0 defect where augmenting the case
  text LOST the attachment report. Plus CW-9: a machine may transcribe an attachment
  into a third authored region; it may not answer. **Aim a round at CW-9 and at
  `source_input()`** — both are new on the shipped path.
- **v0.20.0 — REQ-104 (CW-8)**: the engine was re-vendored again, at `6b0a897`, for
  knowledge freshness. **Parity stayed 7/7 byte-identical**, so unlike the `ae4411f`
  re-vendor this one provably does not change the kit's output — only `knowledge.py`
  differs, and the kit's default source never calls it.
- **v0.19.0 — REQ-100..103 (CW-6, CW-7)**: `scripts/apply_answers.py` folds a
  reviewer's out-of-thread answer into the case TEXT as an operator addendum — never
  into the CaseState — and everything downstream marks which values came from an
  operator rather than the customer. `schemas/correction.schema.json` plus
  `tools/correction_check.py` make a reviewer correction replayable or refuse it.
  **Aim a round here first:** this is the feature the alignment doc flagged as most
  likely to fail one, and its round-trip guard already survived a mutation run before
  a fixture was built for it.
- **v0.18.0 — REQ-098/099 (CW-4, CW-5)**: `scripts/render_review.py` writes
  `_report/review_request.md` — the reviewer's document, with the proposed response
  EMBEDDED VERBATIM so a reviewer approves the exact bytes that would be sent, and
  every owner resolved through `config/routing.json`, which ships with all addresses
  empty and renders NOT ROUTABLE rather than guessing. A full run now costs FIVE engine
  passes (extract 1, generate_report 2, render_reply 1, render_review 1).

Suites at v0.26.0 (the repo version): selftest **311/311**, parity 7/7 (zero
normalizations), golden 3/3, completeness 184 combinations / 0 violations, manifest
valid. Mutation runs across CW-1..CW-9 and the five PLAN_TURMOIL phases: **~90 attempted,
all but one caught**, and the survivor is the defence-in-depth guard noted below —
which round 37 then refuted as unkillable.

**Read that paragraph with round 38 in mind.** Every one of those numbers was green when
the blocker shipped. The suites verify that each part does what it says; nothing in them
compared the customer's QUESTIONS against the customer's ANSWERS, which is where the
defect lived. A count of passing checks is not evidence about what a customer receives.

### There is a LARGE backlog, from three sources

Unlike round 37, this round does not start clean. Merge these before planning:

1. **Round 38 — five blockers, two highs, four mediums** (`VERIFICATION_ROUND38.md`), all
   in the translation layer. The blocker is a CLASS: five of the twenty-six
   customer-facing translations fire only when a field is `reading`/`assumed`, and
   `render_customer` prints only `captured` fields — so the questions and the answers
   are disjoint by construction, and a customer confirming "yes" is confirming a number
   they never saw. Two translations state the OPPOSITE of what the engine recorded.
2. **Round 37 — ten unfixed findings** (`VERIFICATION_ROUND37.md`): M-2 (a marker in a
   customer's own text fabricates an operator addendum — still live), M-3, H-2, H-3,
   M-1, M-4, M-5, L-1..L-4.
3. **An independent external review** — `/Users/axr/Desktop/McGill/CLAUDE_CODE_HANDOFF.md`,
   12 findings (D01–D12) with reproductions, prepared 2026-09-17. Seven are ENGINE issues
   for `McGill-Core` including a `ZeroDivisionError` crash on `1/0 inch`; five are kit.
   D04, D06 and D08 were reproduced independently in-session. Its companion,
   `KIT_CLOSURE_INFORMATION_CHECKLIST.md`, is a set of collection requests and decisions
   for the operator, not claims.

**Operator decision already taken:** fix D06 first — a shared typed formatter for units,
`{value}` interpolation in `questions.json` filled from the field each open item names,
summary stays captured-only and the unconfirmed value rides in the QUESTION. Round 38
then showed D06 is bigger than formatting: seven codes are wrong on MEANING.

### Dormant by design — do not report as a defect

**CW-8's freshness contract ships but never fires.** The kit's default knowledge
source is `NullKnowledge`, which performs no lookups, so no real run carries a
`freshness` at all until FOLLOW-UP-1 wires the graph. The kit's checks exercise the
vendored module directly for that reason. All eight CW features shipped across
v0.16.0–v0.20.0.

**One guard is documented as defence-in-depth, not as covered.**
`render_review.py`'s CaseState reconciliation cannot be isolated by a test — the reply
guard refuses the same pairs, and REQ-093 stops a forged reply carrying a scanned
attachment record. Its docstring says so. A verifier finding "this check is not
covered" is finding something the code already admits; finding a pair that slips past
BOTH guards would be a real one.

(The other item that stood here — whether an unread attachment should force
`needs_human_input` — was **decided by the operator on 2026-09-17** and is now REQ-097,
shipped in v0.17.0. Both grounds are derived; an inline signature image does not force
it. A verifier should attack whether the derivation can be made to disagree with what
the run actually produced, not whether the rule is right.)

---

## FIRST ACTIONS, in order

```bash
cd ~/Desktop/McGill/mcgill-email-to-bom
python3 tools/completeness.py            # expect VIOLATIONS: 0
python3 tools/selftest.py                # expect all green
python3 tools/parity_check.py --manifest tools/parity/parity.json
python3 tools/parity_check.py --manifest tools/golden/golden.json
```

All four should be green at `dc0a05e`. If any is red, stop and find out why before
anything else: nothing was left unverified this time, so a red suite means something
changed underneath. Then:

1. Confirm the vendored engine is what you think it is:

   ```bash
   diff -r -x '__pycache__' src/vendor/email_to_bom ~/Desktop/McGill/email-to-bom-agent/email_to_bom
   ```

   Expect NO output with the clone at `ae4411f` (verified 2026-09-17).
   `-x '__pycache__'` matters: without it the two trees' compiled bytecode differs and
   the result reads like a vendor mismatch when nothing is wrong.
   `src/vendor/PROVENANCE.md` carries the stamp.

2. **Settle the route back before writing code** — rebuild forward from v0.24.0, or fix
   v0.26.0 in place. See the state section.

3. **Work the backlog, not a round.** Round 39 comes AFTER the translation layer is
   rebuilt; running it now would re-find what is already written down. When you do plan
   it, aim it at whatever replaces `config/questions.json`, and at the two things round
   38 proved about verification here:

   - **a green suite is not evidence.** Round 38's blocker passed selftest 311/311,
     parity, golden and completeness. The defect was two design decisions meeting —
     captured-only summary, static question text — neither wrong alone, and no check
     compared the questions against the answers.
   - **the side-by-side mitigation works and closes nothing.** Round 38 confirmed
     `render_review.py` renders the dishonest pairs honestly, and showed it does not
     help: the review request's own instruction is "The response below is sent
     UNCHANGED", so the default action is approve, and H-1's defects are invisible IN
     the side-by-side.

3. Only then consider publishing (see PUBLISHING).

---

## HOW TO RUN A ROUND

1. Write `ACCEPTANCE_ROUND<N>.md` **before** spawning anything. Pre-registration is what
   stops the bar being shaped by the implementation. Copy the structure of
   `ACCEPTANCE_ROUND36.md`.
2. Name your own known weaknesses on the bar explicitly. This has been productive:
   rounds 33, 34 and 35 each **refuted** one, and round 36 settled a carried-forward
   doubt by execution.
3. Spawn the `twyd-factory:twyd-verifier` agent, background, with: the artifact path and
   HEAD, the source-of-truth clone (`~/Desktop/McGill/email-to-bom-agent`, **`ae4411f`** —
   NOT `b15b23d`, which is what rounds 25–36 used; read-only), the bar path, the campaign history, where to aim, and the rules (mutate
   only scratch copies; restore and prove the tree clean; build its own adversarial
   inputs; do not re-litigate settled operator decisions).
4. Ask for two numbers explicitly: **combined mutation survival** and **CaseState
   fidelity**. Those, not the check count, are the measure.
5. Tell it that after twelve FAILs an earned PASS is as valuable as an honest FAIL —
   do not manufacture a finding to keep the streak, do not soften one to end it.
6. **Do not touch the repo while a verifier runs.** It mutates and restores; a
   concurrent commit can capture its mutation.

---

## THE FIVE RECURRING FAILURE SHAPES

Every round's defect has been one of these. Check the fix pass against them before
declaring anything closed.

1. **Fixing the named instance, missing the sibling** — **eighteen** occurrences.
   Rounds 34→35→36 were the same falsy/branch-gated omission three times running, each
   within a screen of the last. When a finding names one site, grep for the shape.
   The eighteenth (REQ-096) is the sharpest illustration yet: the invalidation loop was
   driven by the `ARTIFACTS` declaration *specifically so* nothing could be missed, and
   one key had been exempted from it **by name**, with a comment justifying the
   exemption. `.gitignore` had the same shape on the same day. **An enumeration on the
   unsafe side of a decision is the defect**, however well the surrounding structure is
   built — look for the exception clause inside the general mechanism.
2. **A check that has never been able to fail.** Tautologies, coincidence-matches
   (a token that also appears elsewhere on the page), markers placed in the surviving
   prefix of a truncated value, and checks whose fixture never carries the data.
3. **The tested path is not the shipped path.** A flag the recipe never passes; a helper
   tested directly while the shipped path differs.
4. **Documentation describing something untrue.** All twelve rounds found at least one,
   and twice the commit that fixed one created another.
5. **A fix that opens a new hole.** Round 35's M-2 fix caused round 36's H-2.

---

## THE STOPPING RULE — DECIDED BY THE OPERATOR

> **"Ship when no finding would give a customer a wrong answer."**

This is now the rule, not a proposal. Apply it per finding, not per round:

- A finding whose consequence is a **wrong or missing answer reaching a customer**
  blocks the ship. Examples from this campaign: v0.4.0 discarding 24 of 35 RFQs;
  v0.6.0 discarding 11 of 46; round 36's H-2 (one customer's reply surviving beside
  another's CaseState, so an operator could send the wrong draft); a fabricated price
  or a checkpoint displayed as CLEARED.
- A finding that breaks a **stated guarantee** without changing what a customer
  receives does NOT block. Round 36's C-1 is the reference case: six static column
  names absent from a section that already reads "no lines" — correctly reported,
  correctly fixed, would not have blocked.
- A **coverage gap** — a defence that a mutation can remove undetected, while the
  shipped code is correct — does NOT block. It is next-cycle work. Log it in
  `.astrocode/PROJECT.md` with its round number so it is not lost.

Corollary that matters: a FIX for a blocking-class finding must be **executed**, not
reasoned about, before shipping. The rule does not permit shipping an unverified fix
to a wrong-answer defect. Rounds 25–36 found the defect in the previous fix pass
twelve times out of twelve; inspection is not evidence here.

## Trend, for reference

"Publish on a PASS" may never terminate: the fix pass keeps supplying the next round's
material. Severity, however, is collapsing — v0.4.0 silently discarded 24 of 35 customer
RFQs; round 36's blocker was six static column names missing from a section that already
says "no lines".

**Adopted** (this is the stopping rule above, kept here for the reasoning that led to
it): ship when a round produces no finding whose operator-visible consequence is a wrong
or missing answer to a customer, regardless of PASS/FAIL. Guarantee-level findings and
coverage gaps get logged and fixed in the next cycle rather than gating deployment.

Trend for reference — mutation survival: 50%, 65%, 39%, 32%, 25%, 44%*; CaseState
fidelity: 10/17, 12/17, 13/17, 15/17, 16/17†.
(* round 36 over-sampled deliberately and said so. † shipped-path.)

Round 37's numbers are not comparable to these without a caveat: the engine changed
between round 36 and round 37, so a survival figure that moves may be measuring the
new engine rather than the new checks. Say which when you report it.

---

## PUBLISHING

**Live: v0.21.0** (sha `faac34e2cce8c5ce`), verified by independent read-back after the
round-38 rollback. The record holds 0.21.0, 0.14.0, 0.3.0, 0.2.0.

Deleted on 2026-09-18, each HTTP 204 with the record read back between: **v0.20.0**
(round 37's blocker), then **v0.26.0** and **v0.25.0** (round 38's). `latest` is computed
from the remaining versions — confirmed by deleting one at a time and checking, rather
than assumed. Deletion is the documented rollback and has now worked five times.

Nothing is lost by a rollback: every deleted version's code is on `main` and rebuildable.
Re-publishing is a build plus a publish.

The read-back also corrected a claim this file and PROJECT.md had both been making.
The instance did **not** serve v0.3.0: its record shows four versions, and **v0.14.0
was uploaded 2026-08-27T03:03Z**. The "instance serves v0.3.0" line had been carried
forward from the rollback of v0.6.0 and was stale for three weeks. Read the record
before repeating a version claim, including one from this file.

    0.14.0  d1ee073a42f7522f  2026-08-27T03:03Z
    0.3.0   76c920a1a0c0b934  2026-08-26T16:58Z
    0.2.0   6cdfd8364c509f99  2026-08-26T16:02Z

**Round 37 is still outstanding, and v0.20.0 is live without it.** No blind round has
tested the engine this kit ships (`ae4411f` behaviour) or any of the five scripts added
on 2026-09-17: `attachments.py`, `answers.py`, `apply_answers.py`, `routing.py`,
`render_review.py`. If the round finds something whose consequence reaches a customer,
the rollback below is the response, and it has worked twice.

Note the published package is the publisher's own build: all 29 `src/` files PLUS
`kit.json` (30 files, sha `852edc2f`). That sha deliberately differs from
`dist/kit.zip`'s — different contents, not a mismatch.

```bash
cd ~/Desktop/McGill/mcgill-email-to-bom && source ~/.zshrc && \
python3 tools/publish_kit.py --kit-root . --base https://astro.twyd.cloud \
  --email admin@astrolize.com --note "<what changed>"
```

`source ~/.zshrc` makes the publisher read `ASTRO_ADMIN_PASSWORD` from the environment,
so the credential never appears in a command. **That password is in `~/.zshrc` in
plaintext and in several session transcripts — it is worth rotating.**

Verify by reading the record back (`GET /api/kit-packages/mcgill-email-to-bom`), never by
trusting the publisher's own success line. Roll back by deleting the version:
`DELETE /api/kit-packages/mcgill-email-to-bom/versions/<v>` with no `Content-Type` header
(sending one with an empty body returns 400).
