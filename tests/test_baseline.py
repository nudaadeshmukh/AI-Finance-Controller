"""Phase 5 — `report/baseline.py`. The naive matcher (§8.3): exact order_id
join AND stated fee AND exact UTR AND settlement net closes, no derivation.
"""

from __future__ import annotations

import sqlite3

from recon.ingest import ingest
from recon.report.baseline import compute_baseline
from tests.conftest import MockAdapter


def _order(oid: str, amount: int) -> dict:
    return {
        "order_id": oid,
        "receipt": f"RCPT-{oid}",
        "customer_id": "cust_baseline000001",
        "amount": amount,
        "currency": "INR",
        "status": "paid",
        "created_at": 1_780_000_000,
        "notes": {},
    }


def _payment(eid: str, oid: str, utr: str, amount: int, fee: int | None, tax: int | None) -> dict:
    return {
        "entity_id": eid,
        "type": "payment",
        "debit": 0,
        "credit": amount - (fee or 0) - (tax or 0),
        "amount": amount,
        "currency": "INR",
        "fee": fee,
        "tax": tax,
        "on_hold": False,
        "settled": True,
        "created_at": 1_780_000_000,
        "settled_at": 1_780_100_000,
        "settlement_id": f"setl_{utr}",
        "settlement_utr": utr,
        "order_id": oid,
        "order_receipt": f"RCPT-{oid}",
        "method": "card",
        "description": "Card payment",
    }


def _bank(utr: str, credit: int) -> dict:
    return {
        "txn_id": f"TXN_{utr}",
        "value_date": "2026-08-01",
        "description": f"RTGS CR RAZORPAYSOFTWARE {utr} SETTLEMENT",
        "credit": credit,
        "debit": 0,
        "balance": 10_000_000,
    }


def test_naive_counts_a_clean_stated_fee_settlement(db: sqlite3.Connection) -> None:
    a = _order("order_baseline00001", 100000)
    b = _order("order_baseline00002", 50000)
    pa = _payment("pay_baseline0001", a["order_id"], "111111111111", 100000, 1800, 324)
    pb = _payment("pay_baseline0002", b["order_id"], "111111111111", 50000, 900, 162)
    net = (100000 - 1800 - 324) + (50000 - 900 - 162)
    ingest(
        MockAdapter(orders=[a, b], recon_lines=[pa, pb], bank_txns=[_bank("111111111111", net)]),
        db,
    )

    result = compute_baseline(db)
    assert result.matched == 2
    assert result.name == "exact_id_and_amount"


def test_naive_skips_a_fee_null_settlement(db: sqlite3.Connection) -> None:
    a = _order("order_baseline00003", 100000)
    pa = _payment("pay_baseline0003", a["order_id"], "222222222222", 100000, None, None)
    ingest(MockAdapter(orders=[a], recon_lines=[pa], bank_txns=[_bank("222222222222", 98000)]), db)

    assert compute_baseline(db).matched == 0  # recovering the rate is not "naive"


def test_naive_skips_when_settlement_net_does_not_close(db: sqlite3.Connection) -> None:
    a = _order("order_baseline00004", 100000)
    pa = _payment("pay_baseline0004", a["order_id"], "333333333333", 100000, 1800, 324)
    ingest(
        MockAdapter(orders=[a], recon_lines=[pa], bank_txns=[_bank("333333333333", 90000)]),
        db,
    )
    assert compute_baseline(db).matched == 0
