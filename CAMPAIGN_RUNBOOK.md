# Verification campaign runbook — read this first

You are continuing a blind-verification campaign on this kit. Rounds 25–36 all
returned FAIL, and in every case the defect was introduced by the fix pass for the
previous round. Full reports are `VERIFICATION_ROUND25.md` … `VERIFICATION_ROUND36.md`;
the requirement ledger is `.astrocode/PROJECT.md` (REQ-001…REQ-083).

The operator's standing instruction: **run rounds, fix findings, and publish when
ready.** They have twice authorised rolling a bad version back off the instance, and
both rollbacks worked.

---

## STATE AS OF THIS FILE (uncommitted work in the tree)

Round 36 returned FAIL. Its findings were **partly** addressed and **mostly
unverified**, because a sandbox classifier blocked shell commands mid-pass.

Fixed but NOT verified by execution:
- **C-1** (the blocker, 17th missed sibling) — `bom_columns` vanished from the reply on
  the `lines == []` branch. Fixed in `render_reply.py`. **Verified** by
  `tools/completeness.py` (it no longer reports `bom_columns`).
- **H-2** — round 35's own M-2 fix reintroduced R26-F1: with `--out` redirected, the
  run's own `_report/reply.md` survived. `run_engine.py` now clears the union of
  `--out`'s and `--state`'s directories. **Never executed.**
- **H-3** — four false `route` claims (recipe, README, EXAMPLES, CLAUDE.md): 23 of 24
  open items carry no `route`, and EXAMPLES made it load-bearing for the conversation
  layer. **Never executed.**
- **`tools/completeness.py`** (new) — the structural guard round 36's K-3 asked for.
  Asserts every non-empty CaseState key and every leaf value reaches the reply, over a
  pairwise cross-product of 14 axes. It found C-1 in seconds where the golden suite
  structurally could not. Its first run reported 6 false positives (nested dict key
  names); that was corrected — see the docstrings for why vocabulary ≠ content.

**The built artifact is STALE.** `kit.json` says 0.13.0 and `dist/kit.zip` is the
0.13.0 build, which does NOT contain the above fixes. Do not publish or verify against
the zip until it is rebuilt.

### Open findings from round 36, deliberately untouched

Not fixed, because writing a check that cannot be executed is how this campaign's
vacuous checks were born:

1. **6 of 10 `UNCONFIRMED` members are deletable with the suite green** — one is live on
   a plain camlock email. This is the sharpest open item.
2. `write_state` swallowing `OSError` exits **0** with no state record.
3. An engine failure leaves a **0-byte** `case_state.json`.
4. The *falsy* knowledge-extras variant cannot fail (one layer below a check that can).

---

## FIRST ACTIONS, in order

```bash
cd ~/Desktop/McGill/mcgill-email-to-bom
python3 tools/completeness.py            # expect VIOLATIONS: 0
python3 tools/selftest.py                # expect all green
python3 tools/parity_check.py --manifest tools/parity/parity.json
python3 tools/parity_check.py --manifest tools/golden/golden.json
```

If any is red, fix it before anything else — a red suite here means an unverified fix
was wrong. Then:

1. Fix the four open findings above, and **mutation-test each fix**: break it, watch the
   suite fail and name the case, restore. A fix is not closed until its check has been
   seen to fail.
2. Bump `kit.json` and `registry-entry.json` to **0.14.0**, run `./tools/build_kit.sh`,
   confirm `validate_manifest.py` exits 0 and the zip sha matches.
3. Commit and push.
4. Run **round 37** (see below).

---

## HOW TO RUN A ROUND

1. Write `ACCEPTANCE_ROUND<N>.md` **before** spawning anything. Pre-registration is what
   stops the bar being shaped by the implementation. Copy the structure of
   `ACCEPTANCE_ROUND36.md`.
2. Name your own known weaknesses on the bar explicitly. This has been productive:
   rounds 33, 34 and 35 each **refuted** one, and round 36 settled a carried-forward
   doubt by execution.
3. Spawn the `twyd-factory:twyd-verifier` agent, background, with: the artifact path and
   HEAD, the source-of-truth clone (`~/Desktop/McGill/email-to-bom-agent`, `b15b23d`,
   read-only), the bar path, the campaign history, where to aim, and the rules (mutate
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

1. **Fixing the named instance, missing the sibling** — **seventeen** occurrences.
   Rounds 34→35→36 were the same falsy/branch-gated omission three times running, each
   within a screen of the last. When a finding names one site, grep for the shape.
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

**Proposed:** ship when a round produces no finding whose operator-visible consequence is
a wrong or missing answer to a customer, regardless of PASS/FAIL. Guarantee-level
findings and coverage gaps get logged and fixed in the next cycle rather than gating
deployment.

Trend for reference — mutation survival: 50%, 65%, 39%, 32%, 25%, 44%*; CaseState
fidelity: 10/17, 12/17, 13/17, 15/17, 16/17†.
(* round 36 over-sampled deliberately and said so. † shipped-path.)

---

## PUBLISHING

The instance serves **v0.3.0** — no wrapper defences, no inline reply, none of twelve
rounds of fixes. That is the standing cost of not shipping.

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
