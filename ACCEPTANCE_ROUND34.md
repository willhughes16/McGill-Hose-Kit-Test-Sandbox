# ACCEPTANCE — mcgill-email-to-bom kit, round 34

Pre-registered before the round-34 blind verification.

Rounds 25–33 **all returned FAIL**, and in every case the defect was introduced by the fix
pass for the previous round. Nine for nine. Two builds were published before being verified
and both were dropping real customer requests; both were rolled back.

Two trends, both from round 33: mutation survival is falling (65% → 39%) and CaseState
fidelity is rising (10/17 → 12/17). Round 33 also **refuted** one weakness the author named,
which is the first time a named suspicion turned out to be unfounded.

v0.11.0 closes round 33's two CRITICALs: untrusted text is now stripped by Unicode
**category** rather than by a list of code points, and the anti-tautology field check runs
across four fixtures against the row's value cell. It also adds a REMAINDER section so no
CaseState key can be silently absent.

**Weaknesses the author knows about are named below.** Confirm or refute each, then find
what is not on the list — this campaign's pattern is that the next defect is one nobody
named.

A check FAILS if it cannot be demonstrated by running something.

---

## Part A — the round-33 fixes and their surfaces

### P-1 — `_safe()` after the category rewrite

It now strips Unicode categories `Cc Cf Cs Co Cn Zl Zp`, whole ANSI sequences (7-bit
CSI/OSC/DCS plus 8-bit C1 forms), folds whitespace, and no longer truncates destructively.

- Can anything still make rendered customer text imitate the kit's own structure, hide
  content from a reader, or display text other than what it contains? Consider what is
  **not** in those categories: combining marks (`Mn`) stacked to obscure, homoglyph
  substitution (Cyrillic/Greek lookalikes), fullwidth forms, `Zs` exotic spaces, and RTL
  *script* characters that need no override to reorder.
- Is stripping the right response everywhere, or does it destroy legitimate content? A
  customer writing in Arabic or Hebrew has a right to have their words in the reply.
  Judge whether the fix has traded a security hole for a correctness one.
- Does `_safe()` reach every render site? The previous two rounds each found one it missed.

### P-2 — the REMAINDER backstop

Any top-level CaseState key no section consumed is printed verbatim.

- Is the `_consumed` set accurate? A key listed there but not actually rendered is silently
  absent AND excluded from the backstop — worse than before the backstop existed.
- Can the backstop print something misleading, unsanitised, or enormous?
- Re-measure CaseState fidelity: how many of the 17 keys are rendered whole?

### P-3 — known and unaddressed: no golden coverage of `reply.md`

Round 33 noted that **no parity fixture renders `reply.md`**. The author's reasoning for
leaving it: `reply.md` has no source-engine counterpart, so a golden file for it would be
compared against the kit's own output — circular by the standard round 25 set ("parity is
not circular"), and behavioural coverage belongs in `tools/selftest.py` instead.

**Adjudicate that reasoning.** Is the absence correct, or is a non-circular regression
fixture for the reply both possible and needed? If the selftest coverage is the substitute,
is it actually sufficient — would an unintended rendering change be caught?

### P-4 — known and unaddressed: the synthetic block uses a flag no real run passes

`tools/selftest.py`'s synthetic-CaseState checks render with `--no-reconcile`, because a
hand-built CaseState cannot reconcile against a re-derived one. That is the "tested path is
not the shipped path" shape, and the author's position is that it is unavoidable for
synthetic data and compensated by the four-fixture shipped-path checks.

- Is it compensated? Find a rendering property that ONLY the synthetic block covers, and
  show whether breaking it on the shipped path is detected.
- `tier` and `citation` are reachable only in synthetic CaseStates, never in a real run.
  Does that make their coverage meaningless?

### P-5 — the reconciliation, and a named landmine

Round 33 refuted false refusals for the shipped kit and noted a latent one: the engine's
only nondeterministic value (`ms` timing in `McpKnowledge`) sits on a path `cli.main`
cannot reach — but if knowledge is ever wired in, **both** reconciliations would refuse
every run forever.

- Confirm the landmine is real, and say what it would take to trip it.
- Re-test false refusals independently: repeats, hash seeds, alternate `--config-dir`,
  large inputs, unusual encodings, relative vs absolute paths.

---

## Part B — the standing bar

### P-6 — the rounds 25–33 defences

Flags survive the phase boundary including `--config-dir`; draft and CaseState describe the
same case; both reconciliations fail closed; no failure path leaves a stale
`case_state.json`, `bom_draft.md` or `reply.md`; clearing failures are loud; every clearing
site resolves through the `ARTIFACTS` declaration; all three wrappers return only 0 or 1; a
failed phase preserves the prepare record; a malformed schema fails open; the `UNCONFIRMED`
set is complete against the schema's status enum.

### P-7 — coverage, and report the number

The suite reports 83 checks. Mutation survival by round: 29 → 10/24, 30 → 15/34,
31 → 18/36, 32 → 33/51, 33 → 22/57.

- Mutate every defence and **report how many survived**. That number is the measure.
- Hunt tautologies and coincidence-matches. Round 32 found six vacuous checks; round 33
  found one of the replacements still vacuous because its marker sat in the surviving
  prefix of a truncated value rather than the tail.
- Confirm parity stays green under renderer mutations.

### P-8 — parity, vendor, shipped artifact, docs

Parity 7/7 with expected outputs regenerated from the source engine yourself; `src/vendor/**`
byte-identical; `validate_manifest.py` exits 0; `build_kit.sh` reproducible;
`requires.tools` `[]`; **zero** `email_attachment` tags; every declared artifact produced by
the recipe; the unzipped zip runs all phases from a clean dir under `python3 -S -E`. Every
factual claim in the shipped docs and the recipe true of the kit — every round from 25 to 33
found false ones, and two of round 33's were created by the commit meant to fix another.

### P-9 — nothing sensitive, nothing acts on message content

No credential in repo or zip; fixtures in RFC 2606 reserved namespaces; non-vendored source
makes no network call, no environment read, no subprocess, no `eval`/`exec`. Plant
injections and confirm nothing in the pipeline acts on them.

---

## The question to answer

**Is v0.11.0 safe to publish?** Round 33's own note was that v0.3.0 — what the instance
serves — is worse in every other respect, which argues for shipping soon, but not with its
C-1 open. C-1 is now closed. Say plainly whether anything still blocks.

## Out of scope

- Engine extraction/classification correctness (rounds 1–24).
- The no-attachment decision and the filter removal — both the operator's, already made.
- Roadmap phases 1–4.
