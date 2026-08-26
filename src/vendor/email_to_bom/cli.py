"""CLI: read an RFQ email from a file or stdin, emit a draft BOM as JSON + a readable table.

Exit codes: 0 = clean BOM drafted; 1 = input/config error; 2 = draft produced but open
questions/checkpoints block a clean draft (a human must answer before P21 entry).
Checkpoint actions (QC sign-off, length confirm, quote send) are NOT available here — they are
harness-held (RA1 containment).
"""
from __future__ import annotations

import argparse
import json
import sys

from .core import Agent, load_config
from .mail import extract_rfq_text


def _render_table(res_dict: dict) -> str:
    cols = res_dict["bom_columns"]
    rows = [cols] + [[str(l.get(c, "")) for c in cols] for l in res_dict["lines"]]
    w = [max(len(r[i]) for r in rows) for i in range(len(cols))]
    out = []
    for r in rows:
        out.append(" | ".join(r[i].ljust(w[i]) for i in range(len(cols))))
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="McGill email -> BOM agent (draft only)")
    p.add_argument("email", nargs="?", help="path to RFQ .txt/.eml; omit to read stdin")
    p.add_argument("--component-ids", nargs="*", default=[],
                   help="operator-supplied/confirmed Component IDs to match against the catalog")
    p.add_argument("--coc", action="store_true", help="customer requires a Certificate of Conformance")
    p.add_argument("--json", action="store_true", help="emit JSON only")
    p.add_argument("--config-dir", default=None,
                   help="alternate config directory (rules.json, catalog.json, citations.json), "
                        "e.g. one backed by the P21 item master")
    args = p.parse_args(argv)

    try:
        if args.email:
            with open(args.email, "rb") as fh:
                raw = fh.read()
        else:
            raw = sys.stdin.buffer.read()
    except OSError as e:
        print(f"error: cannot read RFQ input: {e}", file=sys.stderr)
        return 1

    try:
        cfg = load_config(args.config_dir) if args.config_dir else None
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: cannot load config from {args.config_dir}: {e}", file=sys.stderr)
        return 1

    text = extract_rfq_text(raw, filename=args.email)
    res = Agent(cfg).build(text, component_ids=args.component_ids, coc_requested=args.coc)
    d = res.to_dict()

    if args.json:
        print(json.dumps(d, indent=2))
    else:
        print("DRAFT BILL OF MATERIALS (not entered in P21 — operator commits)\n")
        print(_render_table(d))
        if d["notes"]:
            print("\nNotes:")
            for n in d["notes"]:
                print(f"  - {n}")
        if d["classes"]:
            print("\nClasses:", ", ".join(d["classes"]))
        if d["checkpoints"]:
            print("\nCheckpoints (harness-held, require a human):")
            for c in d["checkpoints"]:
                print(f"  - {c['id']} [{c['status']}] owner={c['owner']} ({c['rule_id']})")
        if d["questions"]:
            print("\nQuestions for the operator:")
            for q in d["questions"]:
                print(f"  - {q['text']} ({q['rule_id']})")
        if d["logged_attempts"]:
            print("\nLogged out-of-class attempts:")
            for a in d["logged_attempts"]:
                print(f"  - {a}")
        if d["open_items"]:
            print(f"\nCase state: class={d['request_class']}"
                  + (" URGENT" if d["urgency"]["flagged"] else ""))
            print("Open items (for the conversation layer):")
            for it in d["open_items"]:
                print(f"  - [{it['code']}] {it.get('ask', it.get('quote', ''))}")

    return 2 if (d["questions"] or d["checkpoints"] or d["open_items"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
