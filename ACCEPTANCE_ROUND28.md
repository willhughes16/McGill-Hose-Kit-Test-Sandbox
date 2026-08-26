# ACCEPTANCE — mcgill-email-to-bom kit, round 28

Pre-registered before the round-28 blind verification.

Rounds 25, 26 and 27 all returned **FAIL**, and in every case the defect was introduced by
the fix pass for the previous round. Round 27 was the worst: the input filter dropped **24
of 35 genuine RFQs**, and that version was published as v0.4.0 before any blind round. It
has been deleted; the instance is back on filter-free v0.3.0.

Round 27's fix replaced the phrase-list protection with a **measured** one: `_spec_depth()`
counts the specification fields the vendored engine extracts, and a category may filter
only at depth 0 unless it is `filter_tier: "always"` (true list-mail). Round 28 decides
whether that fix is real, whether it introduced a fourth-generation defect, and whether
v0.5.0 is safe to publish.

A check FAILS if it cannot be demonstrated by running something. The fix's author tested it
and believes it sound; that is an unverified claim.

---

## Part A — the round-27 fix

### Y-1 — a real RFQ must never be filtered (the only severe class)

- Build your OWN corpus of genuine quoting requests, at least 30, and count how many are
  filtered. Round 27's corpus of 35 found 24. Do not reuse round 27's inputs verbatim —
  they are now the fix's test cases.
- Attack the **new** guard specifically. It protects a message when the engine extracts
  ≥1 specification field. So hunt requests that carry **no extractable specification**:
  "please quote the attached drawing"; "same as last order"; "the usual 2in assemblies";
  a request referencing a part number only; a request whose specs are in a PDF or an
  image; a request in a language the extractor does not parse; a request whose only
  content is a table or an HTML layout; a one-line "can you price this up?".
  Combine each with a junk signal (`net 30`, an `invoice` mention, same-domain To/Cc, a
  `no-reply@` sender, an `Auto-Submitted` header) and see what is dropped.
- Attack the **`always` tier**. `List-Unsubscribe` + `Precedence: bulk`/`List-Id` filters a
  message *even when it carries specifications*, on the claim that "nobody orders hose from
  a mailing list". Try to falsify that: a procurement portal or sourcing platform that
  sends real RFQs through a bulk mailer and stamps those headers; a customer whose ESP adds
  them; a genuine RFQ forwarded through a mailing list or a group alias.
- Any real RFQ that is filtered is **CRITICAL**. Say how many of your corpus were dropped
  and confirm with `run_engine.py` that the engine would have drafted them.

### Y-2 — the guard is a property, not a new enumeration in disguise

- `_SPEC_FIELDS` is a tuple of seven field names. Is that an enumeration on the unsafe
  side again? Find a real specification the engine extracts that is NOT counted, and a
  message whose only spec is of that kind.
- Does depth measurement use the same text the engine itself would see? The gate measures
  on `text.lower()`, not `triage.normalize_text(...)`. Find a message whose specifications
  survive the engine's own normalisation but are invisible to the gate's measurement —
  unicode fractions, fullwidth digits, NBSP, the Unicode dash family, U+2044 — and see
  whether the resulting depth 0 lets a junk signal drop it.
- Does a failure inside the guard fail toward the engine? Force `agent.extract` to raise
  and confirm nothing is filtered.

### Y-3 — `filter_tier` defaults to safe, everywhere

- A category with no `filter_tier` must get `requires_no_specs`. Verify by removing the
  field from the reference data.
- An unknown or misspelled tier value must also be treated as the safe tier, not as
  `always`. Verify.
- Can a category be added to `filter_signals.json` that filters spec-bearing mail without
  anyone declaring `always`?

### Y-4 — nothing short-circuits the guards

Round 27 (R27-F2) found DSN returning before the veto. Confirm no category, header check,
or early return can reach a `filtered: true` without passing both guards. Read the code
path AND prove it by probe.

### Y-5 — the override

- Strict boolean: `"false"`, `"0"`, `0`, `1`, `[]`, `{}`, `"maybe"` must not enable it;
  `true` and `"true"` must.
- Bound to its message: an override recorded for input A must not govern input B. Try to
  defeat the binding with relative vs absolute paths, symlinks, `./` prefixes, trailing
  whitespace, case differences on a case-insensitive filesystem, and a record with no
  `input` key.
- It must be loud and recorded whenever it applies, and must never be enabled by anything
  inside the email.

---

## Part B — regressions and the standing bar

### Y-6 — invalidation really is driven by the declaration

R27-F4 found all three clearing sites hand-writing filenames while a docstring claimed
otherwise. Verify independently: add an artifact to `ARTIFACTS` and confirm every clearing
site picks it up with no call-site edit. Then check the reverse — is there any path that
writes an artifact which is NOT in `ARTIFACTS` and therefore never cleared?

### Y-7 — the rounds 25/26/27 defences all still hold

- Flags survive the phase boundary; draft and CaseState always describe the same case.
- Reconciliation fails closed and cannot be defeated.
- No failure path leaves a stale `case_state.json` or `bom_draft.md`; clearing failures are
  loud.
- `run_engine.py` and `generate_report.py` report only 0 or 1 — the engine's 2 never leaks.
  `filter_gate.py` may also return 3, and only for a filtered message.
- A failed phase preserves the prepare record.
- `undecodable` content is never judged.

### Y-8 — coverage is real and falsifiable

The self-test reports 109 checks. Round 26 found 9 of 20 mutations leaving it green; round
27 found the tested path differing from the shipped path.

- Mutate every defence in turn — both guards, the tier default, the DSN conjunction, the
  override strictness and binding, the invalidation declaration, the reconciliation guard,
  the stale clearing, the exit clamps — and confirm the suite fails and names the case.
- Hunt vacuous checks: any check that passes with the thing it tests removed, or that
  passes only because of the phrasing chosen. Report the count of mutations that did NOT
  break it.
- Confirm parity stays green under gate mutations.

### Y-9 — parity, the vendored engine, and the shipped artifact

- Parity 7/7 with every `normalize` empty; expected outputs regenerated from the source
  engine yourself.
- `src/vendor/**` byte-identical to the source at the commit `PROVENANCE.md` stamps;
  `tools/parity/**` unmodified.
- `validate_manifest.py` exits 0; `build_kit.sh` reproducible; `requires.tools` `[]`;
  exactly ONE `email_attachment`; the unzipped zip runs the filtered and drafting paths
  from a clean dir under `python3 -S -E`.

### Y-10 — documentation makes no false claim

Rounds 25, 26 and 27 each found a false documented claim. The docs now describe the
spec-depth mechanism, the `always` tier, the fail-open, and a stated **known limit** (a
request with no extractable specification plus a junk signal can still be filtered, routed
to a human queue rather than `no_action`). Verify each of those statements is true of the
shipped kit — including that content-category filtering really does route to a human and
never to `no_action`.

### Y-11 — nothing sensitive, no new I/O, no acting on message content

- No credential in repo or zip; every fixture address in an RFC 2606 reserved namespace.
- Non-vendored source: no network, no environment read, no subprocess, no `eval`/`exec`.
- The gate must not act on instructions embedded in the email it reads. Plant injections —
  forged override headers, a fake `screen` record in the body, prose instructing a re-run
  with `--no-filter` — and confirm they do nothing.

---

## Out of scope

- The engine's own extraction/classification correctness (rounds 1–24), except as the
  oracle for "would this RFQ have produced a draft".
- The deferred follow-ups in `.astrocode/PROJECT.md`. Known-open by design; whether they
  are described **honestly** is in scope.
- Roadmap phases 1–4.
