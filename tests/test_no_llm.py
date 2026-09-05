"""§25 protected test — `--no-llm` produces a complete run.

The deterministic pipeline must never depend on the LLM layer: with no client
(the `--no-llm` flag, or simply no `GROQ_API_KEY`), `propose()` returns `[]`,
the hypothesis stage is a no-op, and the residual is exactly what the cascade
left. Never skip, weaken, or xfail this file.
"""

from __future__ import annotations

import sqlite3

from recon.hypothesize import propose, run_hypothesis_stage
from recon.ingest import ingest
from recon.match import run_cascade
from recon.models.facts import DerivedFacts
from recon.models.pipeline import CascadeState
from tests.conftest import MockAdapter

_ORDER = {
    "order_id": "order_nollm0000000001",
    "receipt": "RCPT-NOLLM-0001",
    "customer_id": "cust_nollm00000001",
    "amount": 100000,
    "currency": "INR",
    "status": "paid",
    "created_at": 1_780_000_000,
    "notes": {},
}
_RECON = {
    "entity_id": "pay_nollm00000001",
    "type": "payment",
    "debit": 0,
    "credit": 97876,
    "amount": 100000,
    "currency": "INR",
    "fee": 1800,
    "tax": 324,
    "on_hold": False,
    "settled": True,
    "created_at": 1_780_000_000,
    "settled_at": 1_780_100_000,
    "settlement_id": "setl_nollm00000001",
    "settlement_utr": "314159265358",
    "order_id": "order_nollm0000000001",
    "order_receipt": "RCPT-NOLLM-0001",
    "method": "card",
    "description": "Card payment",
}
# No bank txn for this UTR -> the record cannot close -> it is residual.


def _seed(db: sqlite3.Connection) -> None:
    ingest(MockAdapter(orders=[_ORDER], recon_lines=[_RECON]), db)


def test_propose_returns_empty_without_a_client(db: sqlite3.Connection) -> None:
    _seed(db)
    residual = [r["record_key"] for r in db.execute("SELECT record_key FROM recon_lines")]
    assert propose(residual, db, DerivedFacts(), None) == []


def test_hypothesis_stage_is_a_noop_without_a_client(db: sqlite3.Connection) -> None:
    _seed(db)
    run_cascade(db, "no-llm-run")

    residual_before = sorted(
        r["record_key"]
        for r in db.execute(
            "SELECT record_key FROM recon_lines "
            "WHERE record_key NOT IN (SELECT record_key FROM group_members)"
        )
    )
    state = CascadeState(
        run_id="no-llm-run",
        unmatched_recon=list(residual_before),
        unmatched_bank=[],
        unmatched_ledger=[],
        derived=DerivedFacts(),
    )
    groups_before = db.execute("SELECT COUNT(*) AS n FROM match_groups").fetchone()["n"]

    result = run_hypothesis_stage(db, state, None)

    assert result.enabled is False
    assert result.records_resolved == 0
    assert state.unmatched_recon == residual_before
    assert db.execute("SELECT COUNT(*) AS n FROM match_groups").fetchone()["n"] == groups_before


def test_a_full_no_llm_run_classifies_every_residual_record(db: sqlite3.Connection) -> None:
    """The residual record has no bank txn -> after the cascade it must carry a
    specific reason code, with no LLM stage involved."""
    _seed(db)
    run_cascade(db, "no-llm-run")
    row = db.execute(
        "SELECT reason_code FROM exceptions WHERE record_key = 'recon:pay_nollm00000001'"
    ).fetchone()
    assert row is not None
    assert row["reason_code"] == "CROSS_PERIOD_UTR"
