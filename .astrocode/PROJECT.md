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

### Round 32 (blind verification) — FAIL, and what it changed

Round 32 verified the inline-reply feature and returned FAIL with two CRITICALs and four
HIGHs. **Mutation survival 33 of 51 (65%) — the worst recorded — and 28 of the 33 were in
`render_reply.py`, the file that is now the only artifact a human reads.**

- REQ-064 Untrusted text is rendered inert. C-1: an email line beginning `\x1b[2K\x1b[G`
  erased the reply's attribution prefix in any terminal or pager and rendered customer
  text byte-identically to the kit's own checkpoint lines — a customer could display a
  checkpoint as CLEARED. Every value now passes through `_safe()`, which strips whole
  ANSI sequences and all control characters and folds the result to one line. The
  invariant under test is structural: no line may imitate the checkpoint format unless it
  IS a checkpoint.
- REQ-065 Every record is rendered whole. C-2/H-2: `open_items` went through a
  hand-written three-key whitelist — the exact R26-F6 shape `run_state.py` claims was
  eliminated — so a `CAPABILITY_ANSWER_READY` item lost both the customer's question and
  the catalog answer, leaving "propose these" with no referent, and `tier`, `citation`,
  `candidates`, `context_text` were dropped. `fields` and `routing` had already been
  hardened; `open_items` was the missed sibling, the twelfth occurrence. Checkpoints and
  off-column BOM data were fixed in the same pass rather than waiting to be named.
- REQ-066 The reply reconciles, and fails closed. H-1: `generate_report.py` refused an
  edited CaseState and exited 1, and `render_reply.py` then exited 0 and wrote a
  confident reply — zero open items, every checkpoint CLEARED, a fabricated price —
  beneath its own footer swearing no price appears.
- REQ-067 A check must exercise the shape it claims to test. H-3: six checks could not
  fail, and three of the author's replacements still could not, because engine-produced
  fixtures never carried the data — one passed by pure coincidence, matching a route
  string that also appears in the "Route to:" line. A synthetic CaseState now carries
  every shape (extra record keys, off-column data, ANSI, bare CR/BS) with distinctive
  `MUST-APPEAR-*` tokens.
- Round 32 also adjudicated round 31's F-3 in the author's favour: removing the exit
  clamp alone does not leak exit 2, because `__main__`'s broad catch handles `SystemExit`
  first. The property is covered — by the broad catch, not the clamp.

### Round 33 (blind verification) — FAIL, and what it changed

Round 33 returned FAIL — nine for nine — with two CRITICALs. **Mutation survival improved
to 22 of 57 (39%) from round 32's 33/51 (65%), and CaseState fidelity to 12 of 17 keys
rendered whole from 10.** It also REFUTED one of the three weaknesses named on its own bar:
the reply's reconciliation does not produce false refusals (10 repeat renders, 12
PYTHONHASHSEED pairs, absolute paths and an alternate `--config-dir` all reconciled).

- REQ-068 Untrusted text is stripped by Unicode CATEGORY, not by a list of code points.
  C-1: `_safe()` handled ANSI and C0/C1 and passed bidi through, so a `U+202E` override in
  a customer's question rendered as **"Can you confirm the price agreed at $9700?"** forty
  lines above the same file's footer stating that no price appears — an arbitrary
  display-text channel whose highest-value payload is the one content class the kit exists
  never to emit. The author had named the Unicode gap as cosmetic line-reordering and
  underestimated it. Now `Cc/Cf/Cs/Co/Cn/Zl/Zp` are stripped by category, which cannot go
  stale as Unicode grows, and the ANSI pattern covers OSC/DCS and the 8-bit C1 forms.
- REQ-069 A check must be run against every fixture that could falsify it. C-2: round 32's
  own anti-tautology check was pointed at the ONE fixture of five that cannot fail it, and
  the token it hunted was satisfied by the Evidence column its own loop excludes. Reverting
  the round-31 field fix left the suite 69/69 green printing "dropped: []". It now runs
  across four fixtures and compares against the row's VALUE cell only.
- REQ-070 The reply is a superset of the draft, by construction. H-4: it LOST all six
  `questions[].rule_id` the draft carries, plus `extraction.end_fittings` (a barb the
  customer named) and `class_evidence`, while three documents claimed it was a superset.
  Those are now rendered, and a REMAINDER section prints any top-level key no section
  consumed — so completeness is a property of the renderer, not a claim about it.
- REQ-071 Nothing is lost to presentation. H-2: an unrecognised `priority` was never
  printed, because the key sits in the headline set and so was excluded from the
  all-other-keys loop. H-3: 40/48-char truncation silently dropped attributes including a
  Component ID; long values are now shown in full below the table.
- REQ-072 A marker must sit where the defect would remove it. Round 33's first coverage
  attempt put `MUST-APPEAR-LONG` inside the surviving prefix, so the truncation check
  passed either way — the same coincidence-match that round 32 found. Markers now sit in
  the truncation tail.

### Round 34 (blind verification) — FAIL, and the blocker was fabrication

Ten for ten, but **mutation survival fell again: 65% → 39% → 32% (21 of 66)**, and round 34
**refuted** one of the four weaknesses named on its bar (the synthetic block's
`--no-reconcile` is adequately compensated) while confirming three.

- REQ-073 Whitespace FOLDS, it never vanishes. The blocker: round 33's category rewrite ran
  the strip before the whitespace fold, and `\n` is `Cc`, so `"temperature\n250"` rendered
  as `temperature250` — a token present in no email, printed in the Evidence column whose
  entire purpose is to be the customer's verbatim span. It **fabricates rather than loses**,
  with no marker, on a plain message with no hostile intent, and the recipe sends that body
  verbatim. `Cc/Zl/Zp` now fold to a space; only `Cf/Cs/Co/Cn` are removed. Legitimate
  non-Latin script is preserved (verified: Arabic survives, bidi overrides do not) — the
  correctness/security trade the bar asked about lands the right way.
- REQ-074 Every truncated cell has an in-full backstop. H-1: the Value cell got one in
  round 33 and the Evidence cell in the SAME `rows.append(...)` call did not — the
  fourteenth missed-sibling — losing `1450.75 psig`, half of the conflict blocking a quote.
  The four-fixture check also explicitly skipped `evidence`.
- REQ-075 Consumption is tracked, not declared. H-2: the hand-written `_consumed` set was
  wrong in six places, and a key listed there but not rendered was silently absent AND
  excluded from the backstop — worse than having no backstop. Sections now mark their own
  keys as they render, so the set cannot drift from what is emitted.
- REQ-076 A falsy value is information. H-3: `v not in (None, "", [], {}, False)` dropped
  every False-valued key and, since `0 == False`, every `0` and `0.0` —
  `extraction.material_recognized: False` was a shipped-path casualty.
- REQ-077 Never claim a count the page cannot show. H-4: with an alternate `--config-dir`
  supplying no `bom_columns`, the reply printed `Draft BOM lines: 2` and then no BOM
  section and no part numbers. Columns now fall back to the keys the lines carry.
- REQ-078 An absolute claim about content must be true of the content. H-5: the footer
  asserted no price appears anywhere above — false in plain ASCII whenever the customer's
  own question mentions one. It now distinguishes what the ENGINE produces from what the
  customer is quoted saying.
- REQ-079 A regression golden for `reply.md` is needed and is NOT circular. Round 34
  adjudicated the author's reasoning as half right: a *parity* fixture is correctly absent
  (there is no source counterpart), but three reply mutations survive for want of a
  golden-file regression check. Still outstanding.

### Round 35 (blind verification) — FAIL, the narrowest of the campaign

Eleven for eleven, but converging hard: **mutation survival 32% → 25% (14/55; honest
real-regression subset 6/55 = 11%)**, CaseState fidelity 12/17 → 13/17 strict (15/17
shipped-path), and 24 mutations were killed *only* by the new golden suite — it earned its
place immediately.

- REQ-080 A falsy-value fix is not closed until every sibling filter is fixed. The
  blocker: the `extraction` section's filter still contained `False` in its drop-tuple
  after round 34 corrected the identical one in the backstop — the **sixteenth**
  fix-the-instance-miss-the-sibling, and its casualty was round 34 H-3's own named
  example, `extraction.material_recognized: False`, hidden from the backstop by
  `take("extraction")` and swallowed by the filter. Aggravator: the golden suite had
  **enshrined the defect** — the synthetic fixture carried `material_recognized: false`
  and the captured expected file lacked it, so fixing the bug turned the golden suite
  red. Both latent siblings (`class_evidence`, `knowledge` extras) were fixed in the
  same pass, and the golden baseline re-captured with the diff read line by line (four
  intended changes, nothing else).
- REQ-081 A suite run must never touch a real run's artifacts. M-2: fixture commands set
  only `--out`, so `run_engine`'s sibling defaults resolved to the CURRENT directory and
  running the parity or golden suite from the kit root deleted `_report/bom_draft.md`
  and `_report/reply.md`. Undeclared siblings now default to `--out`'s own directory —
  proven with sentinel files surviving both suites.
- REQ-082 Ordering is behaviour and needs coverage. M-3: reversing `PRIORITY_ORDER`
  rendered MUST ACKNOWLEDGE above BLOCKING with every check green. A three-priority
  synthetic now asserts the order, and the golden synthetic fixture carries two
  recognized priority groups.
- REQ-083 `urgency.phrases` — a required schema key — was consumed by `take()` and never
  rendered (M-1), reaching the page only by coincidence. Now rendered, with every other
  non-flagged urgency key.
- Process note: the round-35 fix pass was completed under an intermittent sandbox
  classifier block on shell commands; the two latent-sibling checks were verified
  falsifiable by inspection (each mutation removes exactly the line its token lives on)
  rather than by an executed mutation run. Flagged here so round 36 re-verifies them.

### Round 36 (blind verification) — FAIL, and the first ship under the stopping rule

Twelve for twelve. Mutation survival 43/97 (44%, deliberately over-sampled and said so;
honest real-regression subset 19/97), CaseState fidelity 15/17 strict and **16/17
shipped-path**.

**The operator set the stopping rule after this round: ship when no finding would give a
customer a wrong answer.** v0.14.0 is the first release under it. Applying it per finding:

- REQ-084 **The seventeenth missed sibling.** `bom_columns` — a required, always-populated
  key — was marked consumed by `take()` and rendered only inside `_table(...)`, so on the
  `lines == []` branch (any `out_of_scope` message) its six column names appeared nowhere
  and the backstop could not see the key. Same mechanism as round 35's blocker, one screen
  away. NOT a wrong-answer finding — static config, absent only from a section that already
  reads "no lines" — but it falsified the design's stated sentence, so it was fixed and is
  now verified by `tools/completeness.py`.
- REQ-085 **The structural guard round 36's K-3 asked for.** `tools/completeness.py`
  asserts every non-empty CaseState key and every leaf value reaches the reply, over a
  pairwise cross-product of 14 axes (184 combinations, VIOLATIONS: 0). The golden suite
  compares BYTES and so froze the *absence* of a branch; this property check found the
  blocker in seconds. Its own first run reported six false positives (nested dict key
  names) — corrected by drawing the line at vocabulary vs content, documented in the file.
- REQ-086 **H-2 was the one wrong-answer finding, and round 35's own fix caused it.** The
  M-2 fix scoped clearing to `--out`'s directory, which stopped the suites deleting the
  kit root's `_report/` and thereby reintroduced R26-F1: with `--out` redirected, customer
  A's `reply.md` survived beside customer B's CaseState, so an operator could send A's
  draft answering B. Clearing now iterates the **ARTIFACTS declaration** across the union
  of `--out`'s and `--state`'s directories — both halves load-bearing, and the first cut of
  this fix lost the declaration half and broke R27-F4 (caught by the suite, not by
  inspection). Permanent coverage added; nothing had covered it before.
- REQ-087 **Four false `route` claims.** The recipe, README, EXAMPLES and CLAUDE.md all
  stated every open item carries a `route`; **23 of 24** in the parity fixtures do not, and
  EXAMPLES made it load-bearing for the conversation layer, which would `KeyError`.

### Round 36 backlog — CLOSED in v0.15.0, each mutation-proved

All four coverage gaps listed below are now closed. Each fix was mutation-tested by
execution, not by inspection:

- REQ-088 **The `UNCONFIRMED` enumeration is deleted.** Round 36 found 6 of its 10
  members deletable with the whole suite green, one live on a plain camlock email — a
  future edit could have quietly presented a value the engine refused to confirm. The
  set was CORRECT (exactly the schema enum minus `captured`); the problem was that a
  list can drift unnoticed. So there is no list: `is_unconfirmed()` returns true for
  anything that is not exactly `captured`, which means nothing to delete and a status
  the schema adds later is unconfirmed by default — the safe direction. Coverage is
  driven FROM the schema, so all eleven statuses plus an unheard-of one are checked
  without editing the test. **Mutation-proved:** shrinking it back to a two-member list
  fails NINE checks; the previous version caught it zero times.
- REQ-089 **A state-record write failure is loud.** Round 36: making `write_state`
  swallow `OSError` left `run_engine` exiting **0** with no state record, so a later
  phase would act on the previous run's record — the R26-F1 family via state rather than
  artifacts. **Mutation-proved:** the swallow now yields `exit=0` against an expected 1
  and fails the check.
- REQ-090 **No failure path leaves a 0-byte CaseState.** A zero-byte file is worse than
  absence: it parses as neither valid JSON nor as nothing, and both reconciliation guards
  read it before deciding. Three failure paths are now asserted to leave absence, not an
  empty file.
- REQ-091 **The falsy knowledge-extras variant is covered** — one layer below a check
  that already worked. **Mutation-proved:** reintroducing `False` in the drop-tuple fails
  two checks.

Coverage 110 → 129. Suites at closure: completeness 184/0, selftest 129/129, parity 7/7,
golden 2/2.

### Round 36's gaps as they stood at v0.14.0 (now closed — kept for the record)

Under the stopping rule these do not block: the shipped code is correct today and none
would give a customer a wrong answer. They are IOUs, not unknowns.

1. **6 of 10 `UNCONFIRMED` members are deletable with the suite green** — one live on a
   plain camlock email. The sharpest of these: a future edit could un-mark a field the
   engine refused to confirm, undetected. **Fix first next cycle.**
2. `write_state` swallowing `OSError` exits **0** with no state record.
3. An engine failure leaves a **0-byte** `case_state.json`.
4. The *falsy* knowledge-extras variant cannot fail (one layer below a check that can).

### Coworker alignment — CW-1..CW-3 SHIPPED in v0.16.0

Derived from the Coworker architecture document (Body / Compute / Memory / Factory),
assessed in `COWORKER_ALIGNMENT.md` on 2026-09-17. This kit is one Compute skill —
the document's Evolution 1. It contradicted none of the document's safety rules;
what it lacked was the contract surface Body needs. Three of the eight proposed
features are now in:

- REQ-092 **The reply NAMES every file the engine did not read (CW-1).** The engine
  has no attachment handling at all: `mail.py` reduces a MIME message to "Subject +
  best body part", and there is no `walk()`, no `Content-Disposition` inspection and
  no filename capture anywhere in it. So an RFQ whose dimensions are in the attached
  drawing produced a case that correctly reported them missing and said **nothing
  about the drawing** — a case that reads complete while the document the customer
  considered the answer was never opened. `scripts/attachments.py` names the parts;
  the reply carries an `EVIDENCE NOT READ` block and a headline that is rendered on
  EVERY reply, including "none", so absence of the block cannot mean both "none were
  sent" and "nobody looked". Nothing is opened, decoded or summarised, and no open
  item is added — `open_items[]` is the engine's. Inline parts with a Content-ID are
  named on a quieter line: a block that fires on every signature logo is a block
  reviewers learn to skip, and then the drawing goes unread too.
  **The proper fix is upstream:** an `ATTACHMENT_NOT_READ` open item in
  `ScaleUpLabs/McGill-Core`, beside `HTML_SOURCE_REVIEW` and
  `HIDDEN_CONTENT_DETECTED`, which already exist for "I saw something I could not
  safely read". This is the kit-side interim. **Mutation-proved:** deleting the
  block, the headline, or the inline naming each fails 1–2 checks.
- REQ-093 **The scan happens ONLY on the reconciled path.** `--state` defaults to
  `_report/state.json`, so rendering a CaseState in isolation would otherwise scan
  whatever email an unrelated run left recorded there and print customer A's drawing
  on customer B's reply. Reconciliation is exactly the proof that the recorded
  invocation reproduces THIS CaseState, so it is the only ground on which its input
  may be read; without it the reply says NOT CHECKED. **Mutation-proved:** moving the
  scan outside the branch fails 2 checks, one of them by naming A's file on B's page.
- REQ-094 **Every run writes `_report/run_manifest.json` (CW-2).** Kit name and
  version, the engine's source commit read from `vendor/PROVENANCE.md`, the input's
  sha256 and byte count, the whole invocation, an `idempotency_key`, the CaseState's
  path and schema version, `engine_exit`, the outcome, the open-item counts and
  `evidence_not_read`. `case_state.json` is NOT touched: new information about a run
  goes in a new artifact, never by forking the engine's contract. The key hashes the
  input's CONTENT plus the flags and deliberately not its path, so the same email
  saved under a second name is recognised as the same case. `KIT_VERSION` is a second
  copy of `kit.json`'s version (kit.json cannot ship inside the zip — it carries that
  zip's own sha256), kept honest by a selftest assertion; it caught a stale value on
  its first run. **Mutation-proved:** an unwritten manifest fails 13 checks, a broken
  PROVENANCE regex 2, a path-sensitive key 1.
- REQ-095 **The outcome is stated in words and DERIVED (CW-3).** `engine_exit` cannot
  serve: 2 means "a draft with open items", the normal result for essentially every
  real RFQ, and every document here spends a bullet warning against reading it as
  failure. `run_state.derive_outcome` returns `needs_human_input` when anything blocks
  a quote and `complete` otherwise, computed from `open_items[]` rather than set
  alongside it. `complete` does NOT mean sendable — every case is a draft a human
  reviews. **Failure is deliberately not in the vocabulary:** a failed run writes no
  manifest and the wrapper exits 1, so absence is the failure signal and cannot be
  faked by a half-written record. **Mutation-proved:** hard-coding either value fails
  2 checks.
- REQ-096 **A redirected `--out` leaves no previous customer's CaseState behind.**
  Found while adding the manifest to the invalidation loop, and the EIGHTEENTH
  instance of this campaign's missed-sibling shape — this time on the one key that had
  been exempted BY NAME (`if _name == "case_state": continue`, justified as "--out
  names it explicitly"). With `--out` redirected, customer A's case survived at the
  conventional `_report/case_state.json` while B's was written elsewhere, so a
  consumer reading the default path got A's case back after B's run. Not reachable on
  the recipe path, which never redirects `--out`; reachable by the suites and by any
  Body integration using per-case directories. Verified by execution before the fix.
  **Mutation-proved:** restoring the exemption fails the check.

- REQ-097 **An unread attachment forces `needs_human_input` (v0.17.0).** The operator's
  decision on the question v0.16.0 left open. v0.16.0 derived the outcome from
  `open_items[]` alone, so an RFQ saying "dimensions are on the attached drawing"
  reported `complete`: the engine's asks were all `confirm`, and the drawing was
  invisible to it. A reviewer routing on `complete` would skim a case whose actual
  specification was never opened. The engine cannot raise an open item about a file it
  cannot see, so the outcome has to carry it. Still DERIVED — now from two facts the
  run produced rather than one, never asserted alongside them. An inline part with a
  Content-ID (a signature logo) does NOT force it: routing every footer image to a
  human is how a signal becomes noise, and then the drawing goes unnoticed too. A scan
  that did not complete forces it as well — "we could not tell" is not "they did not".
  **Mutation-proved:** ignoring unread attachments fails 2 checks, counting inline parts
  as unread fails 1, treating an unreadable scan as none fails 1, a reason that counts
  files without naming them fails 1, and not passing the evidence into the derivation
  fails 2.

- REQ-098 **The reviewer gets their own document, and it EMBEDS the response (CW-4,
  v0.18.0).** The Coworker document splits one message in two: Outside Sales receives
  the guidance, Inside Sales receives a review request with the summary, the
  uncertainty and the proposed response, and decides. Until now the kit emitted one
  document trying to be both — `reply.md` is written for the person who receives the
  answer, and a reviewer had to infer the decision from it.
  `scripts/render_review.py` writes `_report/review_request.md`: the decision, the
  outcome and its grounds (blocking items, unread attachments, and every field the
  engine refused to commit to), who it routes to, and the proposed response **embedded
  verbatim**. Embedding rather than re-describing is what makes the split safe: the
  reviewer approves the exact bytes that would be sent, and the two documents cannot
  drift, because one contains the other. Two guards fail closed — the CaseState is
  re-derived, and `reply.md` must equal what `render_reply.render` produces for this
  case *right now*, compared through the renderer itself rather than as prose.
  **Mutation-proved:** summarising instead of embedding fails 1 check, removing the
  stale-reply guard fails 2, and each of the four uncertainty branches fails its own.
- REQ-099 **Owners are resolved, never invented (CW-5, v0.18.0).**
  `config/routing.json` maps the three `routing.recommendation` values, the four
  `open_items[].route` values and the three `checkpoints[].owner` strings the engine
  writes to an addressee. A key with no entry, or an entry with no address, renders
  NOT ROUTABLE and names the key — it does **not** fall back to inside sales. A wrong
  assignee is worse than a visible gap: the case lands with someone who ignores it and
  nobody learns it was misrouted. The two failures stay distinguishable: `unmapped`
  means the ENGINE grew a role the table has never heard of, `unconfigured` means a
  deployment TODO. **The table ships with every address empty on purpose** — inventing
  a Teams group id would be the fabrication this kit exists to prevent. A selftest
  check derives the required keys from the schema enums and from `core.py` itself, so
  a new engine role fails the suite rather than appearing as `unmapped` in production.
  **Mutation-proved:** a fallback to inside sales fails 1, reporting unconfigured as
  routable fails 2, an unreadable table resolving like an empty one fails 1, dropping
  checkpoint owners fails 2.
- **One guard is documented as defence-in-depth rather than claimed as covered.**
  `render_review.py`'s CaseState reconciliation cannot be isolated by a test: for
  content divergence the reply guard refuses the same pairs, and a reply forged to
  match a tampered case cannot carry a scanned attachment record because REQ-093 only
  lets a reconciled render scan the input. Two attempts to write a check for it both
  ended up exercising the reply guard instead. Its observable half — that an
  unreconciled render says the attachments are UNKNOWN — IS asserted. The docstring
  says all of this, rather than implying a coverage the suite does not have.

- REQ-100 **An out-of-thread answer enters as TEXT, never as a value (CW-6, v0.19.0).**
  A reviewer answering "it's 316 stainless" in Teams produces text the email thread
  never sees, so the next run re-asks a question a human already answered.
  `scripts/apply_answers.py` appends the answer to the case TEXT as an operator
  addendum and re-points the invocation at it; the engine reads it as a later message
  in the thread, through the `supersedes` machinery that already carries 529 tests. No
  resolution path was added, because a second way for a value to enter a case is a
  second way to be wrong — and if the engine does not accept an answer, the ask stays
  open, which is the correct outcome. **Mutation-proved:** accepting an author-less
  answer fails 2 checks, allowing a forged marker fails 2.
- REQ-101 **An operator's words are never presented as the customer's.** This is the
  risk CW-6 creates and the reason it needed its own scrutiny. Three things hold the
  line: everything after the FIRST occurrence of the addendum marker is
  operator-supplied by definition rather than by parsing; the reply and review request
  print the addendum verbatim under a banner saying whose words it is, and the reply's
  section heading stops reading "WHAT THE EMAIL SAID"; and every field is classified
  by locating its evidence span in each region — `OPERATOR-STATED` only when the span
  is absent from the customer's text, `SOURCE UNCLEAR` when it is in both, and neither
  when it cannot be located at all.
  Two normalisations and only two: whitespace and CASE. The engine lowercases evidence
  spans, so a case-sensitive test found `male npt` in neither region and marked a
  field the customer plainly wrote as though its authorship were in doubt. Both folds
  apply to both sides, so neither can move a span from one author to the other.
  Span-less fields — most of them — are named once in the banner instead of marked in
  the table: the first cut marked seven of ten rows `SOURCE UNCLEAR` and buried the
  one field an operator really did supply. **Mutation-proved:** deleting the banner
  fails 2, unmarking operator fields fails 1, attributing everything to the customer
  fails 1, restoring the old heading fails 1.
- REQ-102 **The addendum is refused when it cannot be kept honest.** Written back out
  flat, an extracted text that STARTS with header lines re-parses as MIME and the
  engine would read something other than what the operator approved. That is not
  hypothetical: an `.eml` with an empty Subject whose body opens with
  `From:`/`To:`/`Subject:` is the outside-sales forward, and it is the fixture. Rather
  than reasoning about when it happens, `apply_answers.py` reads its own output back
  through the engine's reader and refuses on any difference, naming the fallback
  (paste the answer into the thread) that always works. **Mutation-proved:** the guard
  survived the first mutation run because no fixture tripped it — the fixture above
  was built for it, and the guard now fails 2 checks when removed.
- REQ-103 **A correction must pin to a run to be worth anything (CW-7, v0.19.0).**
  `schemas/correction.schema.json` is the shape Body fills in when a reviewer edits a
  proposal: the original and corrected text, the reason, the reviewer, and
  `correction_of` — the idempotency key, kit version, engine commit and input hash of
  the run being corrected. `tools/correction_check.py` refuses a correction whose pin
  does not match a real run manifest, or whose `original` is not byte-for-byte what
  that run produced. Without the second check a correction can claim the kit said
  something it never said, and the test built from it would enshrine a defect that
  never existed — the same shape as the parity fixture that had enshrined the
  size/length bug. This is the direct answer to *"reviewed corrections may become test
  cases, but never alter production behaviour automatically."* **Mutation-proved:**
  each of the four refusals fails its own check.
- **The schema is deliberately written inside the kit's own validator subset.**
  `tools/_schema_engine.py` supports neither union types (`["string", "null"]`) nor a
  general `oneOf` — its `oneOf` is a hard-coded `source` discriminator for the kit
  manifest and rejects any non-object instance. Both were found by trying. So
  `correction.schema.json` uses `pattern` and the empty string where null would be
  natural, and IS machine-checkable by the kit, which `case_state.schema.json` is not
  (FOLLOW-UP-10). Worth knowing before a fourth schema is written.

- REQ-104 **Every knowledge lookup states how old the fact is (CW-8, v0.20.0).** The
  last of the eight, and the only one that could not be built in the kit:
  `knowledge.py` is vendored, and editing `src/vendor/` to change behaviour is the one
  thing this project never does. So it was built UPSTREAM in `ScaleUpLabs/McGill-Core`
  (`6b0a897`, 10 new tests, 529 -> 539) and re-vendored.
  Each lookup now carries `freshness`: `as_of:<v>` when the source stated when the
  fact was true, `revision:<v>` when only the snapshot is pinned, and `unknown`
  otherwise — **default-deny, exactly as the tier is**. A fact whose age nobody stated
  is not fresh; it is unknown. `find_candidates` claims an age only when every returned
  fact agrees on one, because reporting the newest would make a batch look fresher than
  its oldest member, which is how a stale rating reaches a proposal.
  **Deliberately no wall clock.** Recording when we asked would make the engine's
  output non-deterministic and break byte parity for every consumer that pins it, and
  it answers a different question than how old the fact is. An upstream test asserts
  two runs of one snapshot produce identical lookups.
  **The kit's parity stayed 7/7 byte-identical through the re-vendor**, which is the
  proof that this kit's output is unaffected: the shipped default is `NullKnowledge`,
  which performs no lookups, so the contract ships DORMANT (FOLLOW-UP-1). The kit's
  checks therefore exercise the vendored module directly — the alternative is shipping
  a promise nothing verifies until the graph is wired.
  **Mutation-proved,** both upstream (5, all caught) and kit-side (4, all caught).
- **A mutation run reported a defence as uncovered when the suite had CRASHED on it.**
  The kit-side freshness checks read `entry["freshness"]`, so deleting the key raised
  KeyError, aborted `selftest.py` and took every later check with it — and the harness,
  which counts FAIL lines, saw none. Now `.get(...)`, returning "" the way
  `case_and_draft_agree` returns False. Worth remembering when reading any mutation
  result: no FAIL lines can mean the check is vacuous OR that the suite never got
  there.

### v0.24.0 — phase 5: the reviewer gets the customer's files

- REQ-114 **`run_manifest.deliver` declares what rides with which message.** The
  operator's decision: the reviewer's message carries the customer's source files
  so a transcript can be checked against its original; the customer's reply carries
  nothing, unchanged. Each declared file is identified by filename AND sha256 so
  Body attaches the right bytes, and carries a reason that distinguishes "the
  transcript was read from this" from "nobody read it". `embedded` parts are
  excluded — a signature logo is not evidence, and the instruction was *only
  relevant attachments*.
- REQ-115 **Why this is not an `email_attachment` tag, recorded because the
  contract cannot express it.** The kit manifest has that tag on
  `outputs.artifacts[]`, and three things make it unusable here: at most ONE
  artifact per kit may carry it, it attaches to the REPLY rather than the review,
  and it can only name an artifact the KIT produced — never the customer's own PDF,
  which is a MIME part inside their message and not a file the kit ever writes. So
  the intent is declared in the run record instead, `implemented_by: "body"` is
  stated in the block itself, and the review request tells the reviewer to ask for
  the files if they did not arrive. **A declaration nothing acts on yet is honest
  only if it says so.** The bar's "zero `email_attachment` tags" invariant is
  therefore unchanged and still true.
  **Mutation-proved:** 6 mutations, 6 caught — after one survived because the check
  matched the filename in an `UNREAD` ground eight lines above the section it named.
  That is the third coincidence-match found by mutation today, and the third the
  author did not see by reading.

### v0.23.0 — phase 2: the transcript goes where it is useful

- REQ-112 **`reply.md` names the transcribed file; `review_request.md` carries the
  text.** Job `af54e714` produced a 9,004-byte reply whose first two hundred lines
  were a purchase order's transcript — addresses, fax numbers, account numbers, unit
  prices — with the questions underneath. The executing agent ignored the artifact
  and hand-wrote its own email, breaking the kit's own instruction to send this file
  unsummarised. **When the deliverable is unusable, the rule protecting it gets
  broken**, and that is a design failure rather than an operator one. The same reply
  is now 4,533 bytes.
  Nothing is summarised: a summary of a transcript is a model's answer wearing a
  transcript's clothes. Only its LOCATION changed, and both halves are asserted —
  the reply must NOT repeat it, the review request MUST carry it verbatim.
- REQ-113 **The reviewer's grounds are grounds, not a document dump.** The same
  fault existed one level up: `_uncertainty` emitted one `MACHINE` line per
  transcribed line, putting eighty rows of a purchase order between a reviewer and
  the decision. The ground is now one line per file (name, method, line count) and
  the transcript is its own section.
  **Mutation-proved:** 4 mutations, 4 caught — dumping the transcript back into the
  reply, dropping the file/method naming, removing the review request's section, and
  reverting the ground to per-line output.

### v0.22.0 — phase 1: a document describing many products is not one request

- REQ-111 **The kit no longer presents a merged specification as a finding.** Job
  `af54e714` (2026-09-18): a twenty-line purchase order became a single
  `hose_assembly` whose `size` and `pressure` came off the HOSE line, whose `length`
  came off a `BARB FITTING, 1" MNPT` — **a thread size** — and whose ends came off
  the fittings. `class_evidence` was the single word `hose`. The kit then asked the
  customer to confirm the quantity and length convention of that assembly, for an
  order whose every line already carried a part number, a quantity and a price.
  **The specification it described exists in no document.** Thirty-seven rounds
  never caught it because every fixture is one request per text.
  `scripts/lineitems.py` reads STRUCTURE, never content — it extracts no value and
  touches no field — and reports two measured observations: priced line-item rows
  (PO 7, every fixture 0) and distinct dimensions (fixtures 1-2, a legitimate
  hose-plus-reducer 3, the PO and a prose list of three hoses 5). Either firing
  raises a banner in both documents and a fourth `needs_human_input` ground.
  **Both thresholds were measured, not chosen.** `ROW_MIN` is 3 because a SUBTOTAL
  line matches the item pattern, so a one-item reorder scores 2 once its total is
  counted; firing at 2 would flag a single-item PO. `DIM_MIN` is 5 because a
  hose-plus-reducer honestly names 3.
  **Two gaps stated rather than hidden:** a genuine two-item order scores 2 rows and
  is not flagged, and a prose multi-item request with few dimensions is missed by
  both observations. This does not fix the merge — that is phase 4, per-line-item
  extraction, upstream.
  **A rejected design, recorded because measuring refuted it:** the first candidate
  measured how far apart in the text the engine's evidence spans were, on the theory
  that a merged spec is assembled from distant places. It does not separate — the PO
  spans 6 of 12 lines and the fixtures 4-5 of 8-9. The second candidate's dimension
  regex used `\bin\b`, which never matches `36in` because there is no word boundary
  between a digit and a letter; it scored 0 on every fixture and looked like a clean
  separation. Both were caught by measurement, not review.
  **Mutation-proved:** 9 mutations, 9 caught — including a threshold that nothing
  guarded until the single-line-reorder check existed.

### v0.21.0 — the production failure of 2026-09-17, and CW-9

A customer sent a purchase order as a PDF. The kit replied `out_of_scope` — "No
product request recognized". Four defects, three of them introduced the same day:

- REQ-105 **The recipe forced an agent to FABRICATE a kit artifact.** `apply_answers`
  is optional, but its declared outputs included `_report/augmented_input.txt`, and
  the harness validates declared outputs — so the phase could never be skipped. With
  no out-of-thread answers the agent satisfied `CompletePhase` by hand-writing
  `echo "[no operator addendum...]" > _report/augmented_input.txt`. That file is the
  case text the engine reads, and CLAUDE.md forbids hand-writing artifacts in as many
  words. A phase that cannot be skipped is not optional, whatever its goal says. Only
  `state.json` is declared now.
- REQ-106 **The slow-input warning measured the file, not the text.** "input is 162 KB"
  on a message whose body was 39 bytes — the .eml carried a 118 KB base64 PDF the
  engine never reads. `elapsed_ms` was 13. It now measures the extracted text, which
  is what runtime scales with.
- REQ-107 **A classification was presented as a finding about a request nobody read.**
  The engine captured no fields from 39 bytes of body placeholder and classified
  `out_of_scope`; the reply led with it. To a reviewer that reads as *we looked and
  there is nothing here* while 118 KB of purchase order sat unopened. The reply now
  states the body size on every case, and raises a NOT ASSESSED banner when no field
  was captured and something went unread. Derived; silent on an ordinary case.
- REQ-108 **Augmenting the case text lost the attachment report — a live defect in
  v0.19.0.** CW-6 re-points the invocation at a generated `.txt`, and the attachment
  scan followed it, so a message carrying an unread drawing reported
  `Attachments: none in the source email` once an operator answer was applied. The
  attachment did not stop existing because a reviewer answered a question.
  `run_state.source_input()` now resolves the file the CUSTOMER sent.

- REQ-109 **CW-9: a machine may TRANSCRIBE an attachment; it may not answer.** The
  engine reads no file, and the capability to read one exists a layer above the kit —
  the runtime has a vision-capable host model. So the agent transcribes, and
  `scripts/apply_transcript.py` folds the transcript into the case text as a THIRD
  region. The model never extracts, classifies, answers or maps to fields; the engine
  does all of it, and on the operator's test case the kit went from `out_of_scope`
  with no fields to `order` with a drafted BOM line.
  Guards: the file must be one the scanner found in this message (its sha256 is
  recorded), no marker forgery, the round-trip guard, and a named METHOD — the kit
  cannot verify a transcript is faithful and cannot verify the method either, but
  "parsed a CSV" and "looked at a picture of a table" are different claims.
- REQ-110 **"Proposal only" is enforced everywhere except the CaseState, and that is
  documented rather than glossed.** `tier` is a knowledge-layer concept;
  `fields{}` carries a status and no provenance, so a transcribed value reads as
  `captured` in `case_state.json`. Forking the engine's contract is the one thing this
  kit never does, so the provenance is a manifest overlay — `transcripts[]` and
  `transcribed_fields[]` — plus marks in both human documents, an outcome that always
  demands a human, and a flag on any BOM LINE drawn from transcribed text, which is the
  sharpest hazard: a transposed part number that happens to match the catalog becomes a
  real line. **A consumer reading only the CaseState cannot tell a transcribed value
  from a typed one.** Closing that is upstream work.
- **Two more of the author's own checks could not fail**, both caught by mutation:
  a transcript-refusal check that passed when the guard was deleted because the next
  line raised `KeyError` and the clamp turned it into the same exit code — a refusal
  must be a DECISION, so the check now also requires the error not to be an unhandled
  exception; and the `0 bytes` body line on an unreconciled render, which stated as
  fact something it had not looked at.

Suites at closure: completeness 184/0, selftest **251/251**, parity 7/7, golden 2/2
(re-captured, diff read: one line added per fixture),
manifest valid. Mutation runs across CW-1..CW-8: **50 attempted, 49 caught**, and the
one survivor (M19) is the defence-in-depth guard above, proven non-observable and
documented as such rather than papered over with a check that passes for the wrong
reason. Two of the campaign's own checks were caught by these runs and rewritten: a
filename test that matched the outcome line four rows above the section it meant to
assert, and a tampered-CaseState test that the reply guard was satisfying.

The remaining five features (CW-4 review-request artifact, CW-5 resolvable owners,
CW-6 out-of-band answers, CW-7 correction record, CW-8 knowledge freshness) are
specified in `COWORKER_ALIGNMENT.md` and NOT built. CW-6 is flagged there as the one
most likely to fail a verification round and should get one of its own.

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

### Published state — read the record, do not trust a carried-forward claim

**v0.20.0 is live** (2026-09-17T22:54Z, sha `852edc2f67a008cd`), published on the
operator's instruction without round 37. The instance holds four versions: 0.20.0,
0.14.0 (2026-08-27), 0.3.0 and 0.2.0.

That read-back corrected a claim this document and `CAMPAIGN_RUNBOOK.md` had both
been repeating all day: **the instance was never serving v0.3.0**. v0.14.0 had been
the latest since 2026-08-27. The line had been carried forward from the v0.6.0
rollback and nobody re-read the record for three weeks — the same failure shape as
a check that cannot fail, applied to a fact instead of a test. `GET
/api/kit-packages/mcgill-email-to-bom` requires a bearer token, which is why it was
easy not to look; authenticate from the environment the way the publisher does.

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
  FOUR engine passes as of v0.10.0 (one extract, two in generate_report, one in
  render_reply's reconciliation), so the end-to-end cost is ~4x the single-pass
  figures (round 26 R26-F7; recount at round 33 pre-flight).
