#!/usr/bin/env python3
"""Turn the engine's role and owner KEYS into something Body can message.

`routing.recommendation` is one of three roles, `open_items[].route` one of four,
and `checkpoints[].owner` is free text the engine writes ("QC Department", "Sales
+ Production Manager + Quality Team", "Inside Sales"). None of those is an
address. Body cannot send a Teams message to `inside_sales`.

So this reads `config/routing.json` and resolves a key to an addressee. Two rules
decide everything here, and both point the same way:

  * **Consulted, never invented.** If the table has no entry for a key, or the
    entry has no address, the result says NOT ROUTABLE and names the key. It does
    not fall back to inside sales. A wrong assignee is worse than a visible gap:
    the case lands with someone who ignores it, and nobody learns it was
    misrouted. A gap gets fixed the first time someone reads it.
  * **The two failures are distinguished.** `unmapped` means the table has never
    heard of this key -- which, for the two schema enums, means the ENGINE grew a
    value the kit does not know about, and that is worth seeing. `unconfigured`
    means the key is known and nobody has filled in the address yet. Collapsing
    them would hide an engine change inside a deployment TODO.

The kit stays offline. It resolves a key to a display name and an address string
and stops; Body does the delivering.
"""
from __future__ import annotations

import json
import os

CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "config", "routing.json")

# Resolution states. `routable` is the only one Body may act on.
ROUTABLE = "routable"
UNCONFIGURED = "unconfigured"
UNMAPPED = "unmapped"
NO_TABLE = "no_table"


def load(path=None):
    """Load the routing table. Returns (addressees, error).

    A missing or malformed table is an error, not an empty table: "nobody is
    configured" and "we could not read who is configured" must not resolve the
    same way. Both leave every key unroutable, but only one of them says the file
    is the problem.
    """
    path = path or CONFIG
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        return None, f"cannot read {path}: {e}"
    addressees = data.get("addressees")
    if not isinstance(addressees, dict):
        return None, f"{path} has no 'addressees' object"
    return addressees, None


def resolve(key, addressees, table_error=None):
    """Resolve one key. Always returns a record; never raises, never guesses."""
    key = "" if key is None else str(key)
    if addressees is None:
        return {"key": key, "status": NO_TABLE, "display": None,
                "channel": None, "address": None, "detail": table_error}
    entry = addressees.get(key)
    if not isinstance(entry, dict):
        return {"key": key, "status": UNMAPPED, "display": None,
                "channel": None, "address": None,
                "detail": "no entry in config/routing.json — if this is a role "
                          "the engine emits, the table is out of date"}
    address = entry.get("address") or None
    return {"key": key,
            "display": entry.get("display") or key,
            "channel": entry.get("channel") or None,
            "address": address,
            "status": ROUTABLE if address else UNCONFIGURED,
            "detail": None if address else
                      "known role, but no address is configured for it yet"}


def describe(record):
    """One inert line for a resolution. The caller passes it through _safe()."""
    if record["status"] == ROUTABLE:
        channel = f"{record['channel']}: " if record.get("channel") else ""
        return f"{record['display']} ({channel}{record['address']})"
    label = {UNCONFIGURED: "NOT ROUTABLE — no address configured",
             UNMAPPED: "NOT ROUTABLE — key unknown to the routing table",
             NO_TABLE: "NOT ROUTABLE — the routing table could not be read"}
    return (f"{record.get('display') or record['key']} — {label[record['status']]}"
            f" [{record['key']}]")


def keys_in(case):
    """Every owner key a CaseState names, in the order a reader meets them.

    Derived from the record rather than from a list of places to look: a new
    site that carries a route is picked up by whichever of these branches holds
    it, and `open_items` is walked whole rather than filtered to the codes that
    are known to carry a `route` today.
    """
    out = []

    def add(kind, key):
        if key and (kind, str(key)) not in out:
            out.append((kind, str(key)))

    case = case or {}
    add("recommended", (case.get("routing") or {}).get("recommendation"))
    for item in case.get("open_items") or []:
        add("open item", (item or {}).get("route"))
    for cp in case.get("checkpoints") or []:
        add("checkpoint", (cp or {}).get("owner"))
    return out
