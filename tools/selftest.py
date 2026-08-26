#!/usr/bin/env python3
"""Behavioural self-test for the kit's SAFETY DEFENCES.

Round 26 (R26-F4) found that deleting the reconciliation guard, or the
stale-artifact clearing, left the parity suite at 7/7 green. That is this
project's oldest failure shape -- a check that cannot fail -- pointed at the
defences themselves. Parity compares OUTPUTS; it cannot see a failure path. These
checks can.

Every case here asserts STRUCTURE and BEHAVIOUR (exit codes, which files exist,
whether two artifacts describe the same case), never the wording of a message.
Round 25 and 26 both recorded findings where a check passed because a particular
word appeared; that trap is avoided deliberately.

Run from the kit root:  python3 tools/selftest.py
Exit 0 = every defence held. Exit 1 = a defence is gone.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "src", "scripts", "run_engine.py")
GEN = os.path.join(ROOT, "src", "generate_report.py")
FIX = os.path.join(ROOT, "tools", "parity", "fixtures")
IDS = ["OPW 633C A", "OPW 633E A", "SPS400452", "HOS-064 300 EPDM"]

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def sh(args, cwd):
    p = subprocess.run([sys.executable] + args, cwd=cwd, capture_output=True,
                       text=True, timeout=120)
    return p.returncode, p.stdout, p.stderr


def workdir(*inputs):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "_report"), exist_ok=True)
    for name, src in inputs:
        shutil.copy(os.path.join(FIX, src, "input.eml"), os.path.join(d, name))
    return d


def phase1(d, inp, *extra):
    return sh([RUN, "--in", inp, "--state", "_report/state.json", *extra], d)


def phase2(d, *extra):
    return sh([GEN, "--state", "_report/state.json", *extra], d)


def artifacts(d):
    return sorted(os.listdir(os.path.join(d, "_report")))


def case_and_draft_agree(d):
    """Structural agreement: same BOM line count, same open-item code multiset.

    Returns False rather than raising when either artifact is missing, so a
    removed defence is reported as a clean FAIL instead of a traceback.
    """
    try:
        with open(os.path.join(d, "_report", "case_state.json"), encoding="utf-8") as fh:
            cs = json.load(fh)
        with open(os.path.join(d, "_report", "bom_draft.md"), encoding="utf-8") as fh:
            draft = fh.read()
    except (OSError, json.JSONDecodeError):
        return False
    rows = [l for l in draft.splitlines() if "|" in l][1:]
    codes = sorted(l.split("[", 1)[1].split("]", 1)[0]
                   for l in draft.splitlines() if l.startswith("  - ["))
    return (len(rows) == len(cs["lines"])
            and codes == sorted(i["code"] for i in cs["open_items"]))


print("Defence 1 — flags survive the phase boundary (round 25 F-1)")
d = workdir(("rfq.eml", "confirmed-ids"))
phase1(d, "rfq.eml", "--component-ids", *IDS)
rc, _, err = phase2(d)
check("phase 2 succeeds with flags recorded", rc == 0, err.strip()[:120])
check("draft and CaseState describe the same case", case_and_draft_agree(d))
shutil.rmtree(d)

print("Defence 1b — --coc survives too")
d = workdir(("rfq.eml", "confirmed-ids"))
phase1(d, "rfq.eml", "--coc")
phase2(d)
try:
    with open(os.path.join(d, "_report", "bom_draft.md"), encoding="utf-8") as fh:
        draft = fh.read()
    with open(os.path.join(d, "_report", "case_state.json"), encoding="utf-8") as fh:
        cs = json.load(fh)
    _coc_ok = bool(cs["classes"]) and "Classes:" in draft
except (OSError, json.JSONDecodeError):
    _coc_ok = False
check("C-of-C class in both artifacts", _coc_ok)
shutil.rmtree(d)

print("Defence 1c — the prepare-phase record carries the flags (round 26 R26-F6)")
d = workdir(("rfq.eml", "confirmed-ids"))
with open(os.path.join(d, "_report", "state.json"), "w", encoding="utf-8") as fh:
    json.dump({"invocation": {"input": "rfq.eml", "component_ids": IDS,
                              "coc": False, "config_dir": None}}, fh)
rc, out, err = sh([RUN, "--from-state", "--state", "_report/state.json"], d)
check("--from-state replays the recorded flags", rc == 0, err.strip()[:120])
if rc == 0:
    check("BOM lines came from the recorded IDs",
          json.loads(out)["bom_lines"] == len(IDS))
shutil.rmtree(d)

print("Defence 2 — reconciliation FAILS on divergence")
d = workdir(("rfq.eml", "confirmed-ids"))
phase1(d, "rfq.eml")
p = os.path.join(d, "_report", "case_state.json")
with open(p, encoding="utf-8") as fh:
    cs = json.load(fh)
cs["request_class"] = "order"
with open(p, "w", encoding="utf-8") as fh:
    json.dump(cs, fh, indent=2)
rc, _, _ = phase2(d)
check("divergent CaseState is refused", rc == 1)
check("no draft written on refusal", "bom_draft.md" not in artifacts(d))
shutil.rmtree(d)

print("Defence 2b — reconciliation FAILS CLOSED when there is nothing to check "
      "(round 26 R26-F3)")
for label, prep in (
    ("absent CaseState", lambda dd: os.remove(os.path.join(dd, "_report", "case_state.json"))),
    ("CaseState is a directory", lambda dd: (
        os.remove(os.path.join(dd, "_report", "case_state.json")),
        os.mkdir(os.path.join(dd, "_report", "case_state.json")))),
):
    d = workdir(("rfq.eml", "confirmed-ids"))
    phase1(d, "rfq.eml")
    prep(d)
    rc, _, _ = phase2(d)
    check(f"{label} → refused", rc == 1)
    shutil.rmtree(d)

print("Defence 2c — skipping reconciliation requires saying so out loud")
d = workdir(("rfq.eml", "confirmed-ids"))
rc, _, _ = sh([GEN, "--in", "rfq.eml", "--no-reconcile",
               "--out", "_report/bom_draft.md"], d)
check("--no-reconcile renders without a CaseState", rc == 0)
shutil.rmtree(d)

print("Defence 3 — a failed run leaves NO stale artifact (round 26 R26-F1)")
d = workdir(("A.eml", "confirmed-ids"), ("B.eml", "plain-steam"))
phase1(d, "A.eml")
phase2(d)
before = artifacts(d)
phase1(d, "B.eml")
os.remove(os.path.join(d, "B.eml"))       # input vanishes between phases
rc, _, _ = phase2(d)
check("phase 2 fails when its input is gone", rc == 1)
check("customer A's draft did not survive",
      "bom_draft.md" not in artifacts(d),
      f"before={before} after={artifacts(d)}")
shutil.rmtree(d)

print("Defence 3a2 — generate_report clears ITS OWN artifact before failing")
d = workdir(("rfq.eml", "confirmed-ids"))
phase1(d, "rfq.eml")
phase2(d)
check("draft exists after a good run", "bom_draft.md" in artifacts(d))
# Make phase 2 ALONE fail, with no phase 1 in between to do the clearing for it.
os.remove(os.path.join(d, "_report", "case_state.json"))
rc, _, _ = phase2(d)
check("phase 2 alone fails", rc == 1)
check("its own previous draft did not survive",
      "bom_draft.md" not in artifacts(d), f"artifacts={artifacts(d)}")
shutil.rmtree(d)

print("Defence 3b — a failed extract clears the previous CaseState too")
d = workdir(("A.eml", "confirmed-ids"))
phase1(d, "A.eml")
phase2(d)
rc, _, _ = phase1(d, "missing.eml")
check("failed extract refuses", rc == 1)
check("no artifact from the previous run remains",
      not any(a.endswith((".json", ".md")) and a != "state.json"
              for a in artifacts(d)),
      f"artifacts={artifacts(d)}")
shutil.rmtree(d)

print("Defence 3d — a failed extract preserves the prepare phase's record "
      "(round 26 R26-F10)")
d = workdir(("rfq.eml", "confirmed-ids"))
rec = {"input": "gone.eml", "component_ids": IDS, "coc": True, "config_dir": None}
with open(os.path.join(d, "_report", "state.json"), "w", encoding="utf-8") as fh:
    json.dump({"invocation": rec}, fh)
rc, _, _ = sh([RUN, "--from-state", "--state", "_report/state.json"], d)
check("failed extract refuses", rc == 1, f"exit={rc}")
with open(os.path.join(d, "_report", "state.json"), encoding="utf-8") as fh:
    after = json.load(fh)
check("the prepare phase's invocation survived",
      after.get("invocation") == rec, f"state={after}")
shutil.rmtree(d)

print("Defence 3c — an unremovable artifact stops the run instead of being "
      "ignored (round 26 R26-F5)")
d = workdir(("rfq.eml", "confirmed-ids"))
phase1(d, "rfq.eml")
rp = os.path.join(d, "_report")
os.chmod(rp, 0o555)                        # cannot unlink inside
try:
    rc, _, err = phase1(d, "rfq.eml")
    check("read-only _report → run stops", rc == 1, err.strip()[:100])
finally:
    os.chmod(rp, 0o755)
shutil.rmtree(d)

print("Defence 4 — the wrappers report 0 or 1, NEVER the engine's 2 "
      "(round 26 R26-F2)")
d = workdir(("rfq.eml", "confirmed-ids"))
# The file must EXIST, or the wrapper's own isfile check returns before the
# engine's argparse is ever reached and this case proves nothing.
shutil.copy(os.path.join(d, "rfq.eml"), os.path.join(d, "-x.eml"))
bad = [
    ("existing leading-dash input reaches the engine's argparse",
     [RUN, "--in=-x.eml", "--state", "_report/state.json"]),
    ("missing input", [RUN, "--in", "nope.eml", "--state", "_report/state.json"]),
    ("no input at all", [RUN, "--state", "_report/state.json"]),
    ("--from-state with no record", [RUN, "--from-state", "--state", "_report/state.json"]),
    ("render with no invocation", [GEN, "--state", "_report/state.json"]),
]
for label, args in bad:
    rc, _, _ = sh(args, d)
    check(f"{label} → exit {rc}", rc in (0, 1), f"exit={rc}")
shutil.rmtree(d)

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} defences held")
if failed:
    print("DEFENCES GONE:")
    for name, _, detail in failed:
        print(f"  - {name} {detail}")
sys.exit(1 if failed else 0)
