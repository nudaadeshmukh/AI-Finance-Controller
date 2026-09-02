"""`record()` and `trail()` — §16, §20.4.

Append-only. Imported by everything; imports only `models` (§3.3) — audit
must never depend on any pipeline stage, so it can be called from all of them
without creating a cycle.

`record()` does not open its own transaction: it participates in whatever
transaction the caller already holds, so audit and effect are never
separable (§7.2).
"""

from __future__ import annotations

import json
import sqlite3
import time

from recon.audit.events import AuditEvent
from recon.db.queries import INSERT_AUDIT_LOG, SELECT_AUDIT_TRAIL
from recon.models.types import RecordKey


def record(
    db: sqlite3.Connection,
    stage: str,
    record_key: RecordKey | None,
    action: str,
    detail: dict,
) -> None:
    """§20.4. Append one row to `audit_log`."""
    db.execute(
        INSERT_AUDIT_LOG,
        {
            "ts": int(time.time()),
            "stage": stage,
            "record_key": record_key,
            "action": action,
            "detail_json": json.dumps(detail, sort_keys=True),
        },
    )


def trail(db: sqlite3.Connection, record_key: RecordKey) -> list[AuditEvent]:
    """§20.4. The full audit history for one record, oldest first."""
    rows = db.execute(SELECT_AUDIT_TRAIL, {"record_key": record_key}).fetchall()
    return [
        AuditEvent(
            seq=row["seq"],
            ts=row["ts"],
            stage=row["stage"],
            record_key=row["record_key"],
            action=row["action"],
            detail=json.loads(row["detail_json"]),
        )
        for row in rows
    ]
