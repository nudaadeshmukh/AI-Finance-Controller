"""Pass 3 — `aggregate` — §13.3.

Includes the C-005 regression: `aggregate` must never close a settlement
containing an ambiguous adjustment (§13.7's detection condition), even though
the closing equation balances without knowing which candidate order it
belongs to. Also includes the C-007 regression: `gross` must never
double-count an order referenced only by a refund line pointing at a
different, unrelated settlement.
"""

from __future__ import annotations

import json
import sqlite3

from recon.ingest import ingest
from recon.match import run_cascade
from tests.conftest import MockAdapter


def _order(order_id: str, amount: int, customer: str, created_at: int = 1_780_000_000) -> dict:
    return {
        "order_id": order_id,
        "receipt": f"RCPT-{order_id}",
        "customer_id": customer,
        "amount": amount,
        "currency": "INR",
        "status": "paid",
        "created_at": created_at,
        "notes": {},
    }


def _payment(entity_id: str, order_id: str, utr: str, amount: int, fee: int, tax: int) -> dict:
    return {
        "entity_id": entity_id,
        "type": "payment",
        "debit": 0,
        "credit": amount - fee - tax,
        "amount": amount,
        "currency": "INR",
        "fee": fee,
        "tax": tax,
        "on_hold": False,
        "settled": True,
        "created_at": 1_780_000_000,
        "settled_at": 1_780_100_000,
        "settlement_id": "setl_aggtestAAAAAAA",
        "settlement_utr": utr,
        "order_id": order_id,
        "order_receipt": f"RCPT-{order_id}",
        "method": "card",
        "description": "Card payment",
    }


def _adjustment(entity_id: str, utr: str, amount: int) -> dict:
    return {
        "entity_id": entity_id,
        "type": "adjustment",
        "debit": amount,
        "credit": 0,
        "amount": amount,
        "currency": "INR",
        "fee": None,
        "tax": None,
        "on_hold": False,
        "settled": True,
        "created_at": 1_780_000_000,
        "settled_at": 1_780_100_000,
        "settlement_id": "setl_aggtestAAAAAAA",
        "settlement_utr": utr,
        "order_id": None,  # by construction — §6.2
        "order_receipt": None,
        "method": "card",
        "description": "Adjustment",
    }


def _refund(entity_id: str, order_id: str, utr: str, debit: int, amount: int | None = None) -> dict:
    return {
        "entity_id": entity_id,
        "type": "refund",
        "debit": debit,
        "credit": 0,
        "amount": amount if amount is not None else debit,
        "currency": "INR",
        "fee": None,
        "tax": None,
        "on_hold": False,
        "settled": True,
        "created_at": 1_780_000_000,
        "settled_at": 1_780_100_000,
        "settlement_id": "setl_aggtestAAAAAAA",
        "settlement_utr": utr,
        "order_id": order_id,
        "order_receipt": f"RCPT-{order_id}",
        "method": "card",
        "description": "Refund",
    }


def _bank_txn(txn_id: str, utr: str, credit: int) -> dict:
    return {
        "txn_id": txn_id,
        "value_date": "2026-08-01",
        "description": f"NEFT CR-RAZORPAY-{utr}",
        "credit": credit,
        "debit": 0,
        "balance": 1_000_000,
    }


def test_a_settlement_with_a_non_ambiguous_adjustment_is_matched(db: sqlite3.Connection) -> None:
    order = _order("order_agg0000000001", 100000, "cust_agg000000001")
    payment = _payment("pay_agg00000001", order["order_id"], "111122223333", 100000, 1800, 324)
    # A one-off adjustment with no plausible duplicate order elsewhere.
    adjustment = _adjustment("rfnd_agg0000000001", "111122223333", 5000)
    net = (100000 - 1800 - 324) - 5000
    bank_txn = _bank_txn("TXN_AGG_0001", "111122223333", net)
    ingest(
        MockAdapter(orders=[order], recon_lines=[payment, adjustment], bank_txns=[bank_txn]),
        db,
    )

    result = run_cascade(db, "test")

    agg_stat = next(ps for ps in result.passes if ps.name == "aggregate")
    assert agg_stat.matched == 2  # both recon lines (payment + adjustment) in this group
    group_row = db.execute("SELECT * FROM match_groups WHERE pass_name = 'aggregate'").fetchone()
    assert group_row is not None
    member_keys = {
        row["record_key"]
        for row in db.execute(
            "SELECT record_key FROM group_members WHERE group_id = ?", (group_row["group_id"],)
        )
    }
    assert "recon:rfnd_agg0000000001" in member_keys  # the adjustment IS a group member
    assert member_keys == {
        "bank:TXN_AGG_0001",
        "recon:pay_agg00000001",
        "recon:rfnd_agg0000000001",
        "order:order_agg0000000001",
    }  # exactly one order member — never attributed to the order-less adjustment


def test_ambiguous_adjustment_is_never_matched_c005_regression(db: sqlite3.Connection) -> None:
    """C-005: two orders share customer_id + amount + date; the adjustment
    that nets against one of them (no one knows which) must stay unmatched,
    not be folded into a settlement group the arithmetic happens to close.

    Post-§14.1/C-008: the two payments themselves DO now match (via
    `arithmetic_scope`) - only the ambiguous adjustment line stays unmatched.
    C-005's original finding (an ambiguous adjustment must never become a
    matched member) still holds; this test's assertions were narrowed from
    "match_groups == 0" to "the adjustment specifically is never a member"
    to reflect that.
    """
    same_customer = "cust_agg000000002"
    order_a = _order("order_agg0000000002", 159900, same_customer, created_at=1_780_500_000)
    order_b = _order("order_agg0000000003", 159900, same_customer, created_at=1_780_500_000)
    payment_a = _payment("pay_agg00000002", order_a["order_id"], "444455556666", 159900, 2878, 518)
    payment_b = _payment("pay_agg00000003", order_b["order_id"], "444455556666", 159900, 2878, 518)
    ambiguous_adjustment = _adjustment("rfnd_agg0000000002", "444455556666", 159900)
    net = (159900 - 2878 - 518) * 2 - 159900
    bank_txn = _bank_txn("TXN_AGG_0002", "444455556666", net)
    ingest(
        MockAdapter(
            orders=[order_a, order_b],
            recon_lines=[payment_a, payment_b, ambiguous_adjustment],
            bank_txns=[bank_txn],
        ),
        db,
    )

    run_cascade(db, "test")

    matched_keys = {
        row["record_key"] for row in db.execute("SELECT record_key FROM group_members")
    }
    assert "recon:rfnd_agg0000000002" not in matched_keys, "the ambiguous line must never match"
    assert "recon:pay_agg00000002" in matched_keys, "no longer collateral damage (C-008 resolved)"
    assert "recon:pay_agg00000003" in matched_keys, "no longer collateral damage (C-008 resolved)"

    exc = db.execute(
        "SELECT * FROM exceptions WHERE record_key = ?", ("recon:rfnd_agg0000000002",)
    ).fetchone()
    assert exc is not None
    assert exc["reason_code"] == "AMBIGUOUS_DUPLICATE"


def test_refund_pointing_at_an_order_from_a_different_settlement_c007_regression(
    db: sqlite3.Connection,
) -> None:
    """C-007: a refund's `order_id` links back to an order that PAID (and
    settled) in a different, earlier settlement entirely — its payment recon
    line is not a member of THIS settlement. `gross` must count only orders
    referenced by a `payment` line in this group, never double-count the
    refunded order's full amount just because it's referenced by the refund.
    """
    # The order from an earlier, unrelated settlement - never a member of the
    # settlement under test. Partially refunded, matching the real-data case
    # that surfaced this bug (order.amount > refund.debit).
    original_order = _order("order_agg0000000010", 739800, "cust_agg000000010")

    # The settlement under test: one new payment (large enough that the net
    # stays positive after the refund), plus a refund against the unrelated
    # original_order above.
    new_order = _order("order_agg0000000011", 1000000, "cust_agg000000011")
    new_utr = "777788889999"
    payment = _payment("pay_agg00000011", new_order["order_id"], new_utr, 1000000, 20000, 3600)
    refund = _refund("rfnd_agg0000000011", original_order["order_id"], new_utr, 100000)

    correct_net = (1000000 - 20000 - 3600) - 100000  # does NOT subtract original_order.amount
    bank_txn = _bank_txn("TXN_AGG_0011", new_utr, correct_net)

    ingest(
        MockAdapter(
            orders=[original_order, new_order],
            recon_lines=[payment, refund],
            bank_txns=[bank_txn],
        ),
        db,
    )

    result = run_cascade(db, "test")

    agg_stat = next(ps for ps in result.passes if ps.name == "aggregate")
    assert agg_stat.matched == 2  # payment + refund, both recon lines
    group_row = db.execute("SELECT * FROM match_groups WHERE pass_name = 'aggregate'").fetchone()
    assert group_row is not None
    proof = json.loads(group_row["proof_json"])
    assert proof["gross"] == 1000000  # new_order only - never original_order's 739800
    assert proof["closes"] is True
