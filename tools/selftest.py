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
# The categories that can still be FILTERED, i.e. the depth-0 ones. `newsletter`
# is deliberately absent: since round 28 removed the list-mail exemption from the
# depth guard, a newsletter naming hose specifications reaches the engine, and it
# has its own check asserting exactly that. Keep this list distinct -- a blanket
# retarget once left it with a duplicate, so it read as six categories while
# covering five.
# Categories that can still be FILTERED. Round 29 removed the three
# content-judged ones (invoice/ack/internal) because they dropped 11 of 46
# genuine RFQs, so their fixtures now PASS and are asserted under NOT_FILTERED
# below. `bulk-nospec` exists because the shipped `newsletter` fixture names hose
# specifications and therefore reaches the engine -- bulk mail only filters at
# depth 0.
JUNK = ["auto-reply", "delivery-status", "bulk-nospec"]
# Fixtures that must now reach the engine. Each is a deliberate, documented cost
# of round 29's removals; asserting them stops the removals being quietly undone.
NOT_FILTERED = ["invoice-statement", "bare-ack", "internal-chatter", "newsletter"]
assert len(JUNK) == len(set(JUNK)), "JUNK has a duplicate: coverage is narrower than it looks"
assert not (set(JUNK) & set(NOT_FILTERED)), "a fixture cannot be both filtered and not"
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

print("Defence 5b — every surviving junk category reports a DISTINCT code, and "
      "re-running the gate on the same input is deterministic (C2)")
check("a distinct code for every surviving junk category",
      len(set(codes_seen.values())) == len(JUNK) and None not in codes_seen.values(),
      f"codes={codes_seen}")
d = filter_workdir(("in.eml", "auto-reply"))
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
d = filter_workdir(("junk.eml", "auto-reply"))
rc_filtered, _, _ = gate(d, "junk.eml")
check("a filtered run exits 3", rc_filtered == 3)
shutil.rmtree(d)
d = filter_workdir(("rfq.eml", "bait-rfq"))
rc_pass, _, _ = gate(d, "rfq.eml")
rc_drafted, _, _ = sh([RUN, "--in", "rfq.eml", "--state", "_report/state.json"], d)
check("a real RFQ passes the gate and then drafts, exiting 0",
      rc_pass == 0 and rc_drafted == 0)
shutil.rmtree(d)
d = filter_workdir(("placeholder.eml", "invoice-statement"))
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
shutil.copy(os.path.join(FILTFIX, "auto-reply", "input.eml"), os.path.join(d, "junk.eml"))
phase1(d, "rfq.eml")
phase2(d)
before = artifacts(d)
check("a real RFQ drafts before the filtered run",
      "bom_draft.md" in before and "case_state.json" in before, f"before={before}")
rc, _, _ = gate(d, "junk.eml")
check("the auto-reply that follows it is filtered", rc == 3)
after = artifacts(d)
check("both of the previous run's artifacts are gone",
      "bom_draft.md" not in after and "case_state.json" not in after,
      f"before={before} after={after}")
with open(os.path.join(d, "_report", "state.json"), encoding="utf-8") as fh:
    state = json.load(fh)
check("the filter record for the auto-reply is present",
      state.get("filter", {}).get("filtered") is True, f"state={state}")
shutil.rmtree(d)

print("Defence 5f — a successful extract clears a stale filter record, the "
      "sibling of R26-F1's stale-draft defence (t7)")
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "_report"), exist_ok=True)
shutil.copy(os.path.join(FILTFIX, "auto-reply", "input.eml"), os.path.join(d, "junk.eml"))
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
d = filter_workdir(("junk.eml", "invoice-statement"))
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
d = filter_workdir(("in.eml", "bulk-nospec"))
big_path = os.path.join(d, "in.eml")
with open(big_path, "rb") as fh:
    raw = fh.read()
head, _, body = raw.partition(b"\n\n")
# Spec-FREE filler on purpose. Naming products here would give the message a
# non-zero specification depth, at which point it must pass (round 28, F-2) and
# this check would be testing the opposite of what it claims.
filler = (b"Your account summary is enclosed for your records this period.\n"
          * 15000)
with open(big_path, "wb") as fh:
    fh.write(head + b"\n\n" + body + b"\n" + filler)
check("the generated fixture is around 1 MB", os.path.getsize(big_path) > 900_000,
      f"size={os.path.getsize(big_path)}")
t0 = time.time()
rc, _, err = gate(d, "in.eml")
elapsed = time.time() - t0
check("a ~1 MB depth-0 junk message still filters", rc == 3, err.strip()[:120])
check("filtering finishes in a couple of seconds, not engine-scale minutes",
      elapsed < 10, f"elapsed={elapsed:.2f}s")
shutil.rmtree(d)


# =============================== ROUND 27 ====================================
# Round 27 filtered 24 of 35 genuine RFQs. These checks are the coverage that
# would have caught it: the protection is now spec depth (a measured property),
# and every check below drives the SHIPPED path, not a convenience path.

GATE = os.path.join(ROOT, "src", "scripts", "filter_gate.py")

def eml(d, name, text):
    with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
        fh.write(text)
    return name

def prepare(d, inp, override=None):
    """Write state.json the way the recipe's prepare phase does."""
    st = {"invocation": {"input": inp, "component_ids": [], "coc": False,
                         "config_dir": None}}
    if override is not None:
        st["screen"] = {"override": override, "input": inp}
    with open(os.path.join(d, "_report", "state.json"), "w", encoding="utf-8") as fh:
        json.dump(st, fh)

def gate_from_state(d, *extra):
    """The SHIPPED invocation: --from-state, exactly as the recipe uses it."""
    return sh([GATE, "--from-state", "--state", "_report/state.json", *extra], d)

def filt(d):
    with open(os.path.join(d, "_report", "state.json"), encoding="utf-8") as fh:
        return json.load(fh).get("filter", {})

RFQ_BODY = ("We need 200 feet of 2 inch ID EPDM suction hose, male NPT both ends,\n"
            "150 PSI working pressure, for ambient service on water transfer.\n"
            "Please send your best price and lead time to my attention.\n")

print("Round 27 / R27-F1 — a real RFQ is never filtered by a junk phrase")
for label, extra_hdr, extra_body in [
    ("net-30 terms",        "", "Terms net 30.\n"),
    ("invoice wording",     "", "Invoice to AP on completion.\n"),
    ("remit-to wording",    "", "Remit to accounting once quoted.\n"),
    ("no-reply portal",     "From: no-reply@portal.acme.example\n", ""),
    ("ERP Auto-Submitted",  "Auto-Submitted: auto-generated\n", ""),
    ("internal forward",    "From: rep@mcgill.example\nTo: sales@mcgill.example\n", ""),
]:
    d = workdir()
    hdr = extra_hdr or "From: buyer@acme.example\nTo: quotes@mcgill.example\n"
    if "To:" not in hdr:
        hdr += "To: quotes@mcgill.example\n"
    name = eml(d, "rfq.eml", hdr + "Subject: Hose requirement\n\n" + RFQ_BODY + extra_body)
    prepare(d, name)
    rc, _, _ = gate_from_state(d)
    check(f"RFQ + {label} reaches the engine", rc == 0,
          f"exit={rc} code={filt(d).get('code')}")
    shutil.rmtree(d)

print("Round 27 / R27-F2 — a labelled RFQ inside a multipart/report is not a bounce")
d = workdir()
name = eml(d, "rfq.eml",
           "From: buyer@acme.example\nTo: quotes@mcgill.example\n"
           "Subject: RFQ - hose assemblies, please quote\n"
           "Content-Type: multipart/report; report-type=delivery-status; boundary=z\n\n"
           "--z\nContent-Type: text/plain\n\n" + RFQ_BODY + "--z--\n")
prepare(d, name)
rc, _, _ = gate_from_state(d)
check("RFQ in multipart/report reaches the engine", rc == 0, f"exit={rc}")
shutil.rmtree(d)

print("Round 27 — the six junk categories STILL filter (the feature works)")
for j, want in [("auto-reply", "AUTO_REPLY"),
                ("delivery-status", "DELIVERY_STATUS_NOTIFICATION"),
                ("bulk-nospec", "BULK_MAILING")]:
    d = workdir()
    shutil.copy(os.path.join(ROOT, "tools", "filter", "fixtures", j, "input.eml"),
                os.path.join(d, "junk.eml"))
    prepare(d, "junk.eml")
    rc, _, _ = gate_from_state(d)
    check(f"{j} filters as {want}", rc == 3 and filt(d).get("code") == want,
          f"exit={rc} code={filt(d).get('code')}")
    check(f"{j} leaves no draft or CaseState",
          sorted(artifacts(d)) == ["state.json"], f"artifacts={artifacts(d)}")
    shutil.rmtree(d)

print("Round 27 / R27-F5 — the override works on the SHIPPED path, not just the CLI")
d = workdir()
shutil.copy(os.path.join(ROOT, "tools", "filter", "fixtures", "auto-reply", "input.eml"),
            os.path.join(d, "junk.eml"))
prepare(d, "junk.eml", override=True)
rc, _, _ = gate_from_state(d)
check("recorded override lets a filtered message through (recipe shape)", rc == 0,
      f"exit={rc}")
check("the record says it was an override", filt(d).get("override") is True)
shutil.rmtree(d)

print("Round 27 — an override is an EXPLICIT choice, and is scoped to its message")
d = workdir()
shutil.copy(os.path.join(ROOT, "tools", "filter", "fixtures", "auto-reply", "input.eml"),
            os.path.join(d, "junk.eml"))
prepare(d, "junk.eml", override="false")      # the STRING "false" is truthy in Python
rc, _, _ = gate_from_state(d)
check('override="false" does NOT disable the filter', rc == 3, f"exit={rc}")
shutil.rmtree(d)

d = workdir()
for n in ("a.eml", "b.eml"):
    shutil.copy(os.path.join(ROOT, "tools", "filter", "fixtures", "auto-reply", "input.eml"),
                os.path.join(d, n))
prepare(d, "a.eml", override=True)
with open(os.path.join(d, "_report", "state.json"), encoding="utf-8") as fh:
    st = json.load(fh)
st["invocation"]["input"] = "b.eml"           # override was granted for a.eml
with open(os.path.join(d, "_report", "state.json"), "w", encoding="utf-8") as fh:
    json.dump(st, fh)
rc, _, _ = gate_from_state(d)
check("an override granted for one message does not govern another", rc == 3,
      f"exit={rc}")
shutil.rmtree(d)

print("Round 27 / R27-F3 — a message we cannot fully read is never filtered")
# Round 27 found `undecodable` computed and never consulted, so two messages
# identical but for HTML body size decided oppositely. Both shapes must be safe:
# a junk phrase early with the specs past the scan budget must NOT filter.
HDR = ('From: buyer@acme.example\nTo: quotes@mcgill.example\nSubject: Requirement\n'
       'MIME-Version: 1.0\nContent-Type: text/html; charset="utf-8"\n\n')
for label, doc in [
    ("junk phrase early, specs past the budget",
     HDR + "<html><body><p>Terms net 30. Remit to accounts payable.</p>\n"
     + "<p>Quoted thread follows.</p>\n" * 2000
     + "<p>We need 200 feet of 2 inch ID EPDM suction hose, male NPT both ends, "
       "150 PSI working pressure.</p></body></html>"),
    ("oversize body with a junk phrase at the end",
     HDR + "<html><body>" + "<p>Spring specials on hose reels.</p>\n" * 2000
     + "<p>Terms net 30. Remit to accounts.</p></body></html>"),
]:
    d = workdir()
    name = eml(d, "big.eml", doc)
    prepare(d, name)
    rc, _, _ = gate_from_state(d)
    check(f"oversize: {label} is not filtered", rc == 0,
          f"exit={rc} code={filt(d).get('code')}")
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

print("Round 29 — the RFC 3834 distinction: auto-generated is not auto-replied")
# An ERP requisition sets `Auto-Submitted: auto-generated`; only `auto-replied`
# says "this message is a reply to another", which a customer's original request
# never is. Round 29 (F-2) lost real requisitions by treating them alike. The
# body is deliberately spec-less so ONLY the header distinction can save it.
d = workdir()
name = eml(d, "req.eml",
           "From: erp@vulcan.example\nTo: quotes@mcgill.example\n"
           "Subject: Requisition 88120\nAuto-Submitted: auto-generated\n\n"
           "Please action the attached requisition at your earliest convenience.\n")
prepare(d, name)
rc, _, _ = gate_from_state(d)
check("a spec-less auto-GENERATED requisition reaches the engine", rc == 0,
      f"exit={rc} code={filt(d).get('code')}")
shutil.rmtree(d)

print("Round 29 / F-8 — depth is measured on the BODY, not the echoed subject")
# An out-of-office responder echoes the RFQ subject verbatim, so measuring
# subject+body gave it a non-zero depth and 4 of 6 realistic OOO replies escaped.
d = workdir()
name = eml(d, "ooo.eml",
           "From: buyer@acme.example\nTo: quotes@mcgill.example\n"
           "Subject: Automatic reply: RFQ - 200ft 2in ID EPDM transfer hose, "
           "150 PSI, male NPT both ends\nAuto-Submitted: auto-replied\n\n"
           "I am out of the office until Monday.\n")
prepare(d, name)
rc, _, _ = gate_from_state(d)
check("an OOO echoing a full RFQ subject still filters", rc == 3,
      f"exit={rc} reason={filt(d).get('reason')}")
shutil.rmtree(d)
# ...and the converse: a real request whose specs are in the BODY survives the
# same headers. This pair is what makes body-only measurement the right call
# rather than merely a stricter one.
d = workdir()
name = eml(d, "bait.eml",
           "From: buyer@acme.example\nTo: quotes@mcgill.example\n"
           "Subject: Out of Office: RE: RFQ\nAuto-Submitted: auto-replied\n"
           "List-Unsubscribe: <mailto:u@acme.example>\nPrecedence: bulk\n\n"
           "Please quote 4 of a 36in seat-to-seat 1/2in ID 316 SS steam hose, "
           "male NPT both ends.\n")
prepare(d, name)
rc, _, _ = gate_from_state(d)
check("a real request in the body survives those same junk headers", rc == 0,
      f"exit={rc} code={filt(d).get('code')}")
shutil.rmtree(d)

print("Round 29 / F-6 — a malformed schema fails OPEN, it does not crash")
sys.path.insert(0, os.path.join(ROOT, "src", "scripts"))
import filter_gate as _fg  # noqa: E402
# Round 29 found _load_reason_pattern missing the TypeError its sibling catches,
# so a malformed schema stopped the run with rc=1 instead of failing open.
import tempfile as _tf
for label, content in [
    ("properties is a list", '{"properties": [1, 2]}'),
    ("reason is a list", '{"properties": {"reason": [1, 2]}}'),
    ("not JSON at all", "{not json"),
    ("empty file", ""),
]:
    fp = os.path.join(_tf.mkdtemp(), "bad.json")
    with open(fp, "w", encoding="utf-8") as fh:
        fh.write(content)
    try:
        got = _fg._load_reason_pattern(fp)
        ok = got is None
    except Exception as exc:  # noqa: BLE001
        ok = False
        got = f"raised {type(exc).__name__}"
    check(f"malformed schema ({label}) returns None instead of raising", ok,
          f"got={got!r}")

print("Round 29 — the removed categories must STAY removed")
# Round 29 dropped 11 of 46 genuine RFQs; every content-judged category was
# implicated. These four fixtures must now reach the engine. Asserting it stops
# the removals being quietly reversed by a future 'improvement'.
for name in NOT_FILTERED:
    d = filter_workdir(("in.eml", name))
    rc, _, err = gate(d, "in.eml")
    check(f"{name} reaches the engine (round-29 removal holds)", rc == 0,
          f"exit={rc} {err.strip()[:80]}")
    shutil.rmtree(d)
_sig = json.load(open(os.path.join(ROOT, "src", "reference", "filter_signals.json")))
_codes = {c["code"] for c in _sig["categories"]}
check("no content-judged category has returned",
      not (_codes & {"INVOICE_OR_STATEMENT", "BARE_ACKNOWLEDGEMENT", "INTERNAL_CHATTER"}),
      f"codes={sorted(_codes)}")
check("no filtered route is colder than a human queue except for protocol reports",
      all(c["route"] != "no_action" or c["code"] in
          {"AUTO_REPLY", "DELIVERY_STATUS_NOTIFICATION"} for c in _sig["categories"]),
      f"routes={[(c['code'], c['route']) for c in _sig['categories']]}")
check("the sender-address heuristic that dropped portal RFQs is gone",
      "auto_reply_localparts" not in _sig and "dsn_sender_localparts" not in _sig)
check("the invoice/ack phrase lists are gone",
      not any(k in _sig for k in ("invoice_phrases", "ack_phrases", "ack_max_chars")))

print("Round 28 / F-1 — the spec field list is derived, so no name can go dead")
import dataclasses as _dc
sys.path.insert(0, os.path.join(ROOT, "src", "vendor"))
from email_to_bom.core import Extraction as _Extraction  # noqa: E402
_real = {f.name for f in _dc.fields(_Extraction)}
_measured = set(_fg._spec_field_names())
check("every measured field exists on the engine's Extraction",
      _measured <= _real, f"dead names={sorted(_measured - _real)}")
check("the measured set is non-empty and excludes the non-spec flags",
      _measured and "material_recognized" not in _measured and "customer" not in _measured,
      f"measured={sorted(_measured)}")
check("a length-only order measures a non-zero depth",
      _fg._spec_depth(_fg.core.Agent(_fg.core.load_config()),
                      "go ahead and get us 400 feet of the transfer hose") > 0)

print("Round 28 / F-1 — a length-only order is not filtered as an invoice")
d = workdir()
name = eml(d, "rfq.eml",
           "From: buyer@acme.example\nTo: sales@mcgill.example\nSubject: Baytown line\n\n"
           "Go ahead and get us 400 feet of the transfer hose for the Baytown line.\n"
           "Terms net 30 as usual.\n")
prepare(d, name)
rc, _, _ = gate_from_state(d)
check("length-only order + net-30 reaches the engine", rc == 0,
      f"exit={rc} code={filt(d).get('code')}")
shutil.rmtree(d)

# Each spec kind on its own must protect a message. A single field silently
# dropped from measurement is round 28's F-1 all over again.
for kind, body in [
    ("size only",     "Need the 2 inch ID line for bay 4. Terms net 30."),
    ("length only",   "Get us 400 feet of the transfer hose. Terms net 30."),
    ("quantity only", "Please supply 4 of the usual assemblies. Terms net 30."),
    ("material only", "We want the 316 stainless option this time. Terms net 30."),
]:
    d = workdir()
    name = eml(d, "rfq.eml", "From: buyer@acme.example\nTo: sales@mcgill.example\n"
                             "Subject: requirement\n\n" + body + "\n")
    prepare(d, name)
    rc, _, _ = gate_from_state(d)
    check(f"an RFQ specified by {kind} is not filtered", rc == 0,
          f"exit={rc} code={filt(d).get('code')}")
    shutil.rmtree(d)

print("Round 28 / F-2 — list-mail headers do NOT filter a spec-bearing message")
d = workdir()
name = eml(d, "rfq.eml",
           "From: buyer@acme.example\nTo: sales@mcgill.example\nSubject: requirement\n"
           "List-Unsubscribe: <mailto:u@acme.example>\n"
           "List-Id: <procurement.acme.example>\nPrecedence: bulk\n\n"
           "We need 200 feet of 2 inch ID EPDM suction hose, male NPT both ends,\n"
           "150 PSI, ambient service, 4 assemblies, 316 SS fittings.\n")
prepare(d, name)
rc, _, _ = gate_from_state(d)
check("ESP-stamped RFQ with specifications reaches the engine", rc == 0,
      f"exit={rc} code={filt(d).get('code')}")
shutil.rmtree(d)

# The accepted cost of removing round 27's `always` tier, asserted so it cannot
# regress silently in either direction.
d = workdir()
shutil.copy(os.path.join(FILTFIX, "newsletter", "input.eml"),
            os.path.join(d, "news.eml"))
prepare(d, "news.eml")
rc, _, _ = gate_from_state(d)
check("a hose newsletter naming specifications now reaches the engine "
      "(accepted cost of F-2)", rc == 0, f"exit={rc}")
shutil.rmtree(d)

print("Round 28 / F-3 — a recorded override must name the message it governs")
d = workdir()
shutil.copy(os.path.join(FILTFIX, "auto-reply", "input.eml"),
            os.path.join(d, "junk.eml"))
# The shape the RECIPE writes. Round 28 found this exact shape made the binding
# inert, while the self-test used a shape the recipe never produced.
with open(os.path.join(d, "_report", "state.json"), "w", encoding="utf-8") as fh:
    json.dump({"invocation": {"input": "junk.eml", "component_ids": [],
                              "coc": False, "config_dir": None},
               "screen": {"override": True}}, fh)          # no "input" key
rc, _, _ = gate_from_state(d)
check("an override with no recorded input does NOT apply", rc == 3, f"exit={rc}")
prepare(d, "junk.eml", override=True)                       # with "input"
rc, _, _ = gate_from_state(d)
check("an override naming this message DOES apply", rc == 0, f"exit={rc}")
shutil.rmtree(d)

print("Round 28 / F-6 — an undeclared reason fails open")
d = workdir()
shutil.copy(os.path.join(FILTFIX, "auto-reply", "input.eml"),
            os.path.join(d, "junk.eml"))
prepare(d, "junk.eml")
pat = _fg._load_reason_pattern()
check("the schema declares a reason shape", bool(pat), f"pattern={pat!r}")
check("the reasons the gate actually emits are declared",
      all(_fg._reason_ok(r, pat) for r in
          ("no_evidence", "parse_failed", "override", "quoting_request_detected",
           "undecodable_content", "specifications_present:7")),
      "one of the emitted reasons is not declared")
check("an invented reason is rejected", not _fg._reason_ok("made_up_reason", pat))
shutil.rmtree(d)

print("Round 28 / F-3b — undecodable content is not judged, with a LIVE candidate")
# Round 28 proved the previous two checks vacuous: both fixtures were HTML-only
# over budget, so the body was empty and NO detector could fire -- they passed on
# `candidate is None`, not on the undecodable guard. A header detector fires
# without a body, so this one reaches the guard it claims to test.
d = workdir()
big = ("From: hr@acme.example\nTo: sales@mcgill.example\nSubject: Away\n"
       "Auto-Submitted: auto-replied\nMIME-Version: 1.0\n"
       'Content-Type: text/html; charset="utf-8"\n\n'
       "<html><body>" + "<p>Out of the office this week.</p>\n" * 2000
       + "</body></html>")
name = eml(d, "big.eml", big)
prepare(d, name)
rc, _, _ = gate_from_state(d)
check("oversize body + a live header candidate is not filtered", rc == 0,
      f"exit={rc} code={filt(d).get('code')} reason={filt(d).get('reason')}")
shutil.rmtree(d)

print("Round 28 / F-4 — ALL THREE clearing sites consume the declaration")
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

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} defences held")
if failed:
    print("DEFENCES GONE:")
    for name, _, detail in failed:
        print(f"  - {name} {detail}")
sys.exit(1 if failed else 0)
