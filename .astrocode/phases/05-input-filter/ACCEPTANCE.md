# ACCEPTANCE — Phase 05 Input Filter (UAT)

User-facing checks a human confirms before the phase closes. Not unit tests — each one is
something an operator can do and see. `$KIT` = the kit root.

- [ ] **The user can point the kit at a newsletter, an auto-reply, a bounce, a bare
      "thanks, got it", an invoice/statement or an internal note and get told there was
      nothing to quote — with no BOM draft to read.** After each run `_report/` holds no
      `case_state.json` and no `bom_draft.md`.
- [ ] **The user can see, per filtered message, WHY and WHERE it went, as machine tokens.**
      `_report/state.json` carries a `filter` record with a stable `code`, a `route` from
      the vocabulary declared in `schemas/filter_decision.schema.json`, and the input path
      it was given — different categories report different codes, and the same message
      re-run gives the identical record.
- [ ] **The user's automation can tell "nothing to quote" from "the kit broke" from "a
      draft was produced" by exit status alone** — filtered is a documented, distinct code
      (never the engine's `2`), a real failure is another, and a drafting run is another.
- [ ] **The user can still process a filtered message without editing the kit or the
      email.** The documented override (`--no-filter`) runs verbatim on the newsletter and
      on the bare acknowledgement and produces a CaseState plus a draft; the email file's
      bytes are unchanged.
- [ ] **The user's real RFQs are unaffected — including the tricky ones.** An RFQ that
      happens to carry newsletter/auto-reply headers, one that opens with "Thanks, got
      it.", one bundled with an invoice paragraph, one with corrupted MIME, and a
      zero-byte file all still reach the engine (or fail loudly) — never a quiet
      "filtered".
- [ ] **The user's drafts are byte-for-byte what the engine would have produced without
      the filter.** `python3 tools/parity_check.py --manifest tools/parity/parity.json`
      exits 0, and driving the full documented flow on each parity input yields a
      `case_state.json` identical to the source-captured `expected_output.json`.
- [ ] **The user does not wait on the engine to learn a newsletter was a newsletter.** A
      ~1 MB newsletter is filtered in a couple of seconds, and no engine invocation
      happens on any filtered message.
- [ ] **The user's filtered run never leaves the previous customer's paperwork lying
      around.** After a real RFQ run followed by a newsletter in the same directory, the
      earlier `case_state.json` and `bom_draft.md` are gone.
- [ ] **The user can trust the safety net is real.** `python3 tools/selftest.py` exits 0,
      and it exits non-zero if the filter is forced to always pass through or to always
      filter.
- [ ] **The user installs nothing.** `python3 tools/validate_manifest.py kit.json` and
      `./tools/build_kit.sh` succeed with `requires.tools` still empty, and the unzipped
      `dist/kit.zip` filters a newsletter and drafts a real RFQ under `python3 -S -E`.
