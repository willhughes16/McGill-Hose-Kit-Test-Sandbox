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

Whether a candidate category actually gets filtered turns on the
quoting-request veto (ADR-005's sibling decision, recorded with the others):
a message that carries BOTH the vendored classifier's own "in scope" verdict
AND some sign of an actual request (a question mark, one of the engine's own
`question_cues`, an `order`/`stocking_lead` classification, or a kit-side
`quote_request_cues` hit) is never filtered, however junk-shaped its headers
look. This is what saves a real RFQ that happens to carry bulk/auto-reply
headers, opens with a polite "thanks, got it", or is bundled with an invoice
paragraph (C5). DELIVERY_STATUS_NOTIFICATION is the one category exempt from
the veto -- a bounce is never a request, even one that echoes RFQ text back
in its body.

The gate never rewrites, copies or re-encodes the input file -- it only
reads it -- so a message that reaches the engine is byte-identical to what
this script was given (C4).
"""
from __future__ import annotations

import argparse
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
    ARTIFACTS, FILTER_KEY, StateError, artifact_paths, invalidate,
    make_filter_decision, normalize_invocation, normalize_screen_request,
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
    ctype = str(headers.get("Content-Type", "") or "").lower()
    if "multipart/report" in ctype and "delivery-status" in ctype:
        return str(headers.get("Content-Type", "")).strip()
    sender = _local_part(headers.get("From"))
    if sender and sender in signals.get("dsn_sender_localparts", []):
        return str(headers.get("From", "")).strip()
    if str(headers.get("Return-Path", "") or "").strip() == "<>":
        return "Return-Path: <>"
    return None


def _auto_reply_header(headers, signals):
    val = headers.get("Auto-Submitted")
    if val is not None and str(val).strip().lower() != "no":
        return f"Auto-Submitted: {val}".strip()
    sender = _local_part(headers.get("From"))
    if sender and sender in signals.get("auto_reply_localparts", []):
        return str(headers.get("From", "")).strip()
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

def _invoice_content(subject, body, headers, signals):
    combined = f"{subject}\n{body}".lower()
    for phrase in signals.get("invoice_phrases", []):
        if phrase in combined:
            return phrase
    return None


def _ack_content(subject, body, headers, signals):
    remainder = _strip_quote_and_signature(body)
    max_chars = signals.get("ack_max_chars", 0)
    if not remainder or len(remainder) > max_chars:
        return None
    normalized = remainder.strip().lower().rstrip(".,!;: ")
    if normalized in signals.get("ack_phrases", []):
        return remainder
    return None


def _internal_domain_content(subject, body, headers, signals):
    if headers is None:
        return None
    from_addrs = getaddresses([str(headers.get("From", "") or "")])
    if not from_addrs or "@" not in from_addrs[0][1]:
        return None
    from_domain = from_addrs[0][1].rsplit("@", 1)[-1].strip().lower()
    to_cc = getaddresses([str(headers.get("To", "") or ""),
                           str(headers.get("Cc", "") or "")])
    recipients = [addr for _, addr in to_cc if addr and "@" in addr]
    if not recipients:
        return None
    if all(addr.rsplit("@", 1)[-1].strip().lower() == from_domain
           for addr in recipients):
        return f"internal: {from_domain}"
    return None


_CONTENT_DETECTORS = {
    "invoice_content": _invoice_content,
    "ack_content": _ack_content,
    "internal_domain_content": _internal_domain_content,
}


# ---------------------------------- decide() ----------------------------------

def decide(raw, filename, rules, signals):
    """The ONE seam: decide whether `raw` (the input's bytes) should be
    filtered. Never raises -- any internal failure is caught and treated as
    ambiguity, which resolves to NOT filtered (ADR-001). Returns a partial
    record: {filtered, code, route, evidence, reason}. The caller
    (`main()`) adds `input` and `override` to shape it into the full
    `filter` record (`run_state.make_filter_decision`).
    """
    try:
        return _decide(raw, filename, rules, signals)
    except Exception:  # noqa: BLE001 - deliberate; see module docstring / ADR-001
        return {"filtered": False, "code": None, "route": None,
                "evidence": None, "reason": "parse_failed"}


def _decide(raw, filename, rules, signals):
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

    # DSN is the one category exempt from the quoting-request veto -- a bounce
    # is never a request -- so it can filter immediately without paying for a
    # body decode at all.
    if header_hit is not None and header_hit[0] == "DELIVERY_STATUS_NOTIFICATION":
        code, route, evidence = header_hit
        return {"filtered": True, "code": code, "route": route,
                "evidence": evidence[:80], "reason": None}

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

    # The quoting-request veto: filter only if there is NO quoting request,
    # where a quoting request is product_signal AND request_act.
    klass, _ev = triage.classify(low, rules)
    product_signal = klass != "out_of_scope"
    request_act = _is_request_act(low, klass, rules, signals)
    if product_signal and request_act:
        return {"filtered": False, "code": None, "route": None,
                "evidence": None, "reason": "quoting_request_detected"}

    code, route, evidence = candidate
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
        invalidate([paths["case_state"], paths["bom_draft"]])
    except StateError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    override = bool(args.no_filter)
    if not override and args.state:
        screen = normalize_screen_request(read_state(args.state).get("screen"))
        override = bool(screen and screen.get("override"))

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
        rules = None
        if signals is not None:
            try:
                rules = (core.load_config(args.config_dir) if args.config_dir
                          else core.load_config())["rules"]
            except Exception:  # noqa: BLE001 - an unreadable config is ambiguity
                rules = None

        if signals is None or rules is None:
            print("warning: filter reference data unavailable; failing open "
                  "(this message will reach the engine)", file=sys.stderr)
            raw_decision = {"filtered": False, "code": None, "route": None,
                             "evidence": None, "reason": "no_evidence"}
        else:
            raw_decision = decide(raw, os.path.basename(input_path), rules,
                                   signals)

        code, route = raw_decision.get("code"), raw_decision.get("route")
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
