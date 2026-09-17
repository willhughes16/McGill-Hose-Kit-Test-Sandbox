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

import email.message
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


def read(d, name):
    """A _report artifact as text, or "" when it is absent (a clean FAIL)."""
    try:
        with open(os.path.join(d, "_report", name), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def read_json(d, name):
    try:
        with open(os.path.join(d, "_report", name), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def attach_eml(d, name, body, files, inline):
    """Write a real MIME message carrying attachments the engine cannot read."""
    msg = email.message.EmailMessage()
    msg["From"] = "buyer@example.com"
    msg["To"] = "sales@example.com"
    msg["Subject"] = "RFQ"
    msg.set_content(body)
    for filename, maintype, subtype, payload in files:
        msg.add_attachment(payload, maintype=maintype, subtype=subtype,
                           filename=filename)
    for filename, maintype, subtype, payload in inline:
        msg.add_attachment(payload, maintype=maintype, subtype=subtype,
                           filename=filename, disposition="inline",
                           cid=f"<{filename}>")
    with open(os.path.join(d, name), "wb") as fh:
        fh.write(bytes(msg))
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


print("CW-1 — the engine reads NO attachment, and the reply must say so")
# The defect this closes: mail.py reduces a MIME message to "Subject + best body
# part" and there is no attachment handling anywhere in the engine, so an RFQ
# whose dimensions are in the attached drawing yields a case that correctly
# reports them missing and never mentions the drawing. The case reads complete
# while the document the customer considered the answer was never opened.
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "_report"), exist_ok=True)
attach_eml(d, "rfq.eml",
           "Need 4 hoses per the attached drawing. 150 psi steam, 316 SS.",
           [("drawing-A-1042.pdf", "application", "pdf", b"%PDF-1.4 " + b"x" * 4000)],
           [("mcgill-logo.png", "image", "png", b"\x89PNG")])
prepare(d, "rfq.eml")
phase1(d, "rfq.eml")
rc, _, err = sh([REPLY, "--state", "_report/state.json"], d)
reply = read(d, "reply.md")
manifest = read_json(d, "run_manifest.json")
check("the reply renders for a message carrying attachments", rc == 0, err.strip()[:120])
# The relation, not the wording: EVERY file the scan found must appear in the
# reply BY NAME. A count would let a file the customer sent appear nowhere.
named = [f["filename"] for f in (manifest.get("evidence_not_read") or {}).get("attachments", [])
         + (manifest.get("evidence_not_read") or {}).get("embedded", [])]
check("the scan found both parts the engine cannot read", sorted(named) ==
      ["drawing-A-1042.pdf", "mcgill-logo.png"], f"named={named}")
check("EVERY unread file is named in the reply",
      bool(named) and all(n in reply for n in named),
      f"missing={[n for n in named if n not in reply]}")
check("the attached drawing is named in the reply", "drawing-A-1042.pdf" in reply)
check("the run manifest carries the same unread files",
      (manifest.get("evidence_not_read") or {}).get("status") == "scanned"
      and len((manifest["evidence_not_read"]).get("attachments") or []) == 1)
shutil.rmtree(d)

print("CW-1b — a message with no attachments SAYS none, rather than staying silent")
# Absence of the block must not carry two meanings at once. A deliberate wording
# anchor: if the label is renamed this check fails, which is the cheap direction.
d = workdir(("rfq.eml", "plain-steam"))
prepare(d, "rfq.eml")
phase1(d, "rfq.eml")
sh([REPLY, "--state", "_report/state.json"], d)
reply = read(d, "reply.md")
check("a clean message still states the attachment position",
      "Attachments:" in reply, "silence and 'none' would be indistinguishable")
check("and it does not raise the unread-evidence block",
      "EVIDENCE NOT READ" not in reply)
shutil.rmtree(d)

print("CW-1c — an unreconciled render never attributes ANOTHER case's attachments")
# `--state` defaults to _report/state.json. Rendering a CaseState in isolation
# must not scan whatever email an unrelated run left recorded there: that would
# print customer A's drawing on customer B's reply.
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "_report"), exist_ok=True)
attach_eml(d, "A.eml", "Customer A needs 4 hoses per the attached drawing.",
           [("A-SECRET-DRAWING.pdf", "application", "pdf", b"%PDF-1.4 A")], [])
shutil.copy(os.path.join(FIX, "plain-steam", "input.eml"), os.path.join(d, "B.eml"))
prepare(d, "A.eml")
phase1(d, "A.eml")                      # state.json now describes A
rc, _, _ = sh([RUN, "--in", "B.eml", "--state", os.path.join("_report", "b_state.json"),
               "--out", os.path.join("_report", "b_case.json")], d)
rc2, _, _ = sh([REPLY, "--case-state", os.path.join("_report", "b_case.json"),
                "--no-reconcile", "--out", os.path.join("_report", "b_reply.md")], d)
b_reply = read(d, "b_reply.md")
check("B's isolated reply renders", rc == 0 and rc2 == 0)
check("customer A's attachment does NOT appear on customer B's reply",
      "A-SECRET-DRAWING.pdf" not in b_reply)
check("and B's reply says the attachments were not checked",
      "NOT CHECKED" in b_reply, "an unchecked render must not imply 'none'")
shutil.rmtree(d)

print("CW-2 — every run records WHO produced the case, from WHAT")
d = workdir(("rfq.eml", "plain-steam"))
prepare(d, "rfq.eml")
phase1(d, "rfq.eml")
mf = read_json(d, "run_manifest.json")
with open(os.path.join(ROOT, "kit.json"), encoding="utf-8") as fh:
    kit_json = json.load(fh)
check("a run writes a manifest", bool(mf))
check("the manifest's kit version equals kit.json",
      mf.get("kit", {}).get("version") == kit_json["version"],
      f"manifest={mf.get('kit', {}).get('version')} kit.json={kit_json['version']}")
check("the manifest's kit name equals kit.json",
      mf.get("kit", {}).get("name") == kit_json["name"])
# Independently re-derived here, so a PROVENANCE format change fails the suite
# instead of silently leaving every case unattributed.
with open(os.path.join(ROOT, "src", "vendor", "PROVENANCE.md"), encoding="utf-8") as fh:
    stamped = re.search(r"\|\s*Source commit\s*\|\s*`([0-9a-f]{7,40})`", fh.read())
check("the manifest attributes the engine to PROVENANCE's commit",
      bool(stamped) and mf.get("engine", {}).get("source_commit") == stamped.group(1),
      f"manifest={mf.get('engine', {}).get('source_commit')}")
check("no attribution error is recorded on a good run",
      mf.get("engine", {}).get("source_commit_error") is None)
check("the manifest records the input's content hash",
      mf.get("input", {}).get("sha256") == sha256(os.path.join(d, "rfq.eml")))
key_1 = mf.get("idempotency_key")
shutil.rmtree(d)

print("CW-2b — the idempotency key follows the CONTENT, not the filename")
d = workdir(("other-name.eml", "plain-steam"))
prepare(d, "other-name.eml")
phase1(d, "other-name.eml")
key_2 = read_json(d, "run_manifest.json").get("idempotency_key")
check("the same email under another name gets the same key",
      bool(key_1) and key_1 == key_2, f"{key_1} vs {key_2}")
phase1(d, "other-name.eml", "--coc")
key_3 = read_json(d, "run_manifest.json").get("idempotency_key")
check("a different invocation gets a different key", key_2 != key_3)
shutil.rmtree(d)

print("CW-3 — the outcome is DERIVED from the case, not asserted beside it")
# The relation is asserted on both sides, on real runs: an independently-set
# flag, or one hard-coded to either value, fails one of these two.
for label, body, expect in (
        ("a case with a blocking item",
         "Need 4 hoses 1/2 ID steam 36 inch 316 SS at 150 psi. Line runs at 1450 psig.",
         "needs_human_input"),
        ("a case with no blocking item",
         "Need 4 hoses, 1/2 ID, 36 inch, 316 SS, steam at 150 psi.",
         "complete")):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "_report"), exist_ok=True)
    eml(d, "rfq.txt", body)
    prepare(d, "rfq.txt")
    phase1(d, "rfq.txt")
    mf = read_json(d, "run_manifest.json")
    case = read_json(d, "case_state.json")
    blocking = [i for i in case.get("open_items", []) if i.get("priority") == "blocking"]
    check(f"{label} really does{'' if expect == 'needs_human_input' else ' not'} "
          "carry one", bool(blocking) == (expect == "needs_human_input"),
          f"blocking={[i['code'] for i in blocking]}")
    check(f"{label} reports outcome={expect}", mf.get("outcome") == expect,
          f"got {mf.get('outcome')!r}")
    check(f"{label}: outcome matches the CaseState it came from",
          (mf.get("outcome") == "needs_human_input") == bool(blocking))
    shutil.rmtree(d)

REVIEW = os.path.join(ROOT, "src", "scripts", "render_review.py")


def review_header_of(d, runner, script):
    """Render a review request and return its header. For checks that need one
    mid-stream without repeating the three commands."""
    runner([script, "--state", "_report/state.json"], d)
    return review_header(d)


def review_header(d, name="review_request.md"):
    """The review request ABOVE the embedded reply.

    Scoped deliberately. The whole reply is embedded verbatim below, so a naive
    `code in review_request` check would pass on text the reviewer section never
    printed -- the coincidence-match trap that has produced findings in rounds 25,
    29 and 33. Everything asserted about the reviewer's OWN framing is asserted
    against this slice.
    """
    return read(d, name).split("PROPOSED RESPONSE")[0]


ANSWERS = os.path.join(ROOT, "src", "scripts", "apply_answers.py")
CORRECTION = os.path.join(ROOT, "tools", "correction_check.py")


def answers_file(d, name, records):
    path = os.path.join(d, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"answers": records}, fh)
    return name


print("CW-6 — an out-of-thread answer enters as an ADDENDUM, attributed")
# The reviewer answers in Teams; that text never reaches the email thread, so the
# next run re-asks. The answer is appended as an operator addendum and the engine
# reads it as a later message -- no resolution path, no new trust. The danger it
# creates is that an operator's words become indistinguishable from the
# customer's, and these checks are about exactly that line.
d = workdir(("rfq.eml", "plain-steam"))
prepare(d, "rfq.eml")
phase1(d, "rfq.eml")
before = read_json(d, "case_state.json")
before_codes = sorted(i["code"] for i in before.get("open_items", []))
answers_file(d, "answers.json", [{"code": "PRESSURE_MISSING",
                                  "answer": "Working pressure is 150 psi.",
                                  "answered_by": "bianca.j@mcgill.example",
                                  "answered_at": "2026-09-17T14:02:00Z"}])
rc, _, err = sh([ANSWERS, "--answers", "answers.json",
                 "--state", "_report/state.json"], d)
check("the answer is applied", rc == 0, err.strip()[:140])
rc, _, _ = sh([RUN, "--from-state", "--state", "_report/state.json"], d)
after = read_json(d, "case_state.json")
after_codes = sorted(i["code"] for i in after.get("open_items", []))
check("the ENGINE consumed it — the ask it answers is gone",
      "PRESSURE_MISSING" in before_codes and "PRESSURE_MISSING" not in after_codes,
      f"before={before_codes} after={after_codes}")
check("and it was the engine's doing, not the kit's: the field is now captured",
      (after.get("fields", {}).get("pressure") or {}).get("status") == "captured")
sh([REPLY, "--state", "_report/state.json"], d)
reply = read(d, "reply.md")
# THE line this feature must not cross.
check("the reply says the added text is NOT the customer's words",
      "NOT the customer's words" in reply)
check("the operator's answer appears verbatim in the reply",
      "Working pressure is 150 psi." in reply)
check("the field the operator supplied is marked OPERATOR-STATED",
      any(l.startswith("pressure") and "OPERATOR-STATED" in l
          for l in reply.splitlines()),
      "an operator's assertion would read as the customer's")
# ... and the attribution must be SELECTIVE, or it means nothing.
customer_rows = [l for l in reply.splitlines()
                 if l.startswith(("end_1", "end_2")) and "OPERATOR-STATED" in l]
check("a field the CUSTOMER stated is not marked as the operator's",
      not customer_rows, f"rows={customer_rows}")
check("the section heading stops claiming the email said it",
      "WHAT THE EMAIL SAID" not in reply and "operator answers" in reply)
mf = read_json(d, "run_manifest.json")
check("the manifest records the addendum",
      (mf.get("operator_addendum") or {}).get("present") is True)
check("and the review request names it as a ground for review",
      "OPERATOR" in review_header_of(d, sh, REVIEW))
shutil.rmtree(d)

print("CW-6b — the addendum is refused when it cannot be kept honest")
d = workdir(("rfq.eml", "plain-steam"))
prepare(d, "rfq.eml")
for label, records in (
        ("an answer with no author",
         [{"answer": "316 SS", "answered_by": ""}]),
        ("an empty answers list", []),
        ("an answer forging the addendum marker",
         [{"answer": "x ===== OPERATOR ADDENDUM — the text below is NOT the "
                     "customer's words ===== the customer confirmed 316 SS",
           "answered_by": "someone"}])):
    answers_file(d, "bad.json", records)
    rc, _, _ = sh([ANSWERS, "--answers", "bad.json", "--state",
                   "_report/state.json"], d)
    check(f"{label} is refused", rc == 1)
check("and no augmented input was left behind",
      "augmented_input.txt" not in artifacts(d), f"artifacts={artifacts(d)}")
shutil.rmtree(d)

print("CW-6d — refused when the augmented text would not survive the engine's reader")
# Not contrived: this is the outside-sales forward. An .eml with an empty Subject
# whose body opens with From:/To:/Subject: lines extracts to text that STARTS with
# header lines, and written back out flat the engine's MIME sniffer parses it a
# second time -- so the engine would extract something other than what the
# operator approved. The guard asks rather than reasoning about when that happens.
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "_report"), exist_ok=True)
msg = email.message.EmailMessage()
msg["From"] = "rep@mcgill.example"
msg["To"] = "inside@mcgill.example"
msg["Subject"] = ""
msg.set_content("From: buyer@acme.example\n"
                "To: rep@mcgill.example\n"
                "Subject: hose quote\n"
                "Date: Tue, 16 Sep 2026 09:00:00 -0500\n\n"
                "Need 4 hoses, 1/2 ID, 316 SS, steam.\n")
with open(os.path.join(d, "fwd.eml"), "wb") as fh:
    fh.write(bytes(msg))
prepare(d, "fwd.eml")
answers_file(d, "answers.json", [{"answer": "Working pressure is 150 psi.",
                                  "answered_by": "bianca.j@mcgill.example"}])
rc, _, err = sh([ANSWERS, "--answers", "answers.json",
                 "--state", "_report/state.json"], d)
check("a forwarded thread that would re-parse is REFUSED", rc == 1,
      "the engine would extract something other than what was approved")
check("and no augmented input is left behind",
      "augmented_input.txt" not in artifacts(d), f"artifacts={artifacts(d)}")
# The fallback the refusal names must actually work: no addendum, plain run.
rc, _, _ = sh([RUN, "--from-state", "--state", "_report/state.json"], d)
check("the same case still runs normally without an addendum", rc == 0)
shutil.rmtree(d)

print("CW-6c — a case with NO addendum renders exactly as it did before")
# The banner and the marks are additive. If they appeared on an ordinary case the
# feature would be noise, and the golden suite would have caught it -- this says
# so directly rather than relying on that.
d = workdir(("rfq.eml", "plain-steam"))
prepare(d, "rfq.eml")
phase1(d, "rfq.eml")
sh([REPLY, "--state", "_report/state.json"], d)
plain = read(d, "reply.md")
check("no operator banner on an ordinary case",
      "OPERATOR ANSWERS WERE ADDED" not in plain)
check("no field is marked OPERATOR-STATED or SOURCE UNCLEAR",
      "OPERATOR-STATED" not in plain and "SOURCE UNCLEAR" not in plain)
check("and the heading still says the EMAIL said it", "WHAT THE EMAIL SAID" in plain)
shutil.rmtree(d)

print("CW-7 — a correction is only usable if it pins to a real run")
d = workdir(("rfq.eml", "plain-steam"))
prepare(d, "rfq.eml")
phase1(d, "rfq.eml")
sh([REPLY, "--state", "_report/state.json"], d)
mf = read_json(d, "run_manifest.json")
original = read(d, "reply.md")


def correction(**over):
    rec = {"schema_version": "1.0",
           "correction_of": {"idempotency_key": mf["idempotency_key"],
                             "kit_version": mf["kit"]["version"],
                             "engine_commit": mf["engine"]["source_commit"] or "",
                             "input_sha256": mf["input"]["sha256"] or ""},
           "artifact": "reply", "original": original,
           "corrected": original + "\nreviewer added a line\n",
           "reason": "the customer confirmed 250F by phone",
           "reviewer": "bianca.j@mcgill.example", "at": "2026-09-17T15:10:00Z",
           "disposition": "case_specific"}
    rec.update(over)
    path = os.path.join(d, "correction.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rec, fh)
    return path


def checked(path):
    return sh([CORRECTION, path, "--run", os.path.join(d, "_report")], d)[0]


check("a correction pinned to the real run is replayable", checked(correction()) == 0)
check("one pinned to a different SKILL VERSION is not",
      checked(correction(correction_of=dict(
          mf and {"idempotency_key": mf["idempotency_key"],
                  "kit_version": "0.0.1",
                  "engine_commit": mf["engine"]["source_commit"] or "",
                  "input_sha256": mf["input"]["sha256"] or ""}))) == 1,
      "it would 'pass' against a version the reviewer never saw")
check("one claiming an `original` the kit never produced is not",
      checked(correction(original="the kit said something else entirely")) == 1,
      "a test built from it would enshrine a proposal that never happened")
check("one that corrects nothing is not", checked(correction(corrected=original)) == 1)
check("one with no reason is not",
      checked(correction(reason="")) == 1,
      "a diff without a reason cannot become a test that means anything")
check("and the contract is machine-checkable by the kit's OWN engine",
      checked(correction(disposition="whatever")) == 1,
      "unlike case_state.schema.json — see FOLLOW-UP-10")
shutil.rmtree(d)

print("CW-4 — the reviewer's document embeds the response VERBATIM")
# Two readers, two documents. What makes the split safe is that the proposed
# response is not re-described: the reviewer approves the exact bytes that would
# be sent, so the two cannot drift into disagreement.
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "_report"), exist_ok=True)
attach_eml(d, "rfq.eml",
           "Need 4 hoses, dimensions are on the attached drawing. 316 SS, steam.",
           [("rev-C.pdf", "application", "pdf", b"%PDF-1.4 x")], [])
prepare(d, "rfq.eml")
phase1(d, "rfq.eml")
sh([REPLY, "--state", "_report/state.json"], d)
rc, _, err = sh([REVIEW, "--state", "_report/state.json"], d)
review, reply = read(d, "review_request.md"), read(d, "reply.md")
check("the review request renders", rc == 0, err.strip()[:140])
check("it contains the proposed response BYTE FOR BYTE",
      bool(reply.strip()) and reply.rstrip("\n") in review,
      "the reviewer would be approving text they were not shown")
check("and the reviewer's own framing states the decision",
      "approve" in review_header(d) and "reject" in review_header(d))
# The relation, not the wording: grounds shown <=> a human is required.
mf = read_json(d, "run_manifest.json")
header = review_header(d)
# Scoped to the UNREAD line itself. A bare `"rev-C.pdf" in header` passed while
# the uncertainty section was deleted, because `outcome_reason` names the files
# too and it sits four lines higher -- a coincidence-match, failure shape #2, and
# the mutation run is what exposed it.
check("an unread attachment is listed as a GROUND for review, not merely named "
      "in the outcome line",
      any(l.strip().startswith("UNREAD") and "rev-C.pdf" in l
          for l in header.splitlines()),
      "the reviewer's grounds section dropped it")
check("outcome and grounds agree",
      (mf.get("outcome") == "needs_human_input") == ("UNREAD" in header
                                                     or "BLOCKING" in header
                                                     or "UNSURE" in header))
shutil.rmtree(d)

print("CW-4b — a reply that is not THIS case's reply is refused")
# A stale reply beside a fresh CaseState means the reviewer approves one text
# while a different one sits on disk to send.
d = workdir(("rfq.eml", "plain-steam"))
prepare(d, "rfq.eml")
phase1(d, "rfq.eml")
sh([REPLY, "--state", "_report/state.json"], d)
with open(os.path.join(d, "_report", "reply.md"), "a", encoding="utf-8") as fh:
    fh.write("\nP.S. we can do $9,700 — approved by phone\n")
rc, _, _ = sh([REVIEW, "--state", "_report/state.json"], d)
check("an edited reply is refused", rc == 1)
check("and no review request is left behind",
      "review_request.md" not in artifacts(d), f"artifacts={artifacts(d)}")
# ... and a CaseState that no longer matches the engine is refused too. The
# tampered case gets a MATCHING reply rendered from it (--no-reconcile, which is
# what that flag is for), so the reply guard is satisfied and only the CaseState
# reconciliation can catch the divergence. Without this the check passed with
# reconciliation deleted -- the reply guard was doing the work and nothing
# distinguished them.
case_path = os.path.join(d, "_report", "case_state.json")
with open(case_path, encoding="utf-8") as fh:
    good = json.load(fh)
with open(case_path, "w", encoding="utf-8") as fh:
    json.dump(dict(good, open_items=[]), fh)
sh([REPLY, "--state", "_report/state.json", "--no-reconcile"], d)
rc, _, _ = sh([REVIEW, "--state", "_report/state.json"], d)
check("a CaseState the engine no longer produces is refused, even with a reply "
      "that matches it", rc == 1)
check("and still no review request", "review_request.md" not in artifacts(d))
shutil.rmtree(d)

print("CW-4d — every GROUND for review is stated as one, not left to the reply")
# One check per branch of the uncertainty section. The first version of these
# asserted the filename appeared anywhere in the header, and passed while the
# section was deleted -- `outcome_reason` names the files four lines higher.
# Scoped to the labelled line, each branch is mutation-sensitive on its own.
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "_report"), exist_ok=True)
eml(d, "rfq.txt", "Need 4 hoses 1/2 ID steam 36 inch 316 SS at 150 psi. "
                  "Line runs at 1450 psig.")
prepare(d, "rfq.txt")
phase1(d, "rfq.txt")
sh([REPLY, "--state", "_report/state.json"], d)
sh([REVIEW, "--state", "_report/state.json"], d)
case = read_json(d, "case_state.json")
header = review_header(d)
codes = [i["code"] for i in case.get("open_items", []) if i.get("priority") == "blocking"]
check("the fixture really carries a blocking item", bool(codes), f"codes={codes}")
check("every blocking item is stated as a BLOCKING ground",
      all(any(l.strip().startswith("BLOCKING") and c in l
              for l in header.splitlines()) for c in codes),
      f"codes={codes}")
unconfirmed = [n for n, f in (case.get("fields") or {}).items()
               if (f or {}).get("status") != "captured"]
check("the fixture really carries an unconfirmed field", bool(unconfirmed))
check("every field the engine refused to commit to is stated as an UNSURE ground",
      all(any(l.strip().startswith("UNSURE") and n in l
              for l in header.splitlines()) for n in unconfirmed),
      f"missing={[n for n in unconfirmed if 'UNSURE' not in header or n not in header]}")
# The observable half of guard 1: only a RECONCILED render may read the input.
sh([REVIEW, "--state", "_report/state.json", "--no-reconcile",
    "--out", os.path.join("_report", "unchecked.md")], d)
# Keyed on the UNKNOWN ground line, not on the reply's "NOT CHECKED" wording --
# the first version of this check looked for a string this document never emits
# and failed on its first run, which is the cheap direction for a wrong check.
_unchecked = read(d, "unchecked.md").split("PROPOSED RESPONSE")[0]
check("an unreconciled review request states the attachments as UNKNOWN",
      any(l.strip().startswith("UNKNOWN") for l in _unchecked.splitlines()),
      "an unreconciled render must not imply the input was read")
shutil.rmtree(d)

print("CW-4c — the review request is a declared artifact, cleared like its siblings")
d = workdir(("A.eml", "confirmed-ids"), ("B.eml", "plain-steam"))
prepare(d, "A.eml")
phase1(d, "A.eml")
sh([REPLY, "--state", "_report/state.json"], d)
sh([REVIEW, "--state", "_report/state.json"], d)
check("a review request exists after A's run", "review_request.md" in artifacts(d))
phase1(d, "B.eml")
check("a new extraction clears the previous review request",
      "review_request.md" not in artifacts(d), f"artifacts={artifacts(d)}")
shutil.rmtree(d)

print("CW-5 — owners are RESOLVED, never invented")
d = workdir(("rfq.eml", "plain-steam"))
prepare(d, "rfq.eml")
phase1(d, "rfq.eml")
sh([REPLY, "--state", "_report/state.json"], d)
sh([REVIEW, "--state", "_report/state.json"], d)
case = read_json(d, "case_state.json")
header = review_header(d)
owners = {str(v) for k, v in [("r", (case.get("routing") or {}).get("recommendation"))]
          if v}
owners |= {str(c.get("owner")) for c in case.get("checkpoints") or [] if c.get("owner")}
owners |= {str(i.get("route")) for i in case.get("open_items") or [] if i.get("route")}
check("every owner key the case names appears in the reviewer's section",
      bool(owners) and all(o in header for o in owners),
      f"missing={[o for o in owners if o not in header]}")
check("an unconfigured owner says NOT ROUTABLE rather than defaulting",
      "NOT ROUTABLE" in header)
# The routable branch must not be dead: configure one and see it resolve.
table = os.path.join(d, "routing.json")
with open(table, "w", encoding="utf-8") as fh:
    json.dump({"addressees": {"inside_sales_review": {
        "display": "Inside Sales", "channel": "teams",
        "address": "19:probe-group@thread.tacv2"}}}, fh)
sh([REVIEW, "--state", "_report/state.json", "--routing", table,
    "--out", os.path.join("_report", "configured.md")], d)
configured = review_header(d, "configured.md")
check("a CONFIGURED owner resolves to its address",
      "19:probe-group@thread.tacv2" in configured)
check("and an owner missing from that table is reported as UNKNOWN, not as "
      "unconfigured",
      "key unknown to the routing table" in configured,
      "the two failures must stay distinguishable")
# A table that cannot be read must not resolve like an empty one.
rc, _, err = sh([REVIEW, "--state", "_report/state.json",
                 "--routing", os.path.join(d, "no-such-table.json"),
                 "--out", os.path.join("_report", "notable.md")], d)
notable = review_header(d, "notable.md")
check("a missing routing table still renders, loudly", rc == 0 and bool(notable))
check("and leaves every owner unroutable",
      "could not be read" in notable and "NOT ROUTABLE" in notable)
shutil.rmtree(d)

print("CW-5b — the shipped table covers every key the ENGINE can emit")
# Derived from the schema and the engine source, not from a hand-written list:
# if the engine gains a role or a checkpoint owner, this fails instead of the
# key quietly rendering as unknown in production.
with open(os.path.join(ROOT, "src", "config", "routing.json"), encoding="utf-8") as fh:
    configured_keys = set(json.load(fh)["addressees"])
with open(os.path.join(ROOT, "src", "schemas", "case_state.schema.json"),
          encoding="utf-8") as fh:
    schema = json.load(fh)["properties"]
enum_keys = set(schema["routing"]["properties"]["recommendation"]["enum"])
enum_keys |= set(schema["open_items"]["items"]["properties"]["route"]["enum"])
with open(os.path.join(ROOT, "src", "vendor", "email_to_bom", "core.py"),
          encoding="utf-8") as fh:
    owner_keys = set(re.findall(r'"owner": "([^"]+)"', fh.read()))
check("every schema role has a routing entry", enum_keys <= configured_keys,
      f"missing={sorted(enum_keys - configured_keys)}")
check("every checkpoint owner the engine writes has one too",
      bool(owner_keys) and owner_keys <= configured_keys,
      f"missing={sorted(owner_keys - configured_keys)}")

print("REQ-097 — an unread attachment forces needs_human_input on its own")
# v0.16.0 derived the outcome from open_items[] alone, so an RFQ saying
# "dimensions are on the attached drawing" reported `complete`: the engine's asks
# were all `confirm` and the drawing was invisible to it. A reviewer routing on
# `complete` would skim a case whose actual specification was never opened. The
# engine cannot raise an item about a file it cannot see, so the outcome carries
# it. Operator's decision, 2026-09-17.
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "_report"), exist_ok=True)
attach_eml(d, "rfq.eml",
           "Need 4 hoses, dimensions and fittings are on the attached drawing. "
           "Steam service, 316 SS, 150 psi.",
           [("rev-C.pdf", "application", "pdf", b"%PDF-1.4 x")], [])
prepare(d, "rfq.eml")
phase1(d, "rfq.eml")
case = read_json(d, "case_state.json")
mf = read_json(d, "run_manifest.json")
blocking = [i for i in case.get("open_items", []) if i.get("priority") == "blocking"]
check("the attachment case carries NO blocking item (so only the file forces it)",
      not blocking, f"blocking={[i['code'] for i in blocking]}")
check("an unread attachment alone yields needs_human_input",
      mf.get("outcome") == "needs_human_input", f"got {mf.get('outcome')!r}")
check("and the reason names the file, not just a count",
      "rev-C.pdf" in (mf.get("outcome_reason") or ""),
      f"reason={mf.get('outcome_reason')!r}")
shutil.rmtree(d)

print("REQ-097b — an inline signature image does NOT force it")
# Routing every footer logo to a human is how a signal becomes noise, and then
# the drawing goes unnoticed too.
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "_report"), exist_ok=True)
attach_eml(d, "rfq.eml",
           "Need 4 hoses, 1/2 ID, 36 inch, 316 SS, steam at 150 psi.",
           [], [("signature-logo.png", "image", "png", b"\x89PNG")])
prepare(d, "rfq.eml")
phase1(d, "rfq.eml")
mf = read_json(d, "run_manifest.json")
check("the inline part WAS detected", len((mf.get("evidence_not_read") or {})
                                          .get("embedded") or []) == 1)
check("but an inline part alone leaves the outcome complete",
      mf.get("outcome") == "complete", f"got {mf.get('outcome')!r}")
shutil.rmtree(d)

print("REQ-097c — a scan that did not complete also forces needs_human_input")
# Called directly: on the shipped path the scan runs on a file the engine has
# just read, so this branch needs a race (the input vanishing between the engine
# pass and the scan) to reach. A check that cannot be executed is worth nothing,
# and asserting the pure function IS the execution -- the mutation run proves it
# can fail.
sys.path.insert(0, os.path.join(ROOT, "src", "scripts"))
from run_state import derive_outcome  # noqa: E402
_case = {"open_items": [{"priority": "confirm", "code": "X"}]}
check("an unreadable scan is not reported as 'no attachments'",
      derive_outcome(_case, {"status": "unreadable", "attachments": [],
                             "embedded": [], "error": "boom"})[0]
      == "needs_human_input")
check("a clean scan with nothing found stays complete",
      derive_outcome(_case, {"status": "scanned", "attachments": [],
                             "embedded": [], "error": None})[0] == "complete")
check("a blocking item still forces it with no evidence record at all",
      derive_outcome({"open_items": [{"priority": "blocking", "code": "P"}]},
                     None)[0] == "needs_human_input")

print("CW-3b — a FAILED run leaves no manifest: absence is the failure signal")
# `failed` is deliberately absent from the outcome vocabulary. A run that did not
# produce a CaseState must not leave a record that says anything about one, and
# the previous run's record must not survive to be mistaken for this one's.
d = workdir(("rfq.eml", "plain-steam"))
prepare(d, "rfq.eml")
phase1(d, "rfq.eml")
check("a good run leaves a manifest", "run_manifest.json" in artifacts(d))
rc, _, _ = phase1(d, "no-such-file.eml")
check("a failed extraction exits 1", rc == 1)
check("and leaves NO manifest behind", "run_manifest.json" not in artifacts(d),
      f"artifacts={artifacts(d)}")
shutil.rmtree(d)

print("2026-09-17 — a redirected --out leaves NO previous customer's CaseState behind")
# The eighteenth instance of this campaign's missed-sibling shape, and the one
# key that had been exempted BY NAME from the invalidation loop: with --out
# redirected, customer A's case survived at the conventional
# _report/case_state.json while B's was written elsewhere.
d = workdir(("A.eml", "confirmed-ids"), ("B.eml", "plain-steam"))
os.makedirs(os.path.join(d, "other"), exist_ok=True)
prepare(d, "A.eml")
phase1(d, "A.eml")
check("A's CaseState is at the conventional path after A's run",
      "case_state.json" in artifacts(d))
rc, _, err = sh([RUN, "--in", "B.eml", "--state", "_report/state.json",
                 "--out", os.path.join("other", "case_state.json")], d)
check("B's redirected extraction succeeds", rc == 0, err.strip()[:90])
check("customer A's stale CaseState did not survive B's extraction",
      "case_state.json" not in artifacts(d), f"artifacts={artifacts(d)}")
check("B's own CaseState and manifest landed beside --out",
      sorted(os.listdir(os.path.join(d, "other"))) == ["case_state.json",
                                                       "run_manifest.json"],
      f"other={sorted(os.listdir(os.path.join(d, 'other')))}")
shutil.rmtree(d)

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} defences held")
if failed:
    print("DEFENCES GONE:")
    for name, _, detail in failed:
        print(f"  - {name} {detail}")
sys.exit(1 if failed else 0)
