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
  * FILTER_KEYS     — the input-filter gate's decision, recorded under
                      `FILTER_KEY` in state.json. Deliberately NOT an artifact:
                      a filtered run produces no file at all — its record IS
                      the state key — so ARTIFACTS/invalidate() are untouched.
                      Same discipline as INVOCATION_KEYS: one constructor, one
                      normaliser, read through the declared keys rather than a
                      hand-written whitelist (R26-F6).
  * SCREEN_KEY      — the prepare phase's record of the `--no-filter` override,
                      recorded under `SCREEN_KEY` in state.json. Kept OUT of
                      INVOCATION_KEYS/build_argv on purpose: it is not an engine
                      flag, so folding it into the invocation would leak into
                      the engine argv and put parity at risk.

Invalidation is LOUD. Round 26 (R26-F5) found `except OSError: pass` swallowing
clearing failures, which reproduced the very defect the clearing exists to
prevent: under a read-only `_report/` the stale artifact survived silently. If we
cannot guarantee the old artifacts are gone, the run must say so and stop.
"""
from __future__ import annotations

import json
import os

# Every artifact a run produces, relative to the run directory. Invalidation
# walks this mapping — a new artifact is declared once, here, and every clearing
# site picks it up for free.
ARTIFACTS = {
    "case_state": os.path.join("_report", "case_state.json"),
    "bom_draft": os.path.join("_report", "bom_draft.md"),
}

# The engine invocation's shape. Adding an argument means adding it here.
INVOCATION_KEYS = ("input", "component_ids", "coc", "config_dir")

# The filter gate's decision record, written into state.json under FILTER_KEY.
# A filtered run produces no ARTIFACTS entry — this key IS its record — so
# adding a field here never touches ARTIFACTS or invalidate().
FILTER_KEY = "filter"
FILTER_KEYS = ("filtered", "input", "code", "route", "evidence", "override", "reason")

# The prepare phase's record of the `--no-filter` override, written into
# state.json under SCREEN_KEY. Not an engine flag: kept out of INVOCATION_KEYS
# and build_argv so the engine argv, and therefore parity, never sees it.
SCREEN_KEY = "screen"


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


def make_filter_decision(filtered, input_path, code=None, route=None,
                          evidence=None, override=False, reason=None):
    """Build a filter-gate decision record. The ONLY constructor.

    `filtered` and `input_path` are required — C1 needs to know whether the run
    stopped here, and C6 needs the input path to replay a false positive.
    `code`/`route` are `None` on the pass-through path; when set they must come
    from the closed vocabulary the gate declares (schemas/filter_decision).
    """
    return {
        "filtered": bool(filtered),
        "input": input_path,
        "code": code,
        "route": route,
        "evidence": evidence,
        "override": bool(override),
        "reason": reason,
    }


def normalize_filter_decision(raw):
    """Coerce a recorded filter decision into the current shape, or return None.

    Reads through FILTER_KEYS rather than a hand-written whitelist, so a key
    added to the record cannot be silently dropped here (the R26-F6 shape).
    """
    if not isinstance(raw, dict) or not raw.get("input"):
        return None
    dec = make_filter_decision(bool(raw.get("filtered")), raw["input"])
    for k in FILTER_KEYS:
        if k in raw:
            dec[k] = raw[k]
    dec["filtered"] = bool(dec.get("filtered"))
    dec["override"] = bool(dec.get("override"))
    return dec


def make_screen_request(override=False):
    """Build a screen-override record. The ONLY constructor.

    Records the operator's `--no-filter` choice for the prepare phase to write
    down once, so later phases read it back instead of the flag being re-typed.
    """
    return {"override": bool(override)}


def normalize_screen_request(raw):
    """Coerce a recorded screen request into the current shape, or return None."""
    if not isinstance(raw, dict):
        return None
    return make_screen_request(bool(raw.get("override")))


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
