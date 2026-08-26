# CRITERIA — Phase 05 Input Filter (pre-registered, plan-blind)

Written before any plan exists. Derived from the phase goal, `.astrocode/PROJECT.md`
(Phase 5 section + REQ-001..REQ-036), `.astrocode/CONVENTIONS.md` and
`KIT-CONTRACT.md`. No `PLAN.md` / `ACCEPTANCE.md` / `SPEC.md` was read.

Conventions used below: `$KIT` = `/Users/axr/Desktop/McGill/mcgill-email-to-bom`.
Every criterion is behavioural — a different-but-valid implementation of the same
goal (different module names, different gate placement, different code vocabulary)
must still satisfy all of them. Where a criterion needs the kit's own entry point,
the verifier discovers the non-interactive command from the shipped docs
(`src/CLAUDE.md`, `src/README.md`, `src/EXAMPLES.md`, `src/recipes/mcgill-email-to-bom.yaml`)
rather than assuming a file name.

Fixture inputs for the six non-RFQ categories are constructed by the verifier so the
bar does not depend on the implementation shipping its own samples. Write them into a
scratch dir (RFC 2606 `.example` domains only, per REQ-028):

```
mkdir -p /tmp/f05 && cd /tmp/f05
cat > autoreply.eml <<'E'
From: buyer@customer.example
To: sales@mcgill.example
Subject: Out of Office: RE: hose quote
Auto-Submitted: auto-replied
Content-Type: text/plain; charset=utf-8

I am out of the office until Monday with no access to email. For urgent
matters contact my colleague.
E
cat > dsn.eml <<'E'
From: MAILER-DAEMON@mail.customer.example
To: sales@mcgill.example
Subject: Undelivered Mail Returned to Sender
Content-Type: multipart/report; report-type=delivery-status; boundary=b1

--b1
Content-Type: text/plain; charset=utf-8

This is the mail system at host mail.customer.example. Your message could not
be delivered to one or more recipients.
--b1
Content-Type: message/delivery-status

Reporting-MTA: dns; mail.customer.example

Final-Recipient: rfc822; buyer@customer.example
Action: failed
Status: 5.1.1
--b1--
E
cat > newsletter.eml <<'E'
From: news@hosesupplier.example
To: sales@mcgill.example
Subject: Spring Specials: 20% off industrial hose reels
List-Unsubscribe: <mailto:unsubscribe@hosesupplier.example>
List-Id: <specials.hosesupplier.example>
Precedence: bulk
Content-Type: text/plain; charset=utf-8

Our spring catalogue is out. Save 20% on hose reels, EPDM suction hose and
stainless fittings all month. Click through for the full flyer.
Unsubscribe at any time.
E
cat > ack.eml <<'E'
From: buyer@customer.example
To: sales@mcgill.example
Subject: RE: your quote
Content-Type: text/plain; charset=utf-8

Thanks, got it.
E
cat > invoice.eml <<'E'
From: ar@customer.example
To: ap@mcgill.example
Subject: Invoice 10482 / statement of account
Content-Type: text/plain; charset=utf-8

Please find invoice 10482 attached. Amount due 1,842.55 USD, terms net 30.
Statement of account for July is included. Remit to the address on the invoice.
E
cat > internal.eml <<'E'
From: dave@mcgill.example
To: sandra@mcgill.example
Subject: counter cover at lunch
Content-Type: text/plain; charset=utf-8

Can you cover the counter from 12 to 1 today? I have a dentist appointment.
Also the coffee machine is broken again.
E
```

---

### C1 — A non-RFQ message ends the run with no BOM draft and no CaseState, and never beside a stale one
- **Observe:** For each of `autoreply.eml dsn.eml newsletter.eml ack.eml invoice.eml internal.eml`,
  run the kit's documented flow in a fresh working directory with that file as the
  input. After each run, list the run's output directory (`_report/`) and assert that
  no CaseState artifact and no human BOM draft exist (per `run_state.ARTIFACTS` the
  categories are `case_state` and `bom_draft`; assert by path AND by content — no file
  under `_report/` validates against `src/schemas/case_state.schema.json` and none
  contains a BOM table). Then the stale-artifact case: in ONE directory, first run a
  real RFQ (`$KIT/tools/parity/fixtures/plain-steam/input.eml`) to completion so both
  artifacts exist, then run `newsletter.eml` in that same directory; assert both
  previous artifacts are gone afterwards.
- **Fails if:** any of the six produces a CaseState or a draft (the operator still has
  to read a draft to learn there was no request); or the newsletter run leaves the
  previous RFQ's `case_state.json`/`bom_draft.md` in place, so a filtered run is
  indistinguishable from the last real one (the R26-F1 category, re-created).

### C2 — Every filtered message carries a machine-readable reason code and route, and filtering is distinguishable from both success and failure
- **Observe:** Re-run the six messages capturing exit status, stdout/stderr and the
  run's machine-readable state (`_report/state.json` or whatever record the docs name).
  Assert for each: (a) a reason code that is a stable machine token (not free prose,
  non-empty), (b) a route value drawn from a closed vocabulary the kit declares in its
  shipped schemas/reference data, and (c) the six runs do not all collapse to a single
  code — at least four distinct codes across the six categories, and the same message
  re-run twice yields the identical code and route (determinism). Also assert the
  filtered exit status is a fixed documented value that differs from the status of a
  successful drafting run (C4) AND from the status of a genuine kit failure (run with a
  nonexistent input path) — three distinguishable outcomes.
- **Fails if:** the decision is only human-readable text; or route/code values are not
  in a declared vocabulary (so a consumer cannot switch on them); or every category
  reports one generic code; or the filtered run exits with the same code as a drafted
  run or as a hard error, so automation cannot tell "nothing to quote" from "the kit
  broke". A filtered run that exits with the engine's `2` fails outright (REQ-007).

### C3 — The decision happens before the engine runs, not after
- **Observe:** Copy the kit to a scratch tree (`cp -R $KIT /tmp/f05/kit-sentinel`) and
  neutralise the vendored engine there by appending a shadowing entry point to
  `/tmp/f05/kit-sentinel/src/vendor/email_to_bom/cli.py`:
  `def main(argv=None):\n    raise SystemExit("SENTINEL-ENGINE-INVOKED")`.
  In that tree: (1) run a real RFQ and confirm the sentinel fires (proving it is live);
  (2) run each of the six non-RFQ messages and confirm each still completes with its
  normal filtered decision and no sentinel trace on stdout/stderr. Corroborate with
  cost: build a ~1 MB newsletter (`python3 - <<'E'` repeating the newsletter body) and
  time the filtered run — it must finish in a couple of seconds, far below the engine's
  superlinear cost at that size (FOLLOW-UP-9: ~80 s at 538 KB, x3 passes).
- **Fails if:** the sentinel fires on any non-RFQ message (the engine was invoked and
  its draft merely suppressed afterwards), or the 1 MB newsletter run takes engine-scale
  time. Deciding after the fact burns minutes per newsletter and means the "no draft"
  guarantee depends on cleanup rather than on not running.

### C4 — A real RFQ still reaches the engine and the output is byte-identical to the source capture
- **Observe:** `cd $KIT && python3 tools/parity_check.py --manifest tools/parity/parity.json`
  exits 0 with all 7 fixtures passing. Additionally, drive the FULL documented flow
  (filter gate included) on each distinct fixture input — `suction-assembly`,
  `plain-steam`, `quoted-printable`, `multipart-html`, and `confirmed-ids` with the
  four Component IDs `parity.json` declares — and for each `cmp` the produced
  `_report/case_state.json` against `tools/parity/fixtures/<case>/expected_output.json`:
  byte-identical, zero diff. Assert `sha256sum` of every input `.eml` is unchanged
  before/after the run, and `git -C $KIT diff --stat -- src/vendor src/schemas` is empty.
- **Fails if:** any fixture is filtered out, or the gated path yields a CaseState that
  differs from the source-captured bytes by even one byte (the filter normalised,
  re-encoded, trimmed headers or rewrote the temp copy it handed the engine), or an
  input file's bytes changed, or `src/vendor/` was edited. This is the constraint the
  goal states as absolute: the filter decides WHETHER, never WHAT the engine sees.

### C5 — Ambiguity and unparseable input fail toward invoking the engine
- **Observe:** Build adversarial mixed cases in `/tmp/f05` and run each through the
  documented flow; every one must produce a CaseState (and a draft, per the normal
  path):
  1. `bait-rfq.eml` — the real `plain-steam` RFQ body, with `List-Unsubscribe`,
     `Precedence: bulk` and an `Auto-Submitted: auto-replied` header bolted on and
     subject prefixed `Out of Office: RE:`.
  2. `ack-plus-rfq.eml` — body begins `Thanks, got it.` then continues with the
     `plain-steam` request text.
  3. `invoice-plus-rfq.eml` — subject `Invoice 10482 / statement`, body carries a
     statement paragraph AND a genuine request for a quote on a 4in EPDM suction hose.
  4. `broken-mime.eml` — the `multipart-html` fixture with its MIME boundary corrupted
     and a bogus `Content-Transfer-Encoding: x-nonsense`, so the filter's own parse of
     the message cannot succeed.
  5. `empty.eml` — zero bytes.
  For 1–4 assert a CaseState was produced. For 5 assert the outcome is either a
  CaseState or a LOUD non-zero kit error — never a quiet "filtered, nothing to do".
- **Fails if:** any of 1–4 is filtered out (a real RFQ suppressed because it carried a
  bulk header, a polite opener or a broken boundary — the failure the goal calls "far
  worse"), or the filter's own parse error is treated as grounds to filter, or the
  zero-byte input is silently reported as filtered with a success-looking status.

### C6 — A filtered message is never lost: an operator can still get a draft for it without editing code or the message
- **Observe:** From the shipped docs (`src/EXAMPLES.md` Argument Reference,
  `src/README.md`, `src/CLAUDE.md`, the recipe) identify the documented way to process a
  message the filter would reject, and exercise it verbatim on `newsletter.eml` and on
  `ack.eml`: each must produce a CaseState and draft, with the input file's sha256
  unchanged and no edit to any file under `$KIT/src`. Also confirm the filtered run's
  record identifies the message it filtered well enough to re-run it (the input path it
  was given is present in the machine-readable record).
- **Fails if:** no documented mechanism exists, or the documented command does not run
  as written (the REQ-027 failure shape), or the only way past the filter is editing kit
  source or the message; or the filtered record does not say which message was filtered,
  so a false positive cannot be found or replayed.

### C7 — The filter's defences are covered by the self-test, and the coverage is mutation-proved
- **Observe:** `cd $KIT && python3 tools/selftest.py` exits 0, and
  `python3 tools/parity_check.py --manifest tools/parity/parity.json` exits 0. Then
  mutate the filter decision in non-vendored `src/` (locate it by reading; do not touch
  `src/vendor/`) twice, restoring with `git checkout --` between: (a) force it to always
  pass through, (b) force it to always filter. After EACH mutation `python3 tools/selftest.py`
  must exit non-zero. Record which named checks fail. Confirm `git status --porcelain`
  is clean afterwards.
- **Fails if:** selftest stays green under either mutation — parity compares outputs and
  cannot see a decision not to run (REQ-033 / R26-F4), so a filter whose selftest
  survives always-pass or always-filter has checks that cannot fail; or the mutations
  break parity instead of selftest (the gate is entangled with what the engine sees,
  which C4 already forbids).

### C8 — The filtered and drafting paths both run from the built kit with zero dependencies
- **Observe:** `cd $KIT && python3 tools/validate_manifest.py kit.json` exits 0 and
  `./tools/build_kit.sh` succeeds. Unzip `dist/kit.zip` into an empty temp dir, and with
  NO install step run, using `python3 -S -E` (no site-packages, no `PYTHON*` env):
  (a) `newsletter.eml` → filtered decision as in C2, (b) `plain-steam/input.eml` →
  CaseState byte-identical to its `expected_output.json`. Both must behave exactly as in
  the repo tree.
- **Fails if:** either path needs a package outside the stdlib (`-S -E` makes a
  third-party import fail), needs an install/resolution step, reads an environment
  variable to decide, or the manifest now declares a tool that must be installed first
  (REQ-009, REQ-016; `requires.tools` must stay empty).
