# mcgill-email-to-bom

## Vision

Ship the McGill email→BOM engine as a standard Astro kit at **verified feature
parity** with its source: `ScaleUpLabs/McGill-Core` (private; formerly
`TWYD-Factory-McGill`) at commit `b1f9950`, version 2.0.0.

Parity here is proven, not asserted. The engine is vendored **verbatim** under
`src/vendor/` and the kit's scripts call its own entry point rather than
re-expressing any rule. That is deliberate: the logic carries 507 tests and 24
rounds of blind adversarial verification, and the source project's own recurring
failure mode was *two copies of the same rule drifting apart*. A reimplementation
would recreate that failure by construction. Parity is checked mechanically by
`tools/parity_check.py` against outputs captured from the source engine, with **no
normalization declared at all** — the engine has no clock, no randomness, no
run-ids and emits no absolute paths, so nothing needs masking and parity cannot be
silently loosened.

## Requirements

<!-- One line per requirement. Use stable IDs (REQ-001) so phases can map to them. -->

### Source capability (what the kit must reproduce)

- REQ-001 Accept one RFQ as raw bytes from a `.eml` or `.txt` path — MIME,
  quoted-printable, base64 and HTML included — and decode it the way the source
  does (`mail.extract_rfq_text`).
- REQ-002 Emit the CaseState (`schema_version` 2.0) conforming to
  `src/schemas/case_state.schema.json`: every field with a status and evidence,
  every open item with a stable `code`, `ask`, `priority` and `route`, the
  `request_class`, `routing`, and `knowledge` provenance.
- REQ-003 Classify the request into one of `hose_assembly`, `bulk_hose`,
  `component_rfq`, `order`, `stocking_lead`, `out_of_scope`, and ask only about
  fields belonging to that class.
- REQ-004 Pass `--component-ids` through to catalog matching: hits become BOM
  lines, misses become blocking asks — never silently dropped.
- REQ-005 Pass `--coc` through, and honour the text-detected C-of-C path too.
- REQ-006 Support `--config-dir` so an alternate rules/catalog directory (e.g. one
  backed by the P21 item master) can be supplied without changing the kit.
- REQ-007 Preserve the exit-code contract: **2 = a draft with open items** (the
  normal outcome), 1 = input/config error, 0 reserved. Nothing upstream may treat
  2 as a failure.
- REQ-008 Preserve the never-silently-wrong invariants: ambiguous units never
  capture (they become a `reading` plus a confirm ask); no part number, price,
  lead time or stock position is ever invented; nothing is deleted from an email
  because of styling and HTML-derived drafts carry the provenance marker (DD-1/DD-2);
  derating arms from the highest stated temperature (DD-4).
- REQ-009 Run fully offline and self-contained: `knowledge.source == "none"`, zero
  runtime dependencies, no environment reads, no network, no subprocess.

### Kit contract

- REQ-010 `python3 tools/validate_manifest.py kit.json` exits 0.
- REQ-011 `./tools/build_kit.sh` succeeds, producing `dist/kit.zip` root-relative
  with `CLAUDE.md` at the zip root, and filling `sha256` + `contents[]`.
- REQ-012 `src/EXAMPLES.md` carries all four required sections.
- REQ-013 The recipe `src/recipes/mcgill-email-to-bom.yaml` parses as YAML and its phase
  inputs/outputs are consistent.
- REQ-014 Every declared artifact is actually produced by the workflow the recipe
  describes; exactly one artifact carries `email_attachment`
  (`_report/case_state.json`).
- REQ-015 `dist/kit.zip` is committed (`git add -f dist/kit.zip`).
- REQ-016 The unzipped kit runs from a clean directory with no venv, no install and
  no dependency resolution.

### Parity (one falsifiable requirement per fixture — each must pass `parity_check.py`)

- REQ-017 `suction-assembly` — 4in EPDM suction assembly, quoted-printable, no
  size/temperature stated. Exercises the ungrounded-selection path.
- REQ-018 `plain-steam` — plain-text MIME, seat-to-seat length, 316 SS, male NPT
  both ends. Exercises captured dimensions and end connections.
- REQ-019 `quoted-printable` — the same request QP-encoded with a soft line break
  mid-sentence. Exercises decoding without changing the extracted case.
- REQ-020 `multipart-html` — multipart/alternative with an HTML part and a `<style>`
  block. Exercises HTML flattening and the DD-2 provenance marker.
- REQ-021 `confirmed-ids` — operator-confirmed Component IDs producing 4 populated
  BOM lines. Exercises catalog grounding and checkpoint closure.
- REQ-022 `human-render` — the human-readable draft, compared through the same
  exact comparator (JSON-wrapped). Exercises the renderer, not just the CaseState.

### Round 25 (blind verification) — closed findings, now requirements

Round 25 returned FAIL. The bar was `ACCEPTANCE.md`; the report is
`VERIFICATION_ROUND25.md`. The headline finding was this project's signature
failure class landing in the kit itself: one rule in two places, one copy stale.

- REQ-023 The engine invocation is ONE contract in ONE place. `run_engine.py`
  records the complete invocation (input + every flag) in `state.json`;
  `generate_report.py` replays it through the SAME `build_argv` helper. Closes F-1
  (`--component-ids` / `--coc` were dropped between phases, so the human draft
  showed an empty BOM table and a phantom `SELECTION_UNRESOLVED` the CaseState said
  was closed) and F-6 (`--config-dir` documented but unreachable from the recipe).
- REQ-024 The deliverable must reconcile with the contract. Before writing,
  `generate_report.py` re-derives the CaseState from the replayed invocation and
  asserts it equals `case_state.json`; on any difference it exits 1 rather than
  emit a draft describing a different case. This is the structural defence — it
  catches invocation drift from causes not yet imagined, not just the two flags
  round 25 found.
- REQ-025 A failed run leaves no artifact. `run_engine.py` clears the previous
  `case_state.json` and invalidates `state.json` BEFORE it can fail, so a failed
  re-run cannot leave a schema-valid artifact describing a different email
  (F-4). `parity_check.py` makes this guarantee for fixtures; the runtime now
  makes it too.
- REQ-026 The flagged render path has a fixture. `confirmed-ids-render` runs the
  full two-phase path with flags — the one combination no fixture covered, which is
  exactly where F-1 lived. Mutation-tested: reintroducing F-1 makes it fail.
- REQ-027 Documented invocations must exist. The `mcgill-email-to-bom rfq.eml` form in
  README/EXAMPLES named no shipped executable (F-3); both now distinguish the Astro
  kit invocation from the real `python3` commands.
- REQ-028 Fixture identities stay in reserved namespaces (F-7): `.example` per RFC
  2606 throughout, no ordinary `.com` anyone could own.

### Round 26 (blind verification) — closed findings, now requirements

Round 26 returned **FAIL**. Bar: `ACCEPTANCE_ROUND26.md`; report:
`VERIFICATION_ROUND26.md`. Round 25's F-1 was confirmed genuinely fixed — and the
fix pass then reproduced the same failure class twice. The lesson is now explicit:
**a fix that names an item must be replaced by one that handles the category.**

- REQ-029 Artifacts are a declared SET, not a list of names at each site.
  `run_state.ARTIFACTS` is the single declaration; invalidation walks it. R26-F1:
  the round-25 fix cleared `case_state.json` and missed `bom_draft.md`, so a failed
  phase 2 left customer A's draft beside customer B's CaseState — and the fix made
  the typo'd-path variant *worse*, deleting the CaseState so the stale draft was the
  only artifact left and nothing could contradict it.
- REQ-030 Failure handling does not enumerate exception types. R26-F2: swapping
  `except SystemExit` for `except RuntimeError` let argparse's `SystemExit(2)`
  escape from inside `cli.main`, so the wrapper exited **2** — the code every
  document defines as normal success — with no artifact and no message. The wrappers
  now catch broadly at two levels AND clamp their exit to 0/1, so no future path can
  emit a success-looking code on a failure.
- REQ-031 Reconciliation fails CLOSED. R26-F3: the guard was gated on
  `os.path.isfile`, so an absent, directory or non-regular CaseState skipped the
  check silently and a divergent pair could be landed. A missing CaseState is now an
  error; skipping requires `--no-reconcile` explicitly.
- REQ-032 Clearing and state-writing failures are LOUD. R26-F5: `except OSError:
  pass` swallowed them, so under a read-only `_report/` the stale artifact survived
  with no warning — reproducing the very defect the clearing exists to prevent.
- REQ-033 The defences have their own tests. R26-F4: deleting the reconciliation
  guard, or the stale-clearing, left parity at 7/7 green — parity compares outputs
  and cannot see a failure path. `tools/selftest.py` covers exit codes, which
  artifacts survive a failure, and whether the two artifacts agree. 25 checks,
  each mutation-tested.
- REQ-034 The invocation is recorded once, by the prepare phase, and read by every
  later phase. R26-F6: phase 0 wrote a record nothing read, then the agent re-typed
  the flags onto phase 1 — an unguarded second copy where dropping `--coc` yields
  two perfectly self-consistent artifacts that are quietly wrong. Phase 1 now uses
  `--from-state`.
- REQ-035 A failed phase preserves its inputs. R26-F10: phase 1 wiped the prepare
  phase's record before it could fail, leaving `state.json` as `{}` in exactly the
  case where resuming matters. Invalidation now drops the *result* record only.
- REQ-036 Published figures describe the shipped behaviour. R26-F7 (runtime was
  quoted single-pass when a run makes three engine passes) and R26-F8 (fixture
  counts wrong in both directions — 7 fixtures over 4 distinct inputs, not "six
  fixtures, five distinct inputs").

### Phase 5 — Input Filter (goal)

Decide, before the engine is invoked at all, whether an inbound message is a
quoting request worth drafting a BOM for — and route everything else without
producing a draft.

The engine already classifies in-scope requests six ways, including
`out_of_scope`, so this is NOT a new classification of RFQs. It is a pre-filter on
the mailbox: auto-replies and vacation notices, delivery-status notifications,
newsletters and marketing, bare acknowledgements ("thanks, got it"), invoices and
statements, and internal chatter. Today the kit drafts for any input, so a
newsletter produces a draft BOM full of open items and an operator has to read it
to discover there was never a request.

Hard constraints inherited from the kit:
- The engine stays vendored verbatim; a filter must not alter, truncate or
  normalise the bytes the engine receives, or output parity with the source
  breaks. The filter decides WHETHER to run the engine, never WHAT it sees.
- Filtering out a real RFQ is far worse than passing a newsletter through. The
  kit's whole design line is "better to ask than to be quietly wrong", so the
  filter must fail toward invoking the engine and must never silently discard.
- Every filtered message needs a machine-readable reason and a route, consistent
  with how `open_items` already carry codes and routes.

### Round 27 (blind verification) — closed findings, now requirements

Round 27 returned **FAIL** with two CRITICALs. Bar: `ACCEPTANCE_ROUND27.md`; report:
`VERIFICATION_ROUND27.md`. It found the filter dropping **24 of 35 genuine RFQs** — and
that version was published as v0.4.0. It has been deleted from the instance, which is
back on filter-free v0.3.0.

- REQ-037 What protects a real request is a MEASURED property of the message, never a
  phrase list. `_spec_depth()` counts the specification fields the vendored engine
  extracts; a `requires_no_specs` category may filter only at depth 0. R27-F1: the old
  protection was a 16-phrase `quote_request_cues` list sitting on the *unsafe* side of
  the decision, so one line of `Terms net 30.` dropped a 200-foot EPDM order, and
  `Please price this.` lost a message that `Please quote this.` kept. The guard is
  monotone — more customer detail means more protection — and there is no vocabulary to
  keep current.
- REQ-038 Only true list-mail may filter a spec-bearing message. `filter_tier` is
  declared per category in `filter_signals.json`: `always` for `List-Unsubscribe` plus
  `Precedence: bulk`/`List-Id` (nobody orders hose from a mailing list), and
  `requires_no_specs` for everything else. A category that omits the field defaults to
  the SAFE tier — omission must not grant the power to drop work.
- REQ-039 No category short-circuits the guards. R27-F2: DSN returned before the veto
  "because a bounce is never a request", so a `multipart/report` content type, a
  `postmaster@` sender or a bare `Return-Path: <>` each dropped a labelled RFQ. DSN now
  requires the CONJUNCTION of report-type=delivery-status and a null return path, and
  passes through the same guards as everything else.
- REQ-040 A message that cannot be fully read is never judged. R27-F3: `undecodable` was
  computed and never consulted, so the documented fail-open did not exist and two
  messages identical but for HTML body size decided oppositely.
- REQ-041 Invalidation is driven by the ARTIFACTS declaration, proven by test. R27-F4:
  all three clearing sites hand-wrote the filenames, so REQ-029's claim was FALSE and
  R26-F1's mechanism was intact behind a docstring asserting otherwise. `all_artifacts()`
  is now the only way to clear, and the self-test adds a synthetic artifact and requires
  it to be cleared with no call site edited.
- REQ-042 An override is an explicit choice, scoped to its message. Round 27:
  `bool(raw["override"])` enabled it for the STRING `"false"`, and the record was never
  cleared so an override granted for one email governed the next run. Now strict-boolean
  and bound to the input it was granted for.
- REQ-043 Coverage drives the SHIPPED path. R27-F5: 9 of 20 mutations left the suite
  green, including deleting the override read — the check exercised `--no-filter` on the
  command line while the recipe only ever uses `--from-state` plus the record. All
  round-27 checks drive `--from-state`, and each new guard is mutation-proved.

### Round 28 (blind verification) — closed findings, now requirements

Round 28 returned **FAIL** with two CRITICALs. Bar: `ACCEPTANCE_ROUND28.md`; report:
`VERIFICATION_ROUND28.md`. It confirmed round 27's fix was a real improvement (RFQ loss
24/35 → 15/39 on an independent corpus) and then found it broken on its own central claim.
This is the fourth consecutive round whose findings were all introduced by the previous
round's fix pass.

- REQ-044 The measured field set is DERIVED from the engine, never hand-listed. F-1:
  `_SPEC_FIELDS` named `"length"`, which `core.Extraction` does not have (it has
  `length_value`/`length_type`), so `getattr(e, "length")` was `None` for every message
  ever written and a length-only order — "get us 400 feet of the transfer hose" —
  measured depth 0 and was filtered as an invoice. `_spec_field_names()` now reads
  `dataclasses.fields(core.Extraction)` minus a small non-spec exclusion set, so a name
  cannot go dead and a field the engine adds later counts as protection by default.
- REQ-045 No category is exempt from the depth guard. F-2: `filter_tier: "always"` let
  true list-mail skip it, leaving that category protected solely by the veto — whose
  `request_act` half is the 16-phrase list round 27 was failed for. A customer whose ESP
  stamps `List-Unsubscribe` was dropped to `no_action` with EIGHT specification kinds
  extracted. The tier concept is deleted. **Accepted cost:** a supplier newsletter naming
  hose specifications now reaches the engine and produces a draft an operator dismisses.
  The phase-5 constraint settles that trade — filtering out a real RFQ is far worse.
- REQ-046 An override must name the message it governs, and the RECIPE must write it.
  F-3: `screen_applies()` honoured an input-less record and the recipe template wrote
  exactly that, so the binding was inert on the only path the recipe uses — while the
  self-test wrote a shape the recipe never produced. That is R27-F5's lesson
  reintroduced inside the fix for R27-F5.
- REQ-047 Every clearing site resolves paths through the declaration. F-4: R27-F4 was
  closed at two of three sites; `generate_report.py` still hand-wrote its path while
  `all_artifacts()`'s docstring claimed no site names files. `artifact_path(name)` serves
  single-artifact owners; the self-test now probes all three.
- REQ-048 The whole decision record is validated, not two of its fields. F-6: `reason`
  was unvalidated and the schema's closed enum omitted both reasons round 27 added, so
  every spec-bearing pass-through violated the shipped schema unnoticed.
- REQ-049 Mutation survival is reported as a number. Rounds 26, 27 and 28 each had 9
  behaviour-changing mutations leave the suite green. The round-28 pass mutation-tested
  all seven fixes: **0 of 7 survived**, including "drop length from measurement", the
  exact defect F-1 found. Two `undecodable` checks that round 28 proved vacuous (both
  fixtures were HTML-only over budget, so no detector could fire and they passed on
  `candidate is None`) were rewritten to carry a live header candidate.

### Round 29 (blind verification) — closed findings, now requirements

Round 29 returned **FAIL** with three CRITICALs and recommended rollback. v0.6.0 was
**live** and dropped **11 of 46 genuine RFQs (24%)** on an independent corpus. It has been
deleted from the instance, which is back on filter-free v0.3.0. Fifth consecutive round
whose findings were introduced by the previous round's fix.

- REQ-050 A message's PROSE and its sender ADDRESS are never grounds to drop it.
  `INVOICE_OR_STATEMENT`, `BARE_ACKNOWLEDGEMENT` and `INTERNAL_CHATTER` are deleted, and
  so are `auto_reply_localparts` / `dsn_sender_localparts`. R29-F1/F2: an
  `invoice_phrases` substring sent 6 real RFQs to accounts payable ("net 30" in a
  purchasing email is a purchase order, not an invoice), and `no-reply@`/`donotreply@` —
  the standard sender of every sourcing portal and ERP requisition — sent 5 to
  `no_action`. Only what a sender's software DECLARES under RFC 3834/3464 can filter:
  an automatic reply, a delivery report, or list mail. The detectors are deleted, not
  disabled, so no future category can re-wire them.
- REQ-051 `auto-generated` is not `auto-replied`. RFC 3834 draws the line: `auto-replied`
  means the message IS a reply to another, which a customer's original request never is;
  `auto-generated` is what ERPs stamp on real requisitions. Only the former filters.
- REQ-052 Specification depth is measured on the BODY, not on subject+body. R29-F8: an
  out-of-office responder echoes the RFQ subject verbatim, so 4 of 6 realistic OOO
  replies measured a non-zero depth and escaped the category built to catch them. The
  body is what the sender actually wrote. The same change is what let the depth
  exemption for protocol-certain categories be removed — an exemption that dropped the
  shipped `bait-rfq` fixture, a genuine RFQ body wearing an `auto-replied` header.
- REQ-053 Nothing routes colder than a human queue except the two protocol reports.
  `BULK_MAILING` now routes to `inside_sales_fyi`; a false positive must be visible.
- REQ-054 Every declared category has a check that fails when its detector is deleted.
  R29-F3: `BULK_MAILING` had **zero** coverage — a blanket fixture retarget removed its
  check and never replaced it, so deleting `_bulk_headers` entirely left the suite green
  while the loop header still claimed "the six junk categories".
- REQ-055 A check must be able to fail. R29-F4: the check added to close R27-F4 asserted
  `"report:" in out`, which is unconditionally true — a tautology.
  **CORRECTION (round 30): this requirement was recorded as closed while the line was
  unchanged.** Round 29's replacement anchored on text that did not match, the edit
  silently did nothing, and it was then reported as fixed here and in the commit message —
  a HIGH marked closed in three places without the code changing. Round 30 found it
  byte-identical, and `git blame` put it at round 28's commit. It is now genuinely
  replaced, and the replacement was itself mutation-tested twice: the first rewrite also
  could not fail (it observed where the draft was WRITTEN, which happens regardless of
  which path was cleared), so it was rewritten again to make the run fail after the clear.
  Every string replacement in a fix pass now carries an assertion that the anchor matched.
  Rounds 26, 27 and 28 each had 9 behaviour-changing mutations survive; round 29 had 10 of
  24; round 30 had 15 of 34.
- REQ-056 A guard's own failure never stops the run. R29-F6: `_load_reason_pattern`
  omitted the `TypeError` its sibling `_load_enums` catches, so a malformed schema
  crashed the gate with rc=1 instead of failing open.

**What the feature is now, honestly.** It suppresses machine-generated noise —
auto-replies, bounces, spec-free bulk mail — and nothing else. Invoices, bare
acknowledgements, internal notes and hose-industry newsletters all reach the engine and
produce a draft an operator dismisses. That is a large reduction in scope from phase 5's
ambition, and it is the correct trade: the phase-5 constraint says losing a real RFQ is
far worse than passing junk through, and two rounds of measurement showed prose-based
judgement cannot be made safe.

### Round 30 (blind verification) — FAIL, and the input filter is REMOVED

Round 30 returned **FAIL** and recommended deleting the gate. Phase 5's feature is gone
as of v0.8.0. The measurements that decided it, from an independent 45-message corpus:

| | Round 29 (v0.6.0) | Round 30 (v0.7.0) |
|---|---|---|
| Genuine RFQs dropped | 11/46 (24%) | 13/45 (**28.9%**) |
| Junk suppressed | not measured | 11/33 (33%) |
| **Share of all drops that were real customer requests** | — | **54%** |
| Mutations surviving the suite | 10/24 | **15/34** |

- REQ-057 **The kit does not decide whether a message deserves a quote.** The engine
  reads the whole message and classifies `out_of_scope` after doing so; it asks rather
  than assumes. A pre-engine gate has to reach the opposite kind of judgement — "this
  needs nothing" — without reading properly, and six rounds showed that cannot be made
  safe here. Three scope reductions each moved the failure surface instead of removing
  it: a 16-phrase cue list (round 27), a hand-written field tuple with a dead name plus a
  list-mail exemption (round 28), and content categories plus sender heuristics
  (round 29). Round 30 still lost 28.9%, with 54% of all drops being real business.
- REQ-058 **Two builds were published before being blind-verified, and both were
  dropping customer requests** — v0.4.0 (24/35) and v0.6.0 (11/46). Both were rolled
  back. Nothing ships from here without a passing blind round, whatever the self-test
  says.
- REQ-059 **A fix is not closed until its check has been shown to fail.** Round 30 found
  R29-F4 recorded as closed in a commit message and in this file while the line was
  byte-identical — an unasserted string replacement had silently done nothing. Every
  replacement in a fix pass now asserts its anchor matched, and every new check is
  mutation-tested before it is claimed.

**What remains:** the engine, vendored verbatim, behind a three-phase recipe (`prepare` →
`extract_case` → `generate_report`) with the rounds 25–28 wrapper defences — one
invocation contract, draft/CaseState reconciliation that fails closed, loud stale-artifact
clearing, clamped exit codes. Those are the parts every blind round has confirmed. The
28-check self-test covers exactly them.

### Round 31 (blind verification) — FAIL, and what it changed

Round 31 verified the removal and found the surgery left prose damage, exactly where a
removal round was predicted to leave it. **Mutation survival: 18 of 36.**

- REQ-060 Shipped documentation is shipped bytes. F-1: a regex left a sentence fragment in
  `src/CLAUDE.md`'s Arguments section whose only visible subject became `--config-dir`,
  asserting it "never reaches `run_engine.py`'s argv" — false, `build_argv` passes it. F-2:
  `EXAMPLES.md` Example 5 was truncated mid-list with no `**Produces:**`, violating the kit
  contract's required format. Both were inside `dist/kit.zip`. No gate in `tools/` can see
  documentation damage, which is why they shipped.
- REQ-061 `--config-dir` has a defence. F-4: `--component-ids` and `--coc` each had one and
  the third flag had none — dropping it from `build_argv` left phase 1 at exit 0, phase 2
  reconciling GREEN (both passes replay the same builder, so reconciliation structurally
  cannot see it) and the CaseState built from the wrong item master. The check now plants a
  marker in an alternate catalog and requires it in the output.
- REQ-062 The exit clamp is driven by a path where a 2 can escape. F-3 was **right in
  substance and wrong in its reproduction**: removing the clamp alone does NOT leak a 2
  (the `__main__` broad catch handles it first), but removing both layers does, and no
  check drove the wrappers' own argparse to fail. Three `--bogus-flag` cases now do.
- REQ-063 A superseded design record says so. F-5: all five ADRs in `DECISIONS.md`
  described the deleted gate in the present tense with no superseding entry, and the
  removal commit never touched the file — the "missed the sibling" shape for the eleventh
  time.

## Constraints

- **Never edit `src/vendor/`** to change an outcome. It is a stamped verbatim copy;
  refreshing it means re-running the copy in `src/vendor/PROVENANCE.md` against a
  newer source commit and re-running parity. Parity failing after a refresh means
  engine behaviour changed — investigate before accepting.
- **Never widen a parity normalization** to make a fixture pass. There are none
  today; adding one requires naming the specific benign nondeterminism it covers.
- **Vocabulary order in `vendor/config/rules.json` is behaviour.** First-match-wins
  drives media selection, material grade, question topic and classifier precedence.
  Never re-serialize that file through a tool that sorts keys.
- The `questions` / `open_items` duality must stay in lockstep — some open items
  have no `questions` twin by design. Do not collapse them into one list.
- The kit drafts only. It must never present output as a quote, a confirmed BOM or
  an order, and must never answer, drop, reword or re-prioritize an open item.

## Out of scope / deferred follow-ups

These are **flagged, not done** — capabilities the source has that this kit
deliberately does not wire in, plus known upstream blockers. None of them is
quietly treated as complete.

- **FOLLOW-UP-1 — live graph knowledge (non-self-contained).**
  `src/vendor/email_to_bom/knowledge.py` contains `McpKnowledge`, which reaches a
  graph endpoint over `urllib` (`Authorization: Bearer <key>`, 8s timeout). It is
  **dormant and not wired into this kit**: the engine defaults to `NullKnowledge`
  and every run reports `knowledge.source == "none"`. Wiring it would make the kit
  non-self-contained and require a read-scoped token. Do not add it as a hidden
  dependency.
- **FOLLOW-UP-2 — graph write-back (non-self-contained, containment-critical).**
  The same module contains `TwydIngestion`, which POSTs to
  `{base_url}/api/ingestion/text`. It is harness-held by design: a source test
  asserts `core.py` cannot even reference `TwydIngestion` or `publish`. The kit must
  never hold a write key.
- **FOLLOW-UP-3 — grounded selection is blocked upstream.** Without the P21 item
  master the engine cannot choose a hose or fitting and raises
  `SELECTION_UNRESOLVED`. Unlocking it (and the `verified` knowledge tier) needs the
  P21 item master and the ContiTech catalog from McGill.
- ~~**FOLLOW-UP-4 — no `ac registry init` yet.**~~ **CLOSED 2026-08-26.** The kit now
  owns its own git repo (it no longer sits inside the `~/Desktop` repo), `dist/kit.zip`
  is committed with `git add -f`, origin is
  `github.com/ScaleUpLabs/McGill-email-to-bom-kit` (private), and `ac registry init`
  succeeded on `astro-registry`. This satisfies REQ-015 and the work of phase 1 —
  which was completed before the phase was created, so phase 1 has no plan or
  verification record in the astro loop. Accept or drop it deliberately rather than
  running it as if the work were outstanding.
- **FOLLOW-UP-5 — `download_url` is a placeholder.** `kit.json` still carries
  `https://TODO.example/...`; it is filled in by publishing, not by hand.
- **FOLLOW-UP-6 — fixture corpus is thin and partly synthetic.** Seven fixtures over
  only **four distinct inputs** — `suction-assembly`, `confirmed-ids`, `human-render`
  and `confirmed-ids-render` all share one `.eml` (verified by sha256), so the corpus
  is narrower than the fixture count suggests. All from the source's own
  examples/tests. The identity lines of
  the `suction-assembly` family were anonymised (technical content unchanged) before
  capture. Real RFQ `.eml` files from McGill would make parity claims much stronger;
  they have been requested.
- **FOLLOW-UP-7 — the source's 507-test suite does not run here.** Parity covers the
  seven fixtures (four distinct inputs), not the full suite. The tests live in the source repo and are not
  vendored. A regression in a path no fixture touches would not be caught by this
  kit alone.
- `src/vendor/config/catalog_candidates.json` ships but is never loaded by the
  engine (the source documents this). Harmless dead weight kept for verbatim
  fidelity.
- **FOLLOW-UP-10 — the kit's own validator cannot check its schemas** (round-25/26
  shape, surfaced by the phase-5 verifier). `tools/_schema_engine.py` cannot validate
  `case_state.schema.json` ("additionalProperties subschema
  at path fields"). So both output contracts are documented but not machine-checkable
  by the kit's own tooling — the enums are enforced only by `tools/selftest.py`
  asserting real records against them. Pre-existing, not introduced by phase 5, and
  worth fixing before a third schema is added.
- **FOLLOW-UP-8 — two unreachable schema values, fix belongs upstream** (round 25,
  F-5). `schemas/case_state.schema.json` declares `status: "superseded"` and
  `knowledge.lookups[].op: "ratings_for"`; the engine can emit neither. The schema is
  deliberately NOT corrected here — it is a copy of the source's contract, and editing
  it in the kit would fork the contract while claiming fidelity, which is the exact
  drift this project exists to avoid. Documented in EXAMPLES.md so no consumer builds
  a dead branch; raise it against `ScaleUpLabs/McGill-Core`.
- **FOLLOW-UP-9 — superlinear runtime on large inputs** (round 25, F-8). ~0.1 s at
  8 KB, ~5 s at 134 KB, ~80 s at 538 KB, unbounded beyond. Measured as **inherited**:
  the source engine takes 88.0 s on the same 538 KB input and its output is
  byte-identical, so parity holds and the cost is the engine's, not the kit's. The kit
  now warns above 100 KB from the wrapper scripts and states an honest `estimated_duration`;
  a real fix (or a documented input ceiling) belongs upstream. Note a kit run costs
  THREE engine passes, so the end-to-end cost is ~3x the single-pass figures
  (round 26, R26-F7).
