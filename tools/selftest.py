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
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "src", "scripts", "run_engine.py")
GEN = os.path.join(ROOT, "src", "generate_report.py")
REPLY = os.path.join(ROOT, "src", "scripts", "render_reply.py")
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


def eml(d, name, text):
    with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
        fh.write(text)
    return name


def prepare(d, inp):
    """Write state.json the way the recipe's prepare phase does."""
    with open(os.path.join(d, "_report", "state.json"), "w", encoding="utf-8") as fh:
        json.dump({"invocation": {"input": inp, "component_ids": [],
                                  "coc": False, "config_dir": None}}, fh)


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
# Round 33 (C-2): the round-32 replacement ran on ONE fixture — the only one of
# five that cannot fail it — and the token it hunted was satisfied by the
# Evidence column, which its own loop excludes but the renderer prints. Reverting
# the round-31 field fix left the suite 69/69 green with the check printing
# "dropped: []". Two changes: run across EVERY parity fixture, and require the
# value in the field's OWN ROW rather than anywhere on the page.
def _field_values_present(reply_text, case):
    rows = {}
    for line in reply_text.splitlines():
        if "|" in line:
            rows[line.split("|", 1)[0].strip()] = line
    missing = []
    for fname, f in (case.get("fields") or {}).items():
        row = rows.get(fname)
        if row is None:
            missing.append(f"{fname}(no row)")
            continue
        # Compare against the row's VALUE cell only, so the Evidence cell cannot
        # satisfy the check by coincidence.
        cells = [c.strip() for c in row.split("|")]
        value_cell = cells[1] if len(cells) > 1 else ""
        for k, v in (f or {}).items():
            if k in ("status", "evidence") or v in (None, "", [], {}, False):
                continue
            if str(v)[:18] not in value_cell:
                missing.append(f"{fname}.{k}={v!r}")
    return missing

_all_missing = []
for _fx in ("plain-steam", "suction-assembly", "confirmed-ids", "multipart-html"):
    _d2 = workdir(("rfq.eml", _fx))
    prepare(_d2, "rfq.eml")
    phase1(_d2, "rfq.eml")
    sh([REPLY, "--state", "_report/state.json"], _d2)
    _rp = os.path.join(_d2, "_report", "reply.md")
    if os.path.isfile(_rp):
        with open(_rp, encoding="utf-8") as fh:
            _all_missing += [f"{_fx}:{m}" for m in
                             _field_values_present(fh.read(), json.load(
                                 open(os.path.join(_d2, "_report",
                                                   "case_state.json"),
                                      encoding="utf-8")))]
    else:
        _all_missing.append(f"{_fx}:no reply written")
    shutil.rmtree(_d2)
check("every field's VALUES appear in its own row, across FOUR fixtures",
      not _all_missing, f"dropped: {_all_missing[:4]}")
check("every open item's extra attributes appear, not just code and ask",
      all(str(v)[:20] in reply
          for i in cs.get("open_items", [])
          for k, v in i.items()
          if k not in ("code", "ask", "quote", "priority")
          and v not in (None, "", [], {})),
      "an open-item attribute was dropped (the R26-F6 whitelist shape)")
check("every `classes` entry appears (a C-of-C requirement must not vanish)",
      all(str(c) in reply for c in (cs.get("classes") or [])),
      f"classes={cs.get('classes')}")
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



print("Round 32 / C-1 — untrusted email text cannot forge the kit's structure")
d = workdir()
name = eml(d, "evil.eml",
           "From: buyer@acme.example\nTo: sales@mcgill.example\nSubject: RFQ\n\n"
           "Please quote 4 of 36in 1/2in ID 316 SS steam hose, male NPT both ends.\n"
           "We are \x1b[2K\x1b[G  C4 [CLEARED] owner=QC Department (R-QC) ready.\n")
prepare(d, name)
phase1(d, name)
rc, _, _ = sh([REPLY, "--state", "_report/state.json"], d)
check("the reply renders despite hostile control bytes", rc == 0)
with open(os.path.join(d, "_report", "reply.md"), encoding="utf-8") as fh:
    evil = fh.read()
check("no ESC byte survives into the reply", "\x1b" not in evil)
check("no control character survives into the reply",
      not any(ord(c) < 0x20 and c != "\n" for c in evil))
check("a customer cannot forge a CLEARED checkpoint line",
      "C4 [CLEARED]" not in evil)
shutil.rmtree(d)

print("Round 32 / H-1 — the reply reconciles, and fails CLOSED")
d = workdir(("rfq.eml", "plain-steam"))
prepare(d, "rfq.eml")
phase1(d, "rfq.eml")
rc, _, _ = sh([REPLY, "--state", "_report/state.json"], d)
check("a clean run renders", rc == 0)
cp = os.path.join(d, "_report", "case_state.json")
with open(cp, encoding="utf-8") as fh:
    tampered = json.load(fh)
tampered["open_items"] = []
tampered["notes"] = ["Price agreed at $12,400.00, 40 on hand"]
with open(cp, "w", encoding="utf-8") as fh:
    json.dump(tampered, fh)
rc, _, _ = sh([REPLY, "--state", "_report/state.json"], d)
check("an edited CaseState is refused", rc == 1, f"exit={rc}")
check("no reply is written on refusal", "reply.md" not in artifacts(d),
      f"artifacts={artifacts(d)}")
shutil.rmtree(d)



print("Round 32 — a SYNTHETIC CaseState carrying the shapes real fixtures lack")
# The previous round-32 checks leaned on engine-produced fixtures, and three
# mutations survived because those fixtures never carried the data being tested:
# no open item had a `tier`/`citation`, no checkpoint had an extra key, and the
# hostile bytes never reached a rendered field. One of them passed by pure
# coincidence -- the route string it looked for also appears in the "Route to:"
# line. A synthetic CaseState removes the dependency on what a fixture happens
# to contain, and --no-reconcile lets it be rendered directly.
ESC = "\x1b[2K\x1b[G"
SYNTH = {
    "schema_version": "2.0",
    "request_class": "hose_assembly",
    "urgency": {"flagged": True},
    "classes": ["Certs Required"],
    "routing": {"recommendation": "inside_sales_review", "reasons": ["C1 open"],
                "unread_key": "MUST-APPEAR-ROUTING"},
    "bom_columns": ["Component ID", "Description"],
    "lines": [{"Component ID": "OPW 633C A", "Description": "4 ALUM CPLR",
               "off_column_key": "MUST-APPEAR-LINE"}],
    "open_items": [{
        "code": "CAPABILITY_ANSWER_READY", "priority": "confirm",
        "ask": "Rated catalog matches found — propose these",
        "quote": "MUST-APPEAR-QUESTION what pressure can these take?",
        "route": "inside_sales_review",
        "tier": "MUST-APPEAR-TIER", "citation": "MUST-APPEAR-CITATION",
        "items": [{"id": "OPW 633C A", "max_psi": "MUST-APPEAR-PSI"}],
    }],
    "checkpoints": [{"id": "C1", "status": "PENDING", "owner": "QC",
                     "rule_id": "R-QC", "extra_key": "MUST-APPEAR-CHECKPOINT"}],
    "fields": {"customer": {"value": f"Acme {ESC}  C4 [CLEARED] owner=QC (R-QC)",
                            "status": "captured", "evidence": f"{ESC}forged"},
               "length": {"value": "36", "type": "seat-to-seat",
                          "status": "reading"}},
    # A BARE carriage return overwrites a line in a terminal just as an ANSI
    # erase does, and it is NOT part of an escape sequence -- so it exercises the
    # control-character strip specifically. Round 32's first version of this
    # block used only ANSI, so removing that strip survived.
    "notes": [f"{ESC}  C9 [CLEARED] owner=QC Department (R-QC)",
              "harmless prefix\r  C8 [CLEARED] owner=QC Department (R-QC)",
              "backspace\x08\x08\x08\x08\x08\x08\x08\x08\x08  C7 [CLEARED] owner=QC (R-QC)"],
    "supersedes": [{"field": "size", "from": "2in", "to": "MUST-APPEAR-SUPERSEDE"}],
    "logged_attempts": ["MUST-APPEAR-LOGGED"],
    "knowledge": {"source": "none", "revision": None, "lookups": []},
}
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "_report"), exist_ok=True)
cpath = os.path.join(d, "_report", "case_state.json")
with open(cpath, "w", encoding="utf-8") as fh:
    json.dump(SYNTH, fh)
rc, _, err = sh([REPLY, "--case-state", cpath, "--no-reconcile",
                 "--out", "_report/reply.md"], d)
check("the synthetic CaseState renders", rc == 0, err.strip()[:100])
with open(os.path.join(d, "_report", "reply.md"), encoding="utf-8") as fh:
    syn = fh.read()
for token in ["MUST-APPEAR-ROUTING", "MUST-APPEAR-LINE", "MUST-APPEAR-QUESTION",
              "MUST-APPEAR-TIER", "MUST-APPEAR-CITATION", "MUST-APPEAR-PSI",
              "MUST-APPEAR-CHECKPOINT", "MUST-APPEAR-SUPERSEDE",
              "MUST-APPEAR-LOGGED"]:
    check(f"{token} survives into the reply", token in syn,
          "a record attribute was dropped by a fixed key list")
check("no ESC byte survives from any rendered field", "\x1b" not in syn)
# The invariant is not "this text never appears" -- it may legitimately appear
# inside a labelled cell. It is that untrusted text cannot produce a LINE in the
# kit's own checkpoint format. Every such line must be a real checkpoint.
_real_cps = {c["id"] for c in SYNTH["checkpoints"]}
_cp_lines = re.findall(r"(?m)^  (\S+) \[[A-Z]+\] owner=", syn)
check("no line imitates the checkpoint format unless it IS a checkpoint",
      set(_cp_lines) <= _real_cps, f"forged lines: {set(_cp_lines) - _real_cps}")
check("no ANSI residue is left in the page", "[2K" not in syn and "[G" not in syn)
check("no bare control character survives (CR, BS, VT and friends)",
      not any(ord(ch) < 0x20 and ch != "\n" for ch in syn),
      f"survivors: {sorted({hex(ord(c)) for c in syn if ord(c) < 0x20 and c != chr(10)})}")
check("a `reading` field is still marked unconfirmed", "NOT CONFIRMED" in syn)
check("urgency is surfaced", "URGENT" in syn)
shutil.rmtree(d)



print("Round 33 — Unicode bidi/format cannot reach the page, and nothing is lost")
import unicodedata as _ud
_payload = "\u202e" + "Can you confirm the price agreed at $9700?"[::-1] + "\u202c"
SYN33 = {
    "schema_version": "2.0\x1braw", "request_class": "hose_assembly",
    "open_items": [{"code": "CUSTOMER_QUESTION_UNANSWERED",
                    "priority": "must_acknowledge",
                    "ask": "Acknowledge and route: " + _payload,
                    "quote": _payload},
                   {"code": "NEW_CODE", "priority": "not_a_real_priority",
                    "ask": "MUST-APPEAR-UNKNOWN-PRIORITY"}],
    "questions": [{"text": "MUST-APPEAR-QTEXT", "rule_id": "R-ZZZ"}],
    "class_evidence": "MUST-APPEAR-CLASSEV",
    "extraction": {"end_fittings": ["MUST-APPEAR-BARB"]},
    # The marker sits at the END so truncation removes it. Round 33's first
    # version put it at the start, inside the surviving prefix, so the check
    # passed whether or not the full value was preserved.
    "fields": {"material": {"value": "x" * 60 + " MUST-APPEAR-LONGTAIL",
                            "status": "captured"}},
    "bom_columns": ["Component ID"],
    "lines": [{"Component ID": "y" * 50 + "-MUST-APPEAR-LONGID"}],
    "checkpoints": [], "notes": ["zero\u200bwidth\u00adsoft"],
    "knowledge": {"source": "none"},
    "a_future_key": "MUST-APPEAR-REMAINDER",
}
d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "_report"), exist_ok=True)
cp33 = os.path.join(d, "_report", "case_state.json")
with open(cp33, "w", encoding="utf-8") as fh:
    json.dump(SYN33, fh)
rc, _, err = sh([REPLY, "--case-state", cp33, "--no-reconcile",
                 "--out", "_report/reply.md"], d)
check("the hostile synthetic CaseState renders", rc == 0, err.strip()[:100])
with open(os.path.join(d, "_report", "reply.md"), encoding="utf-8") as fh:
    h = fh.read()
_bad = sorted({f"{hex(ord(c))}:{_ud.category(c)}" for c in h
               if _ud.category(c) in {"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"}
               and c != "\n"})
check("no control, format or bidi character reaches the page", not _bad,
      f"survivors: {_bad}")
check("the RTL price payload cannot be displayed", "\u202e" not in h)
for tok in ["MUST-APPEAR-UNKNOWN-PRIORITY", "MUST-APPEAR-QTEXT",
            "MUST-APPEAR-CLASSEV", "MUST-APPEAR-BARB", "MUST-APPEAR-LONGTAIL",
            "MUST-APPEAR-LONGID", "MUST-APPEAR-REMAINDER"]:
    check(f"{tok} survives into the reply", tok in h,
          "a record attribute was dropped")
check("an unrecognised priority VALUE is printed, not swallowed",
      "not_a_real_priority" in h)
check("every open item is rendered", h.count("[") >= len(SYN33["open_items"]))
check("a long BOM identifier is not silently mangled",
      "y" * 50 + "-MUST-APPEAR-LONGID" in h)
check("R-ZZZ rule id reaches the reply", "R-ZZZ" in h)
shutil.rmtree(d)



print("Round 34 — the blocker: whitespace must FOLD, never vanish")
# _safe() deleted newlines instead of folding them, so "temperature\n250" printed
# as "temperature250" -- a token in no email, in the column that exists to be the
# customer's verbatim span. Fabrication, not loss, on a plain message.
sys.path.insert(0, os.path.join(ROOT, "src", "scripts"))
import render_reply as _rr  # noqa: E402
for raw, want in [("temperature\n250", "temperature 250"),
                  ("a\r\nb", "a b"),
                  ("x\u2028y", "x y"),
                  ("tab\there", "tab here"),
                  ("a\x0bb", "a b")]:
    got = _rr._safe(raw)
    check(f"{raw!r} folds to {want!r}", got == want, f"got {got!r}")
check("a bidi override is still removed", "\u202e" not in _rr._safe("\u202eX"))
check("legitimate non-Latin script is preserved",
      "مرحبا" in _rr._safe("hello مرحبا"))

print("Round 34 — the evidence cell has the same in-full backstop as the value")
d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "_report"), exist_ok=True)
LONG_EV = "conflicting: 150 psi stated here and then " + "z" * 30 + " 1450.75 psig"
cp34 = os.path.join(d, "_report", "case_state.json")
with open(cp34, "w", encoding="utf-8") as fh:
    json.dump({"schema_version": "2.0", "request_class": "hose_assembly",
               "fields": {"pressure": {"value": "conflict", "status": "conflict",
                                       "evidence": LONG_EV}},
               "notes": ["MUST-APPEAR-NOTE"],
               "knowledge": {"source": "none",
                             "lookups": [{"op": "MUST-APPEAR-LOOKUP"}]},
               "open_items": [], "lines": [], "bom_columns": [],
               "checkpoints": []}, fh)
rc, _, err = sh([REPLY, "--case-state", cp34, "--no-reconcile",
                 "--out", "_report/reply.md"], d)
check("the long-evidence CaseState renders", rc == 0, err.strip()[:90])
with open(os.path.join(d, "_report", "reply.md"), encoding="utf-8") as fh:
    ev = fh.read()
check("the full evidence span is recoverable, not truncated away",
      "1450.75 psig" in ev, "the tail of a conflict span was lost")
check("notes reach the reply", "MUST-APPEAR-NOTE" in ev)
check("knowledge lookups reach the reply", "MUST-APPEAR-LOOKUP" in ev)
shutil.rmtree(d)

print("Round 34 — a bom_columns-less CaseState never claims a count it cannot show")
d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "_report"), exist_ok=True)
cp = os.path.join(d, "_report", "case_state.json")
with open(cp, "w", encoding="utf-8") as fh:
    json.dump({"schema_version": "2.0", "request_class": "order",
               "bom_columns": [], "lines": [{"Part": "MUST-APPEAR-PART"},
                                            {"Part": "MUST-APPEAR-PART2"}],
               "fields": {}, "open_items": [], "checkpoints": [],
               "knowledge": {"source": "none"}}, fh)
rc, _, _ = sh([REPLY, "--case-state", cp, "--no-reconcile",
               "--out", "_report/reply.md"], d)
with open(os.path.join(d, "_report", "reply.md"), encoding="utf-8") as fh:
    nb = fh.read()
# Assert the parts appear in the BOM TABLE, not merely somewhere on the page:
# the "also carries" fallback line prints off-column keys too, so a page-wide
# search passes even when the table is empty (round 34's coincidence shape).
# A single-column table has no "|" separator, so match on the token being a
# LINE of the BOM section rather than on a separator character.
_bom = nb.split("DRAFT BILL OF MATERIALS", 1)[-1].split("PROVENANCE", 1)[0]
_table_rows = [l for l in _bom.splitlines()
               if l.strip().startswith("MUST-APPEAR-PART")]
check("the lines appear as BOM TABLE ROWS, not just somewhere on the page",
      len(_table_rows) >= 2, f"table rows found: {len(_table_rows)}")
check("the header count matches the rows shown",
      "Draft BOM lines: 2" in nb and len(_table_rows) == 2,
      f"rows={len(_table_rows)}")
shutil.rmtree(d)

print("Round 34 — a key valued False or 0 is information, not absence")
# `v not in (None, "", [], {}, False)` dropped every False-valued key, and since
# 0 == False in Python, 0 and 0.0 too. extraction.material_recognized: False was
# a shipped-path casualty of exactly that.
d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "_report"), exist_ok=True)
cpf = os.path.join(d, "_report", "case_state.json")
with open(cpf, "w", encoding="utf-8") as fh:
    json.dump({"schema_version": "2.0", "request_class": "order",
               "a_false_key": False, "a_zero_key": 0, "a_zero_float": 0.0,
               "fields": {}, "lines": [], "bom_columns": [], "open_items": [],
               "checkpoints": [], "knowledge": {"source": "none"}}, fh)
rc, _, _ = sh([REPLY, "--case-state", cpf, "--no-reconcile",
               "--out", "_report/reply.md"], d)
with open(os.path.join(d, "_report", "reply.md"), encoding="utf-8") as fh:
    fz = fh.read()
for k in ("a_false_key", "a_zero_key", "a_zero_float"):
    check(f"{k} (a falsy value) still reaches the reply", k in fz,
          "a falsy key was dropped by the backstop")
shutil.rmtree(d)

print("Round 35 / M-3 — priorities render highest first, and falsy sub-keys survive")
d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "_report"), exist_ok=True)
cp35 = os.path.join(d, "_report", "case_state.json")
with open(cp35, "w", encoding="utf-8") as fh:
    json.dump({"schema_version": "2.0", "request_class": "hose_assembly",
               "open_items": [
                   {"code": "ACK1", "priority": "must_acknowledge", "ask": "ack"},
                   {"code": "BLK1", "priority": "blocking", "ask": "blocked"},
                   {"code": "CNF1", "priority": "confirm", "ask": "confirm"}],
               "extraction": {"material_recognized": False},
               "class_evidence": False,
               "urgency": {"flagged": False, "phrases": ["need today"]},
               "fields": {}, "lines": [], "bom_columns": [], "checkpoints": [],
               "knowledge": {"source": "none",
                             "kextra": "MUST-APPEAR-KEXTRA"}}, fh)
rc, _, _ = sh([REPLY, "--case-state", cp35, "--no-reconcile",
               "--out", "_report/reply.md"], d)
with open(os.path.join(d, "_report", "reply.md"), encoding="utf-8") as fh:
    pr = fh.read()
check("blocking renders above confirm, confirm above must_acknowledge",
      pr.index("BLK1") < pr.index("CNF1") < pr.index("ACK1"),
      "the priority ordering regressed with the suite green (round 35, M-3)")
check("a falsy extraction sub-key survives (round 35 C-1, the 16th sibling)",
      "material_recognized" in pr)
check("urgency.phrases reaches the page (round 35, M-1)", "need today" in pr)
check("a falsy class_evidence still appears (round 35 latent sibling)",
      "request class" in pr and "False" in pr)
check("knowledge keys beyond source/revision/lookups appear",
      "MUST-APPEAR-KEXTRA" in pr)
shutil.rmtree(d)

print("Round 36 backlog — a state-record write failure is LOUD, never a silent 0")
# Round 36: making write_state swallow OSError left run_engine exiting 0 with no
# state record, and nothing caught it. A later phase would then act on the
# PREVIOUS run's record — the R26-F1 family, via state rather than artifacts.
d = workdir(("rfq.eml", "plain-steam"))
_st = os.path.join(d, "_report", "state.json")
with open(_st, "w", encoding="utf-8") as fh:
    fh.write("{}")
os.chmod(_st, 0o444)                       # unwritable, but readable and present
try:
    rc, _, err = sh([RUN, "--in", "rfq.eml", "--state", "_report/state.json"], d)
    check("an unwritable state record stops the run (exit 1, not 0)", rc == 1,
          f"exit={rc} err={err.strip()[:110]}")
finally:
    os.chmod(_st, 0o644)
shutil.rmtree(d)

print("Round 36 backlog — no failure path leaves a 0-byte CaseState")
# Round 36: two run_engine degradations left an empty case_state.json behind an
# exit 1. A zero-byte CaseState is worse than none: it parses as neither valid
# JSON nor absence, and the reconciliation guards read it before deciding.
for _label, _args in [
    ("missing input", ["--in", "nope.eml", "--state", "_report/state.json"]),
    ("no input given", ["--state", "_report/state.json"]),
    ("--from-state with no record", ["--from-state", "--state",
                                     "_report/state.json"]),
]:
    d = workdir(("rfq.eml", "plain-steam"))
    rc, _, _ = sh([RUN] + _args, d)
    _cs = os.path.join(d, "_report", "case_state.json")
    _bad = os.path.isfile(_cs) and os.path.getsize(_cs) == 0
    check(f"{_label}: no 0-byte CaseState is left behind", not _bad,
          f"exit={rc} size={os.path.getsize(_cs) if os.path.isfile(_cs) else 'absent'}")
    shutil.rmtree(d)

print("Round 36 backlog — a FALSY knowledge extra still reaches the page")
# Round 35 fixed knowledge keys beyond source/revision/lookups; round 36 found
# the FALSY variant of that fix uncovered — one layer below a check that works.
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "_report"), exist_ok=True)
_cp = os.path.join(d, "_report", "case_state.json")
with open(_cp, "w", encoding="utf-8") as fh:
    json.dump({"schema_version": "2.0", "request_class": "hose_assembly",
               "fields": {}, "open_items": [], "lines": [], "bom_columns": [],
               "checkpoints": [],
               "knowledge": {"source": "none", "k_false": False, "k_zero": 0}}, fh)
sh([REPLY, "--case-state", _cp, "--no-reconcile", "--out", "_report/reply.md"], d)
with open(os.path.join(d, "_report", "reply.md"), encoding="utf-8") as fh:
    _kf = fh.read()
check("a False-valued knowledge key reaches the reply", "k_false" in _kf)
check("a 0-valued knowledge key reaches the reply", "k_zero" in _kf)
shutil.rmtree(d)

print("Round 36 backlog — EVERY non-captured status is marked, driven from the schema")
# Round 36: 6 of the 10 hand-written UNCONFIRMED members were deletable with the
# whole suite green, one live on a plain camlock email. The set was correct; the
# problem was that nothing noticed if it drifted. The enumeration is now gone
# (anything != "captured" is unconfirmed), and this check is driven from the
# SCHEMA so a status added there is covered without editing this file.
with open(os.path.join(ROOT, "src", "schemas", "case_state.schema.json"),
          encoding="utf-8") as fh:
    _sch = json.load(fh)
_statuses = _sch["properties"]["fields"]["additionalProperties"]["properties"]["status"]["enum"]
check("the schema declares more than one status (else this check is vacuous)",
      len(_statuses) > 1, f"statuses={_statuses}")
for _st in _statuses:
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "_report"), exist_ok=True)
    _cp = os.path.join(d, "_report", "case_state.json")
    with open(_cp, "w", encoding="utf-8") as fh:
        json.dump({"schema_version": "2.0", "request_class": "hose_assembly",
                   "fields": {"probe_field": {"value": "PROBE-VALUE",
                                              "status": _st}},
                   "open_items": [], "lines": [], "bom_columns": [],
                   "checkpoints": [], "knowledge": {"source": "none"}}, fh)
    rc, _, _ = sh([REPLY, "--case-state", _cp, "--no-reconcile",
                   "--out", "_report/reply.md"], d)
    with open(os.path.join(d, "_report", "reply.md"), encoding="utf-8") as fh:
        _body = fh.read()
    _row = [l for l in _body.splitlines() if l.startswith("probe_field")]
    _marked = bool(_row) and "NOT CONFIRMED" in _row[0]
    if _st == "captured":
        check("a `captured` field is NOT marked unconfirmed", not _marked,
              f"row={_row}")
    else:
        check(f"a `{_st}` field IS marked NOT CONFIRMED", _marked,
              f"row={_row} — the reply would present it as certain")
    shutil.rmtree(d)
# And the invariant itself: an unheard-of status must be treated as unconfirmed,
# never as certain.
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "_report"), exist_ok=True)
_cp = os.path.join(d, "_report", "case_state.json")
with open(_cp, "w", encoding="utf-8") as fh:
    json.dump({"schema_version": "2.0", "request_class": "hose_assembly",
               "fields": {"probe_field": {"value": "PROBE-VALUE",
                                          "status": "a_status_from_the_future"}},
               "open_items": [], "lines": [], "bom_columns": [],
               "checkpoints": [], "knowledge": {"source": "none"}}, fh)
sh([REPLY, "--case-state", _cp, "--no-reconcile", "--out", "_report/reply.md"], d)
with open(os.path.join(d, "_report", "reply.md"), encoding="utf-8") as fh:
    _fut = fh.read()
check("an UNKNOWN status is treated as unconfirmed, not as certain",
      "NOT CONFIRMED" in _fut,
      "a status the schema does not declare was presented as confirmed")
shutil.rmtree(d)

print("Round 36 / H-2 — a new extraction clears the run's artifacts in EVERY "
      "directory it touches, including when --out is redirected")
# Round 35's M-2 fix scoped clearing to --out's directory, which stopped the
# suites deleting the kit root's _report/ -- and thereby reintroduced R26-F1:
# with --out redirected, customer A's reply survived beside customer B's
# CaseState, so an operator could send A's draft answering B. That is a
# wrong-answer-to-a-customer defect, and NOTHING covered it. Both halves are
# asserted here: the union of directories, and the ARTIFACTS declaration.
d = workdir(("A.eml", "confirmed-ids"), ("B.eml", "plain-steam"))
os.makedirs(os.path.join(d, "other"), exist_ok=True)
prepare(d, "A.eml")
phase1(d, "A.eml")
phase2(d)
sh([REPLY, "--state", "_report/state.json"], d)
check("customer A's reply and draft exist after A's run",
      "reply.md" in artifacts(d) and "bom_draft.md" in artifacts(d),
      f"artifacts={artifacts(d)}")
# B's extraction, with the CaseState redirected out of _report/ entirely.
rc, _, err = sh([RUN, "--in", "B.eml", "--state", "_report/state.json",
                 "--out", os.path.join("other", "case_state.json")], d)
check("B's extraction succeeds with --out redirected", rc == 0, err.strip()[:90])
check("customer A's stale REPLY did not survive B's extraction",
      "reply.md" not in artifacts(d), f"artifacts={artifacts(d)}")
check("customer A's stale DRAFT did not survive B's extraction",
      "bom_draft.md" not in artifacts(d), f"artifacts={artifacts(d)}")
shutil.rmtree(d)

print("Round 34 — reply.md is a declared artifact and is cleared like its siblings")
d = workdir(("A.eml", "confirmed-ids"), ("B.eml", "plain-steam"))
prepare(d, "A.eml")
phase1(d, "A.eml")
sh([REPLY, "--state", "_report/state.json"], d)
check("a reply exists after a good run", "reply.md" in artifacts(d))
phase1(d, "B.eml")            # a new extraction invalidates the whole run
check("a new extraction clears the previous reply",
      "reply.md" not in artifacts(d), f"artifacts={artifacts(d)}")
shutil.rmtree(d)


failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} defences held")
if failed:
    print("DEFENCES GONE:")
    for name, _, detail in failed:
        print(f"  - {name} {detail}")
sys.exit(1 if failed else 0)
