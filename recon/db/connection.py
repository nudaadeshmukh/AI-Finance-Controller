"""SQLite connect/migrate/transaction helpers — §3.2, §7.

One SQLite file per run (§3.1). Stage coupling is via these tables, not
in-memory handoff, so any stage is re-runnable against persisted state.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from pathlib import Path

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open (creating if needed) the SQLite file at `db_path` and apply the
    schema. Foreign keys and WAL are enabled for safer concurrent reads during
    a single-process, single-threaded run.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    apply_schema(conn)
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    """Apply `schema.sql`. Every statement is `CREATE ... IF NOT EXISTS`, so
    this is safe to call against an existing database (idempotency, §4.8).
    """
    schema_sql = resources.files("recon.db").joinpath("schema.sql").read_text(encoding="utf-8")
    with conn:
        conn.executescript(schema_sql)


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """One transaction boundary. Commits on clean exit, rolls back on
    exception — used per source file at ingest, per pass in the cascade, and
    per cluster in the LLM stage (§7.2).
    """
    try:
        conn.execute("BEGIN")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
