# VERIFICATION — round 37 (blind), v0.20.0 at `ea6035c`

Verifier: independent, did not see the build. Inputs: `ACCEPTANCE_ROUND37.md`, the kit tree at
`ea6035c`, the source clone at `6b0a897`, `dist/kit.zip`, and the campaign history
(`CAMPAIGN_RUNBOOK.md`, `.astrocode/PROJECT.md`, `VERIFICATION_ROUND25..36.md`).

**The real kit was never modified.** Every mutation, every forged artifact and every broken-guard
experiment ran against throwaway copies under the session scratchpad (`scratchpad/kit`,
`kit2`, `kit3`, `kit4`, `mut`, `zipkit`). Confirmed at the end of the round:

```
$ git status --porcelain
$ git diff HEAD --stat
$ python3 tools/selftest.py | tail -1
224/224 defences held
$ python3 tools/completeness.py | tail -1
VIOLATIONS: 0 distinct (0 total)
```

Nothing is modified and nothing is untracked except this file.

---

## Verdict: **FAIL**

**The single blocker: `scripts/apply_answers.py` erases the customer's attachments from every
artifact of the run, and flips `outcome` from `needs_human_input` to `complete`.**

It is reproduced below on the recipe's own phase order, first time through, on a plain
non-hostile RFQ with one attached drawing and one ordinary out-of-thread answer. The reply that
gets sent to the customer says **"Attachments: none in the source email"** for a message whose
body says "the dimensions are on the attached drawing". The drawing is named in no artifact at
all. REQ-097 — the operator's own decision, shipped as v0.17.0 — is silently voided by v0.19.0.

This is the campaign's failure shape #5 (a fix that opens a new hole) crossed with #1 (the
sibling nobody looked for): CW-6 re-points `invocation["input"]` at a flat `.txt` that can never
carry a MIME part, and every consumer of "what did the customer attach" reads that field.

Two further findings (H-1, H-2) are in the kit's sharpest feature and are in the same direction
the feature exists to prevent. I judge them serious but **not** independently blocking under the
operator's rule; I say why under each.

**Recommendation: roll v0.20.0 back.** The defect entered in **v0.19.0**, so v0.19.0 is not a
safe target either. **v0.18.0** is the last version without `apply_answers.py`.

---

## Results against the bar

| # | Criterion | Verdict | Basis |
|---|---|---|---|
| K-1 | CW-6: can an operator's words be read as the customer's? | **FAIL** | the marker in customer text fabricates an addendum in the ordinary pipeline (M-2); attribution is sound for `ambiguous` (refuted the author's doubt — see "did not break it"), but `OPERATOR-STATED` is structurally unreachable for **6 of 10** fields (H-2) and the reviewer's document states the *inverse* of the truth for most fields (H-1). |
| K-2 | CW-1: which attachments does the classifier fail to report? | **FAIL** | **four** realistic MIME shapes are dropped with `status: "scanned"` and two empty lists — the one outcome the module docstring says it must never produce (H-3). The author's two suspected holes are both real; a third family (unnamed binary parts) is outside the documented limit entirely. Nested/rfc822/zero-byte/undecodable/300-char-filename all handled correctly. |
| K-3 | CW-4/CW-5: the reviewer's document | **FAIL** (with a refutation) | **I isolated guard 1.** A tampered CaseState + a reply forged through `render_reply.render` satisfies guard 2 and is refused only by guard 1 — proved by deleting guard 1 and watching the forged pair be accepted. The docstring's and runbook's claim that guard 1 "cannot be isolated by a test" is false; the test is given below. Routing is usable and complete (no fourth owner site exists). |
| K-4 | CW-2/CW-3: the run contract | **FAIL** | `outcome_reason` says "no unread attachments" in the same manifest object that names an unread inline file (M-1); `HIDDEN_CONTENT_DETECTED` — "the extracted text may be incomplete" — needs a human and neither ground catches it (M-4); no failure path leaves a manifest and no success path omits one (verified); `KIT_VERSION` drift is caught. |
| K-5 | CW-7 and CW-8 | **PASS** (one L) | `correction_check` accepts only a correctly pinned, byte-exact record and refuses tampered/CRLF/mismatched ones; the freshness checks import the **shipped** `src/vendor` module, and `_freshness` has no path that over-claims (`find_candidates` falls back to the revision unless every fact agrees). One low finding: the tool echoes reviewer-supplied text unescaped (L-1). |
| K-6 | the rounds 25–36 defences still hold | **PARTIAL** | every defence I could drive still fails closed (battery below). `augmented_input.txt` being exempt from `ARTIFACTS` is **not** right (M-3) — it is the nineteenth instance of the shape, and this time it is the exception clause the bar itself asked me to confirm. |
| K-7 | coverage, and report the number | reported | **30 of 83 applied mutations survived all four suites (36%)**; honest subset **23/76 (30%)**. Not comparable with 65→39→32→25 — see below. CaseState fidelity **16/17 strict, 17/17 shipped-path**. Three checks found that cannot fail in the direction that matters. |
| K-8 | parity, vendor, shipped artifact, docs | **FAIL** (docs only) | parity **7/7 regenerated by me from the source engine's own venv**; `src/vendor/**` byte-identical to the clone at `6b0a897`; `validate_manifest.py kit.json` exits 0; **I rebuilt the published package and got sha `852edc2f67a008cd…`, 30 files, nothing unintended**; zip == `src/`; all phases run from the unzipped zip under `python3 -S -E`; zero `email_attachment` tags. **Docs: six false claims, one of them self-contradicted inside a single shipped file** (M-5). |
| K-9 | nothing sensitive, nothing acts on message content | **PASS** | no credential in repo or zip; all fixtures `.example`; **zero** network/env/subprocess/eval in non-vendored `src/`; injections planted in an email, an answers file and a correction record are wholly inert in `reply.md` and `review_request.md` (no forged col-0 structure, no control or bidi characters). |

---

## C-1 (BLOCKER) — one operator answer erases the customer's drawing from the whole run

### What it is

`apply_answers.py` writes `_report/augmented_input.txt` and re-points
`state.json`'s `invocation["input"]` at it. From that moment every consumer of "what did the
customer attach" reads the **augmented text file**, not the customer's email:

* `run_engine.build_manifest` → `attachments.scan(invocation["input"])`
* `render_reply.main` → `attachments.scan(invocation["input"])`
* `render_review.main` → `attachments.scan(invocation["input"])`

`augmented_input.txt` is a flat `.txt` produced from `mail.extract_rfq_text`. By construction it
can never carry a MIME part, so the scan returns `{"status": "scanned", "attachments": [],
"embedded": []}` — which `attachments.py`'s own docstring calls *"the only form that means
'there is nothing the engine missed'"*.

`apply_answers.py` records the original for exactly this reason:

```python
"answers": {"original_input": source, "original_sha256": input_sha256(source), ...}
```

and its docstring says *"the original input's path and hash are recorded in `state.json` so a
later phase can always get back to what the customer actually sent."* **Nothing reads them:**

```
$ grep -rn "original_input\|original_sha256" src/scripts/*.py src/generate_report.py | grep -v apply_answers.py
(no output)
```

### Reproduction — the recipe's own phase order, first run, no re-runs

`n_flip.eml` (RFC 2606 domains) — a `multipart/mixed` with a text body and
`Content-Disposition: attachment; filename="assembly-drawing-D2291.pdf"`. Body:

```
Please quote 4 assemblies of 1 inch ID EPDM hose, 10 ft each, male NPT both ends,
for cold water at 60 psi and 70 F. Material 316 stainless braid.
The fitting layout and all the dimensions are on the attached drawing.
```

`answers3.json` — one ordinary answer: `{"answer": "Length convention is overall length (OAL).",
"answered_by": "Chris Lee", "code": "LENGTH_TYPE_MISSING"}`.

```
### prepare -> apply_answers -> extract_case -> generate_report   (recipe order)
$ python3 scripts/apply_answers.py --answers answers3.json --state _report/state.json    # rc=0
$ python3 scripts/run_engine.py --from-state --state _report/state.json --out _report/case_state.json
$ python3 generate_report.py   --out _report/bom_draft.md      --state _report/state.json
$ python3 scripts/render_reply.py  --out _report/reply.md      --state _report/state.json
$ python3 scripts/render_review.py --out _report/review_request.md --state _report/state.json

$ grep -n "^Attachments" _report/reply.md
6:Attachments: none in the source email
$ grep -n "^Outcome:" _report/review_request.md
4:Outcome: complete — 3 open item(s), none blocking a quote; no unread attachments
$ python3 -c "import json;m=json.load(open('_report/run_manifest.json'));print(m['outcome']);print(m['outcome_reason']);print(json.dumps(m['evidence_not_read']));print(m['input']['path'])"
complete
3 open item(s), none blocking a quote; no unread attachments
{"status": "scanned", "attachments": [], "embedded": [], "error": null}
_report/augmented_input.txt

$ grep -rl "assembly-drawing-D2291" _report/
(nothing — the drawing appears in NO artifact of this run)
```

### The same case without the answer, for contrast

```
outcome : needs_human_input
reason  : 1 attached file(s) the engine never read (assembly-drawing-D2291.pdf);
          the case was derived without them
reply   : Attachments: 1 the engine did NOT read — see EVIDENCE NOT READ below
stderr  : warning: the customer sent 1 file(s) the engine does not read
```

Side by side, one operator answer changes:

| | without the answer | with it |
|---|---|---|
| `reply.md` line 6 (**what is sent**) | `Attachments: 1 the engine did NOT read — see EVIDENCE NOT READ below` | `Attachments: none in the source email` |
| `EVIDENCE NOT READ` block | present, names the file | gone |
| `run_manifest.outcome` | `needs_human_input` | `complete` |
| `outcome_reason` | names the drawing | "no unread attachments" |
| `evidence_not_read` | names the drawing | `scanned`, empty |
| `review_request.md` | `UNREAD  assembly-drawing-D2291.pdf …` | nothing |
| `run_engine` stderr | warning | silent |
| `manifest.input.sha256` | the customer's email | the kit's own intermediate file |

### Why it blocks

The reply is the document the kit tells you to send verbatim. It tells the customer that the
email they sent carried no attachment, and then asks them for the length convention and the
selection that were on the drawing. The reviewer is told the case is `complete`. Nothing in any
artifact says a file went unread. The drawing's existence has been deleted from the run's whole
record, including its provenance: the manifest's `input.sha256` is now the sha of
`augmented_input.txt`, so the customer's email is not identified anywhere, and a CW-7 correction
pinned to this run pins to the kit's own scratch file.

That is a wrong answer and a missing answer reaching a customer. Per the operator's stopping
rule, it blocks.

### Why no suite caught it

Every CW-6 selftest uses the `plain-steam` fixture, which has no attachments:

```
$ sed -n '1127,1240p' tools/selftest.py | grep -c 'workdir(("rfq.eml", "plain-steam"))'
4
```

and `tools/completeness.py` renders with `--no-reconcile`, which forces
`attachments.not_checked(...)` — so 184 combinations never exercise a scan either. The
CW-1 × CW-6 interaction is unrepresentable by the fixtures that exist.

### The fix is small, and it is a one-line contract change

Attachments are a property of **what the customer sent**, not of what the engine read. The three
scan sites should resolve the ORIGINAL input — which `state["answers"]["original_input"]`
already records — and fall back to `invocation["input"]` when no addendum was applied. The
manifest's `input`/`sha256`/`idempotency_key` should likewise identify the customer's email.
**Do not ship the fix on inspection**: twelve of twelve previous rounds found the defect in the
previous fix pass.

---

## H-1 — the reviewer's document states the inverse of the truth for most fields

`render_review._uncertainty` (lines 105–108):

```python
for name, verdict in answers_mod.operator_fields(case, customer_text, operator_text).items():
    out.append(f"  OPERATOR  {_safe(name)} came from an operator's answer, "
               f"not the customer ({_safe(verdict)})")
```

`operator_fields` returns **every verdict that is not `customer`** — which includes
`unattributable` and `ambiguous`. The prose is hard-coded and asserts the operator as the source
regardless.

### Reproduction

Customer email (`k_clean.txt`) says only: `1 inch ID`, `10 ft long`, `male NPT both ends`,
`cold water`, `60 psi`, `70 F`. The operator's two answers say only: *"Material is 316 stainless
braid"* and *"They need 4 assemblies."*

```
$ python3 scripts/apply_answers.py --answers answers2.json --state _report/state.json
$ ... extract, reply, review ...
$ sed -n '/WHY THIS NEEDS YOU/,/BEFORE YOU APPROVE/p' _report/review_request.md

  OPERATOR  length came from an operator's answer, not the customer (unattributable)
  OPERATOR  material came from an operator's answer, not the customer (unattributable)
  OPERATOR  media came from an operator's answer, not the customer (unattributable)
  OPERATOR  quantity came from an operator's answer, not the customer (unattributable)
  OPERATOR  size came from an operator's answer, not the customer (unattributable)
```

`length` (10 ft), `media` (water) and `size` (1 ID) are the **customer's own words**. Three of
the five statements are false, and the two that are true (`material`, `quantity`) are
indistinguishable from them. On a second case the same section asserted it of `material` and
`quantity` when the engine had captured **no value at all** for either (`status: missing`), and
of `pressure` with verdict `(ambiguous)` — which the module defines as "cannot be told apart"
and the reply's own legend explains as "the same words appear in both".

### Severity

The review request is not sent to the customer, so under the operator's rule this does not block
on its own. It is one step from doing so: the documented reviewer actions are approve / **edit**
/ reject / reassign / escalate, and a reviewer told the customer never stated the size will ask
the customer to confirm a size they already gave — which is precisely the re-asking CW-6 exists
to remove, inverted onto the customer.

### Why no check caught it

`CW-4d` ("every GROUND for review is stated as one") uses a fixture with no addendum, so the
operator branch is never exercised there. Its only coverage is one substring test in CW-6:

```python
check("and the review request names it as a ground for review",
      "OPERATOR" in review_header_of(d, sh, REVIEW))
```

A presence test on the literal `"OPERATOR"` cannot fail while the prose is false. **This is a
fourth check that cannot fail in the direction that matters** — the author found three; this is
the one they did not think to look for.

---

## H-2 — `OPERATOR-STATED` is structurally unreachable for 6 of the 10 fields

`answers.classify` locates a field's **evidence span**. When the engine records no span it
returns `UNATTRIBUTABLE` before looking at anything else:

```python
if not span:
    return UNATTRIBUTABLE
```

Across the 31 real CaseStates in my corpus (26 adversarial runs + the 5 JSON parity fixtures)
the distribution is not close:

| field | with an evidence span | without |
|---|---|---|
| `end_1`, `end_2` | 31 | 0 |
| `pressure` | 27 | 4 |
| `temperature` | 25 | 6 |
| `customer`, `length`, `material`, `media`, `quantity`, `size` | **0** | 31 |

So the mark works for the two end connections, the pressure and the temperature, and is
**unreachable** for material, quantity, length, size, media and customer — the fields a reviewer
actually answers in Teams.

### Reproduction

Same run as H-1. `material` and `quantity` were supplied **entirely** by the operator (neither
word appears anywhere in the customer's text), and the reply renders:

```
material    | 316 SS                                   | captured
quantity    | 4                                        | captured
```

with **no mark**, in a table where `temperature` and `pressure` do carry marks — and the banner
above states, falsely:

```
  These fields record no evidence span, so they cannot be attributed to either
  author: length, material, media, quantity, size
```

`material` and `quantity` are attributable, trivially: only one author mentioned them.

### Severity

Not blocking on its own: the banner directly above the table says *"Nothing here has been
confirmed BY THE CUSTOMER"*, so the customer-facing document does not claim the customer
confirmed 316 SS. It is a stated-guarantee break — `EXAMPLES.md` says *"Every document
downstream marks the fields that came from the addendum `OPERATOR-STATED`"*, which is false —
and it makes the reviewer's list (H-1) undifferentiated.

---

## H-3 — four realistic MIME shapes are silently dropped: "Attachments: none" for a message that had one

`attachments._classify` drops a part in two places:

```python
if disposition != "attachment" and not filename:
    return None, None                     # (a) anything unnamed that is not marked `attachment`
...
if maintype == "text" and subtype in _BODY_SUBTYPES:
    return None, None                     # (b) ANY text/plain or text/html not marked `attachment`
                                          #     -- even when it has a filename
```

The module's stated limit covers only an **unnamed** second inline text part. Branch (b) fires
for named ones too, and branch (a) is outside the stated limit entirely.

### Reproduction — one command, eight shapes

```
$ python3 -c "import sys;sys.path.insert(0,'src/scripts');import attachments;..."
named_txt_nodisp     reported=0     Content-Type: text/plain; name="specification.txt"
named_txt_inline     reported=0     Content-Disposition: inline; filename="specification.txt"
named_html_inline    reported=0     Content-Disposition: inline; filename="drawing-notes.html"
pdf_nodisp_noname    reported=0     Content-Type: application/pdf   (no disposition, no name)
rfc822_inline        reported=0     Content-Type: message/rfc822; Content-Disposition: inline
named_txt_attach     reported=1     (correct)
pdf_inline_named     reported=1     (correct)
pdf_nodisp_named     reported=1     (correct)
```

End to end, on an RFQ carrying an attached `specification.txt`
(`Content-Disposition: inline; filename="specification.txt"`) whose contents are
`Material: 316 stainless braid / Length: 25 ft / Working pressure: 150 psi`:

```
$ grep -n "^Attachments" _report/reply.md
6:Attachments: none in the source email

$ sed -n '/CONFIRM/,/WHAT THE EMAIL/p' _report/reply.md
    [MATERIAL_CONFIRM] Material not confirmed as a specific grade. …
    [QTY_MISSING]      Quantity not stated …
```

The reply asks the customer for the material they attached, while asserting they attached
nothing. `run_manifest.evidence_not_read` is `{"status": "scanned", "attachments": [],
"embedded": []}` — byte-identical to a plain-text email that genuinely had no attachment, so a
consumer cannot tell the two apart.

I also confirmed the engine reads only the **first** text part, so a second one is both unread
and unflagged:

```
$ python3 -c "from email_to_bom.mail import extract_rfq_text; print(repr(extract_rfq_text(open('g_second_text.eml','rb').read())[-120:]))"
'…Thanks,\nDana Ruiz\nPurchasing, Example Manufacturing'    # the spec part is absent
```

### Severity

I rank this **just below the blocker** rather than beside it, honestly: branch (b) with a
filename and branch (a) both need a sender that omits `Content-Disposition: attachment`, which
the common clients do not. It is a real false statement in the sent document when it fires, and
it violates the module's own stated invariant. Fix `_classify` to fall through to `attachments`
whenever a part carries a **filename**, whatever its disposition, and to record any non-`text`
part it cannot place.

---

## M-1 — the manifest says "no unread attachments" in the object that names one

An inline drawing with a `Content-ID` — the Outlook "paste the picture into the body" shape — is
classified `embedded`. `derive_outcome` reads `evidence["attachments"]` only, so:

```
$ python3 -c "import json;m=json.load(open('_report/run_manifest.json'));print(m['outcome']);print(m['outcome_reason']);print(json.dumps(m['evidence_not_read']))"
complete
3 open item(s), none blocking a quote; no unread attachments
{"status":"scanned","attachments":[],"embedded":[{"filename":"assembly-drawing-D2291.png", …}],"error":null}
```

on an email whose body says *"the fitting layout and all the dimensions are in the drawing pasted
below"*. The review request's `WHY THIS NEEDS YOU` names only two `UNSURE` fields; the file
appears nowhere in it (`_uncertainty` iterates `evidence["attachments"]` only). The reply names
it on the headline.

The **rule** (an inline signature image does not force a human) is the operator's and I do not
re-litigate it. What I report is that the manifest states `no unread attachments` as a fact in
the same object that lists one, and that the classifier cannot tell a signature logo from a
dimensioned drawing. Not blocking: the file is named in the sent document.

## M-2 — the marker in a customer's own text fabricates an operator addendum

`apply_answers.py` refuses when the RFQ already contains `answers.MARKER` (verified: it does).
But `answers.split()` is also called by `run_engine`, `render_reply` and `render_review` on
**any** input, with no such refusal. A `.txt` RFQ whose body contains the marker produces:

```
$ grep -n "OPERATOR ANSWERS" _report/reply.md
10:OPERATOR ANSWERS WERE ADDED TO THIS CASE — the text below is NOT the customer's words
$ python3 -c "import json;print(json.load(open('_report/run_manifest.json'))['operator_addendum'])"
{'present': True, 'lines': ['Operator answer to MATERIAL_MISSING - from Chris Lee at 2026-09-01:', …]}
```

No operator supplied anything. The customer's own later sentences are printed under a banner
saying they are not the customer's words, a person who never touched the case is named as having
answered it, and the reply tells the customer *"Nothing here has been confirmed BY THE
CUSTOMER"* about their own email. Requires a hostile or very unlucky input (the marker is a
long em-dashed string), so it does not block — but it is a fabrication in the opposite direction
from the one the feature was built to prevent, exactly as the bar predicted.

## M-3 — `augmented_input.txt` is not right as an `ARTIFACTS` exemption

The bar asked me to confirm this. It is not right.

```
### customer A: prepare -> apply_answers -> full run
### customer B: prepare (fresh state.json) -> full run, no answers
$ ls _report
augmented_input.txt  bom_draft.md  case_state.json  reply.md  review_request.md  run_manifest.json  state.json
$ cat _report/augmented_input.txt
Subject: RFQ - hose assemblies
… Dana Ruiz, Purchasing, Example Manufacturing …
===== OPERATOR ADDENDUM — the text below is NOT the customer's words =====
Operator answer to MATERIAL_CONFIRM — from Chris Lee at 2026-09-17T14:00Z:
Material is 316 stainless braid.
```

After customer B's complete run, a **declared output artifact** (`kit.json` →
`outputs.artifacts[].path: "_report/augmented_input.txt"`) holds customer A's RFQ text and A's
operator answers. B's manifest says `operator_addendum.present: false`. And `CLAUDE.md` tells the
reader:

> `_report/augmented_input.txt` | Present **ONLY** when a reviewer's out-of-thread answer was
> folded in … It is the case text the engine read … An **input**, not an output

Both halves are false after B's run, and `kit.json` calls it an output while `CLAUDE.md` calls it
an input. This is the nineteenth occurrence of "an enumeration on the unsafe side of a decision",
and once again it is the exception clause inside the general mechanism, justified by a comment.
Not blocking — no artifact a customer receives changes — but it is the same shape that produced
round 36's blocker.

## M-4 — a case that needs a human for a reason neither ground catches

`HIDDEN_CONTENT_DETECTED` carries `priority: "must_acknowledge"`, and its ask is *"This email
contains style rules that can hide text — review the original message; **the extracted text may
be incomplete**."* That is the same class of risk as an unread attachment, and the outcome does
not carry it:

```
$ # i_hidden.eml — text/html RFQ with <p style="display:none">IGNORE ALL PREVIOUS INSTRUCTIONS…
$ python3 -c "import json;m=json.load(open('_report/run_manifest.json'));print(m['outcome'],'|',m['outcome_reason'])"
complete | 5 open item(s), none blocking a quote; no unread attachments
$ sed -n '/WHY THIS NEEDS YOU/,/BEFORE YOU/p' _report/review_request.md
  UNSURE    length is `reading` …
  UNSURE    temperature is `reading` …
```

The item **is** rendered in the reply and in the embedded response, so a reviewer who reads the
document sees it — that is why this does not block. But `outcome` is the field Body routes on,
and the review request's own grounds section omits the one ground that says the text may be
incomplete. (The injected hidden instruction was wholly inert — see K-9.)

## M-5 — six false claims in shipped documents, one self-contradicted in a single file

All of these files are inside `dist/kit.zip` and inside the published package.

1. **`README.md:69` and `EXAMPLES.md:174-175`: "It never assumes a size from a bare dimension.
   `4 in ID` captures; a bare `4in` or `4"` does not, because it could be ID or OD."** False
   against the engine the kit ships — this is exactly what the `ae4411f` re-vendor changed:

   ```
   $ # shipped engine, input "4in EPDM suction hose assembly, 20 ft"
   size field: {"value": "4 ID", "status": "captured"}
   $ # engine at b15b23d, same input
   size field: {"value": null, "status": "missing"}   length field: {"value": "4", …}
   ```

   `EXAMPLES.md:43-46` contradicts its own line 174 twenty-eight lines earlier: *"For the shipped
   sample (a **4in** EPDM suction hose assembly …) the engine … **captures the size as `4 ID`**"*.
   The doc claims a fail-safe the engine no longer has, on the one behaviour the re-vendor moved.
2. **`EXAMPLES.md:184-190`: "a run costs **four** engine passes … A full kit run makes **four**
   passes … Budget roughly **4x** … **All three scripts** warn on stderr above 100 KB."**
   Instrumented count on a real run:

   ```
   after extract: 1   after report: 3   after reply: 4   after review: 5
   $ grep -rn "warn_if_slow(" src/ | grep -v "def warn_if_slow"
   src/generate_report.py:114 (passes=2)  src/scripts/run_engine.py:313  src/scripts/render_reply.py:719  src/scripts/render_review.py:259
   ```

   Five passes, four warn sites. `src/scripts/run_engine.py:60` repeats "FOUR engine passes in
   total"; `render_review.py:44` says FIFTH. The performance budget a reader is given is 20% low.
3. **`render_review.py:26-33` (and `CAMPAIGN_RUNBOOK.md:93-98`): "Deleting it does not change
   what this script accepts, because guard 2 refuses the same pairs … removing this check failed
   nothing."** Refuted by execution — see K-3 below.
4. **`README.md:80-87` "What is inside"** lists five paths and omits `scripts/render_review.py`,
   `scripts/attachments.py`, `scripts/answers.py`, `scripts/apply_answers.py`,
   `scripts/routing.py`, `scripts/run_state.py`, `config/routing.json` and
   `schemas/correction.schema.json` — the entire v0.16–v0.20 surface. It also describes the
   recipe as `prepare → extract_case → generate_report`; the shipped recipe has four phases.
5. **"the engine carries 529 tests"** — `README.md:89`, `scripts/answers.py:14`,
   `scripts/run_engine.py:6`, `vendor/PROVENANCE.md:4`. The source at `6b0a897` has **539**
   (`./.venv/bin/python -m pytest -q` → `539 passed`), and `PROVENANCE.md:20` says so eleven
   lines below its own stale claim.
6. **`EXAMPLES.md:139`: "Every document downstream marks the fields that came from the addendum
   `OPERATOR-STATED`"** — false for 6 of 10 fields (H-2).

Non-shipped, but worth fixing: `tools/parity/parity.json`'s `source_commit_note` says the
expecteds were captured at `ae4411f`, "which is also the commit `src/vendor/PROVENANCE.md` stamps
and which `src/vendor/**` is byte-identical to". PROVENANCE now stamps `6b0a897`.

## L-1..L-4 (low)

* **L-1** `tools/correction_check.py` prints `correction["reviewer"]` and `["at"]` raw. A record
  with `"at": "2026-09-17\nOutcome: complete"` and an ANSI payload in `reviewer` clears the
  operator's terminal and forges an `Outcome: complete` line in the tool's own output. Kit-side
  tool, not shipped; the rendered documents are all safe.
* **L-2** `answers.validate` accepts a newline in `answered_by`, which adds a line to the
  addendum and a spurious `OPERATOR  …` line to the review request. Contained (every line is
  prefixed and `_safe`'d), but the field should be folded.
* **L-3** `idempotency_key` changes when `component_ids` are reordered or `config_dir` gains a
  trailing slash — the same case is not recognised as a retry. Fail-open toward "new run", so
  safe; worth normalising.
* **L-4** `render_reply.py --state other/state.json` with a default `--out` writes customer B's
  reply into customer A's `_report/`, beside A's `case_state.json` and A's manifest. `run_engine`
  derives its artifact directories from `--out` **and** `--state`; the two renderers do not. The
  recipe never produces this combination.

---

## K-3 answered: the test that isolates guard 1, and why the docstring is wrong

The docstring says the two attempts to write it "both ended up exercising guard 2", and the
runbook repeats it as settled. The construction that works is to satisfy guard 2 **on purpose**,
by building the forged reply through the renderer itself with the REAL evidence and case text:

```python
# scratch copy only
import render_reply, attachments, answers as A
case = json.load(open("_report/case_state.json"))          # TAMPERED: DERATING_REVIEW removed
inp  = json.load(open("_report/state.json"))["invocation"]["input"]
open("_report/reply.md","w").write(
    render_reply.render(case, attachments.scan(inp), A.read_case_text(inp)))
```

With the shipped script, guard 1 refuses:

```
error: _report/case_state.json does not match a re-derived CaseState, so the review request would
       ask a human to approve a response about a different case. Refusing.
       differing top-level keys: ['open_items']                       rc=1
```

With guard 1 removed (`if False and replayed != case:`) in a scratch copy, the same pair is
**accepted**:

```
wrote _report/review_request_forged.md (6669 bytes, outcome=needs_human_input)   rc=0
$ grep -n "^Outcome:\|BLOCKING" _report/review_request_forged.md
4:Outcome: needs_human_input — 1 attached file(s) the engine never read (…)
   (no BLOCKING line at all)
$ # the engine's actual output for this input:
   true blocking items: ['DERATING_REVIEW']
```

The reviewer would approve a case with the derating check — *"Pressure at 350 °F needs a derating
check by inside sales (engine never derates — TESTREPORT-2.5)"* — silently deleted. Guard 1 is
load-bearing and independently observable. It is **not covered** (mutation `rev-01` survived all
four suites), which is a coverage gap, not a defect: the shipped code is correct. What is wrong
is the claim, in a shipped file and in the runbook, that no such check exists.

I found no pair that slips past both guards. The realistic forgery route —
`render_reply.py --no-reconcile` — always stamps `Attachments: NOT CHECKED`, which guard 2
catches; REQ-093 holds.

---

## The two numbers

### Combined mutation survival: **30 of 83 applied = 36%** (honest subset **23 of 76 = 30%**)

84 mutations, each a semantic weakening of one defence in the shipped non-vendored source, each
applied alone to a scratch clone and scored against **all four suites** (selftest 224,
completeness 184, parity 7, golden 2). Scored by exit code **and** by the suites' own summary
lines, so a suite that crashes counts as CAUGHT — the harness failure mode the author named.
One mutation did not apply (`ans-04`, pattern absent). Total wall time 31m32s.

Seven survivors are semantic no-ops I verified rather than defence removals (`att-03` —
`_BODY_SUBTYPES` is gated on `maintype == "text"`; `rr-07` — `[] or X` is `X`; `re-01` — every
call site passes `passes=` explicitly; `app-05`, `rev-10` — `_rc` is already 0/1; `st-13`,
`rev-11` — the same refusal via a different error path). Excluding them: **23/76 = 30%**.

The survivors that are real defence removals, and what each un-guards:

| mutation | what stops being true |
|---|---|
| `ans-02` `AMBIGUOUS → CUSTOMER` | a value appearing in BOTH regions is reported as the customer's — the single thing `answers.py` exists to prevent |
| `ans-09` `UNATTRIBUTABLE → CUSTOMER` | a span-less field is reported as the customer's |
| `ans-08` fold punctuation too | a looser match turns operator words into the customer's |
| `ans-03` split on the LAST marker | an operator pasting the marker shrinks the operator region |
| `ans-10` report only `OPERATOR` | `SOURCE UNCLEAR` and the unattributable list vanish |
| `att-04` unreadable → `scanned` | a file that could not be read reports "nothing was missed" |
| `att-02` drop the disposition half of the guard | an `attachment` part with no filename vanishes |
| `att-07` swallow a part that raises | a part that cannot be inspected vanishes |
| `att-06` `total()` ignores `embedded` | the extract-phase warning stops firing for inline-only |
| `att-09` size always `None` | every attachment renders "size unknown" |
| `app-01` no marker refusal | a second addendum can be stacked on a case that already has one |
| `app-04` keep `extract_case` | a stale extract record survives an addendum |
| `rou-05` skip `open_items[].route` | the open item's owner disappears from the review request |
| `rou-07` malformed table → empty table | "nobody configured" and "could not read" collapse |
| `rev-01` delete guard 1 | **demonstrated above** — a forged pair is accepted |
| `rev-04` do not clear `review_request.md` | **verified**: a failed render leaves customer A's review request on disk, naming A's drawing |
| `rev-08` drop the NOT ROUTABLE explainer | the reviewer is not told the gap needs filling |
| `rr-06` drop `SOURCE UNCLEAR` | the ambiguous mark vanishes from the table |
| `rr-12` drop the unattributable list | span-less fields are silently unmarked |
| `rr-14` count inline parts without naming them | a file the customer sent appears nowhere by name |
| `st-09`, `st-10` key ignores `config_dir` / `component_ids` | two genuinely different runs share an idempotency key |
| `st-14` guess the engine commit | the manifest attributes the engine when it cannot read the stamp |

**Is 36% comparable to 65% → 39% → 32% → 25%?** **No, and not only because the engine changed.**
Three things moved at once: (i) the engine is `6b0a897`, not `b15b23d`; (ii) the suite grew from
106 to 224 checks; and (iii) — the decisive one — **my catalogue is aimed at the five scripts
added on 2026-09-17**, which are the least-covered code in the kit, where the earlier rounds'
catalogues were aimed at `render_reply.py` and `run_state.py`, which have absorbed twelve rounds
of hardening. 51 of my 84 mutations target files that did not exist when 25% was measured. Read
36% as a first measurement of the new surface, not as a movement from 25%.

### CaseState fidelity: **16/17 strict, 17/17 shipped-path** (round 36: 15/17 and 16/17)

Method as in rounds 35/36: a full-shape synthetic CaseState carrying a unique sentinel in all 17
top-level keys and 52 leaf positions, rendered through `render_reply.render`, then every sentinel
searched for in the page.

```
sentinels: 52  present: 51  MISSING: 1
MISSING: ['ZQXextmatZQX']        # extraction.material
  bom_columns FAITHFUL   checkpoints FAITHFUL   class_evidence FAITHFUL   classes FAITHFUL
  extraction  LOSS       fields FAITHFUL        knowledge FAITHFUL        lines FAITHFUL
  logged_attempts FAITHFUL  notes FAITHFUL      open_items FAITHFUL       questions FAITHFUL
  request_class FAITHFUL    routing FAITHFUL    schema_version FAITHFUL   supersedes FAITHFUL
  urgency FAITHFUL
```

Round 36's `bom_columns` blocker is **closed** — the sentinel reaches the page with `lines == []`.
The one remaining strict gap is `render_reply.py:585`'s `k not in fields` filter: an
`extraction` sub-key whose name collides with a field name is dropped on the assumption it is a
duplicate. I checked that assumption on all 31 real CaseStates — every shared key is an exact
duplicate of the `fields` entry, including `customer`, `material`, `size`, `pressure` and
`temperature` — so it is **not** a shipped-path loss today. It is a latent one if the engine ever
lets the two diverge.

---

## What I tried that did NOT break it

Recorded so the failures are auditable too.

**Parity and provenance — fully reproduced, non-circular.**
* All **7** expected outputs regenerated by me from the source clone's own venv
  (`~/Desktop/McGill/email-to-bom-agent/.venv/bin/python -m email_to_bom.cli`), five via `--json`
  and two rendered through `tools/parity/wrap_text.py`. **7/7 match** the committed expecteds.
  (The first `confirmed-ids` attempt mismatched because `--component-ids` greedily ate the
  positional input path — my error, not the fixture's; with the input first it matches exactly.)
* `diff -r -x __pycache__ src/vendor/email_to_bom <clone>/email_to_bom` → no output; same for
  `config/`. `PROVENANCE.md`'s claim that `ae4411f..6b0a897` touched only `knowledge.py` matches
  the clone's own `git diff --stat` (`knowledge.py` + `tests/test_knowledge.py`).
* Source suite: **539 passed in 2.35s**.

**The shipped artifact.**
* `dist/kit.zip` sha256 `e834794356…` == `kit.json`'s `sha256` field; 29 files; unzipped tree is
  byte-identical to `src/` (modulo `__pycache__`).
* **I rebuilt the published package with `tools/publish_kit.py`'s own `build_package`** and got
  `852edc2f67a008cd1791686080ba42ce76b31ed0afa3f8c79ef17e382da9525d` — 30 files, `kit.json` at
  the root, every other entry present in `src/`, **nothing unintended**. That is the sha the
  runbook read back from the instance.
* `python3 tools/validate_manifest.py kit.json` exits 0. **Zero** `email_attachment` tags.
* All four phases run from the unzipped zip, from a clean directory, under `python3 -S -E`,
  producing all six artifacts.

**Defences that held under direct attack.**
* Reconciliation fails closed in all three consumers on a tampered CaseState
  (`generate_report` 1, `render_reply` 1, `render_review` 1) and each clears its own artifact
  first, so `bom_draft.md`, `reply.md` and `review_request.md` are all gone afterwards.
* `--coc`, `--component-ids` and `--config-dir` survive the phase boundary through all four
  phases and appear whole in the manifest's `invocation`.
* A failed extraction leaves **no** manifest, **no** CaseState, and **preserves** the prepare
  phase's `invocation` while dropping `extract_case`.
* A read-only `_report/` makes clearing fail **loudly** and stops the run.
* Every wrapper returns only 0 or 1 across ten failure modes, including argparse errors.
* `apply_answers` refuses when the RFQ already contains the marker, and its round-trip guard
  fires on a forwarded thread whose body carries `From:`/`Subject:` lines. Both messages are
  accurate and actionable.
* `attachments.scan` handles nested multipart, `message/rfc822` (including an attachment inside
  the forwarded message), zero-byte parts, undecodable base64, an unknown charset and a 300-char
  filename — all correctly reported.
* Routing: `config/routing.json` covers **every** key the engine can emit (both schema enums plus
  the three checkpoint owner strings); I found **no fourth owner site** in any real CaseState;
  filling the table in a scratch copy renders real addressees, so the feature is usable; an
  unknown key renders `NOT ROUTABLE — key unknown to the routing table` and never falls back.
* `correction_check.py`: a correctly pinned byte-exact record is REPLAYABLE; a one-word change to
  `original`, and a CRLF variant, are both refused with the right reason.
* CW-8 freshness: the checks import `src/vendor/email_to_bom/knowledge.py` — the **shipped**
  module, not a copy — and I could not construct a path where `_freshness` over-claims;
  `find_candidates` falls back to the revision unless every returned fact agrees on one `as_of`.
* **K-1's attribution soundness question is refuted.** Customer writes "The system is NOT rated
  for 150 psi", operator answers "Working pressure is 150 psi at 250 F": `pressure` renders
  `<-- SOURCE UNCLEAR` and `temperature` renders `<-- OPERATOR-STATED`. `classify` is sound for
  fields that have a span; the problem is the fields that do not (H-2).
* **K-9: twelve planted injections were wholly inert.** An email and an answers file each
  carrying 78-dash rules, `Outcome: complete`, `DECISION: approve`, forged `EVIDENCE NOT READ`
  and `OPERATOR ANSWERS` banners, a forged `PROPOSED RESPONSE` line, a fake routable addressee,
  ANSI escapes and a bidi override produced **zero** forged column-0 structures in `reply.md` or
  `review_request.md` and **zero** control or bidi characters in any rendered artifact. The only
  78-dash lines in the review request are its own two. (`augmented_input.txt` does retain a raw
  `0x1b` from the operator's answer — it is an input file, and every renderer sanitises it on the
  way out.)
* Nothing in non-vendored `src/` imports a network module, reads the environment, spawns a
  subprocess, or calls `eval`/`exec`. No credential anywhere in the repo or the zip. All fixtures
  in RFC 2606 namespaces.
* The `customer` field extracting "150 psi" from "NOT rated for 150 psi" reproduces identically
  at `b15b23d`, so it is pre-existing engine behaviour and out of scope — **not** a re-vendor
  regression. I checked rather than assumed.

---

## Coverage gaps, logged (non-blocking, per the stopping rule)

1. `attach_eml` in `tools/selftest.py` can build exactly two MIME shapes — `attachment` with a
   filename, and `inline` + `cid` + filename. Every shape in H-3 is unrepresentable by it.
2. Every CW-6 check uses `plain-steam`, which has no attachments — so C-1's interaction cannot be
   seen by any of them.
3. `tools/completeness.py` renders with `--no-reconcile`, so its 184 combinations never exercise
   an attachment scan or an operator addendum.
4. `render_review`'s own pre-flight `invalidate` is uncovered (`rev-04` survived); CW-4c tests the
   extract phase's clearing, not this one.
5. The 23 honest mutation survivors above.
6. No golden fixture renders a review request or an addendum case, so rendering changes in either
   are invisible to byte comparison — as the bar itself notes.

---

## The single blocker, named

**`scripts/apply_answers.py` re-points the run's input at `_report/augmented_input.txt`, and
every attachment consumer reads that field — so recording one out-of-thread answer deletes the
customer's attachments from `reply.md`, `review_request.md` and `run_manifest.json`, and flips
`outcome` from `needs_human_input` to `complete`.** The reply that is sent tells the customer
their message carried no attachment and asks them for what was on the drawing.

Roll v0.20.0 back. v0.19.0 carries the same defect; **v0.18.0** is the last version without it.
