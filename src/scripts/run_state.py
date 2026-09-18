#!/usr/bin/env python3
"""The single owner of a run's state: its artifacts, its invocation, its argv.

Round 26 failed this kit twice over the same shape: a fix that named one item and
missed its sibling. `run_engine.py` cleared `case_state.json` before it could fail
but nothing cleared `bom_draft.md`, so a failed phase 2 left the previous
customer's draft sitting beside the new customer's CaseState (R26-F1). And the
invocation record was constructed at three sites, one of them a 4-key whitelist
that would silently drop a fifth key (R26-F6).

So the fix is not another per-item patch. Everything that a run owns is declared
HERE, once:

  * ARTIFACTS       — every file a run produces. Invalidation walks this list, so
                      adding an artifact cannot be forgotten by a clearing site.
  * INVOCATION_KEYS — the engine call's shape. One constructor, one normaliser,
                      one argv builder. A new key is added in one place.

Invalidation is LOUD. Round 26 (R26-F5) found `except OSError: pass` swallowing
clearing failures, which reproduced the very defect the clearing exists to
prevent: under a read-only `_report/` the stale artifact survived silently. If we
cannot guarantee the old artifacts are gone, the run must say so and stop.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

# Every artifact a run produces, relative to the run directory. Invalidation
# walks this mapping — a new artifact is declared once, here, and every clearing
# site picks it up for free.
ARTIFACTS = {
    "case_state": os.path.join("_report", "case_state.json"),
    "bom_draft": os.path.join("_report", "bom_draft.md"),
    # The inline reply body. The kit attaches nothing: everything an operator
    # needs is in the message, so this is the deliverable a human reads.
    "reply": os.path.join("_report", "reply.md"),
    # The run record: who produced this case, from what, and whether it needs a
    # human. Not a deliverable -- the Body/Compute contract's half of the run.
    "manifest": os.path.join("_report", "run_manifest.json"),
    # What the REVIEWER reads: the decision, the grounds for it, who it routes
    # to, and the proposed response embedded verbatim (CW-4).
    "review_request": os.path.join("_report", "review_request.md"),
}

# The engine invocation's shape. Adding an argument means adding it here.
INVOCATION_KEYS = ("input", "component_ids", "coc", "config_dir")

# WHO produced a case. A proposal a reviewer corrects is worthless to Factory if
# nothing records which version of which skill made it, so these travel in the
# run manifest with every case.
#
# `kit.json` is the source of truth for the version and is NOT shipped inside
# `dist/kit.zip` (it carries that zip's own sha256, so it cannot contain
# itself). This constant is therefore a second copy -- the shape that has caused
# most of this campaign's findings -- and it is kept honest the only way a second
# copy can be: `tools/selftest.py` asserts it equals `kit.json`, so a version
# bump that forgets this line fails the suite instead of mis-attributing a case.
KIT_NAME = "mcgill-email-to-bom"
KIT_VERSION = "0.21.0"

# The outcome vocabulary at the Body/Compute boundary (CW-3).
#
# `engine_exit` cannot serve this purpose: 2 means "a draft with open items",
# the normal result for essentially every real RFQ, and every document in this
# kit has to spend a bullet warning people not to read it as failure. So the
# manifest states the outcome in words, DERIVED from what the run produced --
# the CaseState's open items AND the attachments the engine could not read --
# rather than set alongside it. An independently-assigned flag is a second copy
# that can drift, which is failure shape #1 of this campaign.
#
# FAILURE IS NOT IN THIS VOCABULARY, on purpose. A failed run writes no
# manifest at all and the wrapper exits 1, which the clamp in every wrapper
# enforces. Absence is the failure signal, and it cannot be faked by a
# half-written record.
OUTCOME_COMPLETE = "complete"
OUTCOME_NEEDS_HUMAN = "needs_human_input"


def derive_outcome(case, evidence=None, transcript=None):
    """(outcome, reason) for a run. Pure, and derived from what the run produced.

    `complete` does NOT mean sendable. Every case this kit produces is a draft a
    human reviews; `complete` means only that nothing in it requires an answer
    before the case can move. The distinction is the one Body needs to route.

    TWO grounds for `needs_human_input`, and the second was added deliberately
    after the first shipped (REQ-097, operator's decision 2026-09-17):

    1. **A blocking open item.** The engine's own judgement.
    2. **An attachment the engine never read.** v0.16.0 derived the outcome from
       `open_items[]` alone, which meant an RFQ saying "dimensions are on the
       attached drawing" could report `complete`: the engine's asks were all
       `confirm`, and the drawing was invisible to it. A reviewer routing on
       `complete` would skim a case whose actual specification was never opened.
       The engine cannot raise an item about a file it cannot see, so the outcome
       has to carry it.

    Note what does NOT force it: an inline part with a Content-ID -- a signature
    logo. Routing every footer image to a human is how a signal becomes noise,
    and then the drawing goes unnoticed too. See `attachments._classify`.

    A scan that did not complete also yields `needs_human_input`. "We could not
    tell whether the customer attached anything" is not the same as "they did
    not", and only one of those is safe to route as `complete`.

    Still DERIVED, not asserted: both grounds are read from what the run
    produced, never set alongside it. An independently-assigned outcome is a
    second copy that can drift, which is failure shape #1 of this campaign.
    """
    items = (case or {}).get("open_items") or []
    blocking = [i for i in items if (i or {}).get("priority") == "blocking"]
    # A transcribed attachment is not unread. Counting it under both grounds made
    # the reason contradict itself ("read by a MACHINE ... the engine never read"),
    # and a reader resolves a contradiction by trusting whichever clause they
    # finish on.
    _transcribed = {str(t) for t in (transcript or [])}
    unread = [f for f in ((evidence or {}).get("attachments") or [])
              if str(f.get("filename")) not in _transcribed]
    status = (evidence or {}).get("status")

    reasons = []
    if transcript:
        # THIRD ground (CW-9). A transcribed attachment is no longer unread, and
        # that is exactly why it needs a human: a model that transposes a quantity
        # or drops a digit from a part number produces a case that looks complete
        # and is wrong. Transcription makes a case assessable; it never lowers the
        # outcome.
        reasons.append(
            f"{len(transcript)} attachment(s) were read by a MACHINE, not a "
            "person: " + ", ".join(str(t) for t in transcript)
            + ". Every value taken from them is marked TRANSCRIBED and none has "
            "been confirmed by the customer")
    if blocking:
        codes = sorted({str(i.get("code")) for i in blocking})
        reasons.append(f"{len(blocking)} blocking open item(s): {', '.join(codes)}")
    if unread:
        names = ", ".join(str(f.get("filename")) for f in unread)
        reasons.append(
            f"{len(unread)} attached file(s) the engine never read ({names}); "
            "the case was derived without them")
    if evidence is not None and status != "scanned":
        reasons.append(
            "the attachments could not be checked "
            f"({(evidence or {}).get('error') or status}), so it is unknown "
            "whether the customer sent evidence this case does not contain")
    if reasons:
        return OUTCOME_NEEDS_HUMAN, "; ".join(reasons)
    if items:
        return OUTCOME_COMPLETE, (
            f"{len(items)} open item(s), none blocking a quote; no unread "
            "attachments; nothing machine-read")
    return OUTCOME_COMPLETE, "no open items; no unread attachments; nothing machine-read"


def input_sha256(path):
    """Content hash of the RFQ, streamed. None if it cannot be read."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def idempotency_key(invocation, input_sha, augmentation=None):
    """The identity of a RUN, for recognising a retry. ONE expression of it.

    Hashes the input's CONTENT plus the flags, deliberately not the input's path:
    the same email saved under a second name is the same case, and Body must be
    able to recognise a retry without inventing an identity for it.

    It lives here, beside the invocation record, because two sites need it -- the
    manifest writes it and the review request cites it -- and a key computed
    twice is a key that can be computed differently.
    """
    ident = json.dumps({"input_sha256": input_sha,
                        "augmentation": sorted(augmentation or []),
                        "component_ids": (invocation or {}).get("component_ids") or [],
                        "coc": bool((invocation or {}).get("coc")),
                        "config_dir": (invocation or {}).get("config_dir")},
                       sort_keys=True)
    return hashlib.sha256(ident.encode("utf-8")).hexdigest()


def source_input(state):
    """The file the CUSTOMER sent, even after the case text has been augmented.

    `invocation["input"]` is the text the ENGINE reads, and CW-6/CW-9 both
    re-point it at a generated `.txt`. Anything asking a question about the
    MESSAGE -- above all "what did they attach?" -- has to look at the original,
    or it gets a confident "none" from a file that never had attachments.

    That was a live defect in v0.19.0, found while building CW-9: applying an
    operator answer to a message carrying an unread drawing made the reply report
    `Attachments: none in the source email` and drop the EVIDENCE NOT READ block
    entirely. The attachment did not stop existing because a reviewer answered a
    question.

    `transcripts` is consulted before `answers` because transcription runs first,
    so its record is the one that names the real `.eml`.
    """
    for key in ("transcripts", "answers"):
        recorded = ((state or {}).get(key) or {}).get("original_input")
        if recorded:
            return recorded
    return ((state or {}).get("invocation") or {}).get("input")


def engine_commit():
    """The vendored engine's source commit, read from its PROVENANCE stamp.

    Returns (commit, error). Never raises and never guesses: if the stamp cannot
    be read the commit is None and the reason is returned, so the manifest
    records that the engine is unattributed rather than attributing it wrongly.
    `tools/selftest.py` asserts a real commit comes back, so a PROVENANCE format
    change fails the suite here rather than degrading silently in production.
    """
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "vendor", "PROVENANCE.md")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        return None, f"cannot read {path}: {e}"
    m = re.search(r"\|\s*Source commit\s*\|\s*`([0-9a-f]{7,40})`", text)
    if not m:
        return None, f"no 'Source commit' row found in {path}"
    return m.group(1), None


class StateError(Exception):
    """A run-state operation failed in a way that must stop the run."""


def make_invocation(input_path, component_ids=None, coc=False, config_dir=None):
    """Build an invocation record. The ONLY constructor."""
    return {
        "input": input_path,
        "component_ids": list(component_ids or []),
        "coc": bool(coc),
        "config_dir": config_dir,
    }


def normalize_invocation(raw):
    """Coerce a recorded invocation into the current shape, or return None.

    Reads through INVOCATION_KEYS rather than a hand-written whitelist, so a key
    added to the record cannot be silently dropped here (R26-F6).
    """
    if not isinstance(raw, dict) or not raw.get("input"):
        return None
    inv = make_invocation(raw["input"])
    for k in INVOCATION_KEYS:
        if k in raw:
            inv[k] = raw[k]
    inv["component_ids"] = list(inv.get("component_ids") or [])
    inv["coc"] = bool(inv.get("coc"))
    return inv


def build_argv(invocation, as_json):
    """Assemble the engine argv. The ONLY site that does this."""
    argv = [invocation["input"]]
    if as_json:
        argv.append("--json")
    if invocation.get("component_ids"):
        argv += ["--component-ids"] + list(invocation["component_ids"])
    if invocation.get("coc"):
        argv.append("--coc")
    if invocation.get("config_dir"):
        argv += ["--config-dir", invocation["config_dir"]]
    return argv


def artifact_path(name, **overrides):
    """The path of ONE declared artifact. For a site that owns a single file.

    Round 28 (F-4) found `generate_report.py` still hand-writing its path while
    `all_artifacts()`'s docstring claimed no clearing site names files. A site
    that legitimately owns one artifact resolves it through the declaration by
    NAME; only a site clearing the whole run uses all_artifacts().
    """
    return artifact_paths(**overrides)[name]


def all_artifacts(**overrides):
    """Every artifact path a run owns, as a LIST, for invalidation.

    For sites that clear the WHOLE run (the gate, the extract phase). A site
    owning a single artifact uses artifact_path(name) instead -- neither ever
    hard-codes a filename.

    Round 27 (R27-F4) found that although ARTIFACTS was declared centrally, all
    three clearing sites hand-wrote `[paths["case_state"], paths["bom_draft"]]`.
    Nothing consumed the declaration as a set, so adding a third artifact would
    have been missed everywhere -- R26-F1's exact mechanism, intact behind a
    docstring claiming otherwise. Verified by the self-test adding a synthetic
    artifact and requiring both whole-run sites to clear it.
    """
    return list(artifact_paths(**overrides).values())


def invalidate(paths):
    """Delete the given artifacts. Raises StateError if any cannot be removed.

    Called BEFORE work that can fail, so a failure can never leave a previous
    run's artifact behind looking current. Never silent: a missing file is fine,
    an undeletable one stops the run.
    """
    for p in paths:
        if not p or not os.path.lexists(p):
            continue
        try:
            if os.path.isdir(p) and not os.path.islink(p):
                raise StateError(
                    f"{p} is a directory where an artifact belongs; refusing to "
                    "guess — remove it and re-run")
            os.unlink(p)
        except StateError:
            raise
        except OSError as e:
            raise StateError(
                f"cannot clear the previous run's {p}: {e}. Refusing to continue: "
                "a failure now would leave a stale artifact that looks current.")


def read_state(path):
    """Load a state file, returning {} when there isn't a usable one."""
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_state(path, updates, drop=()):
    """Merge `updates` into the state file. Raises StateError on failure.

    Loud for the same reason invalidate() is: if the record of what this run did
    cannot be written, a later phase would act on the previous run's record.
    """
    if not path:
        return
    state = read_state(path)
    for k in drop:
        state.pop(k, None)
    state.update(updates)
    try:
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
            fh.write("\n")
    except OSError as e:
        raise StateError(f"cannot update {path}: {e}")


def artifact_paths(**overrides):
    """Resolve the artifact paths for this run, honouring explicit overrides."""
    paths = dict(ARTIFACTS)
    for k, v in overrides.items():
        if v:
            paths[k] = v
    return paths
