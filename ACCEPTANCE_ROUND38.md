# ACCEPTANCE — mcgill-email-to-bom kit, round 38

Pre-registered before the round-38 blind verification. Written against v0.26.0
(`020c8e5`), which is **live**. A blocker here means a rollback, not a delayed
release. v0.21.0 is the last version a round has seen.

Round 37 returned FAIL — thirteen in a row — with a blocker in code the author had
published hours earlier. It also refuted a "defence in depth" claim in a shipped
docstring. Since then **five versions** have shipped without a round:

| | What changed |
|---|---|
| v0.22.0 | `lineitems.py` — a document describing many products is flagged; two measured thresholds |
| v0.23.0 | the machine transcript moved out of the reply into the review request |
| v0.24.0 | `run_manifest.deliver` — the reviewer's message declares the customer's source files |
| v0.25.0 | **`reply.md` became the CUSTOMER's email**; `config/questions.json` rewords open items; completeness moved to `--record` |
| v0.26.0 | `prepare_input.py` builds the `.eml` from what the runtime delivers; a bare HTML input is refused |

A check FAILS if it cannot be demonstrated by running something.

---

## Read this first: what changed about the stopping rule

Until v0.25.0, "a wrong answer reaching a customer" had to travel through a human
who read an internal document. **Now there is a document written FOR the customer,
in their language, that the kit says to send once approved.** A wrong question in
`reply.md` is a wrong answer to a customer with one fewer human between them. Treat
`reply.md` as the highest-consequence artifact in the kit.

## The author's conflict, and the weakest thing in this build

The same session wrote the code, the tests and this bar. Round 37 showed what that
is worth. And this round has a sharper version of the problem:

**The 26 customer-facing translations in `config/questions.json` were written by the
author without seeing 30 of the 37 engine asks.** Only seven ask strings are
extractable from the engine source; the rest are assembled at runtime. The author
wrote the translations from the CODE NAMES and domain knowledge. The side-by-side in
`review_request.md` caught one mistranslation on its first render (`DIMENSION_CONFIRM`
asked about inside-versus-outside diameter when the engine asks what a measurement
REFERS TO). **Assume there are more.** Trigger every open-item code you can reach,
read the engine's actual ask beside the customer wording, and report every pair where
the customer is being asked a different question than the engine raised.

---

## Part A — the new surface, in order of how badly it could hurt a customer

### K-1 — `reply.md`: is the customer ever asked the wrong question, or the wrong number of them?

- **Translation fidelity**, as above. This is the round's centre of gravity.
- **Selectivity.** 11 codes are `internal`. Is every one of them genuinely something
  a customer cannot answer? Is any `customer` code actually internal (a customer asked
  to resolve something that is McGill's job)?
- **Order.** The kit claims the engine's priority order is preserved. Prove or refute.
- **Loss.** The customer email shows `captured` fields only, through an ALLOW-list of
  attributes (`family, gender, type, kind, unit`). Find a field or attribute a customer
  needed to see and did not. Find a `reading`/`assumed` value a customer should have
  been asked to confirm and was not.
- **The "no questions" path** (job `2e07005c`'s follow-up): an `order` with only
  internal items renders "we have what we need". Is that ever false?
- Untrusted text: the customer's own words, an operator's, and a transcript all reach
  `render_customer` through `_safe`. Find a structure-forging payload.

### K-2 — `prepare_input.py`: the seam between the runtime and the kit

This is the shape the runtime ACTUALLY delivers — a body file and `input/` — and no
round has ever tested it, because every fixture in the campaign was an `.eml`.

- The HTML detector (`looks_like_html`) and the readback markup guard. Bodies that are
  HTML but undetected; bodies that are plain text but contain tags (a customer quoting
  a snippet); RTF; empty; non-UTF-8; a body that is itself an `.eml` WITH attachments
  in `input/` (refused — is the refusal right?).
- Attachments: a filename carrying a region marker; a zero-byte file; a `.eml` inside
  `input/`; a name colliding with the body; hundreds of files; dotfiles (skipped —
  should they be?).
- **The bare-HTML refusal in `run_engine`**: find an HTML input it does NOT refuse, or a
  legitimate non-HTML input it does.
- `prepared_from` in `state.json`: does anything downstream read it, or is it a record
  nothing acts on?

### K-3 — `lineitems.py`: the two thresholds

`ROW_MIN = 3` and `DIM_MIN = 5` were measured on seven fixtures, one real PO excerpt
and three synthetic strings. Two gaps are documented: a genuine two-item order is not
flagged, and a prose list with few dimensions is not flagged.

- Build the false negatives: a two-line PO; "quote the hose, the fittings and the
  clamps". Do the customer emails they produce contain a merged spec presented as
  fact? **That is the wrong answer this detector exists to prevent.**
- Build the false positives: a single complex assembly naming five dimensions; a
  legitimate reorder with three priced lines (hose, two fittings for ONE assembly).
- The MERGED banner fires only when `fields` is non-empty. Is there a merged case with
  empty fields where the customer email still says something false?

### K-4 — the split documents

- `review_request.md` now embeds the complete record AND the customer email AND the
  side-by-side. Is anything in the CaseState in none of them? `completeness.py` renders
  `--record --no-reconcile`, so it never exercises the reconciled path — round 37
  already noted that shape. Is the record `review_request.md` embeds byte-identical
  to what `completeness.py` checks?
- The reply guard in `render_review` compares against `render_customer`. Forge a
  `reply.md` that passes it and differs in what a customer would read.
- The transcript is verbatim in the review, summarised by count in the reply. Can the
  count lie?

### K-5 — `deliver`, and round 37's carry-forwards

- `run_manifest.deliver` names the customer's files for the reviewer by sha256. Body
  does not implement it yet. Is the reviewer told plainly enough that they may not have
  been sent the file?
- **Round 37's unfixed findings — re-check every one and report status:** M-2 (a
  marker in a customer's own text fabricates an operator addendum — **still live**),
  M-3 (`augmented_input.txt` leaks across customers), H-2 (`OPERATOR-STATED`
  unreachable for span-less fields), H-3 (four MIME shapes dropped silently), M-1,
  M-4, M-5, L-1..L-4. Some may have been fixed incidentally; say which.

---

## Part B — the standing bar

### K-6 — the rounds 25–37 defences still hold

Flags survive the phase boundary; every reconciliation fails closed; no failure path
leaves a stale artifact (now SEVEN: `case_state.json`, `bom_draft.md`, `reply.md`,
`run_manifest.json`, `review_request.md`, `rfq.eml`, and the deliberately-uncleared
`augmented_input.txt`/`transcribed_input.txt` — confirm the exemptions are right);
clearing failures are loud; every clearing site resolves through `ARTIFACTS`; all
wrappers return only 0 or 1; a failed phase preserves the prepare record; untrusted
text cannot forge the document's structure — **including every new banner and
separator introduced since round 36**.

### K-7 — coverage, and report the number

Suites: selftest 311, parity 7, golden 3, completeness 184.

- Mutate every defence and **report combined survival**. Round 37 measured 36% / 30%
  honest subset and said it was not comparable to the 65→39→32→25 sequence. Say
  whether yours is comparable to round 37's.
- Report **CaseState fidelity** against the 17-key standard, on the RECORD.
- The author's mutation runs caught **six** of the author's own checks that could not
  fail this cycle, all coincidence-matches or crash-masquerading-as-refusal. The
  checks added after line ~1100 of `tools/selftest.py` are the least-reviewed code in
  the repo. Hunt there.

### K-8 — parity, vendor, shipped artifact, docs

Parity 7/7 regenerated from the source engine yourself; `src/vendor/**` byte-identical
to `ScaleUpLabs/McGill-Core` `main` (`270f32b`); `validate_manifest.py` exits 0; the
published package (35 files, sha `fccdd43c515df397`) contains nothing unintended;
**zero** `email_attachment` tags; every declared artifact produced by the recipe **run
from the runtime's shape** (body file + `input/`), not from an `.eml`; the unzipped
zip runs all phases from a clean dir under `python3 -S -E`.

**Every factual claim in the shipped docs true.** The docs grew by several hundred
lines across five versions. Round 37 found six false claims, one self-contradicted in
a single file.

### K-9 — nothing sensitive, nothing acts on message content

No credential in repo or zip; fixtures in RFC 2606 namespaces; non-vendored source
makes no network call, no environment read, no subprocess, no `eval`/`exec` —
`prepare_input.py`, `questions.py` and `lineitems.py` are new. Plant injections in a
body, an attachment filename, a transcript, an answers file and a correction record.
**Confirm nothing acts on them, and confirm the customer's email does not carry them
either** — `render_customer` is a new surface for injected text to reach a reader.

---

## The question to answer

**Should v0.26.0 stay published, or be rolled back — and to what?** v0.21.0 is the last
version a round has seen, and rolling back to it reinstates the phantom-assembly
behaviour, the 9 KB reply and the bare-HTML failure. Weigh that.

The stopping rule: *ship when no finding would give a customer a wrong answer.*
Apply it per finding. A wrong or missing answer in `reply.md` blocks. A guarantee-level
break that changes nothing a customer receives does not. A coverage gap does not.

If nothing blocks, say so without hedging and list what you tried. After thirteen
FAILs an earned PASS is as valuable as an honest FAIL — do not manufacture a finding
to keep the streak, and do not soften one to end it.

## Out of scope

- Engine extraction/classification correctness except where re-vendoring changed it.
- The operator's decisions: no attachment on the customer reply; the filter removal;
  the unread-attachment outcome rule; the reply being customer-facing; per-line-item
  extraction being upstream; publishing without rounds.
- Body's half of phase 5, and phase 4.
