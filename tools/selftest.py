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
GATE = os.path.join(ROOT, "src", "scripts", "filter_gate.py")
FIX = os.path.join(ROOT, "tools", "parity", "fixtures")
FILTFIX = os.path.join(ROOT, "tools", "filter", "fixtures")
IDS = ["OPW 633C A", "OPW 633E A", "SPS400452", "HOS-064 300 EPDM"]
JUNK = ["auto-reply", "delivery-status", "newsletter", "bare-ack",
        "invoice-statement", "internal-chatter"]
ADVERSARIAL = ["bait-rfq", "ack-plus-rfq", "invoice-plus-rfq", "broken-mime"]

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


def filter_workdir(*inputs):
    """workdir()'s sibling for tools/filter/fixtures (phase 05)."""
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "_report"), exist_ok=True)
    for name, src in inputs:
        shutil.copy(os.path.join(FILTFIX, src, "input.eml"), os.path.join(d, name))
    return d


def gate(d, inp, *extra):
    return sh([GATE, "--in", inp, "--state", "_report/state.json", *extra], d)


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

print("Defence 5a — every junk category is filtered, and filtering leaves no "
      "artifact behind (phase 05, C1/C2)")
codes_seen = {}
for name in JUNK:
    d = filter_workdir(("in.eml", name))
    rc, out, err = gate(d, "in.eml")
    check(f"{name} → gate exits 3 (filtered)", rc == 3, f"exit={rc} {err.strip()[:100]}")
    check(f"{name} → no case_state.json/bom_draft.md in _report",
          not (os.path.isfile(os.path.join(d, "_report", "case_state.json"))
               or os.path.isfile(os.path.join(d, "_report", "bom_draft.md"))))
    try:
        decision = json.loads(out)
    except json.JSONDecodeError:
        decision = {}
    check(f"{name} → non-empty machine-readable code", bool(decision.get("code")),
          f"code={decision.get('code')!r}")
    check(f"{name} → route drawn from the declared vocabulary", bool(decision.get("route")),
          f"route={decision.get('route')!r}")
    codes_seen[name] = decision.get("code")
    shutil.rmtree(d)

print("Defence 5b — the six junk categories report DISTINCT codes, and re-running "
      "the gate on the same input is deterministic (C2)")
check("at least four distinct codes across the six junk categories",
      len(set(codes_seen.values())) >= 4, f"codes={codes_seen}")
d = filter_workdir(("in.eml", "newsletter"))
rc1, out1, _ = gate(d, "in.eml")
rc2, out2, _ = gate(d, "in.eml")
check("the same message re-run twice yields an identical filter record",
      rc1 == rc2 == 3 and out1 == out2)
shutil.rmtree(d)

print("Defence 5c — ambiguous and adversarial messages are NEVER filtered "
      "(C5, ADR-001's fail-open inversion)")
for name in ADVERSARIAL:
    d = filter_workdir(("in.eml", name))
    rc, _, err = gate(d, "in.eml")
    check(f"{name} → gate exits 0 (not filtered)", rc == 0, f"exit={rc} {err.strip()[:100]}")
    rc2, _, err2 = sh([RUN, "--in", "in.eml", "--state", "_report/state.json"], d)
    check(f"{name} → the normal path still produces a CaseState",
          rc2 == 0 and os.path.isfile(os.path.join(d, "_report", "case_state.json")),
          err2.strip()[:100])
    shutil.rmtree(d)
d = filter_workdir(("in.eml", "empty"))
rc, out, err = gate(d, "in.eml")
try:
    empty_filtered = json.loads(out).get("filtered")
except json.JSONDecodeError:
    empty_filtered = None
check("a zero-byte input is never a quiet, success-looking 'filtered'",
      rc == 1 or (rc == 0 and empty_filtered is False),
      f"exit={rc} out={out.strip()[:120]} err={err.strip()[:120]}")
shutil.rmtree(d)

print("Defence 5d — filtered / drafted / broken are three DISTINCT exit codes, "
      "and the gate never returns the engine's 2 (C2, REQ-007)")
d = filter_workdir(("junk.eml", "newsletter"))
rc_filtered, _, _ = gate(d, "junk.eml")
check("a filtered run exits 3", rc_filtered == 3)
shutil.rmtree(d)
d = filter_workdir(("rfq.eml", "bait-rfq"))
rc_pass, _, _ = gate(d, "rfq.eml")
rc_drafted, _, _ = sh([RUN, "--in", "rfq.eml", "--state", "_report/state.json"], d)
check("a real RFQ passes the gate and then drafts, exiting 0",
      rc_pass == 0 and rc_drafted == 0)
shutil.rmtree(d)
d = filter_workdir(("placeholder.eml", "newsletter"))
rc_broken, _, _ = gate(d, "missing.eml")
check("a nonexistent input is the gate's own failure, exit 1", rc_broken == 1)
check("none of the three outcomes is ever the engine's 2",
      2 not in (rc_filtered, rc_pass, rc_drafted, rc_broken))
shutil.rmtree(d)

print("Defence 5e — a filtered run in the SAME directory clears the previous "
      "customer's paperwork (C1, the R26-F1 category)")
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "_report"), exist_ok=True)
shutil.copy(os.path.join(FIX, "plain-steam", "input.eml"), os.path.join(d, "rfq.eml"))
shutil.copy(os.path.join(FILTFIX, "newsletter", "input.eml"), os.path.join(d, "junk.eml"))
phase1(d, "rfq.eml")
phase2(d)
before = artifacts(d)
check("a real RFQ drafts before the filtered run",
      "bom_draft.md" in before and "case_state.json" in before, f"before={before}")
rc, _, _ = gate(d, "junk.eml")
check("the newsletter that follows it is filtered", rc == 3)
after = artifacts(d)
check("both of the previous run's artifacts are gone",
      "bom_draft.md" not in after and "case_state.json" not in after,
      f"before={before} after={after}")
with open(os.path.join(d, "_report", "state.json"), encoding="utf-8") as fh:
    state = json.load(fh)
check("the filter record for the newsletter is present",
      state.get("filter", {}).get("filtered") is True, f"state={state}")
shutil.rmtree(d)

print("Defence 5f — a successful extract clears a stale filter record, the "
      "sibling of R26-F1's stale-draft defence (t7)")
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "_report"), exist_ok=True)
shutil.copy(os.path.join(FILTFIX, "newsletter", "input.eml"), os.path.join(d, "junk.eml"))
shutil.copy(os.path.join(FIX, "plain-steam", "input.eml"), os.path.join(d, "rfq.eml"))
gate(d, "junk.eml")
with open(os.path.join(d, "_report", "state.json"), encoding="utf-8") as fh:
    check("the filter record was written", "filter" in json.load(fh))
phase1(d, "rfq.eml")
with open(os.path.join(d, "_report", "state.json"), encoding="utf-8") as fh:
    check("a successful extract drops the stale filter record",
          "filter" not in json.load(fh))
shutil.rmtree(d)

print("Defence 5g — the gated path is byte-identical to the ungated parity "
      "capture, so parity stays blind to the gate (C4)")
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "_report"), exist_ok=True)
src = os.path.join(FIX, "plain-steam", "input.eml")
shutil.copy(src, os.path.join(d, "rfq.eml"))
before_sha = sha256(src)
rc, _, err = gate(d, "rfq.eml")
check("plain-steam passes the gate", rc == 0, err.strip()[:120])
rc, _, err = phase1(d, "rfq.eml")
check("plain-steam still reaches the engine", rc == 0, err.strip()[:120])
try:
    with open(os.path.join(d, "_report", "case_state.json"), "rb") as fh:
        got = fh.read()
    with open(os.path.join(FIX, "plain-steam", "expected_output.json"), "rb") as fh:
        expected = fh.read()
    identical = got == expected
except OSError:
    identical = False
check("the gated CaseState is byte-identical to the source-captured expected_output.json",
      identical)
check("the source input file's bytes are unchanged", sha256(src) == before_sha)
shutil.rmtree(d)

print("Defence 5h — --no-filter processes a filtered message with no edit to "
      "the kit or the email (C6)")
d = filter_workdir(("junk.eml", "newsletter"))
src = os.path.join(d, "junk.eml")
before_sha = sha256(src)
rc, _, err = gate(d, "junk.eml", "--no-filter")
check("--no-filter forces the gate to pass through", rc == 0, err.strip()[:120])
rc, _, err = phase1(d, "junk.eml")
check("the overridden message reaches the engine", rc == 0, err.strip()[:120])
phase2(d)
check("a CaseState and draft exist despite the message's filter category",
      "case_state.json" in artifacts(d) and "bom_draft.md" in artifacts(d),
      f"artifacts={artifacts(d)}")
check("--no-filter did not touch the input file's bytes", sha256(src) == before_sha)
shutil.rmtree(d)

print("Defence 5i — the decision schema's code/route enums match the declared "
      "category vocabulary exactly (mechanical drift check)")
try:
    with open(os.path.join(ROOT, "src", "reference", "filter_signals.json"),
              encoding="utf-8") as fh:
        signals = json.load(fh)
    with open(os.path.join(ROOT, "src", "schemas", "filter_decision.schema.json"),
              encoding="utf-8") as fh:
        schema = json.load(fh)
    declared_codes = {c["code"] for c in signals["categories"]} | {None}
    declared_routes = {c["route"] for c in signals["categories"]} | {None}
    schema_codes = set(schema["properties"]["code"]["enum"])
    schema_routes = set(schema["properties"]["route"]["enum"])
    check("schema `code` enum equals the t1 category codes plus null",
          declared_codes == schema_codes,
          f"signals={declared_codes} schema={schema_codes}")
    check("schema `route` enum equals the t1 category routes plus null",
          declared_routes == schema_routes,
          f"signals={declared_routes} schema={schema_routes}")
except (KeyError, OSError, json.JSONDecodeError) as e:
    check("vocabulary consistency check could run", False, f"{type(e).__name__}: {e}")

print("Defence 5j — a ~1 MB junk message filters in well under the engine's "
      "superlinear cost at that size, with no engine invocation (C3)")
d = filter_workdir(("in.eml", "newsletter"))
big_path = os.path.join(d, "in.eml")
with open(big_path, "rb") as fh:
    raw = fh.read()
head, _, body = raw.partition(b"\n\n")
filler = (b"Save 20% on hose reels, EPDM suction hose and stainless fittings "
          b"all month.\n" * 15000)
with open(big_path, "wb") as fh:
    fh.write(head + b"\n\n" + body + b"\n" + filler)
check("the generated fixture is around 1 MB", os.path.getsize(big_path) > 900_000,
      f"size={os.path.getsize(big_path)}")
t0 = time.time()
rc, _, err = gate(d, "in.eml")
elapsed = time.time() - t0
check("the ~1 MB newsletter still filters", rc == 3, err.strip()[:120])
check("filtering finishes in a couple of seconds, not engine-scale minutes",
      elapsed < 10, f"elapsed={elapsed:.2f}s")
shutil.rmtree(d)

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} defences held")
if failed:
    print("DEFENCES GONE:")
    for name, _, detail in failed:
        print(f"  - {name} {detail}")
sys.exit(1 if failed else 0)
