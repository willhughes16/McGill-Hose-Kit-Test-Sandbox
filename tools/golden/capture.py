#!/usr/bin/env python3
"""Re-capture the golden reply renderings from the CURRENT kit.

Deliberately a separate, explicit step. A golden file that is silently refreshed
whenever it disagrees is a rubber stamp, not a change-detector, so this must be
run on purpose and its diff read before committing.

Usage (from the kit root):  python3 tools/golden/capture.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GOLDEN = os.path.join(ROOT, "tools", "golden")


def main():
    with open(os.path.join(GOLDEN, "golden.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    for fx in manifest["fixtures"]:
        name = fx["name"]
        out = os.path.join(ROOT, fx["expected_output"])
        # Same substitution the comparator uses, so the two can never read the
        # template differently ({{ }} escaping included).
        cmd = fx["command"].format(input=os.path.join(ROOT, fx["input"]), output=out)
        rc = subprocess.run(cmd, shell=True, cwd=ROOT).returncode
        print(f"  {name}: rc={rc} -> {os.path.relpath(out, ROOT)}")
    print("\nRead the diff before committing. A golden file refreshed without "
          "reading it is a rubber stamp.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
