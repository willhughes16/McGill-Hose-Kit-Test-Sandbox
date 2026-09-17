"""Knowledge sources: the engine's ONE interface to external facts.

Design (see docs/DESIGN_DECISIONS.md DD-3):

* **Facts come from here; rules never do.** Vocabulary that governs a safety
  checkpoint stays in `config/rules.json`, reviewed by a human. This module only
  supplies facts about the world: which components exist, their ratings, customer
  context.
* **Everything is tiered.** `verified` facts may reach a BOM line; `candidate`
  facts may only ever become proposals carrying a citation, which an operator
  confirms. Default-deny: anything not explicitly `verified` is a candidate.
* **Failure degrades, never silences.** Timeout, HTTP error, malformed record,
  empty result — all return "nothing found", and the engine's existing asks fire.
  The engine must be better with a knowledge source and still correct without one.
* **Every lookup is logged** (op, argument, outcome, tier, citation, elapsed ms)
  so a CaseState stays explainable after the graph has moved on.

Implementations: `NullKnowledge` (default — the engine behaves exactly as it does
offline), `FixtureKnowledge` (a pinned snapshot; used by the suite), `McpKnowledge`
(live TWYD graph over MCP's structured primitives — plain JSON-RPC, no LLM in the
loop). A future `ProjectionKnowledge` reading a typed REST projection is a drop-in
third implementation: nothing outside this file changes.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

VERIFIED = "verified"
CANDIDATE = "candidate"


@dataclass(frozen=True)
class ComponentFact:
    """A component the engine may reference. `tier` decides what it may become."""
    id: str
    description: str = ""
    component_type: str = ""
    uom: str = ""
    tier: str = CANDIDATE
    citation: str = ""
    ratings: dict[str, Any] | None = None
    # When the SOURCE last verified this fact, in the source's own words. Empty
    # means the source did not say -- which is not the same as "now", and is never
    # treated as such. See `_Logged._freshness`.
    as_of: str = ""

    @property
    def groundable(self) -> bool:
        """True only for verified facts — the ONLY ones allowed on a BOM line."""
        return self.tier == VERIFIED


def _clean(record: Any) -> ComponentFact | None:
    """Accept a record only if it has a usable id; default-deny the tier.
    Malformed input returns None instead of raising (fail-safe degradation)."""
    if not isinstance(record, dict):
        return None
    cid = record.get("id") or record.get("name")
    if not isinstance(cid, str) or not cid.strip():
        return None
    tier = record.get("tier")
    ratings = record.get("ratings")
    return ComponentFact(
        id=cid.strip(),
        description=str(record.get("description") or "")[:200],
        component_type=str(record.get("component_type") or ""),
        uom=str(record.get("uom") or ""),
        tier=VERIFIED if tier == VERIFIED else CANDIDATE,
        citation=str(record.get("citation") or ""),
        ratings=ratings if isinstance(ratings, dict) else None,
        as_of=str(record.get("as_of") or "")[:64],
    )


_CTRL = re.compile(r"[\x00-\x1f\x7f]")


def _plain(value: str, limit: int = 120) -> str:
    """Strip control characters and cap length. No query escaping is needed:
    values travel as JSON arguments to structured tools, never concatenated into
    a query (DD-3 / the injection fix)."""
    return _CTRL.sub(" ", str(value))[:limit].strip()


class _Logged:
    """Shared lookup log: every call recorded, successes and failures alike."""

    def __init__(self) -> None:
        self._log: list[dict[str, Any]] = []
        self.revision: str | None = None

    def _freshness(self, as_of: str = "") -> str:
        """How old the fact behind a lookup is, in the source's own terms.

        Three forms, and the order is the point:

          ``as_of:<value>``    the source stated when the fact was true. The only
                               form that says anything about THIS fact.
          ``revision:<value>`` no per-fact statement, but the source is pinned, so
                               the fact is at most as fresh as the snapshot.
          ``unknown``          nothing was said. DEFAULT-DENY, exactly as the tier
                               is: a fact whose age nobody stated is not fresh, it
                               is unknown, and a consumer that needs freshness must
                               treat it as stale.

        Deliberately NO wall clock. Recording "we asked at 14:02" would make the
        engine's output non-deterministic and break byte parity for every consumer
        that pins it, and it answers a different question anyway -- when we asked,
        not how old the answer is. The run's own timestamp already exists outside
        the engine; the age of the FACT can only come from the source.
        """
        if as_of:
            return f"as_of:{as_of}"
        if self.revision:
            return f"revision:{self.revision}"
        return "unknown"

    def _record(self, op: str, arg: Any, outcome: str, as_of: str = "",
                **extra: Any) -> None:
        entry = {"op": op, "arg": str(arg)[:80], "outcome": outcome,
                 "freshness": self._freshness(as_of)}
        entry.update(extra)
        self._log.append(entry)

    def log(self) -> list[dict[str, Any]]:
        return list(self._log)


class NullKnowledge(_Logged):
    """The default. No external facts; the engine asks for everything it needs."""

    name = "none"

    def resolve_component(self, component_id: str) -> ComponentFact | None:
        return None

    def find_candidates(self, spec: dict[str, Any]) -> list[ComponentFact]:
        return []

    def ratings_for(self, component_id: str) -> dict[str, Any] | None:
        return None

    def customer_context(self, name: str) -> dict[str, Any] | None:
        return None


class FixtureKnowledge(_Logged):
    """A pinned snapshot loaded from JSON — deterministic, used by the suite and
    usable in production as a frozen projection of the graph."""

    name = "fixture"

    def __init__(self, data: dict[str, Any] | str):
        super().__init__()
        if isinstance(data, str):
            with open(data, encoding="utf-8") as fh:
                data = json.load(fh)
        raw = data if isinstance(data, dict) else {}
        # Normalize ONCE at construction: a present-but-null key ("components": null)
        # used to reach .get(...) defaults and raise TypeError out of build() —
        # round 20's hardening had gone into McpKnowledge only (round 23 driver 2).
        self.data = {
            "revision": raw.get("revision"),
            "components": [r for r in (raw.get("components") or []) if isinstance(r, dict)]
            if isinstance(raw.get("components") or [], list) else [],
            "customers": [r for r in (raw.get("customers") or []) if isinstance(r, dict)]
            if isinstance(raw.get("customers") or [], list) else [],
        }
        self.revision = str(self.data.get("revision") or "") or None

    def resolve_component(self, component_id: str) -> ComponentFact | None:
        key = component_id.strip().upper()
        for rec in self.data.get("components", []):
            fact = _clean(rec)
            if fact and fact.id.upper() == key:
                self._record("resolve_component", component_id, "hit",
                             as_of=fact.as_of,
                             tier=fact.tier, citation=fact.citation)
                return fact
        self._record("resolve_component", component_id, "miss")
        return None

    def find_candidates(self, spec: dict[str, Any]) -> list[ComponentFact]:
        media = (spec.get("media") or "").lower()
        out = []
        for rec in self.data.get("components", []):
            fact = _clean(rec)
            if not fact:
                continue
            hay = f"{fact.id} {fact.description}".lower()
            if not media or media in hay:
                out.append(fact)
        # An as_of is claimed only when EVERY returned fact agrees on one.
        # A mixed result has no single age, and picking the newest would report
        # the batch as fresher than its oldest member -- the direction that gets a
        # stale rating onto a proposal. Disagreement falls back to the revision.
        ages = {f.as_of for f in out}
        self._record("find_candidates", spec, "hit" if out else "miss",
                     as_of=ages.pop() if len(ages) == 1 else "",
                     count=len(out))
        return out[:5]

    def ratings_for(self, component_id: str) -> dict[str, Any] | None:
        fact = self.resolve_component(component_id)
        return fact.ratings if fact else None

    def customer_context(self, name: str) -> dict[str, Any] | None:
        key = name.strip().lower()
        for rec in self.data.get("customers", []):
            if isinstance(rec, dict) and str(rec.get("name", "")).lower() == key:
                self._record("customer_context", name, "hit",
                             as_of=str(rec.get("as_of") or "")[:64],
                             citation=str(rec.get("citation") or ""))
                return rec
        self._record("customer_context", name, "miss")
        return None


class McpKnowledge(_Logged):
    """Live TWYD graph over MCP's structured primitives (JSON-RPC, no LLM).

    **No query string is ever assembled from input.** Every operation calls
    `twyd_get_entity` with the value as a JSON argument, so query structure is
    fixed by the server and injection is impossible by construction rather than
    filtered (V2 lesson: invert, don't sanitize). The only guard applied here is
    a length cap and a control-character strip.

    Every fact from the graph is `candidate` tier — without exception. The graph
    holds LLM-written entity summaries plus vendor decks, training slides and
    correspondence, so a hit means "this string appears in a document", not "this
    is a stocked SKU". `verified` becomes available only through a P21-sourced
    projection (DD-3); until then no graph fact can reach a BOM line, which keeps
    the anti-fabrication guard meaning what it says.
    """

    name = "mcp"

    def __init__(self, url: str, key: str = "", *, timeout: float = 8.0,
                 auth_header: str = "Authorization", auth_scheme: str = "Bearer",
                 transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None):
        super().__init__()
        self.url, self.key, self.timeout = url, key, timeout
        self.auth_header, self.auth_scheme = auth_header, auth_scheme
        self._transport = transport or self._http
        self._id = 0
        # honest provenance: live reads are not snapshot-pinned (DD-3). A pinned
        # revision arrives with the projection.
        self.revision = "live-unpinned"

    # ---- transport ----

    def _http(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream"}
        if self.key:
            headers[self.auth_header] = (f"{self.auth_scheme} {self.key}".strip()
                                         if self.auth_scheme else self.key)
        req = urllib.request.Request(self.url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
        for line in raw.splitlines():          # tolerate SSE framing
            line = line[5:].strip() if line.startswith("data:") else line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        return {}

    def _entity(self, name: str) -> dict[str, Any] | None:
        """One structured lookup. ANY failure yields None, never an exception."""
        clean = _plain(name)
        if not clean:
            return None
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                   "params": {"name": "twyd_get_entity",
                              "arguments": {"name": clean}}}   # value stays JSON
        # INVERTED (round 20): the contract is "any failure yields nothing found",
        # so this catches EVERYTHING rather than enumerating exception types. An
        # enumeration is a list of the failures someone thought of; the round-20
        # verifier crashed Agent.build() with a well-formed 200 whose content was
        # ["oops"] (AttributeError) and with a garbage status line
        # (http.client.BadStatusLine) — neither was in the tuple. The failure kind
        # is recorded in the log, never raised at the caller.
        try:
            data = self._transport(payload)
        except BaseException as exc:                      # noqa: BLE001 - by contract
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            self._record("query", clean, "error", error=type(exc).__name__)
            return None
        try:
            content = data["result"]["content"]
            if not isinstance(content, list):
                raise TypeError("content is not a list")
            text = next(c["text"] for c in content
                        if isinstance(c, dict) and c.get("type") == "text")
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                raise TypeError("tool result is not an object")
            rows = parsed.get("summary_rows") or []
            if not isinstance(rows, list):
                raise TypeError("summary_rows is not a list")
            return rows[0] if rows and isinstance(rows[0], dict) else None
        except BaseException as exc:                      # noqa: BLE001 - by contract
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            self._record("query", clean, "malformed", error=type(exc).__name__)
            return None

    # ---- operations ----

    def resolve_component(self, component_id: str) -> ComponentFact | None:
        t0 = time.monotonic()
        row = self._entity(component_id)
        ms = int((time.monotonic() - t0) * 1000)
        if not row:
            self._record("resolve_component", component_id, "miss", ms=ms)
            return None
        types = row.get("types") or []
        fact = ComponentFact(
            id=str(row.get("name") or component_id),
            description=str(row.get("description") or "")[:200],
            component_type=str(types[0]).title() if isinstance(types, list) and types else "",
            tier=CANDIDATE,          # graph facts are never verified (see docstring)
            citation=f"twyd:entity/{row.get('name')}",
            # The graph states this when it has it. A live fetch does NOT make a
            # fact current: the graph may be serving something ingested a year
            # ago, and "we asked just now" is not an answer to "how old is this".
            as_of=str(row.get("as_of") or "")[:64])
        self._record("resolve_component", component_id, "hit",
                     as_of=fact.as_of,
                     tier=fact.tier, citation=fact.citation, ms=ms)
        return fact

    def find_candidates(self, spec: dict[str, Any]) -> list[ComponentFact]:
        """Not supported against the graph, deliberately. Candidate DISCOVERY needs
        product-selection data the graph does not hold (G-1 waived, catalog not
        ingested); the semantic-retrieval tool returns prose, not SKUs — that path
        belongs to the conversation layer. A projection implements this (DD-3)."""
        self._record("find_candidates", spec, "skipped", reason="unsupported_by_graph")
        return []

    def ratings_for(self, component_id: str) -> dict[str, Any] | None:
        fact = self.resolve_component(component_id)
        if not fact or not fact.description:
            return None
        # Descriptions are LLM-written prose: surfaced as text for a human to read,
        # never parsed into numbers the engine would act on.
        return {"summary_text": fact.description, "tier": CANDIDATE,
                "citation": fact.citation}

    def customer_context(self, name: str) -> dict[str, Any] | None:
        row = self._entity(name)
        if not row or not row.get("description"):
            self._record("customer_context", name, "miss")
            return None
        ctx = {"name": str(row.get("name") or name),
               "summary_text": str(row.get("description"))[:300],
               "tier": CANDIDATE,
               "citation": f"twyd:entity/{row.get('name')}"}
        self._record("customer_context", name, "hit",
                     as_of=str(row.get("as_of") or "")[:64],
                     citation=ctx["citation"])
        return ctx


# ----------------------------- write-back (harness-held) -----------------------------

@dataclass(frozen=True)
class ConfirmedFact:
    """A fact a human has CONFIRMED, ready to become McGill knowledge.

    Provenance is mandatory: who confirmed it, when, and for which case. No clock
    is read here — the caller supplies `confirmed_at`, so the record says what the
    operator actually saw rather than when a job happened to run.
    """
    text: str
    confirmed_by: str
    confirmed_at: str
    case_ref: str
    supersedes: str = ""

    @staticmethod
    def _hdr(value: str) -> str:
        """Collapse whitespace and cap length; escaping is JSON's job below."""
        return re.sub(r"\s+", " ", _plain(value, 120)).strip()

    def document(self) -> dict[str, str]:
        """The `/api/ingestion/text` body.

        Provenance is emitted as ONE JSON object, not as `key: value` lines:
        JSON escaping makes field forgery structurally impossible, where
        sanitizing only removes the vectors someone thought of (round 20 — a
        newline in `confirmed_by` forged a second `case_ref`). Same inversion as
        the query path: let the format do the escaping.
        """
        provenance = {"confirmed_by": self._hdr(self.confirmed_by),
                      "confirmed_at": self._hdr(self.confirmed_at),
                      "case_ref": self._hdr(self.case_ref)}
        if self.supersedes:
            provenance["supersedes"] = self._hdr(self.supersedes)
        # filename by ALLOWLIST: a case_ref can never build a path
        slug = re.sub(r"[^A-Za-z0-9-]+", "-", self.case_ref)[:40].strip("-") or "case"
        return {"name": f"corello-confirmed-{slug}.txt",
                "content": ("[Confirmed McGill fact] "
                            + json.dumps(provenance, sort_keys=True)
                            + "\n\n" + self.text.strip() + "\n")}


class ApprovalRequired(RuntimeError):
    """Raised when a publish is attempted without explicit human approval."""


class TwydIngestion:
    """Publishes confirmed facts back into the graph via `/api/ingestion/text`.

    Harness-held by design (RA1 containment): the engine never imports or calls
    this — `Agent.build()` cannot write to the graph even by accident. The portal
    or the conversation layer calls `publish()` after a human approves, and must
    pass `approved=True` explicitly. Credentials never live here: a `token_provider`
    callable supplies the JWT, so no password touches this code.
    """

    def __init__(self, base_url: str, token_provider: Callable[[], str],
                 *, timeout: float = 15.0,
                 transport: Callable[[str, dict[str, Any], str], int] | None = None):
        self.base_url = base_url.rstrip("/")
        self._token = token_provider
        self.timeout = timeout
        self._transport = transport or self._post
        self.published: list[dict[str, str]] = []

    def _post(self, url: str, body: dict[str, Any], token: str) -> int:
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return int(resp.status)

    def publish(self, fact: ConfirmedFact, *, approved: bool = False) -> int:
        """Publish one confirmed fact. Refuses without explicit approval, without
        provenance, and without a token — an unapproved call is a programming
        error, not a silent no-op."""
        if approved is not True:      # identity, not truthiness: "false"/0/[] are
            raise ApprovalRequired(    # programming errors, never an approval
                "publish() requires approved=True — a human must confirm the fact "
                "before it becomes McGill knowledge")
        if not (fact.text.strip() and fact.confirmed_by.strip()
                and fact.confirmed_at.strip() and fact.case_ref.strip()):
            raise ValueError("a confirmed fact needs text, confirmed_by, "
                             "confirmed_at and case_ref")
        token = self._token()
        if not token:
            raise ApprovalRequired("no ingestion token available")
        doc = fact.document()
        status = self._transport(f"{self.base_url}/api/ingestion/text", doc, token)
        self.published.append(doc)
        return status
