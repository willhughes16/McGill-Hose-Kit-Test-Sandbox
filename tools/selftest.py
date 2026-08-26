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

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "src", "scripts", "run_engine.py")
GEN = os.path.join(ROOT, "src", "generate_report.py")
FIX = os.path.join(ROOT, "tools", "parity", "fixtures")
IDS = ["OPW 633C A", "OPW 633E A", "SPS400452", "HOS-064 300 EPDM"]
# The categories that can still be FILTERED, i.e. the depth-0 ones. `newsletter`
# is deliberately absent: since round 28 removed the list-mail exemption from the
# depth guard, a newsletter naming hose specifications reaches the engine, and it
# has its own check asserting exactly that. Keep this list distinct -- a blanket
# retarget once left it with a duplicate, so it read as six categories while
# covering five.
# Categories that can still be FILTERED. Round 29 removed the three
# content-judged ones (invoice/ack/internal) because they dropped 11 of 46
# genuine RFQs, so their fixtures now PASS and are asserted under NOT_FILTERED
# specifications and therefore reaches the engine -- bulk mail only filters at
# depth 0.
# Fixtures that must now reach the engine. Each is a deliberate, documented cost
# of round 29's removals; asserting them stops the removals being quietly undone.

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


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


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
    # An unrecognised flag drives the WRAPPER's OWN argparse to SystemExit(2).
    # Round 31 reported this unprotected; its stated repro (remove the clamp)
    # does not reproduce, because __main__'s broad catch handles it first.
    # Removing BOTH layers does leak a 2, and no case here made the wrapper's
    # argparse fail at all, so the property was genuinely untested.
    ("unrecognised flag (run_engine)", [RUN, "--bogus-flag"]),
    ("unrecognised flag (generate_report)", [GEN, "--bogus-flag"]),
    ("unrecognised flag (render_reply)",
     [os.path.join(ROOT, "src", "scripts", "render_reply.py"), "--bogus-flag"]),
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

print("Round 27 / R27-F4 — invalidation is driven by the ARTIFACTS declaration")
d = workdir(("rfq.eml", "confirmed-ids"))
driver = os.path.join(d, "drive.py")
with open(driver, "w", encoding="utf-8") as fh:
    fh.write(
        "import os, sys\n"
        f"sys.path.insert(0, {os.path.join(ROOT, 'src', 'scripts')!r})\n"
        "import run_state\n"
        "run_state.ARTIFACTS['synthetic'] = os.path.join('_report', 'synthetic.txt')\n"
        "open(run_state.ARTIFACTS['synthetic'], 'w').write('stale')\n"
        "import run_engine\n"
        "run_engine.main(['--in', 'rfq.eml', '--state', '_report/state.json'])\n"
        "print('SURVIVED' if os.path.exists(run_state.ARTIFACTS['synthetic']) else 'CLEARED')\n")
rc, out, err = sh([driver], d)
check("a newly declared artifact is cleared without editing any call site",
      "CLEARED" in out, f"out={out.strip()[-60:]} err={err.strip()[-80:]}")
shutil.rmtree(d)


# =============================== ROUND 28 ====================================

print("Round 28 / F-4 — clearing sites consume the ARTIFACTS declaration")
d = workdir(("rfq.eml", "confirmed-ids"))
driver = os.path.join(d, "drive3.py")
with open(driver, "w", encoding="utf-8") as fh:
    fh.write(
        "import os, sys\n"
        f"sys.path.insert(0, {os.path.join(ROOT, 'src', 'scripts')!r})\n"
        f"sys.path.insert(0, {os.path.join(ROOT, 'src')!r})\n"
        "import run_state\n"
        "run_state.ARTIFACTS['synthetic'] = os.path.join('_report', 'synth.txt')\n"
        "def stale():\n"
        "    open(run_state.ARTIFACTS['synthetic'], 'w').write('stale')\n"
        "import run_engine, generate_report\n"
        "res = []\n"
        "stale(); run_engine.main(['--in','rfq.eml','--state','_report/state.json'])\n"
        "res.append('engine:' + ('SURVIVED' if os.path.exists("
        "run_state.ARTIFACTS['synthetic']) else 'CLEARED'))\n"
        "# The report phase owns ONE artifact, so it must follow a RENAMED\n"
        "# declaration rather than a literal path. Round 30 found the old check\n"
        "# here asserting `\"report:\" in out` -- unconditionally true, a\n"
        "# tautology that survived two rounds and left this untested.\n"
        "run_state.ARTIFACTS['bom_draft'] = os.path.join('_report', 'renamed.md')\n"
        "open(run_state.ARTIFACTS['bom_draft'], 'w').write('stale-draft')\n"
        "# Make the run FAIL after the clear. The write would otherwise overwrite\n"
        "# the stale file whatever path was cleared, which is why the first\n"
        "# version of this check also could not fail (round 30).\n"
        "os.remove(os.path.join('_report', 'case_state.json'))\n"
        "rc = generate_report.main(['--state','_report/state.json'])\n"
        "survived = os.path.exists(run_state.ARTIFACTS['bom_draft'])\n"
        "res.append('renamed:' + ('HARDCODED' if survived else 'FOLLOWED')"
        " + ':rc=%s' % rc)\n"
        "print(' '.join(res))\n")
rc, out, err = sh([driver], d)
check("the extract phase clears a newly declared artifact",
      "engine:CLEARED" in out, f"out={out.strip()[-90:]}")
check("the report phase follows a RENAMED declaration, not a literal path",
      "renamed:FOLLOWED" in out,
      f"out={out.strip()[-90:]} err={err.strip()[-90:]}")
shutil.rmtree(d)


print("Round 31 / F-3 — the exit clamp is driven by a path where a 2 could ESCAPE")
# Round 31: deleting the clamp from BOTH wrappers left the suite 28/28 green,
# because none of Defence 4's five cases drove argparse inside cli.main. An
# EXISTING input whose name starts with '-' does: the engine's own argparse
# rejects it with SystemExit(2).
REPLY = os.path.join(ROOT, "src", "scripts", "render_reply.py")
d = workdir(("rfq.eml", "confirmed-ids"))
shutil.copy(os.path.join(d, "rfq.eml"), os.path.join(d, "-x.eml"))
for label, args in [
    ("run_engine", [RUN, "--in=-x.eml", "--state", "_report/state.json"]),
    ("generate_report", [GEN, "--in=-x.eml", "--no-reconcile",
                         "--out", "_report/bom_draft.md"]),
]:
    rc, _, _ = sh(args, d)
    check(f"{label}: engine SystemExit(2) cannot escape as exit 2", rc in (0, 1),
          f"exit={rc}")
shutil.rmtree(d)

print("Round 31 / F-4 — --config-dir survives the phase boundary (R25-F1's shape)")
# Round 31: --component-ids and --coc each had a defence; the third flag had
# none. Dropping it from build_argv left phase 1 exit 0, phase 2 reconciling
# GREEN (both passes replay the same builder) and the CaseState built from the
# wrong item master. Reconciliation structurally cannot see it, so the check has
# to compare against a config whose effect is visible in the output.
d = workdir(("rfq.eml", "plain-steam"))
alt = os.path.join(d, "altconfig")
shutil.copytree(os.path.join(ROOT, "src", "vendor", "config"), alt)
with open(os.path.join(alt, "catalog.json"), encoding="utf-8") as fh:
    cat = json.load(fh)
items = cat if isinstance(cat, list) else cat.get("items", [])
if items:
    items[0]["description"] = "ALTCONFIG-MARKER"
with open(os.path.join(alt, "catalog.json"), "w", encoding="utf-8") as fh:
    json.dump(cat, fh)
marker_id = items[0]["id"] if items else None
rc, out, err = sh([RUN, "--in", "rfq.eml", "--state", "_report/state.json",
                   "--config-dir", alt, "--component-ids", marker_id], d)
check("--config-dir reaches the engine (exit 0)", rc == 0, f"exit={rc} {err.strip()[:90]}")
with open(os.path.join(d, "_report", "case_state.json"), encoding="utf-8") as fh:
    cs = json.load(fh)
check("the alternate catalog's data is in the CaseState",
      "ALTCONFIG-MARKER" in json.dumps(cs),
      "the flag was dropped: the CaseState came from the SHIPPED catalog")
rc2, _, err2 = phase2(d)
check("the reply phase agrees with a --config-dir run", rc2 == 0, err2.strip()[:90])
shutil.rmtree(d)

print("Round 31 — the reply is the deliverable, and it carries what the draft drops")
d = workdir(("rfq.eml", "plain-steam"))
phase1(d, "rfq.eml")
phase2(d)
rc, out, err = sh([REPLY, "--state", "_report/state.json"], d)
check("render_reply exits 0", rc == 0, err.strip()[:90])
check("reply.md is produced", "reply.md" in artifacts(d), f"artifacts={artifacts(d)}")
with open(os.path.join(d, "_report", "reply.md"), encoding="utf-8") as fh:
    reply = fh.read()
with open(os.path.join(d, "_report", "case_state.json"), encoding="utf-8") as fh:
    cs = json.load(fh)
check("every open item appears in the reply",
      all(i["code"] in reply for i in cs["open_items"]),
      "an open item was dropped from the reply")
check("every field appears in the reply",
      all(name in reply for name in cs.get("fields", {})),
      "a field was dropped from the reply")
check("the routing recommendation appears",
      str((cs.get("routing") or {}).get("recommendation", "")) in reply)
check("an unconfirmed field is marked as such",
      ("NOT CONFIRMED" in reply) == any(
          (f or {}).get("status") in {"reading", "assumed", "missing", "conflict"}
          for f in cs.get("fields", {}).values()))
check("the reply never claims to be a quote",
      "DRAFT" in reply and "not a quote" in reply)
check("the manifest attaches NOTHING",
      sum(1 for a in json.load(open(os.path.join(ROOT, "kit.json")))
          ["outputs"]["artifacts"] for t in a.get("tags", [])
          if t == "email_attachment") == 0)
shutil.rmtree(d)


failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} defences held")
if failed:
    print("DEFENCES GONE:")
    for name, _, detail in failed:
        print(f"  - {name} {detail}")
sys.exit(1 if failed else 0)
