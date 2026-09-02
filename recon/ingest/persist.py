"""Idempotent upserts — `INSERT ... ON CONFLICT(record_key) DO UPDATE` — §12.2.

One function per source table, plus `persist_exception` for `ingest/`'s own
`MALFORMED_SOURCE_ROW` writes. Re-running never double-counts (§4.8): every
statement here upserts on `record_key`.

`read_*` functions are the inverse: re-hydrate one source row back into its
pydantic model, given a `record_key`. They live here, symmetric with the
`upsert_*` writers, because this is the one place that already knows the
row<->model mapping (e.g. `notes_json` <-> `Order.notes`). `verify/` reads
these — an allowed forward import per §3.3's dependency chain
(`ingest ← match ← verify`, i.e. verify may depend on ingest).
"""

from __future__ import annotations

import json
import sqlite3
import time

from recon.db import queries
from recon.models.pipeline import Exception_
from recon.models.sources import BankTxn, LedgerEntry, Order, ReconLine
from recon.models.types import RecordKey


def upsert_order(db: sqlite3.Connection, order: Order) -> None:
    db.execute(
        queries.UPSERT_ORDER,
        {
            "record_key": f"order:{order.order_id}",
            "order_id": order.order_id,
            "receipt": order.receipt,
            "customer_id": order.customer_id,
            "amount": order.amount,
            "currency": order.currency,
            "status": order.status,
            "created_at": order.created_at,
            "notes_json": json.dumps(order.notes, sort_keys=True),
        },
    )


def upsert_recon_line(db: sqlite3.Connection, line: ReconLine) -> None:
    db.execute(
        queries.UPSERT_RECON_LINE,
        {
            "record_key": f"recon:{line.entity_id}",
            "entity_id": line.entity_id,
            "type": line.type,
            "debit": line.debit,
            "credit": line.credit,
            "amount": line.amount,
            "fee": line.fee,
            "tax": line.tax,
            "on_hold": int(line.on_hold),
            "settled": int(line.settled),
            "created_at": line.created_at,
            "settled_at": line.settled_at,
            "settlement_id": line.settlement_id,
            "settlement_utr": line.settlement_utr,
            "order_id": line.order_id,
            "order_receipt": line.order_receipt,
            "method": line.method,
            "description": line.description,
        },
    )


def upsert_bank_txn(db: sqlite3.Connection, txn: BankTxn) -> None:
    db.execute(
        queries.UPSERT_BANK_TXN,
        {
            "record_key": f"bank:{txn.txn_id}",
            "txn_id": txn.txn_id,
            "value_date": txn.value_date,
            "description": txn.description,
            "credit": txn.credit,
            "debit": txn.debit,
            "balance": txn.balance,
            "utr_extracted": txn.utr_extracted,
        },
    )


def upsert_ledger_entry(db: sqlite3.Connection, entry: LedgerEntry) -> None:
    db.execute(
        queries.UPSERT_LEDGER_ENTRY,
        {
            "record_key": f"ledger:{entry.entry_id}",
            "entry_id": entry.entry_id,
            "entry_date": entry.entry_date,
            "account": entry.account,
            "debit": entry.debit,
            "credit": entry.credit,
            "narration": entry.narration,
            "source_ref": entry.source_ref,
        },
    )


def persist_exception(db: sqlite3.Connection, exc: Exception_) -> None:
    db.execute(
        queries.UPSERT_EXCEPTION,
        {
            "record_key": exc.record_key,
            "reason_code": exc.reason_code.value,
            "reason_text": exc.reason_text,
            "passes_tried": json.dumps(exc.passes_tried),
            "candidates": json.dumps(exc.candidates),
            "created_at": int(time.time()),
        },
    )


def read_order(db: sqlite3.Connection, record_key: RecordKey) -> Order | None:
    row = db.execute(queries.SELECT_ORDER_BY_KEY, {"record_key": record_key}).fetchone()
    if row is None:
        return None
    return Order(
        order_id=row["order_id"],
        receipt=row["receipt"],
        customer_id=row["customer_id"],
        amount=row["amount"],
        currency=row["currency"],
        status=row["status"],
        created_at=row["created_at"],
        notes=json.loads(row["notes_json"]) if row["notes_json"] else {},
    )


def read_recon_line(db: sqlite3.Connection, record_key: RecordKey) -> ReconLine | None:
    row = db.execute(queries.SELECT_RECON_LINE_BY_KEY, {"record_key": record_key}).fetchone()
    if row is None:
        return None
    return ReconLine(
        entity_id=row["entity_id"],
        type=row["type"],
        debit=row["debit"],
        credit=row["credit"],
        amount=row["amount"],
        currency="INR",  # no currency column on recon_lines (§7) - model only allows "INR"
        fee=row["fee"],
        tax=row["tax"],
        on_hold=bool(row["on_hold"]),
        settled=bool(row["settled"]),
        created_at=row["created_at"],
        settled_at=row["settled_at"],
        settlement_id=row["settlement_id"],
        settlement_utr=row["settlement_utr"],
        order_id=row["order_id"],
        order_receipt=row["order_receipt"],
        method=row["method"],
        description=row["description"],
    )


def read_bank_txn(db: sqlite3.Connection, record_key: RecordKey) -> BankTxn | None:
    row = db.execute(queries.SELECT_BANK_TXN_BY_KEY, {"record_key": record_key}).fetchone()
    if row is None:
        return None
    return BankTxn(
        txn_id=row["txn_id"],
        value_date=row["value_date"],
        description=row["description"],
        credit=row["credit"],
        debit=row["debit"],
        balance=row["balance"],
        utr_extracted=row["utr_extracted"],
    )


def read_ledger_entry(db: sqlite3.Connection, record_key: RecordKey) -> LedgerEntry | None:
    row = db.execute(queries.SELECT_LEDGER_ENTRY_BY_KEY, {"record_key": record_key}).fetchone()
    if row is None:
        return None
    return LedgerEntry(
        entry_id=row["entry_id"],
        entry_date=row["entry_date"],
        account=row["account"],
        debit=row["debit"],
        credit=row["credit"],
        narration=row["narration"],
        source_ref=row["source_ref"],
    )
