# ACCEPTANCE — mcgill-email-to-bom kit, round 26

Pre-registered before the round-26 blind verification. Round 25 returned **FAIL** with 8
findings; all 8 were addressed and the kit was renamed (`email-to-bom` →
`mcgill-email-to-bom`) and republished at v0.2.0. Round 26 must decide whether the fixes
are real, whether they introduced anything new, and whether the same failure class still
lives somewhere else.

A check FAILS if it cannot be demonstrated by running something. "Looks right" is not a
pass. The fixes were tested by their own author — treat that as an unverified claim.

---

## Part A — did the round-25 fixes actually close the findings?

### W-1 — F-1: the invocation contract (was HIGH)

Round 25 found `--component-ids` / `--coc` were dropped between phase 1 and phase 2, so
`bom_draft.md` showed an empty BOM table and a phantom `SELECTION_UNRESOLVED` while
`case_state.json` showed 4 lines and no such item.

- Run the recipe's two phases with flags, phase 2 **flagless exactly as the recipe
  states**, and confirm the draft and the CaseState describe the same case.
- Then attack it: find **any** invocation where the two artifacts still disagree.
  `--coc`, `--config-dir`, several `--component-ids`, IDs that do not match the catalog,
  flags in unusual order, an empty `--component-ids` list, a relative vs absolute input
  path, running the phases from different working directories, a `state.json` written by
  an older version of the kit.

### W-2 — the reconciliation guard: can it be defeated, and can it fail open?

`generate_report.py` re-derives the CaseState and refuses to write when it differs.

- Confirm it FAILS on a genuine divergence and names the diverging key.
- **Hunt for fail-open paths**: what happens when `case_state.json` is absent,
  empty, truncated, unreadable, not JSON, or points somewhere unexpected? Does any of
  those write a draft anyway? If a draft can be produced without reconciliation, say so
  and rate it.
- Look for **false positives**: any legitimate run where the guard fires wrongly.

### W-3 — F-4: stale artifacts

- After a failed run, no `case_state.json` from a previous email may survive, and
  `state.json` must not still point at the old run.
- Attack it: a read-only `_report/`, a directory where the artifact should be, a failure
  *during* the write rather than before it, an unwritable `state.json`, two runs racing.

### W-4 — the new fixture is falsifiable

`confirmed-ids-render` is claimed to be a regression guard for F-1, mutation-tested.
Verify independently: reintroduce F-1 (or something equivalent) and confirm that
fixture fails. A guard that cannot fail is a CRITICAL finding.

### W-5 — did the fixes introduce NEW defects?

The fixes changed both wrappers, the recipe, the fixtures and the docs. The engine now
runs up to **three times** per kit run (once in phase 1, twice in phase 2). Look for:
regressions in the exit-code contract, doubled or missing side effects, the extra
invocation changing behaviour or artifacts, performance consequences, and any place the
new `state.json` shape breaks something that read the old one.

### W-6 — the fixes are honestly described

`.astrocode/PROJECT.md` REQ-023..REQ-028, `CONVENTIONS.md`, the commit message and the
round-25 report all describe what was fixed. Every claim must be true of the shipped
kit. In particular: F-5 is claimed to be *documented but deliberately not patched* —
verify the schema is still byte-identical to the source's and that EXAMPLES.md tells a
consumer the truth.

### W-7 — the rename left nothing dangling

`email-to-bom` → `mcgill-email-to-bom`. Confirm: kit id == `registry-entry.json` id ==
directory name; the recipe file is named after the id and `CLAUDE.md` points at it; no
stale `email-to-bom` reference remains anywhere it would break something. The source
repo path `email-to-bom-agent` and the GitHub repo `McGill-email-to-bom-kit` must NOT
have been mangled by the rename.

---

## Part B — the round-25 bar, re-run against the new artifact

### V-1 Parity is real and falsifiable
7/7 via `python3 tools/parity_check.py --manifest tools/parity/parity.json`; every
`normalize` empty; harness proven able to fail by mutation.

### V-2 Parity is not circular
Every `expected_output.json` must come from the **source engine**
(`~/Desktop/McGill/email-to-bom-agent`, its own `.venv`), not from the kit. Regenerate
them yourself and compare. `parity.json` claims all 7 were captured at source commit
`b15b23d` — check that claim.

### V-3 The vendored engine is verbatim
`src/vendor/email_to_bom/` and `src/vendor/config/` byte-identical to the source at the
commit `PROVENANCE.md` stamps. Any local edit is CRITICAL.

### V-4 No second copy of an engine rule
No re-expressed extraction, renderer, vocabulary, open-item code or ask text in kit
code. The invocation argv must be assembled in exactly ONE place.

### V-5 Self-contained and offline
Unzipped `dist/kit.zip` runs from a clean dir with no venv/install/deps;
`requires.tools` is `[]`; `knowledge.source == "none"` on every run; works with network
removed; reads no environment variable; holds no credential.

### V-6 Exit-code contract
Engine exit 2 is never a failure; wrappers still fail loudly (exit 1) on genuine
failures and never write a partial or empty artifact. Prove with real broken inputs.

### V-7 Kit contract compliance
`validate_manifest.py` exits 0; `build_kit.sh` succeeds and the rebuilt zip's sha256
matches `kit.json`; exactly ONE `email_attachment`; every declared artifact actually
produced by the recipe; EXAMPLES.md has all four sections; recipe parses and no phase
reads a file no earlier phase produced.

### V-8 Documentation makes no false claim
Every factual claim in `src/README.md`, `src/CLAUDE.md`, `src/EXAMPLES.md`,
`src/vendor/PROVENANCE.md`. Check the stated open-item codes and BOM-line counts, the
`4 in ID` vs bare `4in` behaviour, the stated runtime figures, and the documented
invocations — round 25 found a documented command that did not exist.

### V-9 Determinism
Repeated runs byte-identical; stable across `PYTHONHASHSEED`; no absolute path,
timestamp or run-id in any artifact.

### V-10 Nothing sensitive ships
No credential/token/key in the zip or repo. No real identity in fixtures — all
addresses must be in RFC 2606 reserved namespaces.

### V-11 The published package matches the repo
The upload package rebuilt from repo HEAD must equal what is published as
`mcgill-email-to-bom` v0.2.0 on `https://astro.twyd.cloud`, sha256
`6cdfd8364c509f991518dc0648f6a05d819856cf987abb80250dff62876e9cad`. Rebuild; do not
trust the publisher's earlier output.

### V-12 The recipe's constraints are coherent
No constraint contradicts another or the engine's actual behaviour; nothing declared is
left unproduced; the reconciliation-failure instruction is actionable.

---

## Out of scope

- The engine's own extraction/classification correctness (rounds 1–24).
- The nine deferred follow-ups in `.astrocode/PROJECT.md`, including FOLLOW-UP-8
  (unreachable schema values, fix belongs upstream) and FOLLOW-UP-9 (inherited
  superlinear runtime). These are known-open by design; flagging them as defects is a
  false positive. What IS in scope is whether they are described honestly.
