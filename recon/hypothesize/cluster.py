"""`cluster_residual()` — §15.3, §20.4.

Clustering key: residual records sharing a `settlement_utr` form one cluster;
records with no usable UTR cluster by `(customer_id, calendar date)`.
Implemented in Phase 6.
"""

from __future__ import annotations

import sqlite3

from recon.models.types import RecordKey


def cluster_residual(residual: list[RecordKey], db: sqlite3.Connection) -> list[list[RecordKey]]:
    """§20.4. Implemented in Phase 6."""
    raise NotImplementedError
