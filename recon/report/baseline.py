"""`compute_baseline()` — the naive matcher, for comparison only (§8.3, §17.2).

Naive matcher = exact `order_id` join **and** stated fee **and** exact UTR
**and** settlement net closes with **no derivation**. It is deliberately
independent of `match/` — it re-extracts the UTR from the bank description
with a plain digit-run regex (never the cascade's truncation-tolerant
`utr_index`), and never touches `facts.fee_slabs`: a settlement with even one
`fee IS NULL` payment line is simply skipped, because recovering that rate is
exactly the work the naive baseline is defined to *not* do.

The number this produces is the floor the cascade must clear to justify its
existence (§8.3: 55–78 pp of headroom below the resolvable ceiling).
"""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict

from pydantic import BaseModel

from recon.db import queries

_UTR_RE = re.compile(r"\d{10,22}")


class BaselineResult(BaseModel):
    """Return type of `compute_baseline()` — fields match §18's `baseline`
    object exactly (`{"name": "exact_id_and_amount", "matched": 0,
    "match_rate": 0.0}`). `extra="forbid"` so a typo'd field fails loudly.
    """

    model_config = {"extra": "forbid"}

    name: str = "exact_id_and_amount"
    matched: int = 0
    match_rate: float = 0.0


def compute_baseline(db: sqlite3.Connection) -> BaselineResult:
    """§20.4. Count recon lines a naive exact-only matcher would resolve."""
    recon_by_utr: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in db.execute(queries.SELECT_ALL_RECON_LINES_FULL):
        if row["settlement_utr"]:
            recon_by_utr[row["settlement_utr"]].append(row)

    # Exact UTR: a single unambiguous digit run in the bank description that
    # equals the settlement UTR verbatim.
    bank_by_utr: dict[str, list[int]] = defaultdict(list)
    for row in db.execute(queries.SELECT_ALL_BANK_TXNS_FULL):
        if row["credit"] <= 0:
            continue
        found = _UTR_RE.search(row["description"] or "")
        if found:
            bank_by_utr[found.group(0)].append(row["credit"])

    orders_amount: dict[str, int] = {
        row["order_id"]: row["amount"] for row in db.execute(queries.SELECT_ALL_ORDERS)
    }

    matched = 0
    for utr, lines in recon_by_utr.items():
        credits = bank_by_utr.get(utr, [])
        if len(credits) != 1:
            continue  # no exact bank match, or ambiguous — naive gives up
        payments = [line for line in lines if line["type"] == "payment"]
        others = [line for line in lines if line["type"] != "payment"]

        # Stated fee only — no derivation.
        if any(line["fee"] is None or line["tax"] is None for line in payments):
            continue
        # Exact order_id join — every payment resolves to a known order.
        order_ids = {line["order_id"] for line in payments}
        if None in order_ids or not order_ids <= orders_amount.keys():
            continue

        gross = sum(orders_amount[oid] for oid in order_ids)
        fees = sum(line["fee"] for line in payments)
        tax = sum(line["tax"] for line in payments)
        refunds = sum(line["debit"] for line in others)
        if gross - fees - tax - refunds != credits[0]:
            continue  # settlement net does not close exactly

        matched += len(lines)

    return BaselineResult(
        name="exact_id_and_amount",
        matched=matched,
        match_rate=round(matched / 400, 4),
    )
