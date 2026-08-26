# Decisions — mcgill-email-to-bom

> Append-only ADR-lite log. Each entry: what we decided, why, and what we rejected.
> Add entries with `ac decision add "<title>" --why "…" --rejected "…"` or
> `/astro-decision`. Agents read this so past decisions are respected, not relitigated.

## ADR-001 — The input filter fails OPEN, not closed
_2026-08-26_

**Why:** Filtering a real RFQ is far worse than passing a newsletter to the engine —
a suppressed request is silently lost, while an unnecessary draft only costs a wasted
run. Everything the gate cannot resolve confidently (no text obtained, a parse defect
or exception, HTML-only body over the declared scan budget, an unrecognised or
undecodable part that could hide the request, a code/route outside the declared
vocabulary, an unreadable reference/schema file) therefore resolves to *not
filtered*. This is a named, intentional inversion of the kit's usual fail-closed
guard idiom (CONVENTIONS: "Guards fail CLOSED") — the inversion is deliberate and
scoped to this one gate, not a relaxation of the general rule. The only loud,
fail-closed exception is a hard input error (missing/unreadable input path), which is
not ambiguity.

**Rejected:** fail closed (filter on any uncertainty) — optimises for not bothering
sales with junk at the cost of silently dropping real business, the opposite of what
the kit exists to do.

## ADR-002 — Gate exit code `3` means "filtered", never `2`
_2026-08-26_

**Why:** The vendored engine's own exit `2` already means "a draft with open items"
and is a normal, successful outcome (CONVENTIONS). Reusing it for "filtered" would
make a filtered run indistinguishable from a drafted-but-incomplete one, which is
exactly the ambiguity C2 forbids. A new, non-overlapping code (`3`) is declared
instead, clamped in `__main__` exactly like `run_engine.py`'s own exit-code
discipline (R26-F2), so filtering is a third outcome distinguishable from both
"drafted" (`0`/`2`) and "the gate itself broke" (`1`).

**Rejected:** overloading the engine's `2` for "filtered" (collapses two distinct
outcomes into one code); reusing `1` for "filtered" (collapses "filtered" with "the
gate's own failure", so automation cannot tell "nothing to quote" from "the kit
broke").

## ADR-003 — The gate is a deterministic script; the recipe only branches on its exit code
_2026-08-26_

**Why:** The recipe is agent-interpreted prose. A judgement call made there ("does
this look like a request?") would be non-deterministic and, critically, unmutatable
— there is no way to mutation-prove a decision written in natural language the way
`tools/selftest.py` mutation-proves code (C7). Putting the entire decision in one
script (`src/scripts/filter_gate.py`) with a single importable seam keeps the
decision testable, deterministic and re-runnable with an identical result on an
identical input, and keeps the recipe phase to "run the script, branch on 0/3/1".

**Rejected:** judging "is this an RFQ" in recipe prose (non-deterministic,
unmutatable, unauditable); splitting the decision across the recipe and the script
(two places to keep in sync, the drift this project exists to avoid).

## ADR-004 — The filter's route vocabulary is disjoint from `open_items[].route`
_2026-08-26_

**Why:** A filtered message and a routed-but-undrafted open item are different
outcomes for an operator: one means "nothing to quote", the other means "a draft
exists but needs a human decision on this item". If the filter reused routing values
like `inside_sales`/`order_desk`, a consumer reading `route` alone could not tell
which situation it was looking at without also checking whether a CaseState exists.
Declaring a disjoint route vocabulary (`no_action`, `accounts_payable`,
`inside_sales_fyi`, `internal_ops`, …) in `src/reference/filter_signals.json` makes
the two outcomes mechanically distinguishable by value alone.

**Rejected:** reusing `open_items[].route` / `routing.recommendation` values for
filtered messages (a filtered message would then be mistakable for a routed,
drafted case — the exact confusion C2 requires be impossible).

## ADR-005 — The gate reads its own cheap, bounded text view; it never calls `extract_rfq_text`
_2026-08-26_

**Why:** `extract_rfq_text` and the HTML/CSS-hiding pipeline behind it are the
engine's superlinear cost centre (FOLLOW-UP-9: ~80s at 538KB, x3 passes) — exactly
the cost the gate exists to avoid paying before it even knows whether the message is
worth engine time (C3). The gate instead does a stdlib `BytesParser` walk over
decoded `text/plain` parts, and falls back to `mail.html_to_text` only for
HTML-only messages under a small declared budget (`html_scan_bytes`); every signal
check on that text is a single linear `re.search` pass. This keeps a ~1MB junk
message filtering in well under a second, and keeps the gate's own parse fully
decoupled from the engine's — a gate exception is never grounds to filter (that
would violate ADR-001).

**Rejected:** reusing the full `extract_rfq_text`/HTML-hiding pipeline for
pre-screening (defeats the purpose of a cheap pre-screen: the gate would pay the
engine's own worst-case cost on every message, including the junk it exists to
reject quickly).
