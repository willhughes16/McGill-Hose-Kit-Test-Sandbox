# Vendored engine provenance

This directory is a **verbatim copy** — not a reimplementation — of the McGill
email→BOM engine. Copying verbatim is deliberate: the logic carries 507 tests and
24 blind verification rounds, and re-expressing it would create a second copy of
rules that must not drift.

| | |
|---|---|
| Source repo | `ScaleUpLabs/McGill-Core` (private; formerly `TWYD-Factory-McGill`) |
| Source commit | `b1f99502adce489f1bd37eddecfbb921a4a4d1f6` |
| Source version | 2.0.0 |
| Vendored on | 2026-08-26T14:01:52Z |
| Copy command | `rsync -a --exclude __pycache__ email_to_bom/ config/` |

The repo is private, so the engine cannot be pinned as a `requires.tools[]`
`url` entry (https + sha256 fetch would need auth) and it is not on PyPI. Vendoring
is therefore what keeps the kit self-contained per the kit contract.

## Refreshing

Re-run the copy command above against a newer commit, update this file, then run
`python3 tools/parity_check.py --manifest tools/parity/parity.json`. Parity failing
after a refresh means engine behaviour changed — investigate before accepting.
