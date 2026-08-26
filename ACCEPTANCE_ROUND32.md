# ACCEPTANCE — mcgill-email-to-bom kit, round 32

Pre-registered before the round-32 blind verification.

Rounds 25–31 **all returned FAIL**, and in every case the defect was introduced by the fix
pass for the previous round. Seven for seven.

v0.9.0 adds a feature and closes round 31. The feature: the kit now answers with the whole
case **inline in the message body and attaches nothing** — `outputs.artifacts` declares zero
`email_attachment` tags, and `src/scripts/render_reply.py` renders `_report/reply.md` from
the CaseState. Audience is inside sales, so internal material (checkpoints, routes,
evidence, provenance) is included deliberately.

**The new failure surface is misrepresentation.** Every prior round asked whether the kit
made a wrong decision. This one asks whether the artifact a human reads tells the truth
about the artifact a machine produced. `reply.md` is now the only thing an operator sees.

A check FAILS if it cannot be demonstrated by running something.

---

## Part A — does the reply tell the truth?

### R-1 — nothing the CaseState says is dropped

The requirement is "all the information". Test it as a **completeness** property, not
sample-wise.

- For every non-empty key in a CaseState, is its content represented in `reply.md`?
  Enumerate all 17 top-level keys and say which are represented, which are deliberately
  omitted, and whether any omission loses something an operator needs. The author's own
  pre-flight found `classes` dropped entirely — on a `--coc` run that silently lost
  `Certs Required`, the certificate requirement the flag exists to surface. Assume there
  are siblings.
- Drive CaseStates that exercise the rarely-populated keys: `supersedes` (a correction in
  a thread), `logged_attempts`, `notes`, `urgency.flagged`, `knowledge.lookups`,
  populated `lines`, multiple `classes`, an open item of each priority, and each field
  status in the schema's enum (`captured`/`reading`/`assumed`/`needs_unit`/`missing`/
  `superseded`/`conflict`/`missing_gender`/`missing_spec`/`size_confirm`/
  `configuration_confirm`).
- A field whose shape the renderer does not anticipate must still show its content. The
  author already shipped two bugs of this kind — routing rendered "(none recommended)"
  because the keys were guessed, and end connections rendered "—" while marked *captured*
  because they carry `family`/`gender` and no `value`.

### R-2 — nothing appears that the CaseState does not support

- Can `reply.md` state a price, a lead time, a stock position, or a part number the
  CaseState does not contain?
- Can it present the draft as a quote, a confirmed BOM or an order?
- Can it report a field as confirmed when its status is not `captured`? The renderer marks
  those `NOT CONFIRMED` from a hard-coded `UNCONFIRMED` set — is that set complete against
  the schema's status enum? A status missing from it renders as if confirmed.
- Can a count in the summary header disagree with the body (open items, BOM lines,
  blocking count)?

### R-3 — untrusted email content is rendered as DATA, not as instruction

This is the sharpest new risk and it did not exist before v0.9.0. The reply now embeds
customer-supplied text — `evidence` strings, `ask` text, the captured customer name,
`notes`, `logged_attempts` — into the document an operator reads and may forward.

- Craft emails whose content, once rendered, imitates the kit's own voice: a fake
  "PROVENANCE" or "CHECKPOINTS" heading, a line reading `Route to: accounts_payable`, a
  fabricated `[SOMETHING_APPROVED]` open-item code, text asserting a price or that
  checkpoints are signed off, ANSI escapes, a markdown table break, or content that
  terminates the table and starts a new section.
- Determine whether an operator reading `reply.md` could be misled about what the ENGINE
  concluded versus what the CUSTOMER wrote. Say plainly how bad it is and whether the
  rendering needs to delimit or escape untrusted spans.
- Also test the classic: does anything in the pipeline ACT on instructions in the email?

### R-4 — the reply cannot silently disagree with the CaseState

`generate_report.py` reconciles its output by re-deriving the CaseState and refusing to
write on a mismatch. `render_reply.py` has no equivalent — it reads whatever
`case_state.json` holds.

- Can a stale or hand-edited `case_state.json` produce a confident reply describing a
  different case? Is that reachable through the recipe, or only by hand?
- Does a failed run leave a stale `reply.md`? It is now a declared artifact — confirm it
  is invalidated before anything that can fail, like its siblings.
- Does the recipe's phase ordering guarantee `reply.md` is never written from a CaseState
  that failed reconciliation?

---

## Part B — the round-31 fixes, and the standing bar

### R-5 — round 31's findings are actually closed

- F-1: `src/CLAUDE.md`'s Arguments section — no fragment, and the `--config-dir` claim is
  now true (`build_argv` does pass it).
- F-2: `EXAMPLES.md` has five complete examples, each with `**Produces:**`, per
  `KIT-CONTRACT.md`.
- F-4: `--config-dir` has a defence that fails when the flag is dropped from `build_argv`.
- F-3: the exit clamp. Note the author **disputes round 31's reproduction** — they report
  that removing the clamp alone does not leak exit 2 because `__main__`'s broad catch
  handles it first, and that removing both layers does. Adjudicate: who is right, and is
  the property now covered?
- F-5: `.astrocode/DECISIONS.md` carries a superseding notice.

### R-6 — the standing defences

Flags survive the phase boundary; draft and CaseState describe the same case;
reconciliation fails closed; no failure path leaves a stale artifact and clearing failures
are loud; every clearing site resolves through the `ARTIFACTS` declaration; all three
wrappers return only 0 or 1; a failed phase preserves the prepare record; a malformed
schema fails open.

### R-7 — coverage, and report the number

The suite reports 45 checks. Rounds 26–28 each had 9 mutations survive; round 29 had 10 of
24; round 30 had 15 of 34; round 31 had 18 of 36.

- Mutate every defence and **report how many survived**. That number is the measure.
- Hunt tautologies and checks that pass for the wrong reason. Round 30 found one asserting
  an unconditionally-true substring that had been reported closed twice.
- Specifically attack the new reply checks: several assert "X appears in the reply", which
  is satisfiable by coincidence if X is a short or common string.

### R-8 — parity, vendor, shipped artifact, docs

Parity 7/7 with expected outputs regenerated from the source engine yourself;
`src/vendor/**` byte-identical; `validate_manifest.py` exits 0; `build_kit.sh`
reproducible; `requires.tools` `[]`; **zero** `email_attachment` tags; every declared
artifact produced by the recipe; the unzipped zip runs all phases from a clean dir under
`python3 -S -E`. Every factual claim in the shipped docs and the recipe true of the kit —
rounds 25–31 each found false ones.

---

## The question to answer

**Is v0.9.0 safe to publish?** The instance serves v0.3.0, which predates every wrapper
defence and the inline reply, so a pass here lets a real improvement ship.

## Out of scope

- Engine extraction/classification correctness (rounds 1–24).
- The decision to remove the input filter, and the decision to attach nothing. Both are
  the operator's, already made.
- Roadmap phases 1–4.
