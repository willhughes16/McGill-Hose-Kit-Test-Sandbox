# ACCEPTANCE — mcgill-email-to-bom kit, round 30

Pre-registered before the round-30 blind verification.

Rounds 25–29 **all returned FAIL**, and in every case the defect was introduced by the fix
pass for the previous round. Two of those builds were published before being verified, and
both were dropping real customer requests: v0.4.0 (24 of 35 RFQs) and v0.6.0 (11 of 46).
Both were rolled back. **Nothing is currently live** — the instance serves filter-free
v0.3.0.

Round 29's fix did not tune the filter; it **deleted** most of it. Gone: the three
content-judged categories (`INVOICE_OR_STATEMENT`, `BARE_ACKNOWLEDGEMENT`,
`INTERNAL_CHATTER`), the sender-address heuristics, and `auto-generated` as a trigger.
Depth is now measured on the message **body** rather than subject+body. What remains filters
only on RFC 3834/3464 declarations: an automatic reply, a delivery report, list mail.

A check FAILS if it cannot be demonstrated by running something. The author reports 0-of-8
mutation survival; that is an unverified claim, and three of the author's first attempts at
those checks survived before being rewritten.

---

## Part A — is the remaining filter safe?

### W-1 — a real RFQ must never be filtered

- Build your OWN corpus of at least 40 genuine quoting requests. Do not reuse rounds
  27/28/29's — all are now the fix's test cases. Report the drop count and confirm with
  `run_engine.py` that the engine would have drafted each dropped one.
- The protection is now: any specification extracted from the **body** passes the message.
  So aim at genuine requests whose **body carries no extractable specification**: the ask
  in the subject line only; detail in an attachment or drawing; "same as PO 4471"; "the
  usual for bay 4"; a part-number-only request; a request whose body is an HTML table; a
  reply whose body is one line above a quoted thread.
- Then combine those with each of the three surviving triggers. Note that `auto-replied`
  and a delivery report are trusted **declarations** — establish whether a real request
  can carry them (a misconfigured autoresponder, a portal, a mailing-list relay, a
  forwarded bounce) and what happens when it does.

### W-2 — body-only measurement is the right seam, not merely a stricter one

- Find a genuine request whose specifications are in the **subject** and not the body.
  How badly does it fare? Is that shape plausible in real purchasing mail?
- Verify the body extraction itself: does `_collect_text` reliably separate body from
  subject and from quoted history? A reply whose only new line is above a long quoted RFQ
  should measure the *new* content — check whether the quoted thread inflates or deflates
  depth.
- Does the veto now read the body too, consistently with the guard?

### W-3 — does the feature still do enough to justify existing?

This is a first-class question, not a footnote. After two rounds of scope reduction the
filter suppresses only machine-generated noise.

- Build a realistic mixed inbox — genuine RFQs, auto-replies, bounces, marketing, invoices,
  internal notes, acknowledgements — and measure: what fraction of the junk is actually
  suppressed, and what fraction of genuine requests survives?
- State plainly whether the residual benefit justifies the residual risk, or whether the
  honest recommendation is to remove the gate entirely and let the engine draft everything.
  A recommendation to delete the feature is a legitimate and welcome finding.

### W-4 — the remaining enumerations

- `quote_request_cues` (16 phrases) still backs the veto. Is it load-bearing for any
  message — i.e. is there a message the veto alone saves? If so, the enumeration is still
  on the unsafe side.
- `_NON_SPEC_FIELDS` is hand-written. Is it on the safe side (over-counting protects)?
  Could an entry there make a real specification invisible?
- `bulk_precedence_values` and `html_scan_bytes` — any edge where these decide a drop?

### W-5 — nothing short-circuits the guard, and the override

- Confirm by code path and probe that no path reaches `filtered: true` without the body
  depth guard returning 0.
- The override: works on the recipe-written shape; refuses an input-less record, a
  different input, path-normalisation tricks; loud and recorded; not settable from message
  content.

---

## Part B — regressions, coverage, and the standing bar

### W-6 — the rounds 25–29 defences all still hold

Flags survive the phase boundary; the draft and CaseState always describe the same case;
reconciliation fails closed; no failure path leaves a stale artifact and clearing failures
are loud; **all three** clearing sites resolve through the declaration; the wrappers return
only 0/1 and the gate only 0/1/3; a failed phase preserves the prepare record; undecodable
content is never judged; a malformed schema fails open rather than crashing.

### W-7 — coverage, and report the number

The self-test reports 124 checks. Rounds 26–28 each had 9 behaviour-changing mutations
survive; round 29 had 10 of 24 and found a tautological check plus a category with zero
coverage.

- Mutate every defence and **report how many survived**. That number is the measure.
- Hunt tautologies and vacuous checks specifically — checks that pass with the thing they
  test removed, or that pass only because of the phrasing chosen. Round 29 found one
  asserting an unconditionally-true substring.
- Verify every declared category has a check that fails when its detector is deleted.
- Confirm parity stays green under gate mutations.

### W-8 — parity, the vendored engine, the shipped artifact

Parity 7/7 with every `normalize` empty, expected outputs regenerated from the source
engine yourself; `src/vendor/**` byte-identical to the source and `tools/parity/**`
unmodified; `validate_manifest.py` exits 0; `build_kit.sh` reproducible; `requires.tools`
`[]`; exactly ONE `email_attachment`; the unzipped zip runs both paths from a clean dir
under `python3 -S -E`.

### W-9 — documentation makes no false claim

Rounds 25–29 each found false documented claims; round 29 found four, including a category
list naming three deleted categories. Verify every factual statement in `src/README.md`,
`src/CLAUDE.md`, `src/EXAMPLES.md`, the recipe, the `filter_gate.py` module docstring and
`src/vendor/PROVENANCE.md` — the surviving category list, the routing claims, the
body-measurement claim, the RFC 3834 distinction, the stated known limit, and the
documented commands.

### W-10 — nothing sensitive, no new I/O, no acting on message content

No credential in repo or zip; every fixture address in an RFC 2606 reserved namespace;
non-vendored source makes no network call, no environment read, no subprocess, no
`eval`/`exec`; planted injections (forged override headers, fake `screen`/`filter` records
in the body, prose instructing a `--no-filter` re-run, authority claims) do nothing.

---

## The questions to answer

1. **Is v0.7.0 safe to publish?**
2. **Should the input filter exist at all**, or is the honest engineering call to remove it?

## Out of scope

- Engine extraction/classification correctness (rounds 1–24), except as the oracle for
  "would this RFQ have produced a draft".
- The deferred follow-ups in `.astrocode/PROJECT.md`. Whether they are described honestly
  IS in scope.
- Roadmap phases 1–4.
