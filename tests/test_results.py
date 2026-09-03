"""Phase 5 — `report/results.py`. §18 `results.json` contract: schema_version
1, every money field a JSON int (paise), the bridge closes to the paise, and
`emit_html` renders from the emitted JSON without drift.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from recon.ingest import ingest
from recon.match import run_cascade
from recon.report.baseline import compute_baseline
from recon.report.html import emit_html
from recon.report.results import assemble_results, emit_results
from tests.conftest import MockAdapter


def _order(oid: str, amount: int, cust: str = "cust_results0000001") -> dict:
    return {
        "order_id": oid,
        "receipt": f"RCPT-{oid}",
        "customer_id": cust,
        "amount": amount,
        "currency": "INR",
        "status": "paid",
        "created_at": 1_780_000_000,
        "notes": {},
    }


def _payment(eid: str, oid: str, utr: str, amount: int, fee: int, tax: int) -> dict:
    return {
        "entity_id": eid,
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
        "balance": 9_000_000,
    }


def _seed_run(db: sqlite3.Connection):
    a = _order("order_results00001", 200000)
    b = _order("order_results00002", 120000)
    pa = _payment("pay_results0001", a["order_id"], "444444444444", 200000, 4000, 720)
    pb = _payment("pay_results0002", b["order_id"], "444444444444", 120000, 2400, 432)
    net = (200000 - 4000 - 720) + (120000 - 2400 - 432)
    ingest(
        MockAdapter(orders=[a, b], recon_lines=[pa, pb], bank_txns=[_bank("444444444444", net)]),
        db,
    )
    return run_cascade(db, "test-run")


def _money_ints_ok(payload: dict) -> bool:
    """Every paise-bearing field is a JSON int (PROJECT_RULES.md rule 1). Rates and
    throughput are the only permitted floats."""
    money: list = [v for v in payload["source_totals"].values()]
    money += [band["amount"] for band in payload["bridge"]]
    money += [r["display_amount"] for r in payload["records"]]
    for rec in payload["records"]:
        if rec["proof"]:
            money += [v for v in rec["proof"].values() if isinstance(v, (int, float))]
    return all(isinstance(v, int) for v in money)


def test_assemble_results_shape_and_bridge_closes(db: sqlite3.Connection) -> None:
    cascade = _seed_run(db)
    baseline = compute_baseline(db)
    doc = assemble_results(
        db, None, baseline, cascade, cascade.derived, run_id="test-run", label="T", seed=7
    )
    payload = doc.model_dump()

    assert payload["schema_version"] == 1
    assert _money_ints_ok(payload), "a non-rate float leaked into results.json"

    signed = 0
    for band in payload["bridge"]:
        if band["sign"] == "+":
            signed += band["amount"]
        elif band["sign"] == "-":
            signed -= band["amount"]
        elif band["sign"] == "=":
            assert signed == band["amount"], "bridge does not close"

    names = [p["name"] for p in payload["passes"]]
    assert names[-1] == "llm_verified"
    assert len(payload["records"]) == 2


def test_emit_results_and_html_roundtrip(db: sqlite3.Connection, tmp_path: Path) -> None:
    cascade = _seed_run(db)
    baseline = compute_baseline(db)
    out = tmp_path / "results.json"
    emit_results(
        db, None, baseline, cascade, cascade.derived, out, run_id="test-run", label="T", seed=7
    )
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["run_id"] == "test-run"
    assert doc["seed"] == 7

    html_out = tmp_path / "report.html"
    emit_html(out, html_out)
    html = html_out.read_text(encoding="utf-8")
    assert "Reconciliation bridge" in html
    assert doc["label"] in html
