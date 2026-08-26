"""Deterministic validators — the mechanical red conditions the blind verifier uses.
Each returns (ok: bool, reason: str). A validator MUST be able to fail a bad BOM.
"""
from __future__ import annotations

from typing import Any

_PRICE_KEYS = {"price", "unit price", "extended price", "cost", "total", "amount"}
_VERIFIED_CLAIMS = ("material verified", "verified by agent", "qc approved", "cert confirmed",
                    "material approved", "verified w/qc", "verified with qc")


def validate_columns(result_dict: dict[str, Any], expected: list[str]) -> tuple[bool, str]:
    if result_dict["bom_columns"] != expected:
        return False, f"columns {result_dict['bom_columns']} != {expected}"
    for line in result_dict["lines"]:
        for col in expected:
            if col not in line:
                return False, f"line missing column {col}: {line.get('Component ID')}"
    return True, "ok"


def validate_no_price(result_dict: dict[str, Any]) -> tuple[bool, str]:
    for line in result_dict["lines"]:
        for k in line:
            if k.lower() in _PRICE_KEYS:
                return False, f"price field present: {k}"
    return True, "ok"


def validate_uom(result_dict: dict[str, Any], uom_set: list[str]) -> tuple[bool, str]:
    for line in result_dict["lines"]:
        uom = line.get("UOM")
        if uom is not None and uom not in uom_set:
            return False, f"invalid UOM '{uom}' on {line.get('Component ID')}"
    return True, "ok"


def validate_catalog(result_dict: dict[str, Any], catalog_ids: set[str],
                     allowed_synthetic: set[str]) -> tuple[bool, str]:
    """Every Component ID on the BOM must be a grounded catalog ID or an allowed
    synthetic instruction line (CMTR / C OF C). No fabricated part numbers (FR-11)."""
    for line in result_dict["lines"]:
        cid = str(line.get("Component ID", "")).upper()
        if cid in allowed_synthetic:
            continue
        # A line grounded in a VERIFIED knowledge fact is not a fabrication: it
        # carries provenance and a citation (DD-3). Candidate facts never reach a
        # line, so this can only admit P21-sourced records.
        if (line.get("provenance") == "knowledge:verified"
                and str(line.get("citation") or "").strip()):
            continue
        if cid not in catalog_ids:
            return False, f"fabricated/unknown Component ID: {cid}"
    return True, "ok"


# Text the engine QUOTES rather than asserts: a customer writing "material
# verified by our QC", or graph prose saying the same, must not read as the agent
# claiming verification (round 20). The rule protects against the AGENT asserting
# it, so the scan covers agent-authored text only.
_QUOTED_KEYS = {"quote", "citation", "context_text", "summary_text", "candidates",
                "items", "knowledge", "arg"}


def _agent_authored(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _agent_authored(x) for k, x in node.items()
                if k not in _QUOTED_KEYS}
    if isinstance(node, list):
        return [_agent_authored(x) for x in node]
    return node


def validate_no_self_verification(result_dict: dict[str, Any]) -> tuple[bool, str]:
    blob = str(_agent_authored(result_dict)).lower()
    for claim in _VERIFIED_CLAIMS:
        if claim in blob:
            return False, f"agent asserts material verification itself: '{claim}'"
    return True, "ok"


def validate_lead_time(result_dict: dict[str, Any]) -> tuple[bool, str]:
    for line in result_dict["lines"]:
        if line.get("Component Type") in ("Hose", "Fitting", "Sleeve"):
            if not line.get("lead_time_note"):
                return False, f"missing lead-time note on {line.get('Component ID')}"
    return True, "ok"


def has_checkpoint(result_dict: dict[str, Any], cid: str) -> bool:
    return any(c["id"] == cid for c in result_dict["checkpoints"])
