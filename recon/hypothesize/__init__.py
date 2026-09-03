"""Hypothesize package — `propose()` (§12.4, §15, §20.4) and the stage runner
that wires it into the pipeline.

`propose()` is the narrow, bounded AI layer: it runs *only* on the cascade's
residual, makes one clustered LLM call per ambiguity, and returns
`MatchProposal`s with `origin="llm"`. It **never raises** — a `None` client,
an empty residual, a timeout, malformed JSON or an unreachable API all resolve
to "propose nothing / propose less" and the pipeline completes (§15.4).

`run_hypothesis_stage()` is the glue: it takes those proposals through the
*same* `verify()` / `commit()` path every cascade proposal uses (CLAUDE.md
rule 3 — there is no LLM fast path), updates the residual, and returns the
honest contribution counts for `results.json` (§15.5).

The verifier is the backstop (§15.6): a hallucinated or injection-driven
proposal cannot become a match, because a match requires arithmetic that
closes against source records the model does not control.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field

from recon import audit
from recon.db import queries
from recon.db.connection import transaction
from recon.hypothesize.client import ChatModel, GroqChatModel, LLMTimeout, LLMUnavailable
from recon.hypothesize.cluster import cluster_residual
from recon.hypothesize.parse import Hypothesis, HypothesisParseError, parse_hypothesis
from recon.hypothesize.prompt import REPAIR, SYSTEM, build_user_message
from recon.ingest.persist import persist_exception
from recon.models.facts import DerivedFacts
from recon.models.pipeline import CascadeState, Exception_, MatchProposal
from recon.models.reasons import REASON_LABELS, ReasonCode
from recon.models.types import RecordKey

LLM_PASS_NAME = "llm_verified"
_ALL_PASS_NAMES = ["utr", "exact", "aggregate", "fee_reversal", "timing", "tolerance", "llm"]

# Reason codes the hypothesis layer is allowed to (re)assign. It never
# overwrites a more specific cascade verdict (AMBIGUOUS_DUPLICATE,
# CROSS_PERIOD_UTR, CONTRADICTORY_LEDGER) — only a bare NO_CANDIDATE or a
# record the cascade left unclassified.
_REPLACEABLE = {None, ReasonCode.NO_CANDIDATE.value}


@dataclass
class LLMStageResult:
    """Honest §15.5 contribution accounting, surfaced in `results.json`."""

    enabled: bool = False
    records_resolved: int = 0
    hypotheses_proposed: int = 0
    hypotheses_rejected_by_verifier: int = 0
    runtime_ms: int = 0
    layer_unavailable: bool = False
    clusters: int = 0
    reasoning_by_group: dict[str, str] = field(default_factory=dict)


def _as_chat_model(client: object, model: str) -> ChatModel | None:
    if client is None:
        return None
    if isinstance(client, ChatModel):
        return client
    return GroqChatModel(client, model)


def _records_for_cluster(db: sqlite3.Connection, cluster: list[RecordKey]) -> list[dict]:
    """The structured + free-text facts one cluster's prompt needs: each
    residual recon line, and the order behind it. Bank txns are deliberately
    not volunteered — the cascade already found none for these, and the
    verifier will re-read whatever the model names anyway.
    """
    out: list[dict] = []
    for key in cluster:
        row = db.execute(queries.SELECT_RECON_LINE_BY_KEY, {"record_key": key}).fetchone()
        if row is None:
            continue
        rec = {
            "record_key": key,
            "source": "recon",
            "type": row["type"],
            "amount": row["amount"],
            "debit": row["debit"],
            "credit": row["credit"],
            "fee": row["fee"],
            "tax": row["tax"],
            "settled": bool(row["settled"]),
            "created_at": row["created_at"],
            "settlement_utr": row["settlement_utr"],
            "order_id": row["order_id"],
            "method": row["method"],
            "description": row["description"],
            "order_receipt": row["order_receipt"],
        }
        out.append(rec)
        if row["order_id"] is not None:
            order = db.execute(
                queries.SELECT_ORDER_BY_KEY, {"record_key": f"order:{row['order_id']}"}
            ).fetchone()
            if order is not None:
                out.append(
                    {
                        "record_key": f"order:{order['order_id']}",
                        "source": "order",
                        "amount": order["amount"],
                        "customer_id": order["customer_id"],
                        "status": order["status"],
                        "created_at": order["created_at"],
                        "notes": order["notes_json"],
                    }
                )
    return out


def _call_model(model: ChatModel, user: str, timeout_s: int) -> Hypothesis:
    """One cluster: initial call, then exactly one repair retry on malformed
    output (§15.4). Timeout and unavailability propagate to the caller.
    """
    raw = model.complete(SYSTEM, user, timeout_s)
    try:
        return parse_hypothesis(raw)
    except HypothesisParseError:
        raw = model.complete(SYSTEM, user + "\n\n" + REPAIR, timeout_s)
        return parse_hypothesis(raw)  # a second failure raises HypothesisParseError


def propose(
    residual: list[RecordKey],
    db: sqlite3.Connection,
    facts: DerivedFacts,
    client: object,
    *,
    model: str = "llama-3.3-70b-versatile",
    timeout_s: int = 20,
) -> list[MatchProposal]:
    """§20.4. Cluster the residual, ask the model once per cluster, and return
    candidate groupings. Never raises.
    """
    del facts  # read-only context is available but the prompt is self-contained
    _REASONING_CACHE.clear()
    _STATS.update(unavailable=False, timeouts=0, malformed=0)
    chat = _as_chat_model(client, model)
    if chat is None or not residual:
        return []

    proposals: list[MatchProposal] = []
    try:
        clusters = cluster_residual(residual, db)
    except Exception:  # noqa: BLE001 - never raise out of the LLM layer (§15)
        return []

    for idx, cluster in enumerate(clusters):
        records = _records_for_cluster(db, cluster)
        if not records:
            continue
        try:
            hypothesis = _call_model(chat, build_user_message(records), timeout_s)
        except LLMUnavailable:
            _STATS["unavailable"] = True
            break  # no point trying further clusters; pipeline completes (§15.4)
        except LLMTimeout:
            _STATS["timeouts"] += 1
            continue
        except HypothesisParseError:
            _STATS["malformed"] += 1
            continue
        except Exception:  # noqa: BLE001
            continue
        if not hypothesis.proposed_group:
            continue
        group_id = f"grp_llm{idx:03d}"
        proposals.append(
            MatchProposal(
                group_id=group_id,
                member_keys=list(dict.fromkeys(hypothesis.proposed_group)),
                pass_name=LLM_PASS_NAME,
                origin="llm",
            )
        )
        _REASONING_CACHE[group_id] = hypothesis.reasoning
    return proposals


# `MatchProposal` has no `reasoning` field (CLAUDE.md rule 12 - no invented
# model fields). The model's prose is audit/UI material, not match logic, so it
# rides alongside in this process-local cache and is written to `audit_log` by
# the stage runner. Both are reset at the start of every `propose()` call.
_REASONING_CACHE: dict[str, str] = {}
_STATS: dict[str, object] = {"unavailable": False, "timeouts": 0, "malformed": 0}


def run_hypothesis_stage(
    db: sqlite3.Connection,
    state: CascadeState,
    client: object,
    *,
    model: str = "llama-3.3-70b-versatile",
    timeout_s: int = 20,
) -> LLMStageResult:
    """Run `propose()` and route every proposal through `verify()`/`commit()`
    — identical to the cascade path (rule 3). Updates `state.unmatched_recon`
    in place and returns the §15.5 contribution counts.
    """
    from recon.verify import commit, verify

    result = LLMStageResult(enabled=True)
    start = time.monotonic()

    chat = _as_chat_model(client, model)
    if chat is None:
        result.enabled = False
        return result

    residual = list(state.unmatched_recon)
    if not residual:
        result.runtime_ms = int((time.monotonic() - start) * 1000)
        return result

    proposals = propose(residual, db, state.derived, chat, model=model, timeout_s=timeout_s)
    result.clusters = len(cluster_residual(residual, db))
    result.hypotheses_proposed = len(proposals)
    result.layer_unavailable = bool(_STATS["unavailable"])

    with transaction(db):
        if result.layer_unavailable:
            audit.record(
                db, "hypothesize", None, "layer_unavailable",
                {"reason_code": ReasonCode.HYPOTHESIS_LAYER_UNAVAILABLE.value},
            )
        for proposal in proposals:
            reasoning = _REASONING_CACHE.get(proposal.group_id, "")
            result.reasoning_by_group[proposal.group_id] = reasoning
            audit.record(
                db,
                "hypothesize",
                None,
                "proposed",
                {"group_id": proposal.group_id, "members": proposal.member_keys,
                 "reasoning": reasoning},
            )
            proof = verify(proposal, db, state.derived)
            commit(proposal, proof, db)
            if proof.closes:
                for key in proposal.member_keys:
                    if key.startswith("recon:") and key in state.unmatched_recon:
                        state.unmatched_recon.remove(key)
                        result.records_resolved += 1
            else:
                result.hypotheses_rejected_by_verifier += 1
                _reject_to_exceptions(db, proposal, proof, reasoning)

    result.runtime_ms = int((time.monotonic() - start) * 1000)
    return result


def _reject_to_exceptions(
    db: sqlite3.Connection, proposal: MatchProposal, proof: object, reasoning: str
) -> None:
    """A rejected LLM proposal: keep the model's reasoning in the audit trail
    (§24 — "with the model's reasoning preserved") and, for any member the
    cascade had not already classified more specifically, record
    `PROOF_DOES_NOT_CLOSE` (§15.4).
    """
    for key in proposal.member_keys:
        if not key.startswith("recon:"):
            continue
        audit.record(
            db,
            "hypothesize",
            key,
            "rejected",
            {
                "group_id": proposal.group_id,
                "delta": getattr(proof, "delta", None),
                "reasoning": reasoning,
            },
        )
        current = db.execute(
            queries.SELECT_EXCEPTION_REASON_BY_KEY, {"record_key": key}
        ).fetchone()
        if current is None or current["reason_code"] in _REPLACEABLE:
            persist_exception(
                db,
                Exception_(
                    record_key=key,
                    reason_code=ReasonCode.PROOF_DOES_NOT_CLOSE,
                    reason_text=REASON_LABELS[ReasonCode.PROOF_DOES_NOT_CLOSE],
                    passes_tried=_ALL_PASS_NAMES,
                    candidates=[],
                ),
            )
