#!/usr/bin/env python3
"""Wrap a text file as {"render": "<contents>"} so parity_check.py can compare it.

parity_check.py is a JSON comparator (it parses both sides with json.loads), so a
plain-text deliverable cannot be compared directly. Rather than argue that the
human-readable draft must match because it is derived from the CaseState, this
brings it under the same exact comparator: both the produced render and the
captured expected render are wrapped identically and diffed structurally.

This lives under tools/ and is NOT shipped in the kit zip -- it is parity
scaffolding, not kit runtime.

Usage: wrap_text.py <text-in> <json-out>
"""
from __future__ import annotations

import json
import sys


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    src, dst = argv[1], argv[2]
    try:
        with open(src, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        print(f"error: cannot read {src}: {e}", file=sys.stderr)
        return 2
    try:
        with open(dst, "w", encoding="utf-8") as fh:
            json.dump({"render": text}, fh, indent=2)
    except OSError as e:
        print(f"error: cannot write {dst}: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
