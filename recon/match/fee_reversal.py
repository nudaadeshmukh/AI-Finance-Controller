"""Pass 4 — `fee_reversal`, slab inference — §13.4, the payments-literacy pass.

Four steps: observe -> detect change point -> **validate before use** ->
derive and close. Step 3 is the one that matters — a slab failing it is
rejected outright, never approximated. That is what turns the classic
wrong-global-rate failure (inferring one card rate across the unannounced
2.00% -> 1.90% boundary, getting ~1.95%, and closing nothing on either side)
loud instead of silent.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import UTC, date, datetime

from recon.db import queries
from recon.ingest.persist import read_recon_line
from recon.match.exact import build_settlement_proposal
from recon.match.money import round_half_up
from recon.models.facts import FeeSlab
from recon.models.pipeline import CascadeState, MatchProposal
from recon.models.sources import ReconLine
from recon.models.types import Paise

_MIN_BUCKET_OBSERVATIONS = 3
_SINGLE_SLAB_PURITY = 0.95
_SPLIT_PURITY = 0.95
_MIN_SPLIT_SEGMENT = 5


def _to_date(epoch_seconds: int) -> date:
    return datetime.fromtimestamp(epoch_seconds, tz=UTC).date()


def _bps(line: ReconLine) -> int:
    return round_half_up(line.fee * 10000, line.amount)


def _mode_purity(bps_values: list[int]) -> tuple[int, float]:
    """Returns (mode_value, purity) where purity = count(mode) / len(values)."""
    counts = Counter(bps_values)
    mode_value, mode_count = counts.most_common(1)[0]
    return mode_value, mode_count / len(bps_values)


def _validate_slab(
    method: str, bps: int, period_start: date, period_end: date, obs: list[ReconLine]
) -> FeeSlab | None:
    """§13.4 Step 3. Accepted only if it reproduces `credit == amount - fee -
    tax` EXACTLY on 100% of the stated-fee lines it's derived from. Rejected
    outright, never emitted, on any single failure.
    """
    slab = FeeSlab(
        method=method,
        period_start=period_start,
        period_end=period_end,
        inferred_bps=bps,
        sample_size=len(obs),
        reproduces_all_stated=True,
    )
    for line in obs:
        fee, tax = derive_fee(line.amount, slab)
        if line.amount - fee - tax != line.credit:
            return None  # rejected outright, never approximated
    return slab


def infer_slabs(lines: list[ReconLine]) -> list[FeeSlab]:
    """§13.4, §20.4. Filters to `type == "payment" AND fee IS NOT NULL`
    itself — refunds/adjustments carry `fee = 0` with `amount > 0` and would
    inject spurious 0-bps observations that destroy the change-point scan.
    """
    stated = [line for line in lines if line.type == "payment" and line.fee is not None]

    by_method: dict[str, list[ReconLine]] = {}
    for line in stated:
        by_method.setdefault(line.method, []).append(line)

    slabs: list[FeeSlab] = []
    for method, obs in by_method.items():
        if len(obs) < _MIN_BUCKET_OBSERVATIONS:
            continue  # no slab derived, no rate guessed - falls through to timing/tolerance

        bps_values = [_bps(line) for line in obs]
        mode_value, purity = _mode_purity(bps_values)
        if purity >= _SINGLE_SLAB_PURITY:
            dates = [_to_date(line.created_at) for line in obs]
            slab = _validate_slab(method, mode_value, min(dates), max(dates), obs)
            if slab is not None:
                slabs.append(slab)
            continue

        # Step 2 — change-point scan. Sort by created_at; a candidate split
        # is an index where bps differs between consecutive observations —
        # not every index boundary, not day boundaries.
        obs_sorted = sorted(obs, key=lambda line: line.created_at)
        bps_sorted = [_bps(line) for line in obs_sorted]

        best_split: int | None = None
        best_min_purity = 0.0
        for i in range(1, len(obs_sorted)):
            if bps_sorted[i] == bps_sorted[i - 1]:
                continue
            left, right = bps_sorted[:i], bps_sorted[i:]
            if len(left) < _MIN_SPLIT_SEGMENT or len(right) < _MIN_SPLIT_SEGMENT:
                continue
            _, left_purity = _mode_purity(left)
            _, right_purity = _mode_purity(right)
            candidate_min = min(left_purity, right_purity)
            if candidate_min > best_min_purity:
                best_min_purity = candidate_min
                best_split = i

        if best_split is None or best_min_purity < _SPLIT_PURITY:
            continue  # no slab derived for this bucket, no rate guessed

        left_obs, right_obs = obs_sorted[:best_split], obs_sorted[best_split:]
        left_mode, _ = _mode_purity(bps_sorted[:best_split])
        right_mode, _ = _mode_purity(bps_sorted[best_split:])
        left_dates = [_to_date(line.created_at) for line in left_obs]
        right_dates = [_to_date(line.created_at) for line in right_obs]

        left_slab = _validate_slab(method, left_mode, min(left_dates), max(left_dates), left_obs)
        if left_slab is not None:
            slabs.append(left_slab)
        right_slab = _validate_slab(
            method, right_mode, min(right_dates), max(right_dates), right_obs
        )
        if right_slab is not None:
            slabs.append(right_slab)

    return slabs


def derive_fee(amount: Paise, slab: FeeSlab) -> tuple[Paise, Paise]:
    """§10, §20.4. `fee = round_half_up(amount * bps, 10000)`,
    `tax = round_half_up(fee * 1800, 10000)` — the synthetic schedule's own
    formula, derived here from observed data, never imported (PROJECT_RULES.md rule 2).
    """
    fee = round_half_up(amount * slab.inferred_bps, 10000)
    tax = round_half_up(fee * 1800, 10000)
    return fee, tax


class FeeReversalPass:
    name = "fee_reversal"

    def run(self, db: sqlite3.Connection, state: CascadeState) -> list[MatchProposal]:
        all_keys = [row["record_key"] for row in db.execute(queries.SELECT_ALL_RECON_KEYS)]
        all_lines = [
            line for key in all_keys if (line := read_recon_line(db, key)) is not None
        ]

        slabs = infer_slabs(all_lines)
        state.derived.fee_slabs = slabs

        proposals: list[MatchProposal] = []
        for utr, bank_key in list(state.derived.utr_index.items()):
            if bank_key not in state.unmatched_bank:
                continue
            proposal = build_settlement_proposal(
                db, state, utr, bank_key, self.name, require_refund_or_adjustment=None
            )
            if proposal is not None:
                proposals.append(proposal)
        return proposals
