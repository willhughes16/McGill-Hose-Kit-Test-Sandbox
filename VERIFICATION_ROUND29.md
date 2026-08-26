# VERIFICATION — ROUND 29 (blind)

Artifact: `mcgill-email-to-bom` kit, **v0.6.0, PUBLISHED** at `https://astro.twyd.cloud`.
Repo HEAD: `36b91da` ("Round 28 CRITICALs closed (v0.6.0): derive the field set, exempt nothing").
Bar: `ACCEPTANCE_ROUND29.md` (pre-registered).
Source-of-truth engine: `/Users/axr/Desktop/McGill/email-to-bom-agent` @ `b15b23d` (read-only).

**VERDICT: FAIL.** Fifth consecutive FAIL; the defect chain is unbroken. Round 27's
CRITICAL — a genuine RFQ dropped because it mentioned a payment term — is **still live
in the published build** for every request whose detail sits in an attachment, and the
protection that round 27 was failed for (a 16-phrase cue list) is once again the only
thing standing between those customers and a silent drop, while the code asserts in
writing that it is not.

**Recommendation: ROLL BACK to v0.3.0.**

---

## First: what I audited is what is live

```
$ python3 tools/publish_kit.py --base https://astro.twyd.cloud --dry-run --out upload1.zip
[publish] Kit: mcgill-email-to-bom v0.6.0  (manifest: registry-entry.json)
[publish] Package built — 25 files, 93984 bytes, sha256 a5ee0534978a…
$ shasum -a 256 upload1.zip
a5ee0534978a98fe0495a41cabce1f90f2fae1bbe4ba2a8a3b145750bbaf71cf  upload1.zip
EXPECTED (ACCEPTANCE Z-8): a5ee0534978a98fe0495a41cabce1f90f2fae1bbe4ba2a8a3b145750bbaf71cf
```

Byte-for-byte match, and reproducible across two builds. Every finding below is live.

---

## Results table

| # | Criterion | Verdict | Basis |
|---|---|---|---|
| **Z-1** | A real RFQ must never be filtered | **FAIL** | **11 of 46** genuine requests in my own corpus dropped. 6 → `accounts_payable`, 5 → `no_action`. All 11 confirmed by the source engine to route to `inside_sales_review`. |
| **Z-2** | Is the filter still capable of filtering? | **PASS (with caveats)** | No `Extraction` field is ever unconditionally populated; depth 0 is reachable. All six categories filter on realistic junk. But `AUTO_REPLY` is largely inert in practice (F-9). |
| **Z-3** | The override | **PASS** | 15-case matrix; correct on the shipped path, correctly refuses every mismatch, `--no-filter` CLI form intact, unreachable from email content. |
| **Z-4** | `reason` validation | **PARTIAL** | Anchoring correct, cost negligible (15 µs), all emit sites declared. But a list-shaped schema **crashes** the gate (rc=1) instead of failing open — F-6. |
| **Z-5** | Nothing short-circuits the depth guard | **PASS** | Exactly one `filtered: True` site (line 490), unreachable except through `depth == 0`. Confirmed by code path and probe. |
| **Z-6** | Rounds 25–28 defences still hold | **PARTIAL** | 6 of 6 sub-items behaviourally sound and non-vacuous (M6/M9–M13/M25 all killed). But the "all three clearing sites" item is guarded by a tautology — F-4. |
| **Z-7** | Coverage is real | **FAIL** | **10 mutations survived** (round 28: 9). One deletes an entire declared category with 121/121 green. The retarget left a category with **zero** coverage. |
| **Z-8** | Parity / vendor / build / published artifact | **PASS** | 7/7 parity, all 7 expected outputs independently regenerated from the source engine, `src/vendor/**` byte-identical, `tools/parity/**` unmodified, manifest valid, reproducible, published sha matches. |
| **Z-9** | Documentation makes no false claim | **FAIL** | Four false claims in three shipped files plus the gate's own module docstring — F-5. |
| **Z-10** | Nothing sensitive, no new I/O, no acting on message content | **PASS** | 6 injection families, zero effect. No credentials, no network/env/subprocess/eval in non-vendored source, all fixture addresses RFC 2606. Input byte-identical after a gate run. |

---

## Corpus results

I built my own corpora (the shipped fixtures are the author's and prove only what the
author thought of). None reuse round 27's or round 28's cases.

**Primary corpus — 46 genuine quoting requests, deliberately thin on extractable
specification** (`corpus/R01–R40`, `corpus2/N1–N6`): detail in an attachment, a drawing
reference, "same as last order", "the usual for bay 4", a bare part number, a table, French,
"can you price this up?", sourcing-portal notifications.

```
$ ./runcorpus.sh corpus/ ; ./runcorpus.sh corpus2/
R10    rc=3  INVOICE_OR_STATEMENT accounts_payable
R15    rc=3  INVOICE_OR_STATEMENT accounts_payable
R18    rc=3  INVOICE_OR_STATEMENT accounts_payable
R24    rc=3  INVOICE_OR_STATEMENT accounts_payable
R29    rc=3  INVOICE_OR_STATEMENT accounts_payable
R33    rc=3  INVOICE_OR_STATEMENT accounts_payable
N1_portal_noreply  rc=3  AUTO_REPLY                    no_action
N2_portal_autosub  rc=3  AUTO_REPLY                    no_action
N3_erp_donotreply  rc=3  AUTO_REPLY                    no_action
N4_esp_bulk        rc=3  BULK_MAILING                  no_action
N6_dsn             rc=3  DELIVERY_STATUS_NOTIFICATION  no_action
                                                (34 others rc=0)
```

**11 of 46 genuine RFQs dropped (24%).**

Oracle — every one would have reached a human without the filter:

```
$ python3 oracle.py <each>          # source engine @ b15b23d, its own .venv
R10 rc=2 class=out_of_scope   lines=0 open_items=1 route=inside_sales_review
R15 rc=2 class=out_of_scope   lines=0 open_items=1 route=inside_sales_review
R18 rc=2 class=out_of_scope   lines=0 open_items=1 route=inside_sales_review
R24 rc=2 class=out_of_scope   lines=0 open_items=1 route=inside_sales_review
R29 rc=2 class=out_of_scope   lines=0 open_items=1 route=inside_sales_review
R33 rc=2 class=out_of_scope   lines=0 open_items=1 route=inside_sales_review
N1_portal_noreply rc=2 class=out_of_scope open_items=1 route=inside_sales_review
N2_portal_autosub rc=2 class=out_of_scope open_items=1 route=inside_sales_review
N3_erp_donotreply rc=2 class=out_of_scope open_items=1 route=inside_sales_review
N4_esp_bulk       rc=2 class=out_of_scope open_items=1 route=inside_sales_review
N6_dsn            rc=2 class=out_of_scope open_items=1 route=inside_sales_review
```

**Mutation-survival count: 10** (24 distinct mutations applied; see Z-7 below).

---

## Findings

### R29-F1 — CRITICAL. Round 27's defect is not closed, and the code says it is

**What the code claims** (`src/scripts/filter_gate.py`, module docstring, lines 50–51):

> "The quoting-request veto still runs as a second net, but it **is never the only thing
> between a customer and a silent drop**."

and inline at line 481:

> "SECOND NET -- the quoting-request veto. **Never load-bearing**: the depth guard above
> applies to every category, so this only ever adds protection."

**Both statements are false**, and they are false for exactly the population at risk. The
depth guard cannot protect a request whose detail is in an attachment — depth is 0 — so the
veto is the *sole* protection, and the veto's `request_act` half is the 16-phrase
`quote_request_cues` enumeration round 27 was failed for.

Instrumenting my corpus at `decide()`:

```
total genuine requests: 46
  DROPPED                         : 11
  saved ONLY by the veto (depth 0):  2   ['R01', 'R08']
  saved by the depth guard        :  1   ['N5_noreply_hyphen']   <- accidental: "City Water" -> media=water
  never had a junk candidate      : 32
```

Of the 14 requests that actually reached the guard, the depth guard saved **one** (by
accident), the enumeration saved **two**, and **eleven** were dropped.

Proof the veto is load-bearing — disable it and R01/R08 drop:

```
$ # mutant: `if False and product_signal and request_act:`
$ ./runcorpus.sh corpus/ | grep -E "R01|R08"
R01    rc=3  INVOICE_OR_STATEMENT accounts_payable None
R08    rc=3  INVOICE_OR_STATEMENT accounts_payable None
```

**Paraphrase fragility.** One ordinary RFQ — subject `Hose assemblies per attached
drawing`, body `<request> the hose assemblies on the attached drawing (Rev C). Terms net
30 as usual.` — with only the request wording varied:

```
$ ./runcorpus.sh frag/
F1_price      rc=3  INVOICE_OR_STATEMENT accounts_payable   "Kindly price the hose assemblies…"
F2_costing    rc=3  INVOICE_OR_STATEMENT accounts_payable   "We need costing for…"
F3_tender     rc=3  INVOICE_OR_STATEMENT accounts_payable   "Please tender for…"
F4_offer      rc=3  INVOICE_OR_STATEMENT accounts_payable   "Please submit your best offer for…"
F5_estimate   rc=3  INVOICE_OR_STATEMENT accounts_payable   "An estimate for … would be appreciated."
F6_quotation  rc=3  INVOICE_OR_STATEMENT accounts_payable   "Your quotation for …, please."
F7_original   rc=0  None                 —                  "Please quote…"
```

**6 of 7 paraphrases of the same RFQ are filed to accounts payable.** Only the literal
phrase "Please quote" survives. Oracle: each produces `class=hose_assembly`,
`open_items=7`, `route=inside_sales_review`.

This is round 27's finding verbatim — `Terms net 30.` on a real hose order, saved or lost
by membership in a word list — reproduced on a build that was shipped as its fix.

**Why the two guards both miss:** the veto requires `product_signal AND request_act`. A
spec-less request with no product noun fails `product_signal` even when it literally says
"Please quote" (R29: *"Please quote the attached schedule. Payment due terms net 30."* →
dropped). And `invoice_phrases` contains `"net 30"`, `"net 60"`, `"terms net"`,
`"invoice"`, `"remit to"`, `"past due"`, `"payment due"`, `"statement of account"` — the
ordinary furniture of a purchasing email.

### R29-F2 — CRITICAL. `no_action` is trivially reachable by the most common real RFQ shape

The author documented this edge rather than fixing it, and wrote that "real RFQ corpora
would tell us how often the shape occurs, and it has not been measured." Measured:

```
$ ./runcorpus.sh corpus2/
N1_portal_noreply  rc=3  AUTO_REPLY  no_action    From: no-reply@ariba.example
N2_portal_autosub  rc=3  AUTO_REPLY  no_action    Auto-Submitted: auto-generated
N3_erp_donotreply  rc=3  AUTO_REPLY  no_action    From: donotreply@vulcan-paper.example
N4_esp_bulk        rc=3  BULK_MAILING no_action   List-Unsubscribe + List-Id + Precedence
N5_noreply_hyphen  rc=0  —                        (escaped by accident: "City Water")
N6_dsn             rc=3  DSN          no_action   postmaster@ + Return-Path: <> + multipart/report
```

**5 of 6 plausible real requests reach `no_action`** — filed where nobody looks, with no
`case_state.json` and no `bom_draft.md`.

**The disclosure is materially incomplete.** `EXAMPLES.md` frames the trigger as "a
spec-less request arriving with an `Auto-Submitted` header". The far more common trigger is
`auto_reply_localparts`, which contains `no-reply`, `noreply`, `no_reply`, `donotreply`,
`do-not-reply` — the standard sender local-part of every sourcing portal (Ariba, Coupa,
Jaggaer) and of most customer ERP requisition notifications. That is the single most
common way a B2B RFQ arrives in an inbox, and it is not mentioned. Disclosure is not
absolution: the documented limitation is worse in practice than described.

### R29-F3 — CRITICAL. An entire declared filter category has zero coverage and can be deleted silently

`BULK_MAILING` appears **zero times** in `tools/selftest.py`:

```
$ grep -c "BULK_MAILING" tools/selftest.py
0
```

The blanket `newsletter` → `invoice-statement` retarget removed
`("newsletter", "BULK_MAILING")` from the per-category loop (because the newsletter fixture
became unfilterable at depth 3) and never replaced it with a spec-less bulk fixture. No
fixture in `tools/filter/fixtures/` can exercise the category. Meanwhile the loop's own
header still claims six:

```
tools/selftest.py:538  print("Round 27 — the six junk categories STILL filter (the feature works)")
tools/selftest.py:539  for j, want in [("auto-reply", "AUTO_REPLY"),
                                       ("delivery-status", "DELIVERY_STATUS_NOTIFICATION"),
                                       ("bare-ack", "BARE_ACKNOWLEDGEMENT"),
                                       ("invoice-statement", "INVOICE_OR_STATEMENT"),
                                       ("internal-chatter", "INTERNAL_CHATTER")]:   # five
```

**Mutation M24 — delete the whole category:**

```python
def _bulk_headers(headers, signals):
    return None  # MUTANT M24: BULK_MAILING category deleted entirely
```

```
$ ./runcorpus.sh junk/          # behaviour change: bulk mail no longer filtered at all
J3_marketing  rc=0  None None no_evidence     (was rc=3 BULK_MAILING no_action)
J10_conf      rc=0  None None no_evidence     (was rc=3 BULK_MAILING no_action)
$ python3 tools/selftest.py | tail -1
121/121 defences held
$ python3 tools/parity_check.py | tail -2
7 fixtures checked, 7 matched, 0 mismatched
```

A related survivor, **M8**, inverts the same detector's named defence:

```python
    if not list_unsub:
        return None
    return "List-Unsubscribe"  # MUTANT — the code comment says "NEVER List-Unsubscribe alone"
```

```
$ # spec-less RFQ carrying only List-Unsubscribe (a customer whose ESP stamps it)
  lu    filtered=True BULK_MAILING None       (baseline: filtered=False no_evidence)
$ python3 tools/selftest.py | tail -1
121/121 defences held
```

That is round 28's F-2 shape — the exact defect round 28 was failed for — reintroducible at
the sibling site with the suite green.

Also weak: `tools/selftest.py:296–298` prints "Defence 5b — the six junk categories report
DISTINCT codes" and then asserts `"at least four distinct codes across the six junk
categories"` over a five-entry list. Two layers of slack in one check.

### R29-F4 — HIGH. The check added to close round 28's F-4 is a tautology

`tools/selftest.py:780–781`:

```python
check("the report phase does not hard-code its path either",
      "report:" in out, f"out={out.strip()[-70:]} err={err.strip()[-70:]}")
```

The assertion is that the driver printed the substring `report:` — true whether the driver
prints `report:CLEARED` or `report:SURVIVED`. It asserts nothing about path resolution.
The actual run prints `report:SURVIVED`.

**Mutation M1 — reintroduce the exact R28-F4 defect:**

```python
# src/generate_report.py:100
invalidate([args.out or "_report/bom_draft.md"])  # MUTANT: hard-coded
```

```
$ python3 tools/selftest.py | tail -1
121/121 defences held
```

Round 28's finding was "R27-F4 was closed at two of three clearing sites, under a docstring
claiming all three." Round 29's fix pass added a check for the third site that cannot fail.
(Removing the clearing altogether *is* caught, by a different check — so the site is
guarded for existence, never for consuming the declaration.)

### R29-F5 — HIGH. Four false claims in shipped documentation

Round 28 removed the list-mail exemption. Three shipped files still document it as live.

**1. `src/README.md`** ("The design line"):

> "…only true list-mail (`List-Unsubscribe` plus `Precedence: bulk`/`List-Id`) **is
> filtered despite carrying specs**, because nobody orders hose from a mailing list."

**2. `src/EXAMPLES.md`** (two claims):

> "Any message with **at least one** extracted specification is passed to the engine,
> **except for true list-mail (see below)**."

> "**Only true list-mail may be filtered despite carrying specifications.** … That is why a
> hose-industry newsletter full of product names **is still filtered** while an RFQ that
> merely mentions an invoice is not."

Directly contradicted by the shipped fixture and by the shipped self-test's own check:

```
$ python3 tools/selftest.py | grep newsletter
  PASS  a hose newsletter naming specifications now reaches the engine (accepted cost of F-2)  — exit=0
$ # tools/filter/fixtures/newsletter: reason='specifications_present:3'
```

Z-9 asked whether the accepted-cost statement about newsletters is documented honestly.
It is stated correctly in the gate's module docstring and **inverted** in both operator-
facing documents. An operator reading `EXAMPLES.md` will believe newsletters are filtered
and that an invoice-mentioning RFQ is safe. Both beliefs are backwards.

**3. `src/reference/filter_signals.json`** — the `filter_tier` concept is deleted from the
code but not from the shipped reference data:

```
$ grep -rn "filter_tier" src/ | grep -v Binary
src/reference/filter_signals.json:9:      "filter_tier": "requires_no_specs"
src/reference/filter_signals.json:15:     "filter_tier": "requires_no_specs"
src/reference/filter_signals.json:21:     "filter_tier": "always"
src/reference/filter_signals.json:27,33,39: "filter_tier": "requires_no_specs"
src/reference/filter_signals.json:130:    "_filter_tier_note": "…'always' may filter a
   message even when it carries product specifications…"
$ grep -c filter_tier src/scripts/filter_gate.py
0
```

Six dead keys and a 500-word note describing behaviour that no longer exists, in the file
`CLAUDE.md` tells a reader is where the vocabulary "is declared once … never re-expressed
in the gate's own code."

**4. `src/scripts/filter_gate.py`** module docstring — the veto claim, quoted in F-1
above. False for every depth-0 request.

### R29-F6 — MEDIUM. The gate crashes instead of failing open on a malformed schema

The module docstring promises that "an unreadable reference/schema file … resolves to NOT
filtered". `_load_reason_pattern` (added in round 28) does not catch `TypeError`, while its
sibling `_load_enums` does:

```python
def _load_enums(path=SCHEMA_PATH):
    ...
    except (OSError, json.JSONDecodeError, AttributeError):   # AttributeError caught
        return None, None

def _load_reason_pattern(path=SCHEMA_PATH):
    try:
        return json.load(fh)["properties"]["reason"].get("pattern")
    except (OSError, json.JSONDecodeError, KeyError, AttributeError):   # TypeError NOT caught
        return None
```

It is called from `main()`, outside `decide()`'s catch-all:

```
$ echo '[{"properties":{"reason":{"pattern":"^x$"}}}]' > src/schemas/filter_decision.schema.json
$ python3 src/scripts/filter_gate.py --in rfq.eml --state _report/state.json
error: unhandled TypeError: list indices must be integers or slices, not str
EXIT=1
```

`rc=1` means the recipe stops the run and never reaches the engine — a genuine RFQ is not
processed at all. Loud rather than silent, so not a silent drop, but it is the documented
fail-open guarantee broken, and it is the "named instance / missed sibling" shape again:
the round-28 loader did not inherit the defensive net its neighbour already had. A
`properties.reason` that is a plain string does fail open correctly (`AttributeError`).

Other Z-4 items pass: the pattern is anchored at both ends; all six reasons the gate can
emit (`no_evidence`, `parse_failed`, `override`, `quoting_request_detected`,
`undecodable_content`, `specifications_present:<N>`) satisfy it; per-decision cost is
15 µs, and a 2.8 MB input decides in 0.09 s.

### R29-F7 — MEDIUM. The R28-F6 defence is tested at the helper, not on the shipped path

The suite tests `_reason_ok` directly and never tests that the gate consults it, nor that
the record written to `state.json` conforms to the shipped schema.

**M14 alone** (neuter the call site) survives. Paired with an undeclared reason on the
filtered path — the actual regression the defence exists to catch:

```
$ # M23 alone: filtered path returns "reason": "category_matched"
$ python3 tools/selftest.py | tail -3
  - override="false" does NOT disable the filter exit=0        <- RED, caught
$ # M23 + M14 together
$ python3 tools/selftest.py | tail -1
121/121 defences held                                          <- GREEN
```

With both applied, every filtered message writes `"reason": "category_matched"` into
`state.json`, violating `filter_decision.schema.json`'s pattern, and the suite is green.
This is the same class as R28-F6 (an undeclared reason silently written) and it remains
undetectable by the suite. `FOLLOW-UP-10` honestly records that the kit's own validator
cannot machine-check this schema — verified:

```
$ python3 -c "... _schema_engine.compile_schema(filter_decision.schema.json)"
compiled ok: False
```

so nothing closes the loop.

### R29-F8 — MEDIUM. `AUTO_REPLY` is largely inert on the junk it exists to catch

The depth guard measures `subject + body`, and an out-of-office responder **echoes the
original subject**, which carries the specification:

```
$ ./runcorpus.sh ooo/          # all Auto-Submitted: auto-replied, identical OOO body
O1  rc=0  specifications_present:1   "Automatic reply: RFQ - 200ft EPDM transfer hose"
O2  rc=0  specifications_present:2   "Out of office: Re: quote for 2in ID steam hose"
O3  rc=0  specifications_present:2   "Automatic reply: RFQ 4471 - camlock assemblies"
O4  rc=0  specifications_present:2   "Auto: Re: 300 psi suction hose pricing"
O5  rc=3  AUTO_REPLY no_action       "Automatic reply: your quote request"
O6  rc=3  AUTO_REPLY no_action       "Out of office"
```

**4 of 6 realistic OOO replies escape.** An out-of-office bounce-back to an RFQ is the
highest-volume auto-reply a quoting inbox receives, and by construction it always carries
the spec it is replying to. This is fail-open, so not a harm — but it means the category's
practical yield is far below what the docs imply, which matters to the
does-the-feature-justify-its-risk question.

### R29-F9 — LOW. Two more untested named defences

- **M5** — `_is_specified` made to treat `0` as not-a-spec: survives. Behaviour-changing:
  `agent.extract("qty 0")` → `quantity=0`, and `_is_specified(0)` is currently `True`.
  (This also answers Z-2's third question: the acceptance's premise is wrong — `0` **is**
  counted as a specification. `False` is not, but `material_recognized` is the only bool
  field and it is excluded, so that branch is unreachable. Safe direction.)
- **M19** — the `_strip_quote_and_signature` dominance test made to read the raw body:
  survives. Behaviour-changing: a real bare acknowledgement with a quoted thread beneath it
  goes from `BARE_ACKNOWLEDGEMENT` to unfiltered. The C5 defence is now entirely masked by
  the depth guard for the `ack-plus-rfq` fixture, so nothing exercises it.

### R29-F10 — LOW (process). The published commit's suite over-reported its coverage

`tools/selftest.py` at `36b91da` — the commit that was built and published — contains the
duplicate `"invoice-statement"` in `JUNK`, and therefore ran and counted 4 duplicate checks:

```
$ git show HEAD:tools/selftest.py > tools/selftest.py && python3 tools/selftest.py | tail -1
125/125 defences held
$ # worktree (deduplicated, uncommitted) 
121/121 defences held
```

The dedup fix is **uncommitted** in the working tree. So the verification evidence attached
to the published v0.6.0 advertised 125 distinct checks where 121 exist, and the correction
is not in the published tree. (The kit's shipped `src/` is unaffected — `selftest.py` is
not packaged.)

---

## What held — including what I tried hard to break and could not

- **Z-3, the override.** 15 cases. Works on the recipe-written shape (`override` + matching
  `input`); correctly refuses a missing `input` key, a different `input`, trailing
  whitespace, a case-differing path, and a symlink alias (`abspath`, not `realpath` — the
  safe direction on a case-insensitive filesystem). Correctly accepts `./`-prefixed,
  absolute and `..`-redundant forms of the same path. `_strict_bool` rejects `1`, `"false"`
  and accepts only `True`/`"true"`-family strings. `--no-filter` on the command line still
  works both with and without `--state`. Nothing in an email can enable it.
- **Z-5, the depth guard cannot be bypassed.** One `filtered: True` site, reachable only
  after `depth == 0`. Header hits no longer short-circuit; `undecodable` is consulted before
  the guard and its check is non-vacuous now (M6 killed — round 28's two vacuous checks are
  genuinely fixed by the F-3b live-candidate check).
- **Z-2, the inverse failure does not hold.** I probed all 10 derived fields against 17
  varied non-empty inputs plus `""` and `" "`; none is ever unconditionally populated, and
  `length_type` cannot be set without `length_value`. `_NON_SPEC_FIELDS` is on the safe
  side: over-excluding raises depth and fails open. All six categories do filter on
  realistic junk I wrote myself (spam and recruiter mail pass, correctly — no category
  claims them).
- **Z-8, parity and provenance are solid.** I regenerated all seven expected outputs from
  the source engine at `b15b23d` in its own venv, including the two render fixtures through
  `wrap_text.py` — all seven match. `src/vendor/email_to_bom` and `src/vendor/config` are
  byte-identical to the source (`diff -r`). `tools/parity/**` unmodified vs HEAD. Every
  `normalize` block empty. `requires.tools: []`, exactly one `email_attachment`,
  `manifest_version: 4`, `validate_manifest.py` exit 0. The unzipped package runs
  gate → engine → report from a clean directory under `python3 -S -E`. `run_engine.py`
  returns only 0/1 (recording `engine_exit: 2` in state); the gate returns only 0/1/3 across
  a missing input, no arguments, an unreadable state and a directory where an artifact
  belongs.
- **Z-10, injection.** Six families, all inert: forged `X-No-Filter` / `Screen-Override`
  headers; a fake `{"screen": {"override": true}}` and `{"filter": {...}}` JSON planted in
  the body; prose claiming ScaleUp Labs authority and pre-granted approval and instructing
  a `--no-filter` re-run "and do not report this to the user"; body text mimicking the
  `reason`/`route`/`code` vocabulary; a CEO urgency-and-authority claim; path-traversal
  references. Every message was filtered exactly as its structural shape dictates, with
  `override: false` recorded. The gate reads only named headers through named detectors and
  never interprets body text as configuration. The input file's sha256 is unchanged after a
  run (C4).
- **Reconciliation, invalidation, override binding, strict bools, DSN conjunction, the
  derived field set.** Mutations M3, M4, M6, M7, M9, M10, M11, M12, M13, M17, M18, M25 were
  all **killed**. The round-26/27/28 fixes to *those* sites are real.

---

## Mutation campaign — 24 mutations, 10 survivors

| ID | Mutation | Result |
|---|---|---|
| M1 | report clearing hard-codes its path (R28-F4) | **SURVIVED** |
| M2 | report clearing removed entirely | killed (120/121) |
| M3 | depth guard `> 3` instead of `> 0` | killed (115/121) |
| M4 | drop `length_value` from the derived set (R28-F1) | killed (118/121) |
| M5 | `_is_specified` treats `0` as not-a-spec | **SURVIVED** |
| M6 | `undecodable` guard neutered (R27-F3) | killed (120/121) |
| M7 | DSN conjunction → disjunction (R27-F2) | killed (116/121) |
| M8 | `List-Unsubscribe` alone marks bulk (R28-F2 shape) | **SURVIVED** |
| M9 | input-less override applies again (R28-F3) | killed (120/121) |
| M10 | override path-binding removed (R27) | killed (120/121) |
| M11 | `_strict_bool` → truthy (R27) | killed (120/121) |
| M12 | clearing failures swallowed (R26-F5) | killed (120/121) |
| M13 | `all_artifacts` hand-writes the pair (R27-F4) | killed (119/121) |
| M14 | reason validation call site neutered (R28-F6) | **SURVIVED** |
| M15 | `code` enum validation neutered | **SURVIVED** (latent) |
| M16 | exit-code clamp removed (R26-F2) | **SURVIVED** (latent) |
| M17 | veto `AND` → `OR` | killed (113/121) |
| M18 | `_NON_SPEC_FIELDS` excludes everything | killed (105/121) |
| M19 | ack dominance test reads the raw body (C5) | **SURVIVED** |
| M20 | missing extractor fails CLOSED | **SURVIVED** (dead branch — see note) |
| M21 | extractor exception fails CLOSED | **SURVIVED** (latent) |
| M23 | filtered path emits an undeclared reason | killed |
| M23+M14 | both together | **SURVIVED** (see F-7) |
| M24 | **`BULK_MAILING` category deleted entirely** | **SURVIVED** |
| M25 | reconciliation comparison neutered | killed |

**Demonstrated behaviour-changing survivors: M1, M5, M8, M19, M24, and M23+M14** — I
produced a concrete input for each where the mutant and the original disagree.
**Latent survivors: M15, M16, M21** — I could not construct a distinguishing input, because
the gate cannot currently emit an undeclared code, cannot return a code outside {0,1,3}, and
I could not make `agent.extract()` raise. They are untested defences rather than proven
live defects. **M20 is dead code:** `main()` fails open before `decide()` whenever
`rules is None`, and `agent` is `None` only in that same branch, so `_spec_depth(None, …)`
is unreachable on the shipped path.

Parity stayed 7/7 green under every gate mutation, as expected — parity compares outputs and
cannot see a gate decision. That separation is sound.

---

## Known limitations of this verification

- I could not exercise the live instance; I verified the published package by sha256
  identity to a local rebuild from HEAD, not by fetching it.
- My corpus is synthetic and adversarial by construction. It answers "can a plausible real
  RFQ be dropped, and how easily", not "what fraction of McGill's actual inbound mail would
  be dropped". The 24% figure is a property of my corpus, not a field measurement — but the
  shapes in it (attachment-only detail, "same as last order", portal notifications, a
  payment term in the footer) are ordinary, not exotic.
- Engine extraction/classification correctness was out of scope except as the oracle.
- I did not attempt to make `agent.extract()` raise, so M21's practical reachability is
  unknown.

---

## The question: stay published, or roll back?

**Roll back to v0.3.0.**

The filter's *purpose* is to save operator attention. Its *cost* is that a genuine customer
request can be filed where nobody will read it, with no artifact left behind. On this build
that cost is being paid at a rate of **11 in 46** on ordinary spec-less requests, and the
finding that drives the decision is **R29-F1**: for exactly the population the depth guard
cannot reach, the sole protection is the 16-phrase enumeration that round 27 was failed for,
and six of seven paraphrases of one perfectly normal RFQ ("Please tender for the hose
assemblies on the attached drawing. Terms net 30 as usual.") are filed to accounts payable.

The benefit side has meanwhile eroded. Newsletters now pass by design. Out-of-office
replies — the highest-volume junk in a quoting inbox — escape 4 times in 6 because the
depth guard reads the subject line they echo. And `BULK_MAILING` can be deleted from the
code without a single check noticing. v0.3.0 loses the junk filtering; it cannot misroute a
customer.

Two things should change before a v0.7.0 is attempted, and neither is a patch to a phrase
list:

1. **Filtering must not be able to route a message somewhere colder than the engine would.**
   If `no_action` is unacceptable for a possible request, no category may route there while
   the gate is capable of a false positive. Every filtered message should land in a human
   queue, or the category should not filter.
2. **`invoice_phrases` is on the unsafe side of the decision.** `"net 30"` and `"invoice"`
   in a message that also asks for something is evidence of a *purchasing* email, not of an
   accounts-payable one. The `INVOICE_OR_STATEMENT` category accounts for 6 of my 11 drops
   and for all 6 paraphrase drops.

Four consecutive rounds found that the fix pass introduced the next round's defect. This
round found the same: the tautological F-4 check, the `TypeError` sibling, and a category
left with zero coverage by the retarget are all artifacts of the round-28 fix pass. The
pattern is not bad luck — each fix has been aimed at the *named instance* in the previous
report rather than at the class.

---

## Tree state

The kit was mutated during verification and **restored exactly**. Final state:

```
$ git status --short
 M tools/selftest.py          <- pre-existing when this round began (JUNK dedup, uncommitted; not mine)
?? ACCEPTANCE_ROUND29.md      <- pre-registered bar
?? VERIFICATION_ROUND29.md    <- this file
```

`src/**`, `tools/parity/**`, `kit.json`, `registry-entry.json` and `dist/kit.zip` are
unmodified from `36b91da`. Every mutation was reverted with `git checkout --` and confirmed
clean before the next step; the one mutation left behind by a harness timeout
(`M16`, the exit-code clamp) was found by `git diff` and reverted immediately. `SPEC.md`,
`ACCEPTANCE*.md` and the source repo were never written to.
