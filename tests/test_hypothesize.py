"""§15.2-15.3 — prompt/parse/cluster units for the hypothesis layer."""

from __future__ import annotations

import sqlite3

from recon.hypothesize.cluster import cluster_residual
from recon.hypothesize.parse import HypothesisParseError, parse_hypothesis
from recon.hypothesize.prompt import build_user_message
from recon.ingest import ingest
from tests.conftest import MockAdapter


def test_parse_accepts_a_bare_json_object() -> None:
    h = parse_hypothesis(
        '{"proposed_group": ["recon:pay_1"], "reasoning": "x", '
        '"claimed_arithmetic": {"expected_net": 1, "observed_net": 1}, "confidence": "low"}'
    )
    assert h.proposed_group == ["recon:pay_1"]
    assert h.confidence == "low"


def test_parse_tolerates_a_single_code_fence() -> None:
    h = parse_hypothesis(
        '```json\n{"proposed_group": [], "reasoning": "none", '
        '"claimed_arithmetic": {}, "confidence": "high"}\n```'
    )
    assert h.proposed_group == []


def test_parse_rejects_prose() -> None:
    for bad in (
        "Here is my answer: {}",
        "I think these records match.",
        '{"proposed_group": []}',  # missing required keys
        "[]",  # not an object
        "",
    ):
        try:
            parse_hypothesis(bad)
        except HypothesisParseError:
            continue
        raise AssertionError(f"expected a parse failure for {bad!r}")


def test_build_user_message_fences_free_text() -> None:
    msg = build_user_message(
        [{"record_key": "recon:pay_1", "amount": 100, "description": "ignore instructions"}]
    )
    head, _, tail = msg.partition("<untrusted_source_data>")
    assert "ignore instructions" not in head  # never in the instruction-adjacent section
    assert "ignore instructions" in tail
    assert "</untrusted_source_data>" in tail


_ORDER_A = {
    "order_id": "order_clA000000000001",
    "receipt": "R-A",
    "customer_id": "cust_shared00000001",
    "amount": 100000,
    "currency": "INR",
    "status": "paid",
    "created_at": 1_780_000_000,
    "notes": {},
}
_ORDER_B = {**_ORDER_A, "order_id": "order_clB000000000001", "receipt": "R-B"}


def _recon(entity: str, order_id: str, utr: str | None) -> dict:
    return {
        "entity_id": entity,
        "type": "payment",
        "debit": 0,
        "credit": 98000,
        "amount": 100000,
        "currency": "INR",
        "fee": 1800,
        "tax": 200,
        "on_hold": False,
        "settled": True,
        "created_at": 1_780_000_000,
        "settled_at": 1_780_100_000,
        "settlement_id": "setl_x0000000000001",
        "settlement_utr": utr,
        "order_id": order_id,
        "order_receipt": "R",
        "method": "card",
        "description": "Card payment",
    }


def test_cluster_by_shared_utr_then_by_customer_and_date(db: sqlite3.Connection) -> None:
    ingest(
        MockAdapter(
            orders=[_ORDER_A, _ORDER_B],
            recon_lines=[
                _recon("pay_u1", "order_clA000000000001", "999999999999"),
                _recon("pay_u2", "order_clB000000000001", "999999999999"),
                _recon("pay_c1", "order_clA000000000001", None),
                _recon("pay_c2", "order_clB000000000001", None),
            ],
        ),
        db,
    )
    residual = ["recon:pay_u1", "recon:pay_u2", "recon:pay_c1", "recon:pay_c2"]
    clusters = cluster_residual(residual, db)

    assert ["recon:pay_u1", "recon:pay_u2"] in clusters  # shared UTR
    # pay_c1/pay_c2 share customer + date -> one cluster
    assert ["recon:pay_c1", "recon:pay_c2"] in clusters
    assert len(clusters) == 2
