# VERIFICATION — ROUND 27 (blind independent verifier)

Artifact: `/Users/axr/Desktop/McGill/mcgill-email-to-bom` @ `fdfbb48` (tree clean at start
and at end; only `?? ACCEPTANCE_ROUND27.md` untracked).
Source of truth: `/Users/axr/Desktop/McGill/email-to-bom-agent` @ `b15b23d` (clean, read-only
throughout).
Bar: `ACCEPTANCE_ROUND27.md` — Part A `X-1..X-5`, Part B `X-6..X-11`, pre-registered.
`VERIFICATION_ROUND25.md` and `VERIFICATION_ROUND26.md` were read. The build conversation was
not available and was not sought.

**OVERALL VERDICT: FAIL.**

The input-filter gate drops real customer RFQs. Not in a contrived corner — in the single most
ordinary shape a purchasing email takes. I built 35 genuine quoting requests; **24 of them were
filtered**, and for **13** I proved with the shipped `run_engine.py` that the engine would have
classified them `hose_assembly` / `bulk_hose` and produced a draft with open items. The trigger
in the worst case is one line of procurement boilerplate:

```
Terms net 30.
```

Adding that line to an RFQ the gate otherwise passes flips it to `INVOICE_OR_STATEMENT`,
route `accounts_payable`, exit 3 — no CaseState, no draft, and the recipe instructs the agent
to tell the requester there was nothing to quote. This is live in published v0.4.0
(reproduced from the unzipped `dist/kit.zip` under `python3 -S -E`).

The cause is this project's oldest failure class, landing on the one mechanism that can make
work disappear: the **quoting-request veto**, the gate's sole protection for a real RFQ wearing
junk signals, requires a hit in a **16-phrase closed list**. Eight of thirteen ordinary RFQ
closing phrasings miss it. "Please quote this." passes; "Please price this." is filtered.
`reference/filter_signals.json` was built as an enumeration and is being used as the spec —
exactly the shape `ACCEPTANCE_ROUND27.md` X-2 pre-registered.

Three further defects compound it:

* the veto is **bypassed entirely** for `DELIVERY_STATUS_NOTIFICATION`, which fires on a `From:`
  local-part of `postmaster`/`bounce`, on `Return-Path: <>`, and on any `multipart/report;
  report-type=delivery-status` — an RFQ inside a `multipart/report` was on X-1's own attack list
  and is filtered even when its subject reads *"RFQ - hose assemblies, please quote"* (R27-F2);
* the documented **fail-open promise is false**. `src/README.md`, `src/EXAMPLES.md` and
  `filter_gate.py`'s own docstring all state that an HTML-only body over the scan budget, an
  undecodable part and "no text obtained" resolve to *not filtered*. They do not: the
  `undecodable` flag is computed and then never consulted on the filtering decision. Two
  messages identical but for HTML body size across the 65536-byte boundary decide oppositely
  (R27-F3);
* `run_state.py`'s central claim — *"ARTIFACTS … Invalidation walks this mapping, so adding an
  artifact cannot be forgotten by a clearing site"*, echoed as REQ-029 — is **false**.
  `invalidate()` takes a hand-written list at every call site. I added a third artifact to the
  single declaration and no clearing site touched it. Round 26's fix centralised the
  *declaration* and left the *R26-F1 mechanism* intact behind it (R27-F4).

And the suite cannot see any of it. `tools/selftest.py` reports 83/83. I ran 20 mutations;
**9 left it fully green**, including deleting the `screen` override read — the recipe's only
route for `--no-filter`, and the documented remedy for exactly the false positives above
(R27-F5).

What held: parity is genuinely untouched by the gate (7/7, byte-identical to the source
captures through the full gated flow, input bytes stable, engine provably never invoked on a
filtered message via a sentinel in `cli.main`); the exit clamps hold under argparse's
`SystemExit(2)`; reconciliation fails closed in all four modes; clearing and state-write
failures are loud; the published upload package reproduces the pre-registered sha256 exactly;
and the gate ignored every instruction I embedded in an email.

Every mutation was made in scratch copies, never in the kit. `git status --porcelain` is back to
`?? ACCEPTANCE_ROUND27.md`, `git diff --stat` empty, `dist/kit.zip` sha256 unchanged at
`b673414987f5736a0df2993a451d16428b43314535e00cab0f136250a0d76aa3`, `src/vendor/` re-diffed
byte-clean against the source afterwards, and the source repo is untouched at `b15b23d`.

---

## Results table

| # | Check | Verdict |
|---|---|---|
| X-1 | A real RFQ must never be filtered | **FAIL** — 24 of 35 genuine RFQs filtered; 13 engine-confirmed as draftable (R27-F1, R27-F2, R27-F3) |
| X-2 | The enumeration is not the spec | **FAIL** — only the listed instances are handled, in both directions; out-of-vocabulary junk is safe, but the `_categories_note` precedence claim is false |
| X-3 | A filtered run is honest and never lossy | **PARTIAL** — artifacts, determinism, exit-3 isolation and replay all hold; every pass-through record violates the shipped schema (R27-F6) |
| X-4 | The gate cannot alter what the engine sees | **PASS** — proven four independent ways |
| X-5 | The override cannot be silently enabled or ignored | **PARTIAL** — loud and effective, but any truthy JSON value enables it and nothing ever clears it (R27-F7) |
| X-6 | Is `run_state.py` a new fault line | **FAIL** — no argv leak, but `invalidate()` is not driven by `ARTIFACTS` (R27-F4); `FILTER_KEYS`/`make_screen_request` are dead code |
| X-7 | The round-25/26 defences still hold | **PASS** — all six re-verified against the current artifact |
| X-8 | The defences are covered and falsifiable | **FAIL** — 9 of 20 mutations left 83/83 green (R27-F5) |
| X-9 | The shipped artifact and published package | **PASS** — sha reproduced exactly, both paths run from the zip |
| X-10 | Documentation makes no false claim | **FAIL** — the fail-open promise, the ARTIFACTS claim, the precedence note, the "ONLY constructor" claim (R27-F3, R27-F4, R27-F8) |
| X-11 | Nothing sensitive, no new I/O | **PASS** — clean static scan, clean audit trap, injections ignored |

---

# PART A — the input filter

## X-1 — a real RFQ must never be filtered — **FAIL**

### How many adversarial RFQs, and what shapes

**35 genuine quoting requests**, all built by me; the shipped `tools/filter/fixtures/` were
used only as controls. Shapes:

* **Set A (10)** — realistic purchasing email: `Terms net 30.` footer; `invoice our AP
  department`; a McGill salesperson forwarding a customer RFQ internally; a sourcing-portal
  notification from `no-reply@`; an ERP-generated requisition carrying `Auto-Submitted:
  auto-generated`; a polite `Thanks.` opener before the request; a one-line terse RFQ
  (`quote 50ft 2in EPDM`); a buyer whose `To:` is their own domain with the supplier on Bcc;
  an RFQ chasing a `past due` earlier request; a Spanish-language RFQ.
* **Set B (10)** — veto-boundary and exemption probes: a no-`net 30` control; `net 30` plus a
  question mark; `From: postmaster@`; `Return-Path: <>`; an HTML-only body over
  `html_scan_bytes` from a portal sender; the same under budget; an unknown-charset text part
  with `invoice` in the subject; a real RFQ inside `multipart/report; report-type=delivery-status`;
  a `Remit to:` footer.
* **Set C (3)** — the scan-budget boundary isolated: identical RFQ, identical headers, HTML body
  22 057 bytes vs 87 757 bytes; and a message with no text part at all.
* **A 13-variant phrasing sweep** — one body, one `net 30` footer, only the closing ask changed.

### The headline: one line of boilerplate

```
$ ./gate.sh cases/A1-net30-rfq.eml
EXIT=3
{ "filtered": true, "input": "in.eml", "code": "INVOICE_OR_STATEMENT",
  "route": "accounts_payable", "evidence": "net 30", "override": false, "reason": null }

$ ./gate.sh cases/B1-control-no-net30.eml     # byte-identical except the "Terms net 30." line
EXIT=0
{ "filtered": false, "input": "in.eml", "code": null, "route": null,
  "evidence": null, "override": false, "reason": "no_evidence" }
```

A1's body is an ordinary RFQ: *"We need 200 feet of 2 inch ID EPDM suction hose, male NPT both
ends, 150 PSI working pressure, for ambient service on water transfer. Please send your best
price and lead time to my attention. Terms net 30."*

The engine's own verdict on the same file, via the shipped wrapper:

```
$ python3 src/scripts/run_engine.py --in A1-net30-rfq.eml --out _report/case_state.json
A1-net30-rfq rc=0 class=bulk_hose lines=0 open=6 checkpoints=2
```

### Every filtered genuine RFQ, with the engine's verdict on the same bytes

| case | gate | code / evidence | engine on the same file |
|---|---|---|---|
| A1 `Terms net 30.` | 3 | `INVOICE_OR_STATEMENT` / `net 30` | `class=bulk_hose open=6 checkpoints=2` |
| A2 `invoice our AP department` | 3 | `INVOICE_OR_STATEMENT` / `invoice` | `class=hose_assembly open=5` |
| A3 internal forward of a customer RFQ | 3 | `INTERNAL_CHATTER` / `internal: mcgill.example.net` | `class=hose_assembly open=4` |
| A4 portal `no-reply@` | 3 | `AUTO_REPLY` / `no-reply@sourcing.example.com` | `class=hose_assembly open=6` |
| A5 ERP `Auto-Submitted: auto-generated` | 3 | `AUTO_REPLY` / `Auto-Submitted: auto-generated` | `class=hose_assembly open=6` |
| A8 buyer's own domain in `To:` | 3 | `INTERNAL_CHATTER` / `internal: acme.example.com` | `class=bulk_hose open=6` |
| A9 `our request is past due` | 3 | `INVOICE_OR_STATEMENT` / `past due` | `class=hose_assembly open=5` |
| A10 Spanish RFQ + `net 30` | 3 | `INVOICE_OR_STATEMENT` / `net 30` | `class=hose_assembly open=7` |
| B3 `From: postmaster@` | 3 | `DELIVERY_STATUS_NOTIFICATION` | `class=bulk_hose open=7 questions=6` |
| B4 `Return-Path: <>` | 3 | `DELIVERY_STATUS_NOTIFICATION` | `class=bulk_hose open=7 questions=6` |
| B5 HTML-only over budget, `no-reply@` | 3 | `AUTO_REPLY` | `class=bulk_hose open=8 questions=6` |
| B9 RFQ inside `multipart/report` | 3 | `DELIVERY_STATUS_NOTIFICATION` | `class=bulk_hose open=7 questions=6` |
| B10 `Remit to:` footer | 3 | `INVOICE_OR_STATEMENT` / `remit to` | `class=bulk_hose open=6 questions=6` |

B3, B4 and B9 each carry the sentence *"Can you quote this today?"* and B4's subject is literally
*"RFQ - hose assemblies, please quote"*. They are filtered anyway — see R27-F2.

Also filtered: C2 and C3 (R27-F3), B7 (an unknown-charset part; the engine also fails on this
one, so it is misclassification rather than lost work), and 8 of the 13 phrasing variants.

### The phrasing sweep — one body, one footer, only the closing ask changes

```
  Please quote for this.                  exit=0  passed
  Please quote on this.                   exit=0  passed
  Please quote this.                      exit=0  passed
  Please price this.                      exit=3  FILTERED
  Please send pricing for this.           exit=0  passed
  Please send pricing on this.            exit=3  FILTERED
  Send us your best price.                exit=3  FILTERED
  Kindly provide your best offer.         exit=3  FILTERED
  We require a firm price and lead time.  exit=3  FILTERED
  Quotation required.                     exit=3  FILTERED
  Please respond with unit price.         exit=3  FILTERED
  Devis demande.                          exit=3  FILTERED
  Please advise price.                    exit=0  passed
```

`pricing for` survives and `pricing on` does not. That is the enumeration deciding whether a
customer gets a quote.

## X-2 — the enumeration is not the spec — **FAIL**

**Category or listed instances?** Listed instances only, and the asymmetry is stark. Six
out-of-vocabulary junk categories all pass through safely (correct direction, no silent
discard):

```
D1 phishing                     exit=0 passed
D2 job application              exit=0 passed
D3 cold vendor pitch            exit=0 passed
D4 calendar invite              exit=0 passed
D5 read receipt                 exit=0 passed
D6 marketing blast, no headers  exit=0 passed
```

D6 is a 50%-OFF marketing blast — squarely the category phase 5 exists for — and it passes
because it lacks `List-Unsubscribe`. Meanwhile A1, a real RFQ, is filtered. The gate is
currently more likely to drop a quoting request than a promo.

**A signal a mildly different phrasing defeats:** `invoice_phrases` is a bare substring test
over subject + body. `net 30`, `invoice`, `past due` and `remit to` are ordinary RFQ
boilerplate; `net 45`, `2% 10 net 30 EOM` and `payable in 30 days` are not in the list. Both
directions are wrong for the same reason.

**The sibling shape (one rule, two places):** `_categories_note` in `filter_signals.json` states
*"ORDERED — list order is behaviour, first match wins, exactly like rules.json's own precedence
lists."* It is not true across tiers — the header tier always beats the content tier regardless
of list position. Moving `INVOICE_OR_STATEMENT` to first place changes nothing:

```
-- with INVOICE_OR_STATEMENT reordered to FIRST:  BULK_MAILING
-- unmodified kit (INVOICE is 4th):               BULK_MAILING
```

An operator tuning precedence through the file the docs point them at gets silence. (The
`detector` name binding is better: renaming `invoice_content` in the JSON silently disables the
category, but the selftest does catch that one — 80/83.)

## X-3 — a filtered run is honest and never lossy — **PARTIAL**

**Artifacts.** Clean. A filtered run in a directory holding a previous customer's paperwork
leaves only `state.json`:

```
$ ls _report                       # before: a real RFQ drafted
bom_draft.md  case_state.json  state.json
$ python3 src/scripts/filter_gate.py --from-state --state _report/state.json ; echo $?
3
$ ls _report
state.json
```

**Determinism.** Identical record across 5 `PYTHONHASHSEED` values (one sha256).

**Exit 3 isolation.** Reachable only from `return 3 if decision["filtered"]`. `--bogus-flag`
(argparse `SystemExit(2)`) → 1 on all three scripts. Missing input → 1. No `--in`/`--from-state`
→ 1. A filtered message whose record cannot be written → 1, not 3. `run_engine.py` and
`generate_report.py` never emit 2 or 3.

**Replay.** Works from the record alone, no edit to kit or email:

```
$ ... screen.override=true, then the recipe's three phases
gate rc=0   (stderr: warning: --no-filter is set; ...)
run_engine rc=0
wrote _report/bom_draft.md (2407 bytes, engine_exit=2, reconciled)
email bytes unchanged: YES
```

**Schema.** Fails — see R27-F6. Every pass-through record violates
`filter_decision.schema.json`.

## X-4 — the gate cannot alter what the engine sees — **PASS**

Four independent proofs.

1. **Input bytes.** sha256 before/after on all 7 parity fixtures and on the override path:
   `hash_same=YES` every time. The gate's only `open()` calls on the input are `"rb"` reads.
2. **Full gated flow vs the source captures.**
   ```
   suction-assembly gate=0 engine=0 BYTE-IDENTICAL
   plain-steam      gate=0 engine=0 BYTE-IDENTICAL
   quoted-printable gate=0 engine=0 BYTE-IDENTICAL
   multipart-html   gate=0 engine=0 BYTE-IDENTICAL
   confirmed-ids    gate=0 engine=0 BYTE-IDENTICAL
   ```
   and `parity_check.py` → `7 fixtures checked, 7 matched, 0 mismatched / normalized fields: (none declared)`.
3. **Gate runs before the engine, sentinel-proven.** A scratch copy of the kit with a sentinel
   wrapping `email_to_bom.cli.main`:
   ```
   gate exit=3
   sentinel file exists? NO
   engine wrapper exit=0
   sentinel after run_engine: ENGINE INVOKED
   ```
   The sentinel fires when the engine really runs, and does not fire on a filtered message.
4. **Vendored tree.** `diff -r` against the source at `b15b23d`: engine IDENTICAL, config
   IDENTICAL. `tools/parity/**` unmodified (`git diff --stat` empty). All 13 mutations I made
   to gate code left parity at 7/7 — the gate is genuinely not entangled with engine output.

## X-5 — the override cannot be silently enabled or silently ignored — **PARTIAL**

`--no-filter` is loud (`warning: --no-filter is set; the input filter is disabled for this run
and every message reaches the engine`), recorded (`override: true`, `reason: "override"`) and
effective (a filtered-category message drafts). Content inside an email cannot enable it (E1–E3
below). But it can be enabled by a non-choice and it is never cleared — see R27-F7.

---

# PART B

## X-6 — `run_state.py` owns four concerns; is that a new fault line? — **FAIL**

**Can a filter key leak into the engine argv?** No — and I tried:

```
raw = {"input":"rfq.eml","component_ids":["A"],"coc":True,"config_dir":None,
       "filter":{...},"screen":{"override":True},"no_filter":True,
       "--no-filter":True,"filtered":True,"override":True}
normalized: {"input":"rfq.eml","component_ids":["A"],"coc":true,"config_dir":null}
argv:       ['rfq.eml', '--json', '--component-ids', 'A', '--coc']
SCREEN_KEY in argv? False    FILTER_KEY in argv? False
```

`normalize_invocation` iterates `INVOCATION_KEYS`, so nothing else can reach `build_argv`.
Parity is safe from this direction. **PASS** on that bullet.

**Is `invalidate()` driven by `ARTIFACTS`?** No. See R27-F4 — this is the X-6 failure.

**Do the normalisers read through their declared key tuples?** Yes for `INVOCATION_KEYS`.
`FILTER_KEYS` does — inside `normalize_filter_decision`, which **nothing calls**.
`make_screen_request` (documented *"The ONLY constructor"*) is also **dead**: the recipe has an
LLM hand-write `{"screen": {"override": …}}` into `state.json` from prose. Three of the four
declared concerns are enforced only in unreachable code.

**Stale filter record beside a fresh CaseState?** Possible, but only off the recipe's path
(`run_engine.py` invoked without `--state`):

```
gate rc=3
run_engine (no --state) rc=0
artifacts: case_state.json  state.json
state.filter = {"filtered": true, "input": "rfq.eml", "code": "INVOICE_OR_STATEMENT", ...}
  => a CaseState exists while state.json still says filtered:true
```

With `--from-state` as the recipe mandates, `state.filter = null`. Low severity.

## X-7 — the round-25 and round-26 defences still hold — **PASS**

All six re-verified against the current artifact.

**Flags survive the phase boundary (R25 F-1).** Five combinations through the real four-phase
sequence; the recorded invocation is unchanged by the gate and the draft reflects the flags:

```
  none:           gate=0 engine=0 report=0 bom_lines=0 draft_table_rows=1 coc_in_draft=0
  ids:            gate=0 engine=0 report=0 bom_lines=4 draft_table_rows=5 coc_in_draft=0
  coc:            gate=0 engine=0 report=0 bom_lines=1 draft_table_rows=2 coc_in_draft=1
  ids+coc:        gate=0 engine=0 report=0 bom_lines=5 draft_table_rows=6 coc_in_draft=1
  ids+coc+config: gate=0 engine=0 report=0 bom_lines=5 draft_table_rows=6 coc_in_draft=1
```

**Reconciliation fails closed (R26-F3).** Four modes, all refused, no draft written:

```
  absent:     rc=1 draft_exists=NO  error: no CaseState to reconcile against at ...
  dir:        rc=1 draft_exists=NO  error: no CaseState to reconcile against at ...
  unreadable: rc=1 draft_exists=NO  error: cannot read ...: [Errno 13] Permission denied
  garbage:    rc=1 draft_exists=NO  error: cannot read ...: Expecting value: line 1 ...
```

**No failure path leaves stale artifacts (R26-F1).**

```
  after good run: bom_draft.md  case_state.json  state.json
  run_engine rc=1                       # input made to vanish
  after failed run: state.json
  state.json keys: ['invocation']       # prepare record preserved — R26-F10 also holds
```

**Clearing / state-write failures are loud (R26-F5).** Under `chmod 500 _report`, all three
scripts rc=1 with a named error. `write_state` is loud too, tested in isolation:

```
gate rc=1
error: cannot update _report/sub/state.json: [Errno 13] Permission denied: ...
state written: NO
```

**The engine's 2 never leaks (R26-F2).** `run_engine.py` rc=0 with `"engine_exit": 2` in stdout;
`generate_report.py` rc=0. `--bogus-flag` → 1 on all three. Exit 3 did not loosen the clamp on
the other two.

## X-8 — the defences are covered and the coverage is falsifiable — **FAIL**

Baseline `83/83 defences held`, parity 7/7. I ran **20 mutations**. **11 were caught**:
`decide_never_filters`, `decide_always_filters`, `drop_veto` (80/83), `drop_reconcile` (81/83),
`gate_no_clear_draft` (82/83), `gate_no_clear_at_all` (82/83), `gate_clamp_removed`,
`invalidate_silent` (82/83), `remove_category`, `rename_detector` (80/83),
`gen_report_no_clear` (82/83). Those checks are real and falsifiable.

**9 left the suite fully green at 83/83** — see R27-F5 for the list and why each matters.

Parity stayed `7/7` under every gate mutation, confirming the gate is not entangled with engine
output.

## X-9 — the shipped artifact and the published package — **PASS**

```
$ python3 tools/validate_manifest.py kit.json           ; echo $?   ->  0
$ ./tools/build_kit.sh
  SHA-256:  b673414987f5736a0df2993a451d16428b43314535e00cab0f136250a0d76aa3   (unchanged)
$ git status --porcelain    ->  ?? ACCEPTANCE_ROUND27.md
requires.tools: []          email_attachment tag count: 1  (_report/case_state.json)
$ python3 tools/publish_kit.py --base https://astro.example.com --dry-run --out upload.zip
  Package built — 25 files, 88738 bytes, sha256 5e2afec85205…
5e2afec8520537acd631fb693b25d63da025ddfd01f92c327a539766b86880b4   (matches the bar; reproduced twice)
```

Unzipped `dist/kit.zip` from an unrelated clean directory, `python3 -S -E`, no install:

```
### DRAFTING PATH   gate rc=0 / run_engine rc=0 / wrote _report/bom_draft.md (2407 bytes, engine_exit=2, reconciled)
### FILTERED PATH   gate rc=3, code INVOICE_OR_STATEMENT, artifacts: state.json
```

Note what that second block means: **the R27-F1 defect is live in published v0.4.0**.

## X-10 — documentation makes no false claim — **FAIL**

See R27-F3 (the fail-open promise, in three documents), R27-F4 (the ARTIFACTS claim, plus
REQ-029), R27-F8 (the precedence note and the "ONLY constructor" claims).

What is honest and worth saying: `src/vendor/PROVENANCE.md` explains the `b1f9950` / `b15b23d`
stamp precisely and correctly. The `estimated_duration` and the three-engine-pass / ~3x figures
in `src/EXAMPLES.md` are accurate. FOLLOW-UP-6 and FOLLOW-UP-7 state the fixture-corpus and
test-suite limits without spin. FOLLOW-UP-9 and FOLLOW-UP-10 are described accurately — the ten
deferred items are, per the bar, out of scope as defects, and I found their **descriptions**
honest. The documented commands in README/EXAMPLES all exist and work as written.

## X-11 — nothing sensitive, no new I/O — **PASS**

**Secrets.** No credential, token, key or password in the repo or the zip; hits are prose in the
round-25/26 reports, the word "tokens" in `parity_check.py`, and `$ASTRO_ADMIN_PASSWORD` named
(not valued) in `KIT-CONTRACT.md`.

**Identities.** Every address across `tools/parity/fixtures` and `tools/filter/fixtures` is in
the RFC 2606 reserved `.example` namespace: `MAILER-DAEMON@mail.customer.example`,
`ap@mcgill.example`, `ar@customer.example`, `buyer@customer.example`, `dana@northside.example`,
`dave@mcgill.example`, `news@hosesupplier.example`, `purchasing@acmedairy.example`,
`sales@mcgill.example`, `sales@mcgillhose.example`, `sandra@mcgill.example`,
`unsubscribe@acmedairy.example`, `unsubscribe@hosesupplier.example`.

**No new I/O.** Static scan of the four non-vendored modules: zero `urllib` / `socket` /
`requests` / `os.environ` / `getenv` / `subprocess` / `os.system` / `eval` / `exec` /
`__import__` / `pickle` (the single grep hit is the word "subprocess" in a docstring).
`filter_gate.py` opens exactly three things: `reference/filter_signals.json`,
`schemas/filter_decision.schema.json`, and the input as `"rb"`. Every write in the kit is
`_report/state.json`, `_report/case_state.json` or `_report/bom_draft.md`.

Runtime audit hook over gate + engine + report:
`NETWORK/SUBPROCESS/ENV-WRITE EVENTS: NONE`. The gate also runs correctly under `env -i`
(rc=0), so nothing is read from the environment.

**Instructions inside email are ignored.** Four deliberate injections — a newsletter body
telling the gate to set `filtered=false`, forged `X-No-Filter` / `X-Filter-Override` /
`X-Screen-Override` headers alongside `Auto-Submitted: no`, a body containing a fabricated
`{"filter": …, "screen": {"override": true}, "invocation": {"input": "/etc/passwd"}}` record,
and a prose instruction to re-run with `--no-filter` and exfiltrate the CaseState:

```
E1-header-injection      EXIT=3  BULK_MAILING / List-Unsubscribe + Precedence: bulk
E2-body-json-injection   EXIT=3  BULK_MAILING / List-Unsubscribe + Precedence: bulk
E3-instruction-to-agent  EXIT=3  BULK_MAILING / List-Unsubscribe + Precedence: bulk
```

and the resulting `state.json` contains the filter record and nothing else. Email content is
treated as bytes throughout.

---

# Findings, by severity

## R27-F1 — CRITICAL — the quoting-request veto is a 16-phrase list, so ordinary RFQ language loses the message

**What breaks.** `filter_gate._decide` filters a message whenever a junk category matches *and*
the veto does not fire. The veto needs `product_signal AND request_act`. `product_signal` is the
vendored classifier and is reliable. `request_act` is not: it is a `"?"` test, `rules.json`'s
14 `question_cues`, an `order`/`stocking_lead` class, or a hit in
`filter_signals.json`'s 16 `quote_request_cues`. An RFQ that states its ask imperatively and has
no question mark misses all four. `invoice_phrases` is a bare substring match over subject +
body, so `net 30`, `invoice`, `past due` and `remit to` — all ordinary in purchasing mail — supply
the category. `_internal_domain_content` supplies it whenever every `To`/`Cc` shares the `From`
domain, which is a salesperson forwarding an RFQ inward, or a buyer who Bcc'd the supplier.
`_auto_reply_header` supplies it for `no-reply@` portal senders and any `Auto-Submitted` header
ERPs set per RFC 3834.

**Reproduction.**

```
$ cat > rfq.eml <<'EOF'
From: Dana Whitfield <dana.whitfield@acme.example.com>
To: quotes@mcgill.example.net
Subject: Hose assembly requirement - plant 4

We need 200 feet of 2 inch ID EPDM suction hose, male NPT both ends,
150 PSI working pressure, for ambient service on water transfer.
Please send your best price and lead time to my attention.
Terms net 30.
EOF
$ python3 src/scripts/filter_gate.py --in rfq.eml --state _report/state.json ; echo "EXIT=$?"
{ "filtered": true, "code": "INVOICE_OR_STATEMENT", "route": "accounts_payable",
  "evidence": "net 30", ... }
EXIT=3
$ python3 src/scripts/run_engine.py --in rfq.eml --out _report/case_state.json
   -> rc=0, class=bulk_hose, open=6, checkpoints=2
```

Delete `Terms net 30.` → exit 0. 24 of my 35 genuine RFQs filtered; 13 engine-confirmed
draftable.

**Why it matters.** This is the one mechanism in the kit that can make a customer request
disappear, and the recipe's phase 0.5 instructs the agent to *"STOP the run here"* and report
that there was nothing to quote. A distributor loses quotable revenue silently, and the
operator's only clue is a record that says the RFQ was an invoice. `PROJECT.md`'s own phase-5
constraint — *"Filtering out a real RFQ is far worse than passing a newsletter through"* — is
violated in the most common email shape in the domain. The fix cannot be more cue phrases;
`request_act` needs to be a property of the *category* (or the veto needs to stop being the only
thing between a real RFQ and exit 3).

## R27-F2 — CRITICAL — the DSN exemption bypasses the veto, so a labelled RFQ is dropped

**What breaks.** `_decide` returns early for `DELIVERY_STATUS_NOTIFICATION` *before* the veto
runs. `_dsn_headers` fires on three things, only one of which is structurally conclusive: a
`multipart/report; report-type=delivery-status` content type; a `From:` local-part in
`dsn_sender_localparts` (`postmaster`, `bounce`, `bounces`, `mailer-daemon`, …); or
`Return-Path: <>`. None of the three is checked against the message actually containing a
delivery report, and no amount of RFQ content can override them.

**Reproduction.**

```
From: Dana Whitfield <dana.whitfield@acme.example.com>
To: quotes@mcgill.example.net
Return-Path: <>
Subject: RFQ - hose assemblies, please quote
...200 feet of 2 inch ID EPDM suction hose... Can you quote this today?

$ gate -> EXIT=3  DELIVERY_STATUS_NOTIFICATION / "Return-Path: <>"
$ engine on the same file -> class=bulk_hose open=7 questions=6
```

Same outcome for `From: postmaster@acme.example.com` and for the identical RFQ wrapped in
`multipart/report; report-type=delivery-status` — the latter is an attack `ACCEPTANCE_ROUND27.md`
X-1 named explicitly.

**Why it matters.** These are the messages the veto was built to save, and they are the ones it
never sees. The docstring's justification — *"a bounce is never a request, even one that echoes
RFQ text back in its body"* — is sound for the structural test only; extending the exemption to
a sender local-part and to `Return-Path: <>` (which some list and forwarding infrastructure sets
on legitimate mail) makes the strongest filter decision in the kit turn on the weakest evidence.

## R27-F3 — HIGH — the documented fail-open behaviour does not exist; `undecodable` is computed and never used

**What breaks.** `_collect_text` returns `(text, undecodable)` and sets `undecodable=True` for
an over-budget HTML body, an undecodable part, or no text part at all. In `_decide`, that flag
is consulted in exactly one place — inside the `candidate is None` branch, where it only picks
between the strings `"parse_failed"` and `"no_evidence"`. It **never affects whether the message
is filtered**. So whenever a header- or content-tier candidate exists, "the gate obtained no
usable text" resolves to *filtered*, because the veto's classifier is then run against an empty
string and returns `out_of_scope`.

**Reproduction — the boundary isolated.** Identical RFQ text, identical headers, only HTML body
size differs across `html_scan_bytes` (65536):

```
C1-html-UNDER-budget  html bytes = 22057   EXIT=0  reason "quoting_request_detected"
C2-html-OVER-budget   html bytes = 87757   EXIT=3  AUTO_REPLY / no-reply@sourcing.example.com
C3-no-text-parts      (application/pdf)    EXIT=3  AUTO_REPLY / no-reply@sourcing.example.com
```

The over-budget body drafts fine in the engine (`class=bulk_hose open=8 questions=6`).

**The false claims.** `src/EXAMPLES.md`: *"**The filter fails toward running the engine.**
Everything the gate cannot resolve confidently — no text obtained, a parse defect, an HTML-only
body over its scan budget, an unrecognised or undecodable part, an undeclared code/route,
unreadable reference data — resolves to *not filtered*, so a real RFQ is never silently dropped
for being ambiguous."* `src/README.md`: *"fails toward running the engine on anything it cannot
resolve confidently."* `filter_gate.py`'s module docstring says the same. Three of the six listed
conditions are false.

**Why it matters.** 64 KB of HTML is unremarkable for Outlook mail with inline CSS and a quoted
thread, and portal notifications are HTML-only from `no-reply@` by construction — the two
conditions co-occur naturally. Worse, the false promise is the reason a reviewer would not look
here: the docs assert this class of RFQ is already safe.

## R27-F4 — HIGH — `invalidate()` is not driven by `ARTIFACTS`; the R26-F1 mechanism survives behind the centralised declaration

**What breaks.** `run_state.py`'s docstring: *"ARTIFACTS — every file a run produces.
**Invalidation walks this list**, so adding an artifact cannot be forgotten by a clearing
site."* REQ-029: *"`run_state.ARTIFACTS` is the single declaration; **invalidation walks it**."*
Neither is true. `invalidate(paths)` takes whatever list the caller passes, and all three call
sites hand-write the names:

```
src/scripts/run_engine.py:168   invalidate([paths["case_state"], paths["bom_draft"]])
src/scripts/filter_gate.py:442  invalidate([paths["case_state"], paths["bom_draft"]])
src/generate_report.py:99       invalidate([paths["bom_draft"]])
```

**Reproduction.** In a scratch copy, add one entry to the single declaration:

```python
ARTIFACTS = {
    "case_state": ...,
    "bom_draft": ...,
    "third_artifact": os.path.join("_report", "third_artifact.txt"),
}
```

then leave a stale copy in place and run the clearing sites:

```
run_engine rc=0
after run_engine, _report: case_state.json  state.json  third_artifact.txt
third_artifact content: STALE THIRD ARTIFACT FROM CUSTOMER A

filter_gate rc=3
after filter_gate, _report: state.json  third_artifact.txt
third_artifact content: STALE THIRD ARTIFACT FROM CUSTOMER A
```

Customer A's artifact survives a filtered run for customer B — the exact R26-F1 sentence, with
the declaration that was supposed to prevent it sitting right there.

**Why it matters.** Round 26's fix was *"a fix that names an item must be replaced by one that
handles the category"*. What shipped centralises the *list of names* and leaves the *iteration*
at the call site, so the guarantee is documentation rather than mechanism. The next artifact —
a filtered-message routing slip, a rendered email — will be forgotten by two of three clearing
sites, and the docstring will still say it cannot be. A one-line change
(`invalidate(artifact_paths(...).values())`) would make the claim true.

## R27-F5 — HIGH — 9 of 20 mutations leave the 83-check suite green, including the recipe's only override path

**What breaks.** `tools/selftest.py` exists because round 26 found the old suite could not fail.
It is much better than what it replaced — 11 of my 20 mutations were caught and named. But nine
were not:

| mutation | consequence if it were real | suite |
|---|---|---|
| `screen_override_ignored` — delete the `state.json` `screen` read | **the recipe's only route for `--no-filter` stops working**; every false positive becomes permanent | 83/83 |
| `bulk_alone` — let `List-Unsubscribe` filter on its own | violates the explicit *"NEVER List-Unsubscribe alone"* invariant; drops RFQs from any customer whose mailer adds the header | 83/83 |
| `write_state_silent` — restore `except OSError: pass` in `write_state` | R26-F5 verbatim; a filtered run would exit 3 with no record | 83/83 |
| `enum_validation_removed` — drop the closed-enum fail-open guard | an undeclared code/route could ship | 83/83 |
| `input_isfile_check_removed` — drop the gate's one fail-closed guard | a missing input no longer errors loudly | 83/83 |
| `html_budget_ignored` — remove the `html_scan_bytes` bound | the FOLLOW-UP-9 cost guard is gone | 83/83 |
| `drop_ack_dominance` — read the raw body instead of the stripped remainder | the dominance test the docstring credits for `ack-plus-rfq` is gone | 83/83 |
| `no_evidence_truncation` — remove `evidence[:80]` | schema `maxLength: 80` silently violated | 83/83 |
| `dsn_veto_exemption_removed` — remove the DSN early return | R27-F2's mechanism, untested in either direction | 83/83 |

Reproduce any row by applying the edit and running `python3 tools/selftest.py`.

Two of these are pointed enough to name. **`screen_override_ignored`** is the R26-F4 shape
exactly: defence 5h tests `--no-filter` on `filter_gate.py`'s command line, but the recipe never
uses that form — phase 0.5 runs `filter_gate.py --from-state --state _report/state.json`, and
the override travels through the `screen` record. `grep -n "screen\|from_state" tools/selftest.py`
shows the suite never exercises `filter_gate.py --from-state` at all and never writes a `screen`
key. The tested path and the shipped path are different code. **`write_state_silent`** is the
sibling of a mutation the suite *does* catch (`invalidate_silent` → 82/83): the read-only-`_report`
check trips on `invalidate` before `write_state` is ever reached, so half the R26-F5 fix is
uncovered. "Named the instance, missed the sibling" — in the coverage this time.

Also worth recording: defence 5j (*"a ~1 MB junk message filters in well under the engine's
superlinear cost"*) builds its fixture as `b"all month.\n" * 15000` appended to the newsletter's
**plain-text** body. It therefore never exercises the `html_scan_bytes` path it was written to
bound, which is why `html_budget_ignored` leaves it green.

## R27-F6 — MEDIUM — every pass-through record violates the shipped `filter_decision.schema.json`

**What breaks.** The schema declares `"evidence": {"type": "string", "maxLength": 80}` — no
`null` in the union, unlike `code`, `route` and `reason`, which all got `["string","null"]`.
`make_filter_decision` always emits the key, and on every pass-through it is `None`.

**Reproduction** (validating real records against the shipped schema):

```
filtered (A1-net30): SCHEMA OK
pass-through (B1):   SCHEMA VIOLATIONS: evidence=None not of type string
veto pass (B2):      SCHEMA VIOLATIONS: evidence=None not of type string
override branch:     SCHEMA VIOLATIONS: evidence=None not of type string
```

**Why it matters.** The pass-through record is the *common* case, so the shipped contract is
violated by most records the kit writes. Three of the four nullable properties were given the
union and the fourth was missed — the signature failure, in the schema. Nothing catches it:
defence 5i compares only the `code`/`route` enums to `filter_signals.json` and never validates a
record, and FOLLOW-UP-10 records that the kit's `_schema_engine.py` cannot parse this schema at
all. FOLLOW-UP-10 is honestly disclosed; this *consequence* of it is not. A consumer who
validates the contract as published will reject valid runs.

## R27-F7 — MEDIUM — the override is enabled by any truthy value and is never cleared

**What breaks.** `normalize_screen_request` does `bool(raw.get("override"))`, so every truthy
JSON value enables the filter bypass — including the string `"false"`:

```
  screen.override=true        -> rc=0 record.override=True  warning=1
  screen.override=false       -> rc=3 record.override=False warning=0
  screen.override="false"     -> rc=0 record.override=True  warning=1
  screen.override="no"        -> rc=0 record.override=True  warning=1
  screen.override="0"         -> rc=0 record.override=True  warning=1
  screen.override="off"       -> rc=0 record.override=True  warning=1
  screen.override=[0]         -> rc=0 record.override=True  warning=1
  screen.override=" "         -> rc=0 record.override=True  warning=1
  screen.override=0 / null / [] / {} -> rc=3 (not enabled)
```

The recipe has an LLM hand-write this key from prose (*`"override": <true if --no-filter was
given, else false>`*), so `"false"` is a realistic authoring slip that inverts the setting.

Separately, **nothing ever clears `SCREEN_KEY`**. `run_engine.write_state` drops `extract_case`
and `FILTER_KEY`; `filter_gate.write_state` drops `extract_case`; neither touches `screen`. A
second message processed in the same `_report/` inherits the first run's override:

```
state keys after a --no-filter run: ['extract_case', 'invocation', 'screen']
screen still present: {'override': True}
-- new message arrives, prepare updates only `invocation` (merge, as write_state does)
gate on a pure newsletter rc=0   ("override": true, "reason": "override")
```

**Why it matters.** Not a lost-RFQ path — it fails toward drafting — but it is the *same stale-record
shape* the author guarded for `FILTER_KEY` and missed for its sibling `SCREEN_KEY`. It is also
mitigated only by prose: the recipe tells the agent to write a fresh `state.json`, while
`run_state.write_state` — the kit's own helper — merges. Consequence: after one legitimate
override, every subsequent message in that directory is unscreened until something happens to
overwrite `screen`. It is loud (the warning prints each time), so it is not silent, but it is not
an operator choice either.

## R27-F8 — LOW/MEDIUM — three more documentation claims that the code does not support

* `filter_signals.json` `_categories_note`: *"ORDERED — list order is behaviour, first match
  wins, exactly like rules.json's own precedence lists."* False across tiers; reordering
  `INVOICE_OR_STATEMENT` to first changes nothing (`BULK_MAILING` still wins). The file is the
  documented tuning surface, so this misleads precisely the person who would edit it.
* `run_state.make_screen_request` / `normalize_filter_decision` / `FILTER_KEYS`: documented as
  *"The ONLY constructor"* and as the anti-`R26-F6` discipline, but `make_screen_request`,
  `normalize_filter_decision` and `FILTER_KEYS` have **no callers anywhere** in `src/` or
  `tools/`. The screen record is authored by an LLM from prose; the filter record is read as raw
  JSON. The declared discipline exists only in unreachable code.
* `filter_gate.py` docstring: *"This is what saves a real RFQ that … carries bulk/auto-reply
  headers, opens with a polite 'thanks, got it', or is bundled with an invoice paragraph."*
  The `thanks` case does hold (A6, exit 0); the bulk/auto-reply case (A4, A5) and the invoice
  case (A2, B10) do not.

## R27-F9 — LOW — an override record does not say what the gate would have decided

`make_filter_decision(False, input_path, override=True, reason="override")` records `code: null`
and `route: null`, so a `--no-filter` run leaves no trace of which category matched or on what
evidence. An operator auditing whether an override was justified cannot tell from the record.
X-3 asks the record to carry a code and a route; on the override branch it carries neither.

## R27-F10 — LOW — a stale filter record can sit beside a fresh CaseState off the recipe's path

`run_engine.py` drops `FILTER_KEY` only when `--state` is given. Invoked without it after a
filtered run, a `case_state.json` appears while `state.json` still reads `filtered: true`
(reproduction under X-6). The recipe always passes `--state`, so this is reachable only by hand.

---

# Known limitations of this verification

* The private `ScaleUpLabs/McGill-Core` repo was compared only through the local clone at
  `b15b23d`; I did not fetch it.
* `publish_kit.py` was exercised with `--dry-run`. The upload package's sha256 matches the
  pre-registered value exactly and reproduces across runs, but I could not confirm what the
  hosted registry actually holds — that needs credentials.
* Engine correctness (rounds 1–24) was out of scope. I used the engine only as an oracle for
  "would this RFQ have produced a draft".
* Runtime was spot-checked, not profiled: FOLLOW-UP-9's superlinear figures are taken as
  previously verified.
* My adversarial RFQs are synthetic and written by me. They are drawn from ordinary purchasing
  and sourcing-portal conventions, and 13 of them are engine-confirmed as in-scope quoting
  requests, but real McGill mail (FOLLOW-UP-6) would test the gate harder still — and given the
  hit rate on `net 30` alone, likely worse.

# Restoration

* Every mutation was applied to copies under
  `/private/tmp/claude-501/.../scratchpad/` (`mut/`, `art/`, `sentinel/`, `order/`), never to the
  kit. The source repo was read-only throughout and is clean at `b15b23d`.
* `./tools/build_kit.sh` was run once in the kit; it reproduced
  `b673414987f5736a0df2993a451d16428b43314535e00cab0f136250a0d76aa3` byte-for-byte and left the
  tree clean.
* Final state: `git log -1` = `fdfbb48`; `git status --porcelain` = `?? ACCEPTANCE_ROUND27.md`;
  `git diff --stat` empty; `src/vendor/` re-diffed byte-identical against the source;
  `83/83 defences held`; `7 fixtures checked, 7 matched, 0 mismatched`;
  `validate_manifest.py` exit 0.

# Verdict

**FAIL**, on X-1, X-2, X-6, X-8 and X-10, with X-3 and X-5 partial.

R27-F1 and R27-F2 alone are disqualifying: the gate drops genuine, engine-draftable customer
RFQs, and it does so on the most ordinary phrasing and boilerplate in the domain. R27-F5 explains
why the phase closed on a UAT sign-off with the defect intact — the suite that was built to make
these defences falsifiable cannot see nine of them, including the deletion of the only escape
hatch the recipe offers for exactly this failure. R27-F3 and R27-F4 mean the two documents a
reviewer would consult to reassure themselves — the gate's fail-open promise and the
centralised-artifact guarantee — both assert properties the shipped code does not have.

Round 25's fix pass introduced round 26's defect; round 26's fix pass produced a centralisation
that documents a guarantee it does not implement (R27-F4), and phase 5 then built the kit's
first work-destroying mechanism on top of an enumeration (R27-F1). The pattern is now three
rounds deep and has not changed shape.
