"""`cluster_residual()` — §15.3, §20.4.

One LLM call is made per cluster, not per record, so cost and latency scale
with ambiguity rather than record count (§15.3).

Clustering key, in order of preference:
  1. a shared `settlement_utr`
  2. otherwise `(customer_id, calendar date)` of the record's order
  3. otherwise the record stands alone (`(record_key,)`) — an adjustment with
     no order and no UTR has nothing to cluster on

Deterministic: clusters and their members come back in sorted order, so a
re-run produces byte-identical prompts.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from recon.db import queries
from recon.models.types import RecordKey


def _order_key_for(row: sqlite3.Row) -> tuple[str, ...] | None:
    order_id = row["order_id"]
    if order_id is None:
        return None
    return ("order", order_id)


def cluster_residual(
    residual: list[RecordKey], db: sqlite3.Connection
) -> list[list[RecordKey]]:
    """§20.4. Partition the residual into LLM-call-sized clusters."""
    buckets: dict[tuple, list[RecordKey]] = {}

    for record_key in residual:
        row = db.execute(
            queries.SELECT_RECON_LINE_BY_KEY, {"record_key": record_key}
        ).fetchone()
        if row is None:
            buckets.setdefault(("solo", record_key), []).append(record_key)
            continue

        utr = row["settlement_utr"]
        if utr:
            key: tuple = ("utr", utr)
        elif row["order_id"] is not None:
            order = db.execute(
                queries.SELECT_ORDER_BY_KEY, {"record_key": f"order:{row['order_id']}"}
            ).fetchone()
            if order is not None:
                day = datetime.fromtimestamp(order["created_at"], tz=UTC).date().isoformat()
                key = ("cust", order["customer_id"], day)
            else:
                key = ("solo", record_key)
        else:
            key = ("solo", record_key)

        buckets.setdefault(key, []).append(record_key)

    return [sorted(members) for _, members in sorted(buckets.items())]
