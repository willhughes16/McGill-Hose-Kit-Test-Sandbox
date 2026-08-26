#!/usr/bin/env python3
"""Decide whether an inbound message is worth handing to the engine at all.

This is the input-filter GATE (Phase 05). It runs BEFORE the engine, never
after: `run_engine.py` is never imported or invoked from here, so a filtered
message costs a cheap stdlib parse, never an engine pass (ADR-005).

Exit codes -- ONLY these three, enforced by the clamp in `__main__` exactly
like `run_engine.py`'s own discipline (R26-F2) -- 2 is the ENGINE's own "draft
with open items" code and must never leak from here:
    0  not filtered  -- proceed to the engine
    3  filtered      -- do NOT run the engine; nothing to quote (ADR-002)
    1  the gate's own failure (bad usage, unreadable input, unwritable state)

The gate fails OPEN, on purpose -- a named inversion of the kit's usual
fail-closed guard idiom (ADR-001). Filtering a real RFQ is far worse than
handing the engine a newsletter: everything the gate cannot resolve
confidently -- no text obtained, a parse defect or exception, an HTML-only
body over the declared scan budget, an unrecognised/undecodable part, a
code/route outside the declared vocabulary, an unreadable reference/schema
file -- resolves to NOT filtered. Only a hard input error (the path itself is
missing or unreadable) is loud and fails closed; that is not ambiguity.

The whole decision lives behind ONE seam, `decide()`, so `tools/selftest.py`
can call it directly (as well as via subprocess) and mutation-prove it (C7,
ADR-003): the recipe phase only branches on this script's exit code, it never
judges "is this a request" itself.

Signal vocabulary (categories, cue phrases, thresholds) is declared once in
`reference/filter_signals.json` (t1); the closed code/route/reason enums this
script must never emit outside of are declared in
`schemas/filter_decision.schema.json` (t2). Both are loaded by a `__file__`-
relative path so this runs the same way in the repo tree and in the unzipped
kit under `python3 -S -E`.

Whether a candidate category actually gets filtered turns on SPECIFICATION
DEPTH: `_spec_depth()` counts the fields the vendored engine extracts from the
message, and a message with ANY specification at all is never filtered, however
junk-shaped its headers look. No category is exempt. That is what saves a real
RFQ carrying bulk or auto-reply headers, opening with "thanks, got it", bundled
with an invoice paragraph, or arriving through a sourcing portal.

The measurement is a property of the message, and the field list is derived from
the engine's own `Extraction` dataclass rather than written out here, so a field
cannot go dead and a field the engine adds later counts as protection by default.
Two earlier designs failed exactly here and both are worth remembering: round 27
protected RFQs with a 16-phrase `quote_request_cues` list and lost 24 of 35
genuine requests to a line of "Terms net 30."; round 28 then found a hand-written
field tuple naming "length", which `Extraction` does not have, so length-only
orders measured zero. The quoting-request veto still runs as a second net, but it
is never the only thing between a customer and a silent drop.

The gate never rewrites, copies or re-encodes the input file -- it only
reads it -- so a message that reaches the engine is byte-identical to what
this script was given (C4).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import sys
from email import policy
from email.parser import BytesHeaderParser, BytesParser
from email.utils import getaddresses

_HERE = os.path.dirname(os.path.abspath(__file__))
_VENDOR = os.path.join(os.path.dirname(_HERE), "vendor")
for _p in (_VENDOR, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from email_to_bom import core, mail, triage  # noqa: E402  (needs sys.path above)
from run_state import (  # noqa: E402
    ARTIFACTS, FILTER_KEY, StateError, all_artifacts, artifact_paths, invalidate,
    make_filter_decision, normalize_invocation, normalize_screen_request,
    screen_applies,
    read_state, write_state,
)

_SRC = os.path.dirname(_HERE)
SIGNALS_PATH = os.path.join(_SRC, "reference", "filter_signals.json")
SCHEMA_PATH = os.path.join(_SRC, "schemas", "filter_decision.schema.json")


# --------------------------- reference data loading -------------------------

def _load_signals(path=SIGNALS_PATH):
    """Load the signal vocabulary. Returns None (never raises) if it can't be
    read or parsed -- an unreadable reference file is ambiguity, not grounds
    to filter (ADR-001)."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _load_enums(path=SCHEMA_PATH):
    """Load the closed code/route vocabulary from the decision schema. Returns
    (None, None) if it can't be read -- callers must then skip validation
    rather than treat that as grounds to filter."""
    try:
        with open(path, encoding="utf-8") as fh:
            schema = json.load(fh)
        props = schema.get("properties", {})
        codes = set(props.get("code", {}).get("enum", []))
        routes = set(props.get("route", {}).get("enum", []))
        return codes, routes
    except (OSError, json.JSONDecodeError, AttributeError):
        return None, None


def _load_reason_pattern(path=SCHEMA_PATH):
    """The declared shape of `reason`, from the same schema as the code/route
    enums. Returns None when unreadable -- callers then skip validation rather
    than treat an unreadable schema as grounds to filter."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)["properties"]["reason"].get("pattern")
    except (OSError, json.JSONDecodeError, KeyError, AttributeError, TypeError):
        # TypeError included deliberately: round 29 (F-6) found this sibling of
        # _load_enums missing it, so a malformed schema crashed the gate with an
        # unhandled TypeError and rc=1 instead of failing open. A guard's own
        # failure must never stop the run.
        return None


def _reason_ok(reason, pattern):
    """Whether a reason matches the shipped schema's declared shape.

    Round 28 (F-6) found only `code`/`route` validated, so the two reasons round
    27 added made every spec-bearing pass-through violate the schema unnoticed.
    """
    if reason is None or not pattern:
        return True
    return bool(re.match(pattern, str(reason)))


# ------------------------------- text helpers --------------------------------

def _local_part(value):
    if not value:
        return None
    addrs = getaddresses([str(value)])
    if not addrs or "@" not in addrs[0][1]:
        return None
    return addrs[0][1].split("@", 1)[0].strip().lower()


_QUOTE_START = re.compile(
    r"^(on .+ wrote:|-{2,}\s*original message\s*-{2,}|from:.*)$", re.IGNORECASE)
_SIG_DELIM = re.compile(r"^--\s*$", re.MULTILINE)


def _strip_quote_and_signature(body):
    """The remainder after quoted history and a signature block are removed --
    the dominance test for BARE_ACKNOWLEDGEMENT reads this, never the raw
    body, so a real request tacked on after a polite opener is not lost in a
    substring match (C5's ack-plus-rfq)."""
    kept = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(">") or _QUOTE_START.match(stripped):
            break
        kept.append(line)
    text = "\n".join(kept)
    m = _SIG_DELIM.search(text)
    if m:
        text = text[:m.start()]
    return text.strip()


def _collect_text(msg, signals):
    """A cheap, bounded text view: decoded text/plain parts verbatim, and
    text/html parts run through `mail.html_to_text` ONLY under the declared
    `html_scan_bytes` budget. Never calls `mail.extract_rfq_text` and never
    runs the HTML-hiding pipeline on a large body (ADR-005) -- that is the
    engine's own superlinear cost, which this gate exists to avoid paying on
    every message. Returns (text, undecodable); undecodable is True when no
    usable text part could be read at all, so the caller can tell "genuinely
    nothing here" from "this message just doesn't mention anything".
    """
    if msg is None:
        return "", True
    texts = []
    saw_any = False
    undecodable = False
    try:
        parts = list(msg.walk())
    except Exception:  # noqa: BLE001 - a parse defect is ambiguity, not grounds to filter
        return "", True
    budget = signals.get("html_scan_bytes", 0) if signals else 0
    for part in parts:
        try:
            if part.is_multipart():
                continue
            ctype = part.get_content_type()
        except Exception:  # noqa: BLE001
            continue
        if ctype == "text/plain":
            saw_any = True
            try:
                texts.append(str(part.get_content()))
            except Exception:  # noqa: BLE001
                undecodable = True
        elif ctype == "text/html":
            saw_any = True
            try:
                html = str(part.get_content())
            except Exception:  # noqa: BLE001
                undecodable = True
                continue
            if len(html.encode("utf-8", errors="replace")) <= budget:
                try:
                    texts.append(mail.html_to_text(html))
                except Exception:  # noqa: BLE001
                    undecodable = True
            else:
                undecodable = True  # over budget: fail open, never truncate-and-scan
    if not saw_any:
        undecodable = True
    return "\n".join(texts), undecodable


# Non-spec fields on the engine's Extraction record. Everything ELSE counts as a
# specification, derived from the dataclass itself -- so a field name cannot go
# dead and a field the engine adds later counts as protection by default (the
# safe direction). Round 28 (F-1) found `_SPEC_FIELDS` hand-listing "length",
# which `Extraction` does not have (it has length_value/length_type), so
# getattr(e, "length") was None for every message ever written and a length-only
# order -- "get us 400 feet of the transfer hose" -- measured depth 0 and was
# filtered as an invoice. A hand-written list of attribute names is an
# enumeration that can silently stop matching the thing it enumerates.
_NON_SPEC_FIELDS = frozenset({
    "customer",              # who asked, not what they want
    "material_recognized",   # a bool flag about `material`, not a spec itself
})


def _spec_field_names():
    """Spec-bearing Extraction fields, read off the engine's own dataclass."""
    return tuple(f.name for f in dataclasses.fields(core.Extraction)
                 if f.name not in _NON_SPEC_FIELDS)


def _is_specified(value):
    """Whether an extracted field actually carries a specification."""
    if value is None or value is False:
        return False
    return value not in ("", [], {})


def _spec_depth(agent, low):
    """How many specification fields the engine extracts from this message.

    The round-27 replacement for a phrase list as the thing protecting a real
    RFQ, and the ONLY thing that protects one: a message with any specification
    at all is never filtered. Measured, not enumerated, and monotone -- more
    customer detail means more protection.
    """
    if agent is None:
        return 99      # no extractor => unknown depth => fail toward the engine
    try:
        e = agent.extract(low)
    except Exception:  # noqa: BLE001 - never let the guard's own failure filter
        return 99      # unknown depth counts as "specified": fail toward the engine
    return sum(1 for f in _spec_field_names() if _is_specified(getattr(e, f, None)))


def _is_request_act(low, klass, rules, signals):
    """Is this a request AT ALL, independent of product words -- the engine
    assumes yes, so this is genuinely new vocabulary (ADR-005's sibling)."""
    if "?" in low:
        return True
    for cue in rules.get("question_cues", []):
        if re.search(rf"\b{re.escape(cue)}\b", low):
            return True
    if klass in ("order", "stocking_lead"):
        return True
    for cue in signals.get("quote_request_cues", []):
        if cue in low:
            return True
    return False


# ------------------------------ header-tier detectors -------------------------

def _dsn_headers(headers, signals):
    """A real bounce, evidenced by the CONJUNCTION of its two markers.

    Round 27 (R27-F2) took each marker as sufficient on its own, so a
    `postmaster@` sender, or a bare `Return-Path: <>`, or any `multipart/report`
    dropped a message whose subject read "RFQ - hose assemblies, please quote".
    A genuine DSN is a report-type=delivery-status multipart WITH a null return
    path; a human forwarding a bounce has neither. Requiring both costs nothing
    real and removes three false-positive routes.
    """
    ctype = str(headers.get("Content-Type", "") or "").lower()
    is_report = "multipart/report" in ctype and "delivery-status" in ctype
    # The report-type declaration alone. An earlier round also demanded a null
    # `Return-Path`, which lost real bounces that do not set one; and the reason
    # that requirement existed -- protecting a genuine RFQ forwarded inside a
    # multipart/report -- is now handled by the body-depth guard, which no
    # category can skip. Detect the declaration; let the guard decide.
    if is_report:
        return str(headers.get("Content-Type", "")).strip()
    return None


def _auto_reply_header(headers, signals):
    """An automatic REPLY, per RFC 3834 -- never an original request.

    Round 29 (F-2) found two defects here. The sender local-part test
    (`no-reply@`, `donotreply@`) dropped real RFQs, because that is the standard
    sender of every sourcing portal and ERP requisition notice -- the most common
    way a B2B request arrives. It is gone: an address is not a declaration.

    And `auto-generated` was treated the same as `auto-replied`. RFC 3834 draws a
    real line: `auto-replied` means this message IS a reply to another, which a
    customer's original request never is; `auto-generated` merely means software
    produced it, which is exactly what an ERP requisition is. Only `auto-replied`
    (and the legacy `X-Autoreply`/`X-Autorespond` markers) filter now.
    """
    val = str(headers.get("Auto-Submitted", "") or "").strip().lower()
    if val.startswith("auto-replied"):
        return f"Auto-Submitted: {val}"
    for legacy in ("X-Autoreply", "X-Autorespond"):
        if headers.get(legacy):
            return f"{legacy}: {headers.get(legacy)}".strip()
    return None


def _bulk_headers(headers, signals):
    list_unsub = headers.get("List-Unsubscribe")
    if not list_unsub:
        return None  # NEVER List-Unsubscribe alone
    precedence = str(headers.get("Precedence", "") or "").strip().lower()
    if precedence in signals.get("bulk_precedence_values", []):
        return f"List-Unsubscribe + Precedence: {precedence}"
    list_id = headers.get("List-Id") or headers.get("List-ID")
    if list_id:
        return f"List-Unsubscribe + List-Id: {list_id}".strip()
    return None


_HEADER_DETECTORS = {
    "dsn_headers": _dsn_headers,
    "auto_reply_header": _auto_reply_header,
    "bulk_headers": _bulk_headers,
}


# ------------------------------ content-tier detectors -------------------------

# EMPTY, on purpose. Round 29 dropped 11 of 46 genuine RFQs and every content
# detector was implicated: an `invoice_phrases` substring sent 6 to accounts
# payable ("net 30" in a purchasing email is a purchase order, not an invoice),
# and the ack/internal detectors judged a message by its length or its
# addressing. A message's prose is not evidence that its sender wants nothing.
# The detectors are deleted rather than disabled so a new category cannot re-wire
# a capability that has failed twice.
_CONTENT_DETECTORS = {}


# ---------------------------------- decide() ----------------------------------

def decide(raw, filename, rules, signals, agent=None):
    """The ONE seam: decide whether `raw` (the input's bytes) should be
    filtered. Never raises -- any internal failure is caught and treated as
    ambiguity, which resolves to NOT filtered (ADR-001). Returns a partial
    record: {filtered, code, route, evidence, reason}. The caller
    (`main()`) adds `input` and `override` to shape it into the full
    `filter` record (`run_state.make_filter_decision`).
    """
    try:
        return _decide(raw, filename, rules, signals, agent)
    except Exception:  # noqa: BLE001 - deliberate; see module docstring / ADR-001
        return {"filtered": False, "code": None, "route": None,
                "evidence": None, "reason": "parse_failed"}


def _decide(raw, filename, rules, signals, agent=None):
    mail_like = mail.looks_like_mime(raw, filename)
    headers = None
    if mail_like:
        try:
            headers = BytesHeaderParser(policy=policy.default).parsebytes(raw)
        except Exception:  # noqa: BLE001
            headers = None

    # Tier 1: structural header checks, cheap, only when headers exist. Order
    # comes from signals["categories"] itself -- first match wins, exactly
    # like rules.json's own precedence lists.
    header_hit = None
    if mail_like and headers is not None:
        for cat in signals["categories"]:
            detector = _HEADER_DETECTORS.get(cat["detector"])
            if detector is None:
                continue
            evidence = detector(headers, signals)
            if evidence:
                header_hit = (cat["code"], cat["route"], evidence)
                break

    # NOTHING short-circuits the guards below. Round 27 (R27-F2) let DSN filter
    # before them "because a bounce is never a request", which dropped a labelled
    # RFQ whose only sin was a multipart/report content type.

    try:
        msg = BytesParser(policy=policy.default).parsebytes(raw)
    except Exception:  # noqa: BLE001
        msg = None
    subject = str(headers.get("Subject", "")) if headers is not None else ""
    body, undecodable = _collect_text(msg, signals)
    text = f"{subject}\n\n{body}".strip()
    low = text.lower()

    candidate = header_hit
    if candidate is None:
        for cat in signals["categories"]:
            detector = _CONTENT_DETECTORS.get(cat["detector"])
            if detector is None:
                continue
            evidence = detector(subject, body, headers, signals)
            if evidence:
                candidate = (cat["code"], cat["route"], evidence)
                break

    if candidate is None:
        reason = "parse_failed" if undecodable and not text else "no_evidence"
        return {"filtered": False, "code": None, "route": None,
                "evidence": None, "reason": reason}

    # Fail-open on anything we could not fully read. Round 27 (R27-F3) found
    # `undecodable` was computed and then never consulted, so the fail-open the
    # docs promised did not exist and an HTML body crossing a size threshold
    # flipped the decision. A message we cannot fully read is a message we must
    # not judge.
    if undecodable:
        return {"filtered": False, "code": None, "route": None,
                "evidence": None, "reason": "undecodable_content"}

    code, route, evidence = candidate

    # THE GUARD -- specification depth, a measured property of the message, and
    # the only thing between a customer request and a silent drop. It applies to
    # EVERY category without exception.
    #
    # Round 27 exempted true list-mail ("nobody orders hose from a mailing
    # list"), which left that category protected solely by the veto below --
    # whose request_act half is the 16-phrase cue list round 27 was failed for.
    # Round 28 (F-2) then dropped a customer whose ESP stamps List-Unsubscribe,
    # with EIGHT specification kinds extracted. The exemption is gone: the
    # enumeration must not be load-bearing anywhere, for anyone.
    #
    # The cost is real and accepted: a supplier newsletter naming hose
    # specifications now reaches the engine and produces a draft an operator
    # dismisses. PROJECT.md's phase-5 constraint settles that trade outright --
    # "filtering out a real RFQ is far worse than passing a newsletter through".
    # Measured on the BODY ALONE, deliberately. The subject is not the customer's
    # words: an out-of-office responder echoes the RFQ subject back verbatim, so
    # round 29 (F-8) found 4 of 6 realistic OOO replies measuring a non-zero
    # depth and escaping. The body is what the sender actually wrote -- an OOO
    # body says "I am away", a real request states what it wants.
    #
    # This replaced a protocol exemption for `auto-replied`/DSN, which would have
    # let those two categories skip the guard. That exemption dropped the shipped
    # `bait-rfq` fixture: a genuine RFQ body wearing an `Auto-Submitted:
    # auto-replied` header. No category is exempt; the measurement got sharper
    # instead.
    depth = _spec_depth(agent, body.lower())
    if depth > 0:
        return {"filtered": False, "code": None, "route": None,
                "evidence": None, "reason": f"specifications_present:{depth}"}

    # SECOND NET -- the quoting-request veto. Never load-bearing: the depth guard
    # above applies to every category, so this only ever adds protection.
    # Body only, for the same reason as the depth guard: the subject can be a
    # machine's echo of the customer's words, not the customer's words.
    body_low = body.lower()
    klass, _ev = triage.classify(body_low, rules)
    product_signal = klass != "out_of_scope"
    request_act = _is_request_act(body_low, klass, rules, signals)
    if product_signal and request_act:
        return {"filtered": False, "code": None, "route": None,
                "evidence": None, "reason": "quoting_request_detected"}

    return {"filtered": True, "code": code, "route": route,
            "evidence": evidence[:80], "reason": None}


# ------------------------------------ CLI -------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--in", dest="inp", default=None,
                   help="path to the RFQ .eml/.txt; omit with --from-state")
    p.add_argument("--from-state", action="store_true",
                   help="take the input path from --state (written by the "
                        "prepare phase) instead of re-typing it here")
    p.add_argument("--state", default=None,
                   help="state.json to read the invocation/override from and "
                        "record the filter decision into")
    p.add_argument("--no-filter", action="store_true",
                   help="force pass-through: every message reaches the "
                        "engine, and the override is recorded (C6)")
    p.add_argument("--config-dir", default=None,
                   help="alternate rules/catalog directory -- honoured by the "
                        "quoting-request veto's classifier call")
    p.add_argument("--out", dest="out", default=ARTIFACTS["case_state"],
                   help="case_state.json path to invalidate before deciding")
    p.add_argument("--draft", default=None,
                   help="bom_draft.md path to invalidate before deciding "
                        f"(default {ARTIFACTS['bom_draft']})")
    args = p.parse_args(argv)

    paths = artifact_paths(case_state=args.out, bom_draft=args.draft)

    # Resolve the input path BEFORE clearing anything, so a usage error does
    # not destroy a previous run's artifacts.
    if args.from_state:
        invocation = normalize_invocation(read_state(args.state).get("invocation"))
        if not invocation:
            print(f"error: --from-state given but {args.state} records no "
                  "usable invocation; run the prepare phase first or pass "
                  "--in", file=sys.stderr)
            return 1
        input_path = invocation["input"]
    elif args.inp:
        input_path = args.inp
    else:
        print("error: pass --in <rfq> or --from-state", file=sys.stderr)
        return 1

    if not os.path.isfile(input_path):
        # A hard input error, not ambiguity -- this is the one case that
        # fails closed and loud (ADR-001).
        print(f"error: no such input file: {input_path}", file=sys.stderr)
        return 1

    # A record of a decision NOT to run the engine can only mislead once a
    # fresh CaseState/draft exist beside it, and vice versa (the R26-F1
    # shape) -- clear both artifacts on EVERY branch below, before anything
    # that can fail.
    try:
        invalidate(all_artifacts(case_state=args.out, bom_draft=args.draft))
    except StateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    override = bool(args.no_filter)
    if not override and args.state:
        # A recorded override governs only the message it was granted for
        # (round 27): a stale record from the previous run must not silently
        # disable the safeguard for a different email.
        screen = normalize_screen_request(read_state(args.state).get("screen"))
        override = screen_applies(screen, input_path)

    if override:
        # Opting out is explicit and loud (CONVENTIONS) -- this is C6's
        # no-code-edit escape hatch for a false positive.
        print("warning: --no-filter is set; the input filter is disabled for "
              "this run and every message reaches the engine", file=sys.stderr)
        decision = make_filter_decision(False, input_path, override=True,
                                         reason="override")
    else:
        try:
            with open(input_path, "rb") as fh:
                raw = fh.read()
        except OSError as e:
            print(f"error: cannot read {input_path}: {e}", file=sys.stderr)
            return 1

        signals = _load_signals()
        allowed_codes, allowed_routes = _load_enums()
        rules, agent = None, None
        if signals is not None:
            try:
                cfg = (core.load_config(args.config_dir) if args.config_dir
                       else core.load_config())
                rules = cfg["rules"]
                # The SAME cfg powers the depth guard's extractor and the veto's
                # classifier, so the two guards can never disagree about config.
                agent = core.Agent(cfg)
            except Exception:  # noqa: BLE001 - an unreadable config is ambiguity
                rules, agent = None, None

        if signals is None or rules is None:
            print("warning: filter reference data unavailable; failing open "
                  "(this message will reach the engine)", file=sys.stderr)
            raw_decision = {"filtered": False, "code": None, "route": None,
                             "evidence": None, "reason": "no_evidence"}
        else:
            raw_decision = decide(raw, os.path.basename(input_path), rules,
                                   signals, agent)

        code, route = raw_decision.get("code"), raw_decision.get("route")
        # Round 28 (F-6): only code/route were checked, so the two reasons round
        # 27 added made every spec-bearing pass-through violate the shipped
        # schema unnoticed. Validate the whole declared record, not two of its
        # fields.
        reason = raw_decision.get("reason")
        if not _reason_ok(reason, _load_reason_pattern()):
            print(f"warning: gate produced an undeclared reason {reason!r}; "
                  "failing open (this message will reach the engine)",
                  file=sys.stderr)
            raw_decision = {"filtered": False, "code": None, "route": None,
                             "evidence": None, "reason": "no_evidence"}
            code = route = None
        code_ok = allowed_codes is None or code in allowed_codes
        route_ok = allowed_routes is None or route in allowed_routes
        if not (code_ok and route_ok):
            print(f"warning: filter_gate produced an undeclared code/route "
                  f"({code!r}/{route!r}); failing open", file=sys.stderr)
            raw_decision = {"filtered": False, "code": None, "route": None,
                             "evidence": None, "reason": "no_evidence"}

        decision = make_filter_decision(
            raw_decision.get("filtered", False), input_path,
            code=raw_decision.get("code"), route=raw_decision.get("route"),
            evidence=raw_decision.get("evidence"), override=False,
            reason=raw_decision.get("reason"))

    try:
        if args.state:
            # Preserve `invocation` (REQ-035); only the stale extract result
            # is dropped, since a filtered/overridden run has not recomputed
            # it (the sibling of what t7 does for a successful extract).
            write_state(args.state, {FILTER_KEY: decision},
                        drop=("extract_case",))
    except StateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(json.dumps(decision, indent=2))
    return 3 if decision["filtered"] else 0


if __name__ == "__main__":
    # Clamp: this gate reports 0, 3 or 1 and nothing else -- 2 is the
    # ENGINE's own "draft with open items" code and must never leak from a
    # failure path here (R26-F2's discipline, applied to the new codes).
    try:
        _rc = main()
    except KeyboardInterrupt:
        _rc = 1
    except BaseException as _e:  # noqa: BLE001 - deliberate
        print(f"error: unhandled {type(_e).__name__}: {_e}", file=sys.stderr)
        _rc = 1
    raise SystemExit(_rc if _rc in (0, 1, 3) else 1)
