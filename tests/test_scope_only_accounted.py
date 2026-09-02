"""§14.1, PROJECT_RULES.md rule 4 ("no third state") — C-008's resolution.

The eighth protected test (§25). Never skip, weaken, or xfail this file.

`arithmetic_scope` lets `verify()` sum over more than `member_keys`, so a
proof can close on a group whose committed membership deliberately excludes
one ambiguous record. This file is what keeps that mechanism honest: every
scope-only key must be independently accounted for (an `exceptions` row) by
end-of-run, and `report/scoring.check_scope_only_accounted()` must actually
refuse to score — not just fail a test — if one isn't.
"""

from __future__ import annotations

import sqlite3

from recon.errors import ScoringError
from recon.ingest import ingest
from recon.match import run_cascade
from recon.models.facts import DerivedFacts
from recon.models.pipeline import MatchProposal
from recon.report.scoring import check_scope_only_accounted
from recon.verify import commit, verify
from tests.conftest import MockAdapter

_ORDER = {
    "order_id": "order_scope0000000001",
    "receipt": "RCPT-SCOPE-0001",
    "customer_id": "cust_scope00000001",
    "amount": 100000,
    "currency": "INR",
    "status": "paid",
    "created_at": 1_780_000_000,
    "notes": {},
}

# fee=1800, tax=324 -> expected_net = 100000 - 1800 - 324 = 97876
_CORRECT_CREDIT = 97876

_RECON_LINE = {
    "entity_id": "pay_scope00000001",
    "type": "payment",
    "debit": 0,
    "credit": _CORRECT_CREDIT,
    "amount": 100000,
    "currency": "INR",
    "fee": 1800,
    "tax": 324,
    "on_hold": False,
    "settled": True,
    "created_at": 1_780_000_000,
    "settled_at": 1_780_100_000,
    "settlement_id": "setl_scope00000001",
    "settlement_utr": "121212121212",
    "order_id": "order_scope0000000001",
    "order_receipt": "RCPT-SCOPE-0001",
    "method": "card",
    "description": "Card payment",
}


def _scope_only_adjustment(entity_id: str, amount: int) -> dict:
    """A recon line shaped like an ambiguous adjustment: no order, netting
    against the settlement's bank credit. Never a real member of the group
    built below - only ever passed via `arithmetic_scope`.
    """
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
        "settlement_id": "setl_scope00000001",
        "settlement_utr": "121212121212",
        "order_id": None,
        "order_receipt": None,
        "method": "card",
        "description": "Scope-only adjustment",
    }


def _bank_txn(credit: int) -> dict:
    return {
        "txn_id": "TXN_SCOPE_0001",
        "value_date": "2026-08-01",
        "description": "NEFT CR-RAZORPAY-121212121212",
        "credit": credit,
        "debit": 0,
        "balance": 5_000_000,
    }


def test_arithmetic_scope_closes_while_excluding_the_scope_only_key(
    db: sqlite3.Connection,
) -> None:
    """`verify()` sums over `arithmetic_scope`, `commit()` writes
    `group_members` from `member_keys` only - the scope-only key never
    becomes a member, but the equation still closes on its value.
    """
    scope_only_amount = 5000
    adjustment = _scope_only_adjustment("adj_scope00000001", scope_only_amount)
    bank_txn = _bank_txn(_CORRECT_CREDIT - scope_only_amount)

    ingest(
        MockAdapter(orders=[_ORDER], recon_lines=[_RECON_LINE, adjustment], bank_txns=[bank_txn]),
        db,
    )

    member_keys = [
        "order:order_scope0000000001",
        "recon:pay_scope00000001",
        "bank:TXN_SCOPE_0001",
    ]
    arithmetic_scope = [*member_keys, "recon:adj_scope00000001"]
    proposal = MatchProposal(
        group_id="grp_scope_test",
        member_keys=member_keys,
        pass_name="test",
        origin="cascade",
        arithmetic_scope=arithmetic_scope,
    )

    proof = verify(proposal, db, DerivedFacts())
    assert proof.closes is True, proof
    assert proof.scope_only_keys == ["recon:adj_scope00000001"]

    commit(proposal, proof, db)

    member_rows = {
        row["record_key"]
        for row in db.execute(
            "SELECT record_key FROM group_members WHERE group_id = ?", ("grp_scope_test",)
        )
    }
    assert member_rows == set(member_keys)
    assert "recon:adj_scope00000001" not in member_rows

    # The scope-only key's own audit trail shows it was counted without
    # becoming a member - reconstructable without reading match_groups.
    trail = db.execute(
        "SELECT action FROM audit_log WHERE record_key = ? ORDER BY seq",
        ("recon:adj_scope00000001",),
    ).fetchall()
    assert [row["action"] for row in trail] == ["counted_not_committed"]


def test_arithmetic_scope_must_be_a_superset_of_member_keys(db: sqlite3.Connection) -> None:
    """A proposer bug - arithmetic_scope narrower than member_keys - is an
    internal contract violation, not a business-ambiguity outcome. §21:
    "Internal bug in a pass -> caught at boundary" via a plain exception,
    not one of the three ReconError classes (PROJECT_RULES.md rule 10).
    """
    bank_txn = _bank_txn(_CORRECT_CREDIT)
    ingest(MockAdapter(orders=[_ORDER], recon_lines=[_RECON_LINE], bank_txns=[bank_txn]), db)
    proposal = MatchProposal(
        group_id="grp_scope_bad",
        member_keys=[
            "order:order_scope0000000001",
            "recon:pay_scope00000001",
            "bank:TXN_SCOPE_0001",
        ],
        pass_name="test",
        origin="cascade",
        arithmetic_scope=["order:order_scope0000000001"],  # missing two real members
    )
    try:
        verify(proposal, db, DerivedFacts())
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for a non-superset arithmetic_scope")


def test_check_scope_only_accounted_passes_when_exception_row_exists(
    db: sqlite3.Connection,
) -> None:
    """The happy path: a scope-only key that has an exceptions row by
    end-of-run does not block scoring.
    """
    scope_only_amount = 5000
    adjustment = _scope_only_adjustment("adj_scope00000002", scope_only_amount)
    bank_txn = _bank_txn(_CORRECT_CREDIT - scope_only_amount)
    ingest(
        MockAdapter(orders=[_ORDER], recon_lines=[_RECON_LINE, adjustment], bank_txns=[bank_txn]),
        db,
    )
    proposal = MatchProposal(
        group_id="grp_scope_accounted",
        member_keys=[
            "order:order_scope0000000001",
            "recon:pay_scope00000001",
            "bank:TXN_SCOPE_0001",
        ],
        pass_name="test",
        origin="cascade",
        arithmetic_scope=[
            "order:order_scope0000000001",
            "recon:pay_scope00000001",
            "bank:TXN_SCOPE_0001",
            "recon:adj_scope00000002",
        ],
    )
    proof = verify(proposal, db, DerivedFacts())
    assert proof.closes is True
    commit(proposal, proof, db)

    db.execute(
        "INSERT INTO exceptions "
        "(record_key, reason_code, reason_text, passes_tried, candidates, created_at) "
        "VALUES (?, 'AMBIGUOUS_DUPLICATE', 'test', '[]', '[]', 0)",
        ("recon:adj_scope00000002",),
    )

    check_scope_only_accounted(db)  # must not raise


def test_check_scope_only_accounted_raises_scoring_error_when_unaccounted(
    db: sqlite3.Connection,
) -> None:
    """The enforcement path: a scope-only key with NO exceptions row by
    end-of-run must raise ScoringError, refusing to score - not just fail a
    test in CI.
    """
    scope_only_amount = 5000
    adjustment = _scope_only_adjustment("adj_scope00000003", scope_only_amount)
    bank_txn = _bank_txn(_CORRECT_CREDIT - scope_only_amount)
    ingest(
        MockAdapter(orders=[_ORDER], recon_lines=[_RECON_LINE, adjustment], bank_txns=[bank_txn]),
        db,
    )
    proposal = MatchProposal(
        group_id="grp_scope_unaccounted",
        member_keys=[
            "order:order_scope0000000001",
            "recon:pay_scope00000001",
            "bank:TXN_SCOPE_0001",
        ],
        pass_name="test",
        origin="cascade",
        arithmetic_scope=[
            "order:order_scope0000000001",
            "recon:pay_scope00000001",
            "bank:TXN_SCOPE_0001",
            "recon:adj_scope00000003",
        ],
    )
    proof = verify(proposal, db, DerivedFacts())
    assert proof.closes is True
    commit(proposal, proof, db)
    # Deliberately no exceptions row inserted for recon:adj_scope00000003.

    try:
        check_scope_only_accounted(db)
    except ScoringError as exc:
        assert "recon:adj_scope00000003" in str(exc)
    else:
        raise AssertionError("expected ScoringError for an unaccounted scope-only key")


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
        "settlement_id": "setl_scope_e2e0001",
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
        "settlement_id": "setl_scope_e2e0001",
        "settlement_utr": utr,
        "order_id": None,
        "order_receipt": None,
        "method": "card",
        "description": "Adjustment",
    }


def test_end_to_end_cascade_recovers_settlement_mates_and_stays_accounted(
    db: sqlite3.Connection,
) -> None:
    """The real scenario (C-008): a settlement with two clean payments plus
    one ambiguous adjustment (two same-customer/amount/date orders). Through
    the real cascade: the clean payments now match, the ambiguous adjustment
    stays unresolved with AMBIGUOUS_DUPLICATE, and the runtime invariant
    check passes cleanly on the resulting state - no code path needed to
    special-case this beyond what §14.1 already wires up.
    """
    same_customer = "cust_scope0e2e0001"
    same_ts = 1_780_400_000
    order_a = _order("order_scopee2e0000001", 199900, same_customer, same_ts)
    order_b = _order("order_scopee2e0000002", 199900, same_customer, same_ts)
    unrelated_order = _order("order_scopee2e0000003", 500000, "cust_scope0e2e0099", 1_780_000_000)

    utr = "999988887777"
    payment_a = _payment("pay_scopee2e0001", order_a["order_id"], utr, 199900, 3598, 648)
    payment_b = _payment("pay_scopee2e0002", order_b["order_id"], utr, 199900, 3598, 648)
    unrelated_payment = _payment(
        "pay_scopee2e0003", unrelated_order["order_id"], utr, 500000, 9000, 1620
    )
    ambiguous_adjustment = _adjustment("rfnd_scopee2e0001", utr, 199900)

    net = (199900 - 3598 - 648) * 2 + (500000 - 9000 - 1620) - 199900
    bank_txn = {
        "txn_id": "TXN_SCOPE_E2E_0001",
        "value_date": "2026-08-01",
        "description": f"NEFT CR-RAZORPAY-{utr}",
        "credit": net,
        "debit": 0,
        "balance": 1_000_000,
    }

    ingest(
        MockAdapter(
            orders=[order_a, order_b, unrelated_order],
            recon_lines=[payment_a, payment_b, unrelated_payment, ambiguous_adjustment],
            bank_txns=[bank_txn],
        ),
        db,
    )

    run_cascade(db, "test")

    matched_keys = {row["record_key"] for row in db.execute("SELECT record_key FROM group_members")}
    for key in ("recon:pay_scopee2e0001", "recon:pay_scopee2e0002", "recon:pay_scopee2e0003"):
        assert key in matched_keys, f"{key} should now match (C-008 resolved)"
    assert "recon:rfnd_scopee2e0001" not in matched_keys

    exc = db.execute(
        "SELECT * FROM exceptions WHERE record_key = ?", ("recon:rfnd_scopee2e0001",)
    ).fetchone()
    assert exc is not None
    assert exc["reason_code"] == "AMBIGUOUS_DUPLICATE"

    check_scope_only_accounted(db)  # must not raise on real cascade output
