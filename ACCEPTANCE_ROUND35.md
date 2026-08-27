# ACCEPTANCE — mcgill-email-to-bom kit, round 35

Pre-registered before the round-35 blind verification.

Rounds 25–34 **all returned FAIL** — ten for ten, every defect introduced by the previous
fix pass. But the numbers are converging: mutation survival 65% → 39% → 32%, CaseState
fidelity 10/17 → 12/17, and rounds 33 and 34 each **refuted** one weakness the author
named. Round 34's blocker (whitespace deleted rather than folded, fabricating tokens like
`temperature250` in the Evidence column) is closed in v0.12.0, along with its five HIGHs.

New since round 34: a **golden regression suite** for `reply.md` (`tools/golden/`),
closing REQ-079. Its expected files are deliberately the kit's own output — a
change-detector, not a correctness proof — and re-capture is a separate explicit step.

A check FAILS if it cannot be demonstrated by running something.

---

## Part A — the round-34 fixes

### N-1 — folding, and both directions of the trade

`_safe()` now folds `Cc/Zl/Zp` to a space and strips only `Cf/Cs/Co/Cn`.

- Fabrication direction: can any input still produce a token in the reply that appears in
  no email? Multi-codepoint sequences, combining-mark stacking, NFKC-normalizable
  compatibility characters, surrogate halves, whitespace runs collapsing across a
  field boundary.
- Destruction direction: does folding/stripping now destroy legitimate content? RTL
  scripts, CJK, emoji (which are `So`, should survive), ZWJ emoji sequences (ZWJ is `Cf` —
  a family emoji will lose its joiners; judge whether that matters for this domain).
- Forgery direction: with `Cf` stripped, is there still any way to make a rendered line
  imitate the kit's structure?

### N-2 — the consumption tracker and the backstop

Sections now mark their own keys via `take()`; the backstop prints any unconsumed,
non-empty key.

- Is `take()` called accurately? A section that takes a key and then conditionally renders
  nothing reproduces the H-2 shape. Check each `take` against what its section really
  emits, especially the multi-key `take("request_class", "urgency", ...)`.
- The falsy fix: `v is not None and v != "" and v != [] and v != {}` — note `v != ""`
  is False for `0 == ""`? Verify the comparisons behave for 0, 0.0, False, empty
  string, and note `0 == ""` is False in Python but check anyway.

### N-3 — the golden suite

- Adjudicate its non-circularity framing (expected files are the kit's own output,
  declared as change-detection). Is the framing honest in `tools/golden/README.md`?
- Can it be silently re-captured? Is anything preventing a fix pass from running
  `capture.py` to green a red suite without reading the diff — and should there be?
- Are two fixtures enough? Find a rendering property whose regression neither fixture
  would notice.
- The `reply-plain-steam` fixture writes into `tools/golden/fixtures/.../_report/` at
  check time. Does that interact badly with anything (parallel runs, the parity suite,
  git status noise)?

### N-4 — the evidence backstop and the count claims

- Long evidence spans: recoverable in full below the table, with the truncation marker in
  the cell?
- Header counts vs body: open items, BOM lines, blocking counts — can any disagree with
  what the body shows, on any CaseState?

---

## Part B — the standing bar

### N-5 — the rounds 25–34 defences

Flags survive the phase boundary including `--config-dir`; both reconciliations fail
closed; no failure path leaves a stale `case_state.json`, `bom_draft.md` or `reply.md`;
clearing failures are loud; every clearing site resolves through `ARTIFACTS`; wrappers
return only 0 or 1; a failed phase preserves the prepare record; a malformed schema fails
open; the `UNCONFIRMED` set is complete; falsy values survive the backstop.

### N-6 — coverage, and report the number

The suite reports 101 checks plus the 2-fixture golden suite. Mutation survival:
29 → 10/24, 30 → 15/34, 31 → 18/36, 32 → 33/51, 33 → 22/57, 34 → 21/66.

- Mutate every defence and **report how many survive the combined suites** (selftest +
  parity + golden). That number is the measure.
- Hunt tautologies and coincidence-matches; round 34 found a check passing via a fallback
  line rather than the table it claimed to test.

### N-7 — parity, vendor, shipped artifact, docs

Parity 7/7 with expected outputs regenerated from the source engine yourself;
`src/vendor/**` byte-identical; `validate_manifest.py` exits 0; `build_kit.sh`
reproducible; `requires.tools` `[]`; **zero** `email_attachment` tags; the unzipped zip
runs all phases from a clean dir under `python3 -S -E`. Every factual claim in the shipped
docs true — rounds 25–34 all found false ones. The direct-run blocks now include
`render_reply.py`; verify they work verbatim.

### N-8 — nothing sensitive, nothing acts on message content

No credential in repo or zip; fixtures in RFC 2606 namespaces; non-vendored source makes
no network call, no environment read, no subprocess, no `eval`/`exec`. Plant injections
and confirm nothing acts on them.

---

## The question to answer

**Is v0.12.0 safe to publish?** Ten rounds of findings are closed; the instance still
serves v0.3.0, which predates every wrapper defence and the inline reply. If the answer is
no, name the single blocker. If the answer is yes, say so plainly — after ten FAILs, an
earned PASS matters.

## Out of scope

- Engine extraction/classification correctness (rounds 1–24).
- The no-attachment decision and the filter removal.
- Roadmap phases 1–4.
