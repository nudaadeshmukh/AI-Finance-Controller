"""`AuditEvent` model — §16. Mirrors the `audit_log` table columns (§7)
exactly, since those columns are the only documented shape for an audit event.
"""

from __future__ import annotations

from pydantic import BaseModel

from recon.models.types import RecordKey


class AuditEvent(BaseModel):
    seq: int
    ts: int
    stage: str
    record_key: RecordKey | None
    action: str
    detail: dict
