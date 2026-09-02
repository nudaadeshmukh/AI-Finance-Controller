"""§14, CLAUDE.md rule 3 — the verifier is the sole gate.

`commit()` is the ONLY function that writes `match_groups`, there is no
confidence threshold or override, and a deliberately wrong group must be
rejected, not matched. Never skip, weaken, or xfail this file (§25).
"""

from __future__ import annotations

import sqlite3

from recon.ingest import ingest
from recon.models.facts import DerivedFacts
from recon.models.pipeline import MatchProposal
from recon.verify import commit, verify
from tests.conftest import MockAdapter

_ORDER = {
    "order_id": "order_verify000000001",
    "receipt": "RCPT-VERIFY-0001",
    "customer_id": "cust_verify0000001",
    "amount": 100000,
    "currency": "INR",
    "status": "paid",
    "created_at": 1_780_000_000,
    "notes": {},
}

# fee=1800, tax=324 -> expected_net = 100000 - 1800 - 324 = 97876
_CORRECT_CREDIT = 97876

_OK_MEMBER_KEYS = [
    "order:order_verify000000001",
    "recon:pay_verify00000001",
    "bank:TXN_VERIFY_0001",
]


def _recon_line(**overrides: object) -> dict:
    base = {
        "entity_id": "pay_verify00000001",
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
        "settlement_id": "setl_verify0000001",
        "settlement_utr": "111122223333",
        "order_id": "order_verify000000001",
        "order_receipt": "RCPT-VERIFY-0001",
        "method": "card",
        "description": "Card payment",
    }
    base.update(overrides)
    return base


def _bank_txn(**overrides: object) -> dict:
    base = {
        "txn_id": "TXN_VERIFY_0001",
        "value_date": "2026-08-01",
        "description": "NEFT CR-RAZORPAY-111122223333",
        "credit": _CORRECT_CREDIT,
        "debit": 0,
        "balance": 5_000_000,
    }
    base.update(overrides)
    return base


def _ingest_fixture(db: sqlite3.Connection, recon_line: dict, bank_txn: dict) -> None:
    adapter = MockAdapter(orders=[_ORDER], recon_lines=[recon_line], bank_txns=[bank_txn])
    ingest(adapter, db)


def test_a_correctly_closing_group_is_matched(db: sqlite3.Connection) -> None:
    _ingest_fixture(db, _recon_line(), _bank_txn())
    proposal = MatchProposal(
        group_id="grp_verify_ok",
        member_keys=_OK_MEMBER_KEYS,
        pass_name="exact",
        origin="cascade",
    )

    proof = verify(proposal, db, DerivedFacts())

    assert proof.closes is True
    assert proof.gross == 100000
    assert proof.fees == 1800
    assert proof.tax == 324
    assert proof.expected_net == _CORRECT_CREDIT
    assert proof.observed_net == _CORRECT_CREDIT
    assert proof.delta == 0

    commit(proposal, proof, db)

    group_row = db.execute(
        "SELECT * FROM match_groups WHERE group_id = ?", ("grp_verify_ok",)
    ).fetchone()
    assert group_row is not None
    assert bool(group_row["closes"]) is True

    member_rows = db.execute(
        "SELECT record_key FROM group_members WHERE group_id = ?", ("grp_verify_ok",)
    ).fetchall()
    assert {row["record_key"] for row in member_rows} == set(proposal.member_keys)


def test_a_deliberately_wrong_group_is_rejected_not_matched(db: sqlite3.Connection) -> None:
    """The bank credit does not match the closing equation — a hallucinated
    or buggy proposal. The verifier must catch it; there is no override.
    """
    wrong_bank_txn = _bank_txn(txn_id="TXN_VERIFY_WRONG", credit=90000)  # should be 97876
    wrong_recon_line = _recon_line(entity_id="pay_verify_wrong", settlement_utr="999988887777")
    _ingest_fixture(db, wrong_recon_line, wrong_bank_txn)
    proposal = MatchProposal(
        group_id="grp_verify_wrong",
        member_keys=[
            "order:order_verify000000001",
            "recon:pay_verify_wrong",
            "bank:TXN_VERIFY_WRONG",
        ],
        pass_name="exact",
        origin="cascade",
    )

    proof = verify(proposal, db, DerivedFacts())

    assert proof.closes is False
    assert proof.delta != 0

    commit(proposal, proof, db)

    # Rejected: nothing written to match_groups/group_members.
    assert db.execute("SELECT COUNT(*) AS n FROM match_groups").fetchone()["n"] == 0
    assert db.execute("SELECT COUNT(*) AS n FROM group_members").fetchone()["n"] == 0
    # Per §11's lifecycle, a rejected proposal returns members to Unmatched,
    # not straight to exceptions — only cascade+LLM exhaustion does that.
    assert db.execute("SELECT COUNT(*) AS n FROM exceptions").fetchone()["n"] == 0
    # But the rejection is auditable, per member.
    rejected = db.execute(
        "SELECT * FROM audit_log WHERE stage = 'verify' AND action = 'rejected'"
    ).fetchall()
    assert len(rejected) == len(proposal.member_keys)


def test_a_confident_llm_hallucination_is_still_rejected(db: sqlite3.Connection) -> None:
    """§15.6 / §24: the verifier is what makes a bad LLM proposal harmless,
    regardless of how confidently it was claimed — `origin="llm"` gets no
    special treatment.
    """
    wrong_bank_txn = _bank_txn(txn_id="TXN_VERIFY_LLM", credit=1)
    _ingest_fixture(
        db, _recon_line(entity_id="pay_verify_llm", settlement_utr="555566667777"), wrong_bank_txn
    )
    proposal = MatchProposal(
        group_id="grp_verify_llm",
        member_keys=[
            "order:order_verify000000001",
            "recon:pay_verify_llm",
            "bank:TXN_VERIFY_LLM",
        ],
        pass_name="llm_verified",
        origin="llm",
    )

    proof = verify(proposal, db, DerivedFacts())
    assert proof.closes is False

    commit(proposal, proof, db)
    assert db.execute("SELECT COUNT(*) AS n FROM match_groups").fetchone()["n"] == 0


def test_unresolved_fee_never_closes_even_if_delta_is_zero(db: sqlite3.Connection) -> None:
    """A payment with fee/tax still NULL (undetermined) must never verify as
    closing, even in the freak case the stated bank credit happens to equal
    the gross amount (delta == 0 by coincidence, not by proof).
    """
    null_fee_line = _recon_line(
        entity_id="pay_verify_nullfee",
        settlement_utr="222233334444",
        fee=None,
        tax=None,
        credit=100000,  # equals gross exactly - would look like delta == 0
    )
    matching_bank_txn = _bank_txn(txn_id="TXN_VERIFY_NULLFEE", credit=100000)
    _ingest_fixture(db, null_fee_line, matching_bank_txn)
    proposal = MatchProposal(
        group_id="grp_verify_nullfee",
        member_keys=[
            "order:order_verify000000001",
            "recon:pay_verify_nullfee",
            "bank:TXN_VERIFY_NULLFEE",
        ],
        pass_name="exact",
        origin="cascade",
    )

    proof = verify(proposal, db, DerivedFacts())

    assert proof.closes is False, "an unresolved fee must never verify, even if delta looks like 0"


def test_missing_member_record_is_unverifiable(db: sqlite3.Connection) -> None:
    """A proposal referencing a record_key that does not exist in the
    database (§15.4: "References unknown key -> Reject") must not close.
    """
    _ingest_fixture(db, _recon_line(), _bank_txn())
    proposal = MatchProposal(
        group_id="grp_verify_missing",
        member_keys=[
            "order:order_verify000000001",
            "recon:pay_does_not_exist",
            "bank:TXN_VERIFY_0001",
        ],
        pass_name="exact",
        origin="cascade",
    )

    proof = verify(proposal, db, DerivedFacts())
    assert proof.closes is False


def test_committing_the_same_closing_proposal_twice_is_idempotent(db: sqlite3.Connection) -> None:
    _ingest_fixture(db, _recon_line(), _bank_txn())
    proposal = MatchProposal(
        group_id="grp_verify_twice",
        member_keys=_OK_MEMBER_KEYS,
        pass_name="exact",
        origin="cascade",
    )
    proof = verify(proposal, db, DerivedFacts())

    commit(proposal, proof, db)
    commit(proposal, proof, db)

    assert db.execute("SELECT COUNT(*) AS n FROM match_groups").fetchone()["n"] == 1
    assert db.execute("SELECT COUNT(*) AS n FROM group_members").fetchone()["n"] == 3


def test_matching_clears_a_stale_exception_for_the_same_key(db: sqlite3.Connection) -> None:
    """A record cannot be simultaneously matched and an exception
    (CLAUDE.md rule 4) — a later successful match must clear an earlier run's
    stale exception row for the same record_key.
    """
    _ingest_fixture(db, _recon_line(), _bank_txn())
    db.execute(
        "INSERT INTO exceptions "
        "(record_key, reason_code, reason_text, passes_tried, candidates, created_at) "
        "VALUES (?, 'NO_CANDIDATE', 'stale from an earlier run', '[]', '[]', 0)",
        ("recon:pay_verify00000001",),
    )

    proposal = MatchProposal(
        group_id="grp_verify_clears_exception",
        member_keys=_OK_MEMBER_KEYS,
        pass_name="exact",
        origin="cascade",
    )
    proof = verify(proposal, db, DerivedFacts())
    assert proof.closes is True
    commit(proposal, proof, db)

    assert (
        db.execute(
            "SELECT COUNT(*) AS n FROM exceptions WHERE record_key = ?",
            ("recon:pay_verify00000001",),
        ).fetchone()["n"]
        == 0
    )


def test_commit_is_the_only_function_writing_match_groups() -> None:
    """Static check: `queries.UPSERT_MATCH_GROUP` is referenced nowhere in
    `recon/` except `verify/__init__.py` — the sole-writer rule as a fact
    about the codebase, not just this test file's own behaviour.
    """
    import ast
    from pathlib import Path

    recon_root = Path(__file__).parent.parent / "recon"
    allowed = recon_root / "verify" / "__init__.py"
    definition_site = recon_root / "db" / "queries.py"  # where the constant itself is assigned
    violations = []
    for py_file in recon_root.rglob("*.py"):
        if py_file in (allowed, definition_site) or py_file.is_relative_to(recon_root / "generate"):
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            # Covers both `queries.UPSERT_MATCH_GROUP` (Attribute) and a
            # direct `from ... import UPSERT_MATCH_GROUP` (Name, Load-only -
            # a Store in queries.py itself is the definition, already
            # excluded above).
            is_attr_use = isinstance(node, ast.Attribute) and node.attr == "UPSERT_MATCH_GROUP"
            is_name_use = (
                isinstance(node, ast.Name)
                and node.id == "UPSERT_MATCH_GROUP"
                and isinstance(node.ctx, ast.Load)
            )
            if is_attr_use or is_name_use:
                violations.append(str(py_file.relative_to(recon_root.parent)))
    assert not violations, f"UPSERT_MATCH_GROUP referenced outside verify/__init__.py: {violations}"
