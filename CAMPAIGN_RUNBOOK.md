# Verification campaign runbook — read this first

You are continuing a blind-verification campaign on this kit. Rounds 25–36 all
returned FAIL, and in every case the defect was introduced by the fix pass for the
previous round. Full reports are `VERIFICATION_ROUND25.md` … `VERIFICATION_ROUND36.md`;
the requirement ledger is `.astrocode/PROJECT.md` (REQ-001…REQ-096).

The operator's standing instruction: **run rounds, fix findings, and publish when
ready.** They have twice authorised rolling a bad version back off the instance, and
both rollbacks worked.

> **READ THIS BEFORE PLANNING A ROUND: the engine underneath changed.** Rounds 25–36
> all ran against the engine as vendored at `b15b23d`. The kit now vendors
> **`ae4411f`** — one commit later, and a behavioural one ("size is not a length").
> **No round has ever tested the engine this kit currently ships.** That is the single
> most important fact in this file, and it is why round 37 exists.

---

## STATE AS OF THIS FILE (2026-09-17 — all work is MERGED to `main`)

`main` is at `dc0a05e`, the merge of PR #1. Working tree clean. **`kit.json` and the
built `dist/kit.zip` are at v0.16.0 and current** — unlike the last two times this file
was written, the artifact is not stale.

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

Suites at `dc0a05e`: selftest **160/160**, parity 7/7 (zero normalizations), golden
2/2, completeness 184 combinations / 0 violations, manifest valid, zip `2945d8ea`.
Mutation run on the new work: **11 mutations, 11 caught, 0 survivors.**

### Nothing is carried forward as an open finding

Round 36's four open items are all closed and mutation-proved. There is no backlog to
clear before round 37 — which is unusual for this campaign, and means the round starts
clean rather than against a fix pass.

### Two things deliberately left undecided — do not "fix" them silently

1. **An unread attachment does not force `needs_human_input`.** A case whose dimensions
   are in an unopened drawing can report `outcome: complete`, because the outcome is
   derived from `open_items[]` alone and none of them blocks. This is correct by
   REQ-095's definition and arguably still wrong for routing. It is the operator's call,
   and it is recorded in PR #1. A verifier may legitimately report it as a finding; it
   is not an oversight.
2. **`CW-4`…`CW-8` are specified and unbuilt.** See `COWORKER_ALIGNMENT.md`. Their
   absence is not a defect.

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

2. **Run round 37.** There is no backlog to clear first. Aim it at the engine change:
   rounds 25–36 tested `b15b23d`, and the shipped engine is now `ae4411f`. The
   highest-value targets, in order:
   - **the re-vendor itself** — size/length extraction on real-shaped threads, and
     whether the four re-captured parity expecteds are right rather than merely
     self-consistent (the old ones enshrined a live defect, which is the precedent);
   - **`attachments.py` and the evidence block** — new code on the shipped path, and the
     one place where a scan of the wrong file would put customer A's drawing on customer
     B's reply (REQ-093 guards exactly that; try to get past it);
   - **the run manifest** — whether `outcome` can disagree with the CaseState it came
     from, and whether a failed run can leave one behind.

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

The instance serves **v0.3.0**. `main` is at **v0.16.0**. The gap is thirteen versions:
no wrapper defences, no inline reply, no attachment honesty, no run manifest, none of
twelve rounds of fixes, and the OLD engine — the one that reads a phone number as a
hose length on real McGill mail. That is the standing cost of not shipping.

**The gate before publishing is round 37**, for the reason at the top of this file: no
round has tested `ae4411f`. The re-vendor is a materially better engine on real mail,
which is an argument for shipping it, not for skipping the check.

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
