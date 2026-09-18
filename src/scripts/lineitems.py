#!/usr/bin/env python3
"""Is this document ONE request, or a list of many? (Phase 1)

The engine is built on an assumption no fixture ever tested: one text describes
one request. Give it a twenty-line purchase order and it does not refuse — it
builds a SINGLE specification by taking pieces from different products.
Job `af54e714`, 2026-09-18, on a real customer PO:

    size      3/4 ID    <- from the HOSE line
    pressure  300 psi   <- from the HOSE line
    length    1         <- from `BARB FITTING, 1" MNPT` -- a THREAD SIZE
    end_1/2   barb      <- from the barb fittings

`class_evidence` was the single word `hose`. The kit then asked the customer to
confirm the quantity and length convention of that assembly, for an order whose
every line already carried a part number, a quantity and a price.

**The specification it described exists in no document.** That is worse than an
incomplete case, and it is what this module exists to catch: not to fix the
merge -- fixing it is per-line-item extraction, upstream, and a project -- but to
stop the kit stating the merged spec as though it described something real.

This reads STRUCTURE, never content. It extracts no value, changes no field and
touches no open item; it counts shapes in the text so the renderers can qualify
what the engine produced. Same category as `attachments.scan`: a fact about the
document, not a second source of case data.

TWO OBSERVATIONS, because one was not enough, and the numbers below are measured
rather than assumed:

  * **line-item rows** -- a row ending in a quantity and two money columns. On the
    real PO: 7 of 7. On all seven parity fixtures, on an RFQ that quotes two
    prices in prose, and on an enumerated multi-item request: 0. Precise, and
    blind to any list that is not a table.
  * **distinct dimensions** -- a single assembly names one or two; a catalogue
    order names many. Measured: fixtures 1-2, a legitimate hose-plus-reducer 3,
    the PO 5, a prose list of three different hoses 5. This is what catches the
    multi-item request that carries no table.

Their thresholds differ because their precision differs, and both numbers were
measured rather than chosen:

  * ROW_MIN is 3 because a SUBTOTAL LINE matches the item pattern. A one-item
    reorder scores 1; the same reorder with a `Subtotal ... 243.00 243.00` line
    scores 2. Firing at 2 would flag a single-item purchase order.
  * DIM_MIN is 5 because a legitimate hose-plus-reducer honestly names 3, and a
    complex single assembly can name 4. Fixtures score 1-2; the PO and a prose
    list of three hoses both score 5.

SECOND KNOWN GAP, from the same measurement: a genuine TWO-item order scores 2
rows and often only 2 dimensions, so it is not flagged. Two rows is ambiguous —
it is either two products or one product and its total — and this module would
rather miss that case than fire on every single-item PO. A banner reviewers learn
to skip catches nothing at all.

KNOWN GAP, stated rather than hidden: a multi-item request written as prose with
few dimensions ("please quote the hose, the fittings and the clamps") is not
detected by either. Neither observation claims to find every one; each says what
it counted.
"""
from __future__ import annotations

import os
import re
import sys

_VENDOR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

from email_to_bom.mail import extract_rfq_text  # noqa: E402

# A line-item row: ... <qty> <price> <amount>. Anchored at end of line, requires
# the two-decimal money columns every priced table has.
_ROW = re.compile(r"\s(\d{1,5})\s+(\d[\d,]*\.\d{2})\s+(\d[\d,]*\.\d{2})\s*$")

# A dimension: 3/4", 1-1/2 in, 36in, 25mm. The negative lookbehind keeps it off
# part numbers and decimals. NOTE the absence of \b before `in`: there is no word
# boundary between a digit and a letter, so `\bin\b` never matches "36in" -- the
# first cut of this scored 0 on every fixture for that reason, which would have
# made the threshold meaningless while looking like a clean separation.
_DIM = re.compile(r'(?<![\w/.-])(\d{1,3}(?:-\d+/\d+)?|\d+/\d+)\s*(?:"|in\b|inch\b|mm\b)',
                  re.I)

ROW_MIN = 3
DIM_MIN = 5


def scan(text):
    """Count the shapes that mean 'more than one product'. Never raises."""
    text = text or ""
    rows = [l.strip() for l in text.splitlines() if _ROW.search(l)]
    dimensions = sorted({m.group(1) for m in _DIM.finditer(text)})
    grounds = []
    if len(rows) >= ROW_MIN:
        grounds.append(f"{len(rows)} rows carry a quantity and two money columns, "
                       "which is a line-item table")
    if len(dimensions) >= DIM_MIN:
        grounds.append(f"{len(dimensions)} different dimensions are named "
                       f"({', '.join(dimensions)}), which is more than one "
                       "assembly has")
    return {"rows": rows,
            "row_count": len(rows),
            "dimensions": dimensions,
            "dimension_count": len(dimensions),
            "multi_item": bool(grounds),
            "grounds": grounds}


def scan_file(path):
    """Scan the text the ENGINE read, through the engine's own reader.

    The whole case text, transcript included: a purchase order usually arrives as
    an attachment, so scanning only the customer's typed body would miss every
    document this module exists for.
    """
    try:
        with open(path, "rb") as fh:
            return scan(extract_rfq_text(fh.read(), filename=path))
    except OSError:
        return scan("")
