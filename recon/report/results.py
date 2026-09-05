"""`results.json` assembly and emission — §18.

`results.json` is the pipeline's only output to the frontend: static,
self-contained, committed. `schema_version` is `1`.

## Signature deviation from §20.4

§20.4 sketches `emit_results(report, path)`. The real contract, recorded
here and echoed into §20.4:

    assemble_results(db, score, baseline, cascade, facts) -> ResultsDocument
    emit_results(db, score, baseline, cascade, facts, path, *,
                 run_id, label, seed) -> None
    emit_html(results: Path, out: Path) -> None          # unchanged from §20.4

`score()` stays narrow — it is the one function with sealed-key access and
its job is "produce the metric numbers", not "assemble the document".
`assemble_results()` builds the whole §18 document from the DB plus the
phase's already-computed results, so it is unit-testable without the
filesystem. `emit_results()` is a thin serializer over it. `run_id`/`label`/
`seed` are keyword-only because §18 requires them and they live in neither
the DB nor any other argument (`seed` comes from `manifest.json`; see the
§8.3.1 note in `docs/project-progress.md`). `emit_html()` reads the emitted
JSON so the HTML can never drift from it.

## Determinism

`generated_at` is `MAX(recon_lines.created_at)` — a fixed property of the
frozen dataset ("data as of"), not wall-clock. The per-record `audit` array
carries only `stage`/`action`/`detail`, never a timestamp (§18), for the
same reason. Every field is therefore byte-identical across re-runs **except
the measured timing fields** — `passes[].runtime_ms`,
`summary.runtime_ms_cascade`, `summary.throughput_per_sec_cascade` — which
are wall-clock by nature (like `audit_log.ts`) and vary by a few ms. The
reconciliation content — matches, proofs, bridge, exceptions, slabs,
scores — is fully deterministic.

## The bridge (§18 `bridge[]`, §23.2)

Band semantics beyond §18's skeleton are not specified. Computed run-level:

    Gross orders − Processing fees − GST on fees − Refunds
                 − Settled next cycle + Prior cycle spillover  =  Bank credited

`Settled next cycle` / `Prior cycle spillover` are the signed residual
`Bank credited − (Gross − Fees − Tax − Refunds)` — the accrual-vs-cash
timing difference the two labels name. The waterfall closes to the paise by
construction. Fees/tax use the same slab-derived values `verify()` uses for
`fee IS NULL` payment lines, so the run-level totals match the settlement
sums the cascade actually closed on.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pydantic import BaseModel

from recon import audit
from recon.db import queries
from recon.match.base import find_applicable_slab
from recon.match.constants import (
    AMOUNT_DELTA_PAISE_PER_DERIVED_LINE,
    LEDGER_LAG_DAYS,
    UTR_TRUNCATION_DIGITS,
)
from recon.match.fee_reversal import derive_fee
from recon.models.facts import DerivedFacts
from recon.report.baseline import BaselineResult
from recon.report.scoring import ScoreReport

SCHEMA_VERSION = 1

_LLM_PASS_NAME = "llm_verified"
_CASCADE_PASS_ORDER = ["utr", "exact", "aggregate", "fee_reversal", "timing", "tolerance"]


class ResultsDocument(BaseModel):
    """The full §18 document. Inner objects are plain dicts — this model is a
    serialization envelope, not a place to re-validate every field. Money
    fields inside are JSON ints (paise); `tests/test_money.py` checks a
    committed `results.json`.
    """

    model_config = {"extra": "forbid"}

    schema_version: int = SCHEMA_VERSION
    run_id: str
    label: str
    generated_at: int
    seed: int
    summary: dict
    baseline: dict
    ceiling: dict
    llm_contribution: dict
    source_totals: dict
    bridge: list[dict]
    passes: list[dict]
    records: list[dict]
    exceptions: list[dict]
    derived_fee_slabs: list[dict]
    tolerance_constants: dict


def _scalar(db: sqlite3.Connection, query: str) -> int:
    return db.execute(query).fetchone()["n"]


def _resolved_fee_tax(row: sqlite3.Row, facts: DerivedFacts) -> tuple[int, int]:
    """Fee/tax for a payment line, deriving via a validated slab where the
    stored values are NULL — identical to `verify()`'s resolution so the
    run-level bridge totals match the settlement sums the cascade closed on.
    """
    if row["fee"] is not None and row["tax"] is not None:
        return row["fee"], row["tax"]
    slab = find_applicable_slab(facts, row["method"], row["created_at"])
    if slab is None:
        return row["fee"] or 0, row["tax"] or 0
    return derive_fee(row["amount"], slab)


def _build_bridge(db: sqlite3.Connection, facts: DerivedFacts) -> list[dict]:
    orders_amount = {r["order_id"]: r["amount"] for r in db.execute(queries.SELECT_ALL_ORDERS)}
    orders_key = {r["order_id"]: r["record_key"] for r in db.execute(queries.SELECT_ALL_ORDERS)}

    payment_order_ids: set[str] = set()
    fees = tax = refunds = 0
    fee_keys: list[str] = []
    refund_keys: list[str] = []
    next_cycle_keys: list[str] = []
    for row in db.execute(queries.SELECT_ALL_RECON_LINES_FULL):
        if row["type"] == "payment":
            if row["order_id"]:
                payment_order_ids.add(row["order_id"])
            f, t = _resolved_fee_tax(row, facts)
            fees += f
            tax += t
            if f or t:
                fee_keys.append(row["record_key"])
            if not row["settled"]:
                next_cycle_keys.append(row["record_key"])
        else:  # refund / adjustment
            refunds += row["debit"]
            refund_keys.append(row["record_key"])

    gross = sum(orders_amount[oid] for oid in payment_order_ids if oid in orders_amount)
    gross_keys = [orders_key[oid] for oid in payment_order_ids if oid in orders_key]

    not_a_settlement = {r["record_key"] for r in db.execute(queries.SELECT_NOT_A_SETTLEMENT_KEYS)}
    bank_credited = 0
    bank_keys: list[str] = []
    for row in db.execute(queries.SELECT_ALL_BANK_TXNS_FULL):
        if row["credit"] > 0 and row["record_key"] not in not_a_settlement:
            bank_credited += row["credit"]
            bank_keys.append(row["record_key"])

    net_earned = gross - fees - tax - refunds
    residual = bank_credited - net_earned
    settled_next_cycle = -residual if residual < 0 else 0
    prior_cycle_spillover = residual if residual > 0 else 0

    return [
        {"label": "Gross orders", "amount": gross, "sign": "+", "record_keys": sorted(gross_keys)},
        {"label": "Processing fees", "amount": fees, "sign": "-", "record_keys": sorted(fee_keys)},
        {"label": "GST on fees", "amount": tax, "sign": "-", "record_keys": sorted(fee_keys)},
        {"label": "Refunds", "amount": refunds, "sign": "-", "record_keys": sorted(refund_keys)},
        {
            "label": "Settled next cycle",
            "amount": settled_next_cycle,
            "sign": "-",
            "record_keys": sorted(next_cycle_keys),
        },
        {
            "label": "Prior cycle spillover",
            "amount": prior_cycle_spillover,
            "sign": "+",
            "record_keys": [],
        },
        {
            "label": "Bank credited",
            "amount": bank_credited,
            "sign": "=",
            "record_keys": sorted(bank_keys),
        },
    ]


def _proof_public(proof: dict) -> dict:
    """The §18 `records[].proof` shape — the closing-equation fields only."""
    return {
        "gross": proof["gross"],
        "fees": proof["fees"],
        "tax": proof["tax"],
        "refunds": proof["refunds"],
        "expected_net": proof["expected_net"],
        "observed_net": proof["observed_net"],
        "delta": proof["delta"],
        "closes": proof["closes"],
        "tolerance_applied": proof.get("tolerance_applied", 0),
    }


def _audit_detail(action: str, detail: dict) -> str:
    if action in ("matched", "rejected", "counted_not_committed"):
        return f"group {detail.get('group_id', '')}"
    if action == "classified":
        return str(detail.get("reason_code", ""))
    if action == "excluded":
        return "not a settlement"
    return ""


def _build_records(db: sqlite3.Connection) -> list[dict]:
    group_meta = {
        row["group_id"]: row
        for row in db.execute(queries.SELECT_ALL_MATCH_GROUPS)
    }
    members_by_group: dict[str, list[str]] = {}
    group_of_key: dict[str, str] = {}
    for row in db.execute(queries.SELECT_ALL_GROUP_MEMBERS):
        members_by_group.setdefault(row["group_id"], []).append(row["record_key"])
        group_of_key[row["record_key"]] = row["group_id"]

    exception_keys = {row["record_key"] for row in db.execute(queries.SELECT_EXCEPTION_RECON_KEYS)}

    records: list[dict] = []
    for row in db.execute(queries.SELECT_ALL_RECON_LINES_FULL):
        key = row["record_key"]
        trail = [
            {"stage": ev.stage, "action": ev.action, "detail": _audit_detail(ev.action, ev.detail)}
            for ev in audit.trail(db, key)
        ]
        display_amount = row["debit"] if row["type"] in ("refund", "adjustment") else row["amount"]

        if key in group_of_key:
            gid = group_of_key[key]
            meta = group_meta[gid]
            proof = json.loads(meta["proof_json"])
            records.append(
                {
                    "record_key": key,
                    "source": "recon",
                    "display_amount": display_amount,
                    "status": "matched",
                    "pass_name": meta["pass_name"],
                    "group_id": gid,
                    "member_keys": sorted(members_by_group.get(gid, [])),
                    "proof": _proof_public(proof),
                    "audit": trail,
                }
            )
        else:
            records.append(
                {
                    "record_key": key,
                    "source": "recon",
                    "display_amount": display_amount,
                    "status": "exception" if key in exception_keys else "unresolved",
                    "pass_name": None,
                    "group_id": None,
                    "member_keys": [],
                    "proof": None,
                    "audit": trail,
                }
            )
    records.sort(key=lambda r: r["record_key"])
    return records


def _build_exceptions(db: sqlite3.Connection) -> list[dict]:
    out: list[dict] = []
    for row in db.execute(queries.SELECT_ALL_EXCEPTIONS):
        if not row["record_key"].startswith("recon:"):
            continue  # NOT_A_SETTLEMENT bank debits are excluded, not exceptions (rule 9)
        out.append(
            {
                "record_key": row["record_key"],
                "reason_code": row["reason_code"],
                "reason_text": row["reason_text"],
                "passes_tried": json.loads(row["passes_tried"]),
                "candidates": json.loads(row["candidates"]),
            }
        )
    out.sort(key=lambda e: e["record_key"])
    return out


def _build_passes(
    db: sqlite3.Connection, cascade_passes: list, llm_runtime_ms: int = 0
) -> list[dict]:
    """`matched` from the persistent `match_groups.pass_name` (survives a
    re-run / `report`); `runtime_ms` from this invocation's `CascadeResult`
    (transient by nature — a re-run against a matched db legitimately spends
    ~0 ms)."""
    runtime_by_name = {ps.name: ps.runtime_ms for ps in cascade_passes}
    matched_by_name = {
        row["pass_name"]: row["n"] for row in db.execute(queries.SELECT_RECON_MEMBERS_BY_PASS)
    }
    rows = [
        {
            "name": name,
            "matched": matched_by_name.get(name, 0),
            "runtime_ms": runtime_by_name.get(name, 0),
        }
        for name in _CASCADE_PASS_ORDER
    ]
    rows.append(
        {
            "name": _LLM_PASS_NAME,
            "matched": matched_by_name.get(_LLM_PASS_NAME, 0),
            "runtime_ms": llm_runtime_ms,
        }
    )
    return rows


def assemble_results(
    db: sqlite3.Connection,
    score: ScoreReport | None,
    baseline: BaselineResult,
    cascade,
    facts: DerivedFacts,
    *,
    run_id: str,
    label: str,
    seed: int,
    llm: object = None,
) -> ResultsDocument:
    """Build the full §18 document. `score` is `None` only when the answer
    key is absent (§12.6: metrics omitted, run still emits). `llm` is an
    optional `LLMStageResult` (Phase 6) — `None` on a `--no-llm` run, in
    which case `llm_contribution.enabled` is `False`."""
    generated_at = _scalar(db, queries.SELECT_MAX_RECON_CREATED_AT)
    runtime_ms_cascade = cascade.runtime_ms
    llm_runtime_ms = int(getattr(llm, "runtime_ms", 0) or 0)
    throughput = round(400 / (runtime_ms_cascade / 1000), 2) if runtime_ms_cascade else 0.0

    if score is not None:
        summary = {
            "records_processed": 400,
            "matched": score.matched,
            "match_rate": score.match_rate,
            "match_precision": score.match_precision,
            "false_matches": score.false_matches,
            "unresolved": score.unresolved,
            "excluded": score.excluded,
            "runtime_ms_cascade": runtime_ms_cascade,
            "runtime_ms_llm": llm_runtime_ms,
            "throughput_per_sec_cascade": throughput,
        }
        ceiling = {
            "resolvable": score.ceiling_resolvable,
            "rate": score.ceiling_rate,
            "achievable": score.ceiling_achievable,
            "achievable_rate": score.ceiling_achievable_rate,
        }
    else:
        unresolved = sum(1 for _ in db.execute(queries.SELECT_EXCEPTION_RECON_KEYS))
        summary = {
            "records_processed": 400,
            "matched": None,
            "match_rate": None,
            "match_precision": None,
            "false_matches": None,
            "unresolved": unresolved,
            "excluded": _scalar(db, queries.SELECT_NOT_A_SETTLEMENT_COUNT),
            "runtime_ms_cascade": runtime_ms_cascade,
            "runtime_ms_llm": llm_runtime_ms,
            "throughput_per_sec_cascade": throughput,
        }
        ceiling = {"resolvable": None, "rate": None, "achievable": None, "achievable_rate": None}

    source_totals = {
        "orders_gross": _scalar(db, queries.SELECT_ORDERS_GROSS),
        "recon_net": _scalar(db, queries.SELECT_RECON_NET),
        "bank_credited": _scalar(db, queries.SELECT_BANK_CREDITED),
        "ledger_revenue": _scalar(db, queries.SELECT_LEDGER_REVENUE),
    }

    derived_fee_slabs = [
        {
            "method": slab.method,
            "period_start": slab.period_start.isoformat(),
            "period_end": slab.period_end.isoformat(),
            "inferred_bps": slab.inferred_bps,
            "gst_bps": slab.gst_bps,
            "sample_size": slab.sample_size,
            "reproduces_all_stated": slab.reproduces_all_stated,
        }
        for slab in facts.fee_slabs
    ]

    return ResultsDocument(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        label=label,
        generated_at=generated_at,
        seed=seed,
        summary=summary,
        baseline={
            "name": baseline.name,
            "matched": baseline.matched,
            "match_rate": baseline.match_rate,
        },
        ceiling=ceiling,
        llm_contribution={
            "enabled": bool(getattr(llm, "enabled", False)),
            "records_resolved": int(getattr(llm, "records_resolved", 0) or 0),
            "hypotheses_proposed": int(getattr(llm, "hypotheses_proposed", 0) or 0),
            "hypotheses_rejected_by_verifier": int(
                getattr(llm, "hypotheses_rejected_by_verifier", 0) or 0
            ),
        },
        source_totals=source_totals,
        bridge=_build_bridge(db, facts),
        passes=_build_passes(db, cascade.passes, llm_runtime_ms),
        records=_build_records(db),
        exceptions=_build_exceptions(db),
        derived_fee_slabs=derived_fee_slabs,
        tolerance_constants={
            "amount_delta_paise_per_derived_line": AMOUNT_DELTA_PAISE_PER_DERIVED_LINE,
            "utr_truncation_digits": UTR_TRUNCATION_DIGITS,
            "ledger_lag_days": LEDGER_LAG_DAYS,
        },
    )


def emit_results(
    db: sqlite3.Connection,
    score: ScoreReport | None,
    baseline: BaselineResult,
    cascade,
    facts: DerivedFacts,
    path: Path,
    *,
    run_id: str,
    label: str,
    seed: int,
    llm: object = None,
) -> None:
    """§20.4 (extended signature — see module docstring). Assemble and write
    `results.json`."""
    doc = assemble_results(
        db, score, baseline, cascade, facts,
        run_id=run_id, label=label, seed=seed, llm=llm,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc.model_dump(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
