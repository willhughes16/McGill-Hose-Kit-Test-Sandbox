# email-to-bom

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
- REQ-013 The recipe `src/recipes/email-to-bom.yaml` parses as YAML and its phase
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
- **FOLLOW-UP-6 — fixture corpus is thin and partly synthetic.** Six fixtures, five
  distinct inputs, all from the source's own examples/tests. The identity lines of
  the `suction-assembly` family were anonymised (technical content unchanged) before
  capture. Real RFQ `.eml` files from McGill would make parity claims much stronger;
  they have been requested.
- **FOLLOW-UP-7 — the source's 507-test suite does not run here.** Parity covers the
  six fixtures, not the full suite. The tests live in the source repo and are not
  vendored. A regression in a path no fixture touches would not be caught by this
  kit alone.
- `src/vendor/config/catalog_candidates.json` ships but is never loaded by the
  engine (the source documents this). Harmless dead weight kept for verbatim
  fidelity.
