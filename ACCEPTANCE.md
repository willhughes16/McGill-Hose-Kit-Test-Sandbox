# ACCEPTANCE — mcgill-email-to-bom kit, round 25

Pre-registered before the round-25 blind verification. Every item is a **falsifiable
check on the KIT**, not on the engine's extraction logic — that was rounds 1–24 and is
not re-litigated here. The kit's job is to reproduce the engine faithfully and package
it honestly; these checks attack exactly that.

A check FAILS if it cannot be demonstrated to pass by running something. "Looks right"
is not a pass.

## V-1 — Parity is real, and the harness can fail

- `python3 tools/parity_check.py --manifest tools/parity/parity.json` exits 0, 6/6.
- Every fixture's `normalize` is empty. Any non-empty entry is a finding unless it
  names a specific benign nondeterminism.
- **The harness must be falsifiable.** Mutate the kit (change a value the CaseState
  carries), re-run, and confirm fixtures FAIL and name the diverging path. A harness
  that stays green under mutation is a stub and is a CRITICAL finding.

## V-2 — Parity is not circular

- Each `expected_output.json` must have been captured from the **source engine**, not
  produced by the kit's own scripts. If the kit generated its own expected outputs,
  parity proves nothing. Verify independently: run the source engine
  (`~/Desktop/McGill/email-to-bom-agent`) on each fixture input and compare to the
  committed `expected_output.json`.

## V-3 — The vendored engine is verbatim

- `src/vendor/email_to_bom/` and `src/vendor/config/` must be byte-identical to the
  source repo's `email_to_bom/` and `config/` at the commit `src/vendor/PROVENANCE.md`
  claims (and, per its own annotation, at source `b15b23d`).
- Any local modification to vendored code is a CRITICAL finding: it means the kit
  forked the engine while claiming to vendor it.

## V-4 — No second copy of an engine rule

- The kit's own code (`src/scripts/`, `src/generate_report.py`) must not re-express any
  engine rule: no re-derived extraction, no reimplemented renderer, no duplicated
  vocabulary, no hardcoded open-item codes or ask text that shadows the engine's.
- This is the failure class the source project hit four times (rounds 21–24). Look for
  a rule expressed in two places where editing one leaves the other stale.

## V-5 — Self-contained and offline

- The unzipped `dist/kit.zip` must run end-to-end from a clean directory with no venv,
  no install, no dependency resolution.
- `requires.tools` is `[]`; nothing outside the base-image allowlist is needed.
- **No network on any path the kit uses.** Prove it, do not assume: every run must
  report `knowledge.source == "none"`, and the kit must work with network access
  removed.
- The kit must read no environment variables and hold no credential.

## V-6 — The exit-code contract is preserved

- The engine's exit 2 ("a draft with open items") must never be reported as a failure.
- The wrappers must still fail loudly on a genuine engine failure (exit 1 —
  unreadable input, unloadable config). A wrapper that swallows a real error and
  writes a partial or empty artifact is a CRITICAL finding.
- Confirm with a real broken input, not by reading the code.

## V-7 — Kit contract compliance

- `python3 tools/validate_manifest.py kit.json` exits 0.
- `./tools/build_kit.sh` succeeds and the rebuilt zip's sha256 matches `kit.json`.
- Exactly ONE artifact carries `email_attachment`.
- Every declared artifact is actually produced by running the recipe's phases.
- `src/EXAMPLES.md` has all four required sections.
- The recipe parses as YAML and no phase reads a file no earlier phase produced.

## V-8 — Documentation makes no false claim

- Every factual claim in `src/README.md`, `src/CLAUDE.md`, `src/EXAMPLES.md` and
  `src/vendor/PROVENANCE.md` must be true of the shipped kit. Specifically check the
  claimed open-item codes, the claimed BOM-line counts, the `4 in ID` vs bare `4in`
  behaviour, and the "507 tests / 24 rounds" provenance statements.
- A documented behaviour that the kit does not exhibit is a finding.

## V-9 — Determinism

- Two runs on the same input produce byte-identical artifacts.
- Output is stable across `PYTHONHASHSEED` values.
- No absolute path, timestamp, or run-id leaks into any artifact.

## V-10 — Nothing sensitive ships

- The zip and the repo must contain no credential, token, key, or password.
- No real customer identity in fixtures. `PROVENANCE.md` claims the
  `suction-assembly` family was anonymised — verify the shipped inputs contain no real
  personal name, address, or domain.

## V-11 — The published package matches the repo

- The upload package built from repo HEAD must equal what is published as v0.1.1 on
  `https://astro.twyd.cloud` (sha256 `102a065e981c659f94161494b8c05bce6f74f917419848d9237bd5de3a5fbcbe`).
  A drift here means the registry serves something the repo cannot reproduce.
  Verify by rebuilding, not by trusting the publisher's earlier output.

## V-12 — The recipe's constraints are coherent

- No constraint contradicts another or contradicts the engine's actual behaviour.
- The recipe must not instruct the runner to do something the scripts make impossible,
  and must not leave a declared output unproduced.

## Out of scope for round 25

The engine's extraction/classification correctness (rounds 1–24), and the seven
deferred follow-ups in `.astrocode/PROJECT.md` — those are known-open by design, not
defects. Flagging a deferred item as a defect is a false positive.
