# VERIFICATION — ROUND 33 (blind, independent)

**Artifact:** `mcgill-email-to-bom` kit v0.10.0, HEAD `9bb3bad` ("Correct the engine pass count: four, not three")
**Bar:** `ACCEPTANCE_ROUND33.md`, pre-registered before this verifier was spawned
**Source of truth:** `/Users/axr/Desktop/McGill/email-to-bom-agent` @ `b15b23d`, its own `.venv/bin/python` (3.14.6)
**Verifier saw:** ACCEPTANCE_ROUND33.md, the kit tree, the source repo, VERIFICATION_ROUND25–32.md. Nothing of the build.

## VERDICT: **FAIL**

Nine for nine. Two CRITICAL findings. Both are the campaign's own documented failure shapes,
landing inside the round-32 fix pass:

* **C-1** — a customer can put a **fabricated price** into `reply.md` on the shipped path with no
  flags and no tampering, 42 lines above the reply's own footer swearing no price appears.
* **C-2** — the check the author added in round 32 *specifically* to stop "a check that passes for
  the wrong reason" is pointed at the one fixture of five that cannot exercise it. Reverting the
  round-31 fix leaves the suite at **69/69 green** while the reply shows CAPTURED end connections
  as `—`.

**Mutation survival: 22 of 57 valid mutations (39%).** Down from round 32's 33/51 (65%) — a real
improvement, credited below. Still 22.

**CaseState key faithfulness: 12 of 17 rendered whole, 2 partial, 3 absent** (strictly: 9 whole
without a lossiness caveat). Round 32 measured 10 / 4 / 3.

**Is v0.10.0 safe to publish? No.** C-1 is customer-reachable and manufactures the one content
class the kit exists to never produce. Everything else could wait; C-1 cannot.

---

## Q-1 .. Q-8 results table

| # | Subject | Verdict | Why |
|---|---|---|---|
| **Q-1** | `_safe()` coverage and the Unicode gap | **FAIL** | Unicode gap is live and worse than named (C-1). One render site misses `_safe()` entirely: raw ESC reaches the page (H-1). |
| **Q-2** | Reconciliation: false refusals and cost | **PARTIAL** | No false refusal reproducible — named weakness #2 **REFUTED** for the shipped kit. But the fourth pass is undocumented in two places and unwarned (M-2/M-3/M-4). |
| **Q-3** | Tested path ≠ shipped path | **FAIL** | Confirmed as named, plus: no parity fixture renders `reply.md` at all, and `tier`/`citation` are unreachable in any kit run. |
| **Q-4** | Completeness of the reply | **FAIL** | `questions[].rule_id` present in `bom_draft.md`, absent from `reply.md` — the reply is a strict subset where docs claim a superset. Priority value droppable. Truncation loses data. `UNCONFIRMED` set: **complete** (held). |
| **Q-5** | Rounds 25–31 defences | **PASS** | Every named defence held under direct probing; failures fail closed and loud. |
| **Q-6** | Coverage / mutation survival | **FAIL** | 22/57 survived (39%). Round-31 F-3's two checks cannot fail for either mechanism individually. |
| **Q-7** | Parity, vendor, artifact, docs | **PARTIAL** | Parity 7/7 independently regenerated; vendor 12/12 byte-identical; zip runs clean under `-S -E`. **Eight false doc claims** (M-1..M-8). |
| **Q-8** | Nothing sensitive, nothing acts on content | **PASS** | Clean. Injections planted; nothing in the pipeline acted on any of them. |

---

## CRITICAL

### C-1 — A customer can display a fabricated price in the reply. Shipped path, no flags.

`_safe()` handles ANSI and C0/C1. It does nothing about Unicode bidi. `U+202E` (RIGHT-TO-LEFT
OVERRIDE) is honoured by every mainstream mail client in plain text and HTML alike.

The `quote` of a `CUSTOMER_QUESTION_UNANSWERED` item is echoed **verbatim** — the strongest
customer-controlled channel in the CaseState. Reproduction, from a bare email through all three
recipe phases:

```
$ cat rfq.eml            # payload bytes are reversed; U+202E makes them display forward
... Can you confirm the price agreed at $9700?   <- as DISPLAYED
... ‮0079$ ta deerga ecirp eht mrifnoc uoy naC‬?   <- as STORED

$ python3 src/scripts/run_engine.py   --from-state --state _report/state.json --out _report/case_state.json
$ python3 src/scripts/render_reply.py --out _report/reply.md --state _report/state.json
wrote _report/reply.md (3296 bytes, 5 open items, 1 BOM lines)
```

`_report/reply.md`, verbatim, twice (lines 23 and 26):

```
    [CUSTOMER_QUESTION_UNANSWERED] Acknowledge and route: ‮0079$ ta deerga ecirp eht mrifnoc uoy naC‬?
        quote: ‮0079$ ta deerga ecirp eht mrifnoc uoy naC‬?
```

and at line 64 of the same file:

```
No price, lead time or stock position appears above: the engine produces none.
```

In the operator's mail client those two lines read **"Can you confirm the price agreed at $9700?"**
The kit's document asserts a price cannot appear; a price appears; the customer chose the number.
`render_reply.py`'s own docstring lists "never state a price, a lead time or a stock position"
as a thing it must never do "because the whole engine is built the other way."

The author named the Unicode gap as known-and-unaddressed, framed as line-reordering and hidden
text. That framing understates it. RTL override does not merely reorder — it lets the customer
author **arbitrary display text** inside the kit's own document, and the highest-value payload is
exactly the content class the kit is built to never emit. This is not cosmetic.

Also confirmed live: `U+200B` (ZWSP) and `U+00AD` (soft hyphen) survive `_safe()` — two visually
identical strings carry different bytes, and an operator's Ctrl-F for the customer's words fails:

```
  - ZW​​JOIN
  - SOFT\xadHYPH
```

Held, for the record: `U+2028`/`U+2029` **are** folded — `str.split()` treats them as whitespace.
That half of the gap is closed by accident, not by design; nothing tests it (see R06).

**Fix direction:** `_safe()` must strip or escape `Cf` (format) characters, or at minimum
`U+200B–U+200F`, `U+202A–U+202E`, `U+2066–U+2069`, `U+00AD`, `U+FEFF`. Stripping is safer than
escaping for a plain-text body.

---

### C-2 — Round 32's replacement check is pointed at the one fixture that cannot fail it.

Round 31 found the reply rendering a CAPTURED end connection as `—` (end connections carry
`family`/`gender` and no `value`). Round 32's H-3 replaced the field check with one asserting
CONTENT, not just names:

```python
check("every field's VALUES appear in the reply, not just its name", not _missing, ...)
```

It is bound to a single fixture, `plain-steam` (`tools/selftest.py:383`).

I reverted the round-31 fix — one line, `value = _safe(f.get("value"), 40) or "—"` — and ran the
suite:

```
$ python3 tools/selftest.py | grep -E "every field's VALUES|defences held"
  PASS  every field's VALUES appear in the reply, not just its name  — dropped: []
69/69 defences held
```

The reply the reverted renderer actually produces, from the shipped `suction-assembly` fixture:

```
Field       | Value               | Status                     | Evidence
------------|---------------------|----------------------------|-----------
end_1       | —                   | captured                   | hose shank
end_2       | —                   | captured                   | kam
pressure    | —                   | reading  <-- NOT CONFIRMED | suction
```

Round 31's defect verbatim, suite green. Running the check's own logic across all five JSON
fixtures shows why:

```
  plain-steam          round-32 H-3 check -> PASS (cannot see the bug)  missing=[]
  suction-assembly     round-32 H-3 check -> FAIL  missing=["end_2.family='camlock'", "end_2.gender='male'"]
  quoted-printable     round-32 H-3 check -> PASS (cannot see the bug)  missing=[]
  multipart-html       round-32 H-3 check -> PASS (cannot see the bug)  missing=[]
  confirmed-ids        round-32 H-3 check -> FAIL  missing=["end_2.family='camlock'", "end_2.gender='male'"]
```

Two of five fixtures would have caught it. The check is driven by one of the three that cannot.
On `plain-steam`, every field token the check looks for appears somewhere in the page regardless —
`end_1.family='shank'` is satisfied by the **Evidence** column (`hose shank`), which the check
excludes from its loop but the renderer still prints.

The author fixed the check's *logic* in round 32 and left it pointed at a fixture that cannot
exercise it. That is the same defect class the fix was written to end, one round later.

**Fix direction:** drive this check over every JSON fixture, and assert the token appears in the
field's **own table row**, not anywhere in the page.

---

## HIGH

### H-1 — `_safe()` is missed at exactly one render site: `schema_version`. Raw ESC reaches the page.

`render_reply.py:279` is the only interpolation in `render()` of CaseState-sourced data that does
not pass through `_safe()`:

```python
    L.append(f"  schema_version: {case.get('schema_version')}")
```

Synthetic CaseState with `schema_version: "2.0\x1b[2K\x1b[G  C9 [CLEARED] owner=QC (R-QC)"`:

```
$ python3 -c "r=open('_report/reply.md',encoding='utf-8').read(); print('ESC present:', '\x1b' in r)"
ESC present: True
LINE repr: '  schema_version: 2.0\x1b[2K\x1b[G  C9 [CLEARED] owner=QC (R-QC)'
```

`\x1b[2K\x1b[G` erases the line and returns the cursor to column 0. In any terminal or pager the
line renders as `  C9 [CLEARED] owner=QC (R-QC)` — round 32's C-1 defect, reproduced verbatim,
through the one field the fix did not cover.

The three selftest checks written for C-1 — "no ESC byte survives into the reply", "no control
character survives", "no ESC byte survives from any rendered field" — all pass, because the
synthetic CaseState sets `schema_version: "2.0"`. **They cannot fail on this route.**

Q-1 asked: *"Does `_safe()` get applied at EVERY point untrusted text reaches the page? Enumerate
the render sites and find one it misses."* Answer: no; this one. Q-1 → FAIL.

**Scope, honestly:** `SCHEMA_VERSION` is a module constant in `src/vendor/email_to_bom/core.py:93`,
so a customer cannot set it, and reconciliation refuses a hand-edited CaseState. This is a
defence-in-depth breach and a false invariant, not a live customer exploit. It is exactly the
"hardened the siblings, missed one" shape the bar predicted, in the file the bar predicted.

### H-2 — An open item's `priority` value is never printed, and the item can be dropped undetected.

`_ITEM_HEADLINE = ("code", "ask", "quote", "priority")` excludes `priority` from the
every-other-key loop, on the assumption the group header carries it. For a priority outside
`PRIORITY_ORDER` the header is the literal string `(OTHER PRIORITY)`:

```
  (OTHER PRIORITY)
    [NEW_CODE_X] UNKNOWN-PRIORITY item
```

The actual value — `emergency_escalate` in my synthetic — appears **nowhere in the reply**. The
comment at line 182 promises "never silently omit an item with a new priority": the item survives,
its priority does not. For an escalation priority a future engine adds, the reply presents it as
ranking below `blocking`, unlabelled.

Mutation **R18** (drop the leftover group entirely) **survived**: the item can vanish completely
with the suite green.

### H-3 — The 40/48-character truncation silently drops the data "render whole records" exists to preserve.

`render_reply.py` truncates field values to 40, evidence to 48, BOM cells to 40. Live on the
shipped path, from a stock adversarial email through all three phases:

```
temperature | candidates=['250f', '633c'], kind=confl… | conflict  <-- NOT CONFIRMED | 250f / 633c
pressure    | candidates=["'suction' (vacuum service)… | conflict  <-- NOT CONFIRMED | ...
```

Synthetic, showing the shape at its worst:

```
end_1        | family=camlock, gender=male, size=4in, … | captured  | male KAM x hose barb
                          ^ thread=NPT-TAPERED and sleeve=plated steel are GONE

Component ID
MCG-ASSY-4IN-EPDM-SUCTION-PLATED-STEEL-…
```

A **truncated part number in a bill of materials**. The round-31/32 fix replaced "guess one key"
with "show every attribute the engine set" and then capped the result at 40 characters, so the
whole-record guarantee holds only for short records. Mutation R30 (limit → 3) *is* caught, so the
suite notices catastrophic truncation and not the real thing.

### H-4 — The reply LOSES information `bom_draft.md` carries, where every document claims the opposite.

`questions[]` is dropped from the reply. It is not the redundant twin the bar hypothesised: its
`text` duplicates `open_items[].ask`, but its **`rule_id` is unique to it** — `open_items` has no
`rule_id`. Measured on the shipped `suction-assembly` fixture:

```
R-CMTR in draft: 1
R-CMTR in reply: 0
rule_ids in case_state.questions: ['R-CATALOG','R-CMTR','R-EXTRACT','R-LENGTH','R-PRESSURE','R-TEMPERATURE']
```

`bom_draft.md` prints all six (`... (R-CMTR)`, `... (R-PRESSURE)` …). `reply.md` prints none.
Against:

* `render_reply.py:4-7` — *"Everything an operator needs is in the message body, including the parts `bom_draft.md` deliberately drops"*
* recipe, phase 2 — *"The reply already carries everything `bom_draft.md` drops"*
* `CLAUDE.md` — `bom_draft.md` is *"A **lossy** view kept for parity, not for sending"*

The recipe then tells the agent to send `reply.md` and **not** to attach anything, so an operator
who receives only the reply cannot trace any question to its governing work instruction. The
"lossy" artifact is a strict superset in this respect.

Also absent, and not redundant:

* **`extraction.end_fittings`** — the fixture email says *"male KAM x hose barb"*; the CaseState's
  `extraction.end_fittings` is `["SHANK","BARB","KAM"]` while `fields` has only `end_1=shank`,
  `end_2=camlock`. `grep -ci barb reply.md` → **0**. A fitting the customer named reaches the
  CaseState and dies in the renderer.
* **`class_evidence`** (`"hose"`) — the token that decided `request_class`, and `request_class`
  decides which fields even apply. Absent.

### H-5 — Round-31 F-3's two exit-code checks cannot fail for either mechanism they guard.

`run_engine.py` has three overlapping layers: the `except SystemExit` handler in `run_engine()`,
the `except BaseException` handler in `__main__`, and the clamp `SystemExit(0 if _rc == 0 else 1)`.
The two checks assert only `rc in (0, 1)`, so **any single deletion is invisible**:

```
mutation E04 (delete the except SystemExit handler)         -> SURVIVED
mutation E03 (delete the clamp)                            -> SURVIVED
both deleted together:
  PASS  run_engine: engine SystemExit(2) cannot escape as exit 2  — exit=1
  SUITE STILL GREEN with BOTH defences deleted
```

Round 31's finding was that the clamp's deletion left the suite green because no case drove
argparse inside `cli.main`. The fix added a case that does — and still cannot fail, because a
third layer catches it. Behaviour today is safe (triple-guarded); the *check* is vacuous, which is
how the next regression gets in.

### H-6 — Mutation survival: 22 of 57 (39%).

Full run: 35 killed, 22 survived, 1 invalid (find-string absent — E02's `drop=` tuple had been
restructured). Comparable in construction to round 32's 51.

**Killed (35)** — the round-32 fixes are genuinely guarded, and this is the real improvement:
every `_safe` gutting (R01–R05), every whole-record loop in `open_items` / `checkpoints` /
`lines` / `routing` (R08, R09, R13, R14, R15), `classes`/`Applies` (R16), urgency (R17),
supersedes (R20), logged_attempts (R21), both reconciliations and both fail-closed returns
(R31, R32, G01, G07), reply invalidation (R34), `--no-reconcile` defaulting on (R36),
`invalidate` going silent (S01), the invocation whitelist (S02), all three `build_argv` flags
(S03–S05), `all_artifacts` hand-writing paths (S07), and the extract phase's whole-run clearing
(E01).

**Survived (22), triaged:**

*Real, uncovered defences:*
| Mutation | What it removes |
|---|---|
| R07 | the C1/`0x9B` strip — every control check tests only `ord(c) < 0x20` |
| R06 | the whitespace fold — the only handler for `U+2028`/`U+2029` |
| R10 | the round-31 field-value fix (**C-2**) |
| R12 | `UNCONFIRMED` shrunk to `{"reading"}` — a status renders as confirmed |
| R18 | unknown-priority items dropped entirely (**H-2**) |
| R19 | `notes` dropped — and this makes the C-1 forgery checks *more* likely to pass, since they assert absence |
| R22, R23 | the summary header lies about blocking count / open-item count |
| R29 | the no-price footer removed (the quote check tests only the header) |
| S06 | `ARTIFACTS` loses the `reply` declaration — no reply equivalent of the "renamed declaration" checks exists |
| S08 | `write_state` swallows failures — loudness is undefended |
| E03, E04, G04, R35 | exit-code layers (**H-5**) |

*My mutation was a no-op or masked — not scored against the kit:* G02 (a later `open()` fails
closed anyway), G05 (duplicated an existing branch), R33/R37 (downstream failures still return 1),
E05/E06 (masked by fixture naming / later parse failure). I list these rather than bank them.

Also: **no parity fixture renders `reply.md`.** Parity is 7/7 and says nothing about the artifact a
human reads. That is why 28 of round 32's 33 survivors were in this file, and why `selftest.py`
alone carries it.

---

## MEDIUM — the documentation

Every round 25–32 found a false claim. This round found eight, **two of them inside the commit
whose entire purpose was to correct the pass count.**

**M-1** `src/EXAMPLES.md:143` — the bullet's bold heading still says **three**, two lines above the
corrected body saying four:

```
- **Large threads are slow, and a run costs three engine passes.** A single pass
  ...
  100 KB. A full kit run makes **four** passes: ...
```

**M-2** `src/scripts/run_engine.py:54-57` — shipped source, untouched by the correction:

```python
# Past this size the engine's runtime grows superlinearly, and a kit run makes
# THREE engine passes in total (one here, two in generate_report.py), so the real
# cost is ~3x a single pass.
```

**M-3** `src/scripts/render_reply.py:9-14` — the worst of the three, because it denies the file's
own headline v0.10.0 feature:

```
This reads `_report/case_state.json` and nothing else. That is deliberate and
different from `generate_report.py`, which re-runs the engine ...: there is no
upstream text to be byte-identical to here, so re-running would buy nothing and
cost a third engine pass. The CaseState IS the contract, and it was already
reconciled against a replayed extraction by `generate_report.py`.
```

The script re-runs the engine 33 lines below this paragraph. A reader auditing whether the reply is
checked would conclude from the docstring that it is not.

**M-4** `src/EXAMPLES.md:150` — *"Both scripts warn on stderr above 100 KB."* Three scripts now make
engine passes. `grep -c warn_if_slow src/scripts/render_reply.py` → **0**. The fourth pass is
unwarned, so the reply phase can silently take as long as the extract phase on a large thread.

**M-5** Agent-facing guardrail, missing sibling. `CLAUDE.md` — *"**Never bypass a reconciliation
failure.** If `generate_report.py` refuses …"*; recipe phase-2 constraint — *"A reconciliation
failure means **the draft** would contradict the CaseState."* Both name only the draft.
`render_reply.py --no-reconcile` was introduced in the same commit and has no agent-facing rule,
while its own `--help` says "never in a real run." An agent hitting the reply's refusal is
instructed by nothing.

**M-6** `src/EXAMPLES.md` — *"**Two schema values the engine cannot emit** … `status: "superseded"`
and `knowledge.lookups[].op: "ratings_for"`."* The status half is **correct** (I drove all ten
others; see below). The lookups half is not: `cli.main` constructs `Agent(cfg)` with no knowledge
argument, so `self.knowledge` is always `NullKnowledge`, whose methods never call `_record`.
**All five `op` values are unreachable in a kit run,** and `lookups` is always `[]`. The bullet's
purpose is telling integrators what not to branch on, and it implies the other four are reachable.

**M-7** `registry-entry.json` — `provides.scripts` is `["generate_report.py",
"scripts/run_engine.py"]`. `scripts/render_reply.py` — the script that produces the primary
deliverable — is absent, and `git log -S'render_reply' -- registry-entry.json` returns nothing.
Shipped metadata for v0.10.0 does not know about it.

**M-8** "Knowledge provenance" is advertised in `CLAUDE.md`'s deliverables table, in the recipe, and
in `render_reply.py`'s docstring as a reason the reply supersedes the draft. It is structurally
always:

```
  knowledge source: none
  knowledge lookups: 0
```

`src/README.md:98` is honest about this (*"the live-knowledge adapter exists in `vendor/` but is
dormant and not wired into this kit"*). The three documents that sell the reply are not.

**M-9** Q-3 confirmed as named: the synthetic block renders with `--no-reconcile`, a flag no real
run passes. Two further points the bar did not name: because reconciliation requires the CaseState
to equal a fresh engine replay, whole-record rendering **can only** be exercised through that flag;
and `tier`/`citation` (MUST-APPEAR-TIER, MUST-APPEAR-CITATION) sit on the knowledge-sourced
`CAPABILITY_ANSWER_READY` branch (`core.py:800-809`), unreachable in any kit run. The catalog-sourced
branch at `core.py:793` carries `quote` and `items` and **is** reachable — so round 32's C-2 was a
real defect, correctly fixed.

---

## LOW

**L-1** `_ANSI`'s second alternative `\x1b[@-Z\\-_]` matches the two-byte `\x1b]` of an OSC
sequence, leaving printable residue (`0;title`) in the page; the `\x07` terminator is stripped by
`_CONTROL`. Cosmetic — the residue cannot start a line. 8-bit CSI (`0x9B`) *is* handled, by the
C1 range in `_CONTROL`, not by the regex. A lone `\x1b` split across two adjacent fields is
stripped by `_CONTROL`, so no ESC survives that route.

**L-2** `render_reply.py:307` — `out = args.out or os.path.join("_report", "reply.md")` hard-codes an
artifact filename, against `run_state.py`'s `all_artifacts` docstring: *"neither ever hard-codes a
filename."* I tried to turn this into a behavioural defect and **failed**: `artifact_paths()`
overrides re-create the key, so a renamed declaration still resolves and still clears loudly:

```
$ # ARTIFACTS["reply"] renamed to "message_body" (key gone), stale reply.md planted, _report read-only
error: cannot clear the previous run's _report/reply.md: [Errno 13] Permission denied ... Refusing to continue
rc=1
```

The `except (StateError, KeyError)` at line 310 is therefore dead for `KeyError` — a branch that
can never fire. Contract inconsistency, not a hole.

**L-3** Bidi and zero-width characters defeat `str.ljust`, so the fields table visually
misaligns whenever they are present.

---

## CaseState key faithfulness — 12 / 2 / 3

| Key | Verdict | Note |
|---|---|---|
| `request_class` | whole | |
| `classes` | whole | `Applies:` |
| `routing` | whole | recommendation + reasons + any unread key |
| `bom_columns` | whole | drives the table |
| `checkpoints` | whole | every extra key rendered |
| `notes` | whole | droppable undetected (R19) |
| `supersedes` | whole | |
| `logged_attempts` | whole | |
| `schema_version` | whole | **unsanitised** (H-1) |
| `open_items` | whole* | `priority` value never printed for an unknown priority (H-2) |
| `fields` | whole* | truncated at 40 / 48 (H-3) |
| `lines` | whole* | truncated at 40, including Component ID (H-3) |
| `urgency` | **partial** | only `flagged`; `phrases` dropped — recoverable via `routing.reasons` (`urgent: asap, rush`) only when routing recommends |
| `knowledge` | **partial** | only `source`/`revision`/`lookups`; always empty in practice (M-8) |
| `class_evidence` | **absent** | the token that decided `request_class` |
| `questions` | **absent** | **`rule_id` is lost** (H-4) |
| `extraction` | **absent** | `end_fittings` carries a fitting no field does (H-4) |

Round 32: 10 whole / 4 partial / 3 absent. Strictly counting the three starred keys as partial:
9 / 5 / 3.

---

## What I tried that did NOT break it — so the pass legs are auditable

**Named weakness #2 (false refusal) is REFUTED for the shipped kit.** I could not make the
reconciliation reject a legitimate run:

```
10 consecutive reply renders, each reconciling                       -> 10/10 reconciled
PYTHONHASHSEED sweep, extract in {0,1,12345,99999} x reply in {0,7,4242} -> 12/12 reconciled
absolute input path in the invocation record                          -> reconciled
alternate --config-dir (selftest's ALTCONFIG fixture)                 -> reconciled
```

The engine has no clock, randomness, run-id or absolute path on the `cli.main` path. The **one**
nondeterministic value anywhere in it is `ms = int((time.monotonic() - t0) * 1000)`
(`knowledge.py:281-294`), written straight into a lookup record by `_record`'s `entry.update(extra)`.
It reaches the CaseState only through `McpKnowledge`, which `cli.main` never instantiates — so it
cannot fire. **Latent landmine worth recording:** if knowledge is ever wired in, `ms` differs
between passes, and *both* reconciliations refuse *every* run permanently — no draft and no reply,
with an error telling the operator to re-run the phase that will fail again. v0.10.0 doubled the
blast radius of that future bug by adding the second reconciliation.

**The `UNCONFIRMED` set is complete.** Q-4 asked me to drive the statuses with no fixture. I built
four emails and drove all six, plus `conflict` and `assumed`. Every one is marked:

```
  [gender]  end_1 status=missing_gender          marked=True
  [flange]  end_1 status=missing_spec            marked=True
  [triclmp] end_1 status=size_confirm            marked=True
  [code61]  end_1 status=configuration_confirm   marked=True
            fluid_detail status=assumed          marked=True
  (earlier) temperature status=conflict          marked=True
```

`superseded` is the only enum value with zero literal occurrences in the engine — the EXAMPLES.md
claim is right. The set is complete against everything emittable. It is still hand-written, and
R12 shows a future status renders as confirmed with the suite green, so `status != "captured"`
would be the structural form.

**Parity 7/7, regenerated by me from the source engine's own venv** — not by running the kit's
checker:

```
$ .venv/bin/python -m email_to_bom.cli <fixture> --json [--component-ids ...]
  MATCH  suction-assembly / plain-steam / quoted-printable / multipart-html / confirmed-ids
  MATCH  human-render / confirmed-ids-render   (via tools/parity/wrap_text.py)
```

(My first attempt "mismatched" two fixtures — my own argv error: `--component-ids` with `nargs="*"`
swallows a trailing input path. `run_state.build_argv` puts the input first and avoids this. The
kit is right; I was wrong.)

**Vendor byte-identity: 12/12 files identical** to `email-to-bom-agent@b15b23d` (8 `.py`, 4 config
JSON), with no source file left unvendored. `PROVENANCE.md` is specific and honest about the
`b1f9950` / `b15b23d` distinction.

**The zip runs all three phases from a clean directory under `python3 -S -E`:**

```
phase 0 rc=0 / phase 1 rc=0 / phase 2a rc=0 / phase 2b rc=0
  OK  _report/reply.md (2937)  _report/case_state.json (4438)  _report/bom_draft.md (1684)
files created outside _report/: none
```

`shasum` of `dist/kit.zip` matches `kit.json` **and** `registry-entry.json`; 22 zip entries and
`contents[]` are identical sets; `validate_manifest.py kit.json registry-entry.json` exits 0;
`requires.tools` is `[]`; **zero** `email_attachment` tags on any artifact.

**Q-8 is clean.** Non-vendored source: no `os.environ`/`getenv`, no `subprocess`, no `socket`/
`urllib`/`requests`, no `eval`/`exec`/`__import__`/`pickle` — zero matches. The vendored engine's
`urllib` use is confined to `McpKnowledge`/`TwydIngestion`, unreachable from `cli.main`, with no
credential literals (a `token_provider` callable). No secrets anywhere. Fixtures are in the RFC 2606
reserved `.example` TLD (`northside.example`, `acmedairy.example`, `mcgillhose.example`). I planted
ANSI erase sequences, bare CR/BS, bidi overrides, zero-width characters, forged `[CLEARED]`
checkpoint lines and an unknown open-item priority: **nothing in the pipeline acted on any of
them.** Every one was either neutralised or rendered as inert data — with the two exceptions
recorded as C-1 and H-1.

**Q-5 held under direct probing.** Flags survive the phase boundary; draft and CaseState agree;
both reconciliations fail closed; a reconciliation refusal leaves no `reply.md`; clearing failures
are loud (reproduced with a read-only `_report/`); `--config-dir` survives; a failed phase
preserves the prepare record.

---

## Tree integrity

All mutation and adversarial work was done on **copies** under
`/private/tmp/.../scratchpad/`. The kit tree was never modified.

```
$ git status --porcelain
?? ACCEPTANCE_ROUND33.md          # pre-existing, expected
$ git diff --stat HEAD
                                  # (empty — no tracked file changed)
$ python3 tools/selftest.py | tail -1
69/69 defences held
$ python3 tools/parity_check.py | tail -2
7 fixtures checked, 7 matched, 0 mismatched
```

The working tree is clean and byte-identical to `9bb3bad` apart from this file and the
pre-registered acceptance bar. Nothing was patched; nothing was fixed.

---

## Recommendation

**Do not publish v0.10.0.** The instance serving v0.3.0 is worse in every other respect, and that
argues for shipping *something* soon — but not this build with C-1 open, because C-1 is the first
finding in this campaign where a customer can put fabricated financial content into the artifact a
human reads, unaided, on the shipped path.

Ordered:

1. **C-1** — strip Unicode `Cf`/bidi in `_safe()`. One function, and it closes the only
   customer-reachable finding in this report.
2. **H-1** — route `schema_version` through `_safe()`. One line. Then make one selftest check
   render a CaseState whose `schema_version` carries the payload, so the route can fail.
3. **C-2** — drive the field-values check over every fixture and scope the assertion to the
   field's own row.
4. **H-4** — render `questions[].rule_id`, `class_evidence` and `extraction`, or stop claiming the
   reply is a superset of the draft. Do not do the latter: the rule ids are the audit trail.
5. **H-2 / H-3** — print the priority value; raise or remove the truncation limits for Component
   IDs and multi-attribute fields.
6. **M-1 .. M-8** — eight false claims. Grep for every count and capability the docs assert and
   check each against the code, rather than fixing the instances this report names.

And a process note, offered because eight consecutive rounds have had the same cause: **M-1 and M-2
were introduced by the commit that fixed M-1's sibling.** The pass-count correction edited two
files and left the same claim standing in two others, one of them the shipped script. A grep for
the claim would have found all four in one second. Fixing the instance a reviewer named, without
searching for the pattern, is now the single most reliable predictor of the next round's FAIL.
