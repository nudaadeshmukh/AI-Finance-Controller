"""Shared pytest fixtures — in-memory DB fixture per Phase 1's acceptance."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest

from recon.db.connection import apply_schema


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    """An in-memory SQLite connection with the full schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    apply_schema(conn)
    try:
        yield conn
    finally:
        conn.close()


def make_db() -> sqlite3.Connection:
    """A standalone in-memory DB, for tests that need more than one
    independent connection (e.g. determinism across two separate runs).
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    apply_schema(conn)
    return conn


class MockAdapter:
    """A `SourceAdapter` built from plain lists — no fixture files touched.
    Each `.orders()`/etc. call returns a fresh iterator so the adapter can be
    reused across multiple `ingest()` calls in idempotency tests.
    """

    def __init__(
        self,
        orders: list[dict] | None = None,
        recon_lines: list[dict] | None = None,
        bank_txns: list[dict] | None = None,
        ledger_entries: list[dict] | None = None,
    ) -> None:
        self._orders = orders or []
        self._recon_lines = recon_lines or []
        self._bank_txns = bank_txns or []
        self._ledger_entries = ledger_entries or []

    def orders(self) -> Iterator[dict]:
        return iter(self._orders)

    def recon_lines(self) -> Iterator[dict]:
        return iter(self._recon_lines)

    def bank_txns(self) -> Iterator[dict]:
        return iter(self._bank_txns)

    def ledger_entries(self) -> Iterator[dict]:
        return iter(self._ledger_entries)


@pytest.fixture
def one_valid_order() -> dict:
    return {
        "order_id": "order_test0000000001",
        "receipt": "RCPT-TEST-0001",
        "customer_id": "cust_test0000000001",
        "amount": 100000,
        "currency": "INR",
        "status": "paid",
        "created_at": 1_780_000_000,
        "notes": {},
    }
