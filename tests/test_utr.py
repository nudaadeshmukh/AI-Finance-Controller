"""Pass 1 — `utr` — §13.2."""

from __future__ import annotations

import sqlite3

from recon.ingest import ingest
from recon.match.utr import UtrPass, extract_utr
from recon.models.facts import DerivedFacts
from recon.models.pipeline import CascadeState
from tests.conftest import MockAdapter

# §6.3's five observed description formats, one UTR each.
_DESCRIPTIONS = [
    ("NEFT CR-RAZORPAY SOFTWARE PVT LTD-022011173948", "022011173948"),
    ("UPI/022011173948/RAZORPAY/SETTLEMENT", "022011173948"),
    ("IMPS/P2A/022011173948/RAZORPAY SOF", "022011173948"),
    ("RTGS CR RAZORPAYSOFTWARE 022011173948 SETTLEMENT", "022011173948"),
    ("NEFT-022011173948-RAZORPAY SOFTWARE PRIVATE LIM", "022011173948"),
]


def test_extract_utr_handles_all_five_observed_formats() -> None:
    for description, expected in _DESCRIPTIONS:
        assert extract_utr(description) == expected


def test_extract_utr_picks_the_longest_candidate_ruling_out_date_like_runs() -> None:
    # A 10-digit, date-like run alongside the real, longer 12-digit UTR -
    # both qualify under \d{10,22}, but the longer one must win.
    description = "NEFT CR 2026081412 RAZORPAY-985172444723"
    assert extract_utr(description) == "985172444723"


def test_extract_utr_returns_none_with_no_digit_run() -> None:
    assert extract_utr("VENDOR PAYMENT - OFFICE SUPPLIES") is None


def test_extract_utr_ignores_short_runs_under_ten_digits() -> None:
    assert extract_utr("REF 123456") is None


def _order(order_id: str, amount: int) -> dict:
    return {
        "order_id": order_id,
        "receipt": f"RCPT-{order_id}",
        "customer_id": "cust_utr0000000001",
        "amount": amount,
        "currency": "INR",
        "status": "paid",
        "created_at": 1_780_000_000,
        "notes": {},
    }


def _recon_line(entity_id: str, order_id: str, utr: str, amount: int, credit: int) -> dict:
    return {
        "entity_id": entity_id,
        "type": "payment",
        "debit": 0,
        "credit": credit,
        "amount": amount,
        "currency": "INR",
        "fee": amount - credit,
        "tax": 0,
        "on_hold": False,
        "settled": True,
        "created_at": 1_780_000_000,
        "settled_at": 1_780_100_000,
        "settlement_id": "setl_utrtestAAAAAA",
        "settlement_utr": utr,
        "order_id": order_id,
        "order_receipt": f"RCPT-{order_id}",
        "method": "card",
        "description": "Card payment",
    }


def test_matched_utr_is_indexed_not_proposed(db: sqlite3.Connection) -> None:
    order = _order("order_utr0000000001", 100000)
    recon_line = _recon_line("pay_utr00000001", order["order_id"], "444455556666", 100000, 98000)
    bank_txn = {
        "txn_id": "TXN_UTR_0001",
        "value_date": "2026-08-01",
        "description": "NEFT CR-RAZORPAY-444455556666",
        "credit": 98000,
        "debit": 0,
        "balance": 1_000_000,
    }
    adapter = MockAdapter(orders=[order], recon_lines=[recon_line], bank_txns=[bank_txn])
    ingest(adapter, db)

    state = CascadeState(
        run_id="test",
        unmatched_recon=["recon:pay_utr00000001"],
        unmatched_bank=["bank:TXN_UTR_0001"],
        unmatched_ledger=[],
        derived=DerivedFacts(),
    )
    proposals = UtrPass().run(db, state)

    assert proposals == []  # utr never proposes a match itself
    assert state.derived.utr_index == {"444455556666": "bank:TXN_UTR_0001"}
    assert "bank:TXN_UTR_0001" in state.unmatched_bank  # still open for exact/aggregate


def test_unrelated_debit_is_excluded_not_an_exception_in_the_ambiguous_sense(
    db: sqlite3.Connection,
) -> None:
    bank_txn = {
        "txn_id": "TXN_UTR_RENT",
        "value_date": "2026-08-05",
        "description": "VENDOR PAYMENT - OFFICE RENT AUGUST",
        "credit": 0,
        "debit": 50000,
        "balance": 950_000,
    }
    ingest(MockAdapter(bank_txns=[bank_txn]), db)

    state = CascadeState(
        run_id="test",
        unmatched_recon=[],
        unmatched_bank=["bank:TXN_UTR_RENT"],
        unmatched_ledger=[],
        derived=DerivedFacts(),
    )
    proposals = UtrPass().run(db, state)

    assert proposals == []
    assert "bank:TXN_UTR_RENT" not in state.unmatched_bank

    exc_row = db.execute(
        "SELECT * FROM exceptions WHERE record_key = ?", ("bank:TXN_UTR_RENT",)
    ).fetchone()
    assert exc_row is not None
    assert exc_row["reason_code"] == "NOT_A_SETTLEMENT"
    # NOT_A_SETTLEMENT is excluded, not matched or a business-ambiguity exception.
    assert db.execute("SELECT COUNT(*) AS n FROM match_groups").fetchone()["n"] == 0


def test_credit_with_no_recon_utr_match_is_left_for_tolerance(db: sqlite3.Connection) -> None:
    """An unmatched credit (e.g. a truncated UTR) is neither indexed nor
    excluded — it stays open for the tolerance pass (Phase 4).
    """
    bank_txn = {
        "txn_id": "TXN_UTR_NOMATCH",
        "value_date": "2026-08-06",
        "description": "NEFT CR-RAZORPAY-777788889999",
        "credit": 12345,
        "debit": 0,
        "balance": 900_000,
    }
    ingest(MockAdapter(bank_txns=[bank_txn]), db)  # no recon_lines with this UTR at all

    state = CascadeState(
        run_id="test",
        unmatched_recon=[],
        unmatched_bank=["bank:TXN_UTR_NOMATCH"],
        unmatched_ledger=[],
        derived=DerivedFacts(),
    )
    proposals = UtrPass().run(db, state)

    assert proposals == []
    assert state.derived.utr_index == {}
    assert "bank:TXN_UTR_NOMATCH" in state.unmatched_bank
    assert db.execute("SELECT COUNT(*) AS n FROM exceptions").fetchone()["n"] == 0
