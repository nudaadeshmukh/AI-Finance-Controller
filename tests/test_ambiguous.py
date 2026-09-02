"""§9.4, §13.7, CLAUDE.md rule 8 — the 11 ambiguous records per run must stay
unresolved. They are the deliverable, not a failure. Never skip, weaken, or
xfail this file (§25).

Per C-008 (docs/challenges-log.md): the ambiguous-adjustment guard defers the
ENTIRE settlement containing the ambiguous line, not just the line itself —
`verify()` derives its arithmetic strictly from `proposal.member_keys` (no
independent settlement query), so there is no way to keep the equation
correct while excluding only the ambiguous member without inventing
undocumented model surface. This file tests that actual, understood
behavior — including its settlement-mates staying unresolved too — not a
narrower claim that would hide the real scope.
"""

from __future__ import annotations

import json
import sqlite3

from recon.ingest import ingest
from recon.match import run_cascade
from recon.match.classify import classify_residual
from recon.models.facts import DerivedFacts
from recon.models.pipeline import CascadeState
from tests.conftest import MockAdapter


def _order(order_id: str, amount: int, customer: str, created_at: int) -> dict:
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
        "settlement_id": "setl_ambiguoustestA",
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
        "settlement_id": "setl_ambiguoustestA",
        "settlement_utr": utr,
        "order_id": None,
        "order_receipt": None,
        "method": "card",
        "description": "Adjustment",
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


def test_ambiguous_adjustment_and_its_settlement_mates_stay_unresolved(
    db: sqlite3.Connection,
) -> None:
    """A settlement with two unrelated, cleanly-resolvable payments PLUS the
    ambiguous pair (two same-customer/amount/date orders and the adjustment
    that nets against one of them, unknown which). The whole settlement -
    all four recon lines - must stay unmatched (C-008's documented scope,
    not a bug).
    """
    same_customer = "cust_ambig0000001"
    same_ts = 1_780_400_000
    order_a = _order("order_ambig000000001", 199900, same_customer, same_ts)
    order_b = _order("order_ambig000000002", 199900, same_customer, same_ts)
    unrelated_order = _order("order_ambig000000003", 500000, "cust_ambig0000099", 1_780_000_000)

    utr = "555566667777"
    payment_a = _payment("pay_ambig0000001", order_a["order_id"], utr, 199900, 3598, 648)
    payment_b = _payment("pay_ambig0000002", order_b["order_id"], utr, 199900, 3598, 648)
    unrelated_payment = _payment(
        "pay_ambig0000003", unrelated_order["order_id"], utr, 500000, 9000, 1620
    )
    ambiguous_adjustment = _adjustment("rfnd_ambig0000001", utr, 199900)

    net = (199900 - 3598 - 648) * 2 + (500000 - 9000 - 1620) - 199900
    bank_txn = _bank_txn("TXN_AMBIG_0001", utr, net)

    ingest(
        MockAdapter(
            orders=[order_a, order_b, unrelated_order],
            recon_lines=[payment_a, payment_b, unrelated_payment, ambiguous_adjustment],
            bank_txns=[bank_txn],
        ),
        db,
    )

    run_cascade(db, "test")

    assert db.execute("SELECT COUNT(*) AS n FROM match_groups").fetchone()["n"] == 0
    matched_keys = {row["record_key"] for row in db.execute("SELECT record_key FROM group_members")}
    for key in (
        "recon:rfnd_ambig0000001",
        "recon:pay_ambig0000001",
        "recon:pay_ambig0000002",
        "recon:pay_ambig0000003",  # the collateral cost, per C-008
    ):
        assert key not in matched_keys


def test_classify_residual_names_the_ambiguous_adjustment_with_both_candidates(
    db: sqlite3.Connection,
) -> None:
    same_customer = "cust_ambig0000002"
    same_ts = 1_780_500_000
    order_a = _order("order_ambig000000010", 299900, same_customer, same_ts)
    order_b = _order("order_ambig000000011", 299900, same_customer, same_ts)
    utr = "111122223333"
    payment_a = _payment("pay_ambig0000010", order_a["order_id"], utr, 299900, 5398, 972)
    payment_b = _payment("pay_ambig0000011", order_b["order_id"], utr, 299900, 5398, 972)
    ambiguous_adjustment = _adjustment("rfnd_ambig0000010", utr, 299900)
    net = (299900 - 5398 - 972) * 2 - 299900
    bank_txn = _bank_txn("TXN_AMBIG_0002", utr, net)

    ingest(
        MockAdapter(
            orders=[order_a, order_b],
            recon_lines=[payment_a, payment_b, ambiguous_adjustment],
            bank_txns=[bank_txn],
        ),
        db,
    )

    run_cascade(db, "test")

    exc = db.execute(
        "SELECT * FROM exceptions WHERE record_key = ?", ("recon:rfnd_ambig0000010",)
    ).fetchone()
    assert exc is not None
    assert exc["reason_code"] == "AMBIGUOUS_DUPLICATE"
    candidates = json.loads(exc["candidates"])
    assert set(candidates) == {"order:order_ambig000000010", "order:order_ambig000000011"}


def test_classify_residual_never_picks_one_candidate(db: sqlite3.Connection) -> None:
    """Never resolve the ambiguity even when called directly, bypassing the
    cascade's own settlement-level defer.
    """
    same_customer = "cust_ambig0000003"
    same_ts = 1_780_600_000
    order_a = _order("order_ambig000000020", 99900, same_customer, same_ts)
    order_b = _order("order_ambig000000021", 99900, same_customer, same_ts)
    utr = "444455556666"
    payment_a = _payment("pay_ambig0000020", order_a["order_id"], utr, 99900, 1798, 324)
    payment_b = _payment("pay_ambig0000021", order_b["order_id"], utr, 99900, 1798, 324)
    ambiguous_adjustment = _adjustment("rfnd_ambig0000020", utr, 99900)
    ingest(
        MockAdapter(
            orders=[order_a, order_b],
            recon_lines=[payment_a, payment_b, ambiguous_adjustment],
        ),
        db,
    )

    state = CascadeState(
        run_id="test",
        unmatched_recon=[
            "recon:pay_ambig0000020",
            "recon:pay_ambig0000021",
            "recon:rfnd_ambig0000020",
        ],
        unmatched_bank=[],
        unmatched_ledger=[],
        derived=DerivedFacts(),
    )
    exceptions = classify_residual(db, state)
    adj_exc = next(e for e in exceptions if e.record_key == "recon:rfnd_ambig0000020")
    assert adj_exc.reason_code == "AMBIGUOUS_DUPLICATE"
    assert len(adj_exc.candidates) == 2
