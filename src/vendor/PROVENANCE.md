# Vendored engine provenance

This directory is a **verbatim copy** — not a reimplementation — of the McGill
email→BOM engine. Copying verbatim is deliberate: the logic carries 529 tests and
24 blind verification rounds, and re-expressing it would create a second copy of
rules that must not drift.

| | |
|---|---|
| Source repo | `ScaleUpLabs/McGill-Core` (private; formerly `TWYD-Factory-McGill`) |
| Source commit | `6b0a897` (freshness); engine behaviour as of `ae4411f` |
| Source version | 2.0.0 |
| Vendored on | 2026-09-17 (re-vendored; previously 2026-08-27T22:45:00Z) |
| Copy command | `rsync -a --exclude __pycache__ email_to_bom/ config/` |

> **Re-vendored at `6b0a897` (2026-09-17).** One file changed, `knowledge.py`: every
> lookup now carries a `freshness` of `as_of:<v>`, `revision:<v>` or `unknown`
> (CW-8). **Parity stayed 7/7 byte-identical**, which is the proof that this kit's
> output is unaffected — the shipped default is `NullKnowledge`, which performs no
> lookups, so the contract ships dormant (FOLLOW-UP-1). 529 -> 539 source tests.
>
> **Re-vendored at `ae4411f` (2026-08-27).** That commit is the corpus fix pass:
> a size stated without the word "ID" is captured as a size (it used to fall through and
> be drafted as the LENGTH), and a unit that crosses a line break or a material-grade
> token can no longer become a dimension. 507 -> 529 source tests. Every parity expected
> output was re-captured at this commit and the diffs read: they change only size and
> length fields and the open items that follow from them.

The repo is private, so the engine cannot be pinned as a `requires.tools[]`
`url` entry (https + sha256 fetch would need auth) and it is not on PyPI. Vendoring
is therefore what keeps the kit self-contained per the kit contract.

## Refreshing

Re-run the copy command above against a newer commit, update this file, then run
`python3 tools/parity_check.py --manifest tools/parity/parity.json`. Parity failing
after a refresh means engine behaviour changed — investigate before accepting.
