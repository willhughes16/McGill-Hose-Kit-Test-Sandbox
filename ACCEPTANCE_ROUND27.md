# ACCEPTANCE — mcgill-email-to-bom kit, round 27

Pre-registered before the round-27 blind verification. Rounds 25 and 26 both returned
**FAIL**, and in both cases the defect was introduced by the *immediately preceding fix
pass*. Phase 5 then added the input-filter gate — the first mechanism in this kit that
can make a real customer request disappear — and closed on a human UAT sign-off, not a
blind round. Round 27 is that blind round.

A check FAILS if it cannot be demonstrated by running something. The gate's author and
the UAT walkthrough both concluded it was sound; treat that as an unverified claim.

---

## Part A — the input filter (phase 5), the new way to be silently wrong

### X-1 — a real RFQ must never be filtered

This is the only finding class that would be severe. The gate's stated design is
fail-open: anything ambiguous reaches the engine.

- Attack it hard. Construct real quoting requests that wear every junk signal the gate
  looks for — read `src/reference/filter_signals.json` for the vocabulary, then defeat
  it. Bulk/`List-Unsubscribe`/`Precedence: bulk` headers on a genuine RFQ; a genuine RFQ
  in a reply to a newsletter thread; `auto-submitted` / `X-Autoreply` headers on a real
  request; a real request from `no-reply@` or `MAILER-DAEMON@`; an RFQ inside a
  `multipart/report`; an RFQ whose only text is in an HTML part styled like marketing; a
  one-line RFQ ("quote 50ft 2in EPDM"); a terse RFQ that opens with "thanks"; an RFQ in a
  forwarded invoice; an RFQ from an internal domain; non-English and mixed-language
  requests; an RFQ whose body is mostly a quoted junk thread with two real lines at top.
- Any real RFQ that the gate filters is a **CRITICAL** finding.

### X-2 — the enumeration is not the spec

`filter_signals.json` is by construction a list. This project's oldest failure class is
"the enumeration is treated as the spec".

- Find junk categories outside the vocabulary and confirm the outcome is safe (passing
  through and drafting is acceptable; silently discarding is not).
- Find a signal whose presence flips the decision in a way a mildly different phrasing
  defeats — and say whether the *category* or only the *listed instances* are handled.
- Check for the sibling shape: a rule expressed both in `filter_signals.json` and in
  `filter_gate.py` code, where editing one leaves the other stale.

### X-3 — a filtered run is honest and never lossy

- `_report/` must hold no `case_state.json` and no `bom_draft.md` after a filtered run,
  including when a previous run left them there.
- The filter record must carry a code, a route and the input path, all inside the closed
  enums of `src/schemas/filter_decision.schema.json`, and must be deterministic.
- Exit 3 must be reachable ONLY for a filtered message, and must never collide with the
  engine's 2 or a wrapper's 1. Confirm no path returns 3 for a failure.
- A filtered message must be replayable: an operator must be able to get a draft for it
  from the record alone, without editing the kit or the email. Verify the email's bytes
  are unchanged.

### X-4 — the gate cannot alter what the engine sees

Byte-level parity with the source engine is the kit's core claim.

- Prove the gate does not rewrite, truncate, re-encode or normalise the input. Compare
  input hashes before and after; run the full gated flow on every parity fixture and
  compare to the source-captured `expected_output.json`.
- Prove the gate runs BEFORE the engine and that no engine invocation happens on a
  filtered message (a sentinel in the vendored `cli.main` is a good way).
- `src/vendor/**` and `tools/parity/**` must be byte-identical to the source /
  unmodified.

### X-5 — the override cannot be silently enabled or silently ignored

- `--no-filter` must be loud on stderr, recorded, and effective.
- Can the override be turned on by something other than an explicit operator choice — a
  malformed `state.json`, a stray key, a truthy string, an inherited record from a
  previous run? Can a message carry content that enables it?
- Conversely: can an operator's explicit override be silently dropped?

---

## Part B — did phase 5 break rounds 25/26, and is `run_state.py` now a single point of failure?

### X-6 — `run_state.py` owns four concerns; is that a new fault line?

It now declares `ARTIFACTS`, `INVOCATION_KEYS`, `FILTER_KEYS` and `SCREEN_KEY`, and
supplies every constructor, normaliser and the argv builder.

- Does a change in one concern reach another? Can a filter key leak into the engine argv
  (which would break parity)? Can `SCREEN_KEY` reach `build_argv`?
- Do the normalisers still read through their declared key tuples, or has a hand-written
  whitelist reappeared?
- Is `invalidate()` still driven by `ARTIFACTS` rather than by names at the call site?
- Does the filter record participate in invalidation correctly — can a stale filter
  record sit beside a fresh CaseState, or vice versa?

### X-7 — the round-25 and round-26 defences still hold

Re-run the earlier bars against the current artifact. Each of these was a real defect:

- Flags survive the phase boundary; the draft and the CaseState always describe the same
  case (round 25 F-1).
- Reconciliation FAILS CLOSED on an absent / directory / unreadable CaseState (R26-F3),
  and cannot be defeated.
- No failure path leaves a previous run's `case_state.json` or `bom_draft.md` (R26-F1),
  and clearing failures are loud (R26-F5).
- The wrappers report only 0 or 1 — the engine's 2 can never leak (R26-F2). Note exit 3
  is now legitimate for `filter_gate.py`; check that this did not loosen the clamp on the
  other two scripts.
- A failed phase preserves the prepare record (R26-F10).

### X-8 — the defences are covered and the coverage is falsifiable

`tools/selftest.py` reports 83 checks. Round 26 found that removing a defence left the
old suite green, and that two of the author's own new checks were vacuous.

- Mutate each defence in turn — the gate's `decide()`, the reconciliation guard, the
  stale-clearing, the exit clamp — and confirm the selftest fails and names the case.
- Hunt for vacuous checks: any check that passes with the thing it tests removed, or that
  passes only because of the specific phrasing chosen.
- Confirm parity stays green under gate mutations (the gate must not be entangled with
  what the engine sees).

### X-9 — the shipped artifact and the published package

- `validate_manifest.py` exits 0; `build_kit.sh` is reproducible; `requires.tools` is
  `[]`; exactly ONE `email_attachment`.
- The unzipped `dist/kit.zip` runs both the filtered and drafting paths from a clean dir
  under `python3 -S -E` with no install.
- The upload package rebuilt from repo HEAD must equal published `mcgill-email-to-bom`
  v0.4.0, sha256
  `5e2afec8520537acd631fb693b25d63da025ddfd01f92c327a539766b86880b4`.

### X-10 — documentation makes no false claim

Every factual claim in `src/README.md`, `src/CLAUDE.md`, `src/EXAMPLES.md`,
`src/recipes/mcgill-email-to-bom.yaml` and `src/vendor/PROVENANCE.md` must be true of the
shipped kit — the documented commands must exist and work as written, the stated codes
and routes must be the ones emitted, the runtime figures must reflect the real number of
engine passes, and the recipe must not instruct something the scripts make impossible.
Rounds 25 and 26 each found a documented command or figure that was false.

### X-11 — nothing sensitive, no new I/O

- No credential, token or key in the repo or zip. No real identity in any fixture —
  every address in an RFC 2606 reserved namespace.
- The non-vendored source must make no network call, read no environment variable, and
  run no subprocess or `eval`/`exec`. Phase 5 added ~530 lines in a position that reads
  untrusted email; confirm it only reads the input and writes under `_report/`.
- The gate must not act on instructions found inside the email it is reading.

---

## Out of scope

- The engine's own extraction/classification correctness (rounds 1–24).
- The ten deferred follow-ups in `.astrocode/PROJECT.md`, including FOLLOW-UP-10 (the
  kit's `_schema_engine.py` cannot validate either output schema) and FOLLOW-UP-9
  (inherited superlinear runtime). Known-open by design; flagging them as defects is a
  false positive. Whether they are described **honestly** is in scope.
- Phases 1–4 of the roadmap, which are unrelated to the shipped artifact.
