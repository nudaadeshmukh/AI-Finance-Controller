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


def _infer_gst_bps(stated: list[ReconLine]) -> int | None:
    """S10: GST on the fee, derived from observed (fee, tax) pairs — never a
    hardcoded constant (CLAUDE.md rule 2, C-018/R-1: the pipeline previously
    hardcoded 1800, the generator's own literal, which is exactly the shared-
    constant firewall breach rule 2 exists to catch even without an import).

    Unlike the per-method fee rate, GST is a single global rate (S10), so this
    is derived once from every stated line with a nonzero fee — a zero-fee
    line (UPI) carries no rate information; `tax = round_half_up(fee * bps,
    10000)` can't be inverted from `0 = round_half_up(0 * bps, 10000)`.

    Candidate values come from inverting the formula on each line, then the
    same validate-before-use discipline as S13.4 Step 3: the accepted
    candidate must reproduce `tax` EXACTLY on every one of these lines, not
    just the line it came from. Returns `None` if no candidate does — never
    a guessed rate.
    """
    priced = [line for line in stated if line.fee]
    if not priced:
        return None
    candidates = Counter(round_half_up(line.tax * 10000, line.fee) for line in priced)
    for bps, _ in candidates.most_common():
        if all(round_half_up(line.fee * bps, 10000) == line.tax for line in priced):
            return bps
    return None


def _validate_slab(
    method: str, bps: int, gst_bps: int, period_start: date, period_end: date,
    obs: list[ReconLine],
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
        gst_bps=gst_bps,
        sample_size=len(obs),
        reproduces_all_stated=True,
    )
    for line in obs:
        fee, tax = derive_fee(line.amount, slab)
        if line.amount - fee - tax != line.credit:
            return None  # rejected outright, never approximated
    return slab


def _extend_outer_edges_to_window(
    pairs: list[tuple[FeeSlab, list[ReconLine]]],
    window_start: date | None,
    window_end: date | None,
) -> list[FeeSlab]:
    """C-011. A slab's `period_start` / `period_end` is bounded by the dates
    of the *stated* fees it was derived from. When a method's earliest (or
    latest) slab has no change-point neighbour on its outer side, that bound
    is an artefact of sparse evidence, not a real rate boundary — extend it
    to the observed data-window edge, so a fee-null line dated before the
    first stated fee of its method still resolves.

    Only the OUTER edges move. The gap between two consecutive slabs of the
    same method (an unannounced rate change, e.g. card 2.00% -> 1.90%) is
    genuinely ambiguous for the day or two between the last observation of
    one rate and the first of the next, and stays exactly as inferred.

    Each widened slab is re-run through `_validate_slab` against its own
    observations; a widening that somehow fails validation is discarded and
    the original (already-validated) slab is kept. `inferred_bps` never
    changes, so in practice this always passes — but the gate is real, not
    decorative, and would catch a future change where the period affects
    derivation.
    """
    if not pairs:
        return []
    pairs = sorted(pairs, key=lambda p: p[0].period_start)
    out: list[FeeSlab] = []
    for idx, (slab, obs) in enumerate(pairs):
        start, end = slab.period_start, slab.period_end
        if idx == 0 and window_start is not None and window_start < start:
            start = window_start
        if idx == len(pairs) - 1 and window_end is not None and window_end > end:
            end = window_end
        if (start, end) == (slab.period_start, slab.period_end):
            out.append(slab)
            continue
        widened = _validate_slab(slab.method, slab.inferred_bps, slab.gst_bps, start, end, obs)
        out.append(widened if widened is not None else slab)
    return out


def infer_slabs(lines: list[ReconLine]) -> list[FeeSlab]:
    """§13.4, §20.4. Filters to `type == "payment" AND fee IS NOT NULL`
    itself — refunds/adjustments carry `fee = 0` with `amount > 0` and would
    inject spurious 0-bps observations that destroy the change-point scan.

    After inference, each method's outer slab edges are extended to the
    observed data-window (min/max `created_at` across every line) — see
    `_extend_outer_edges_to_window` and `docs/challenges-log.md` C-011.
    """
    stated = [line for line in lines if line.type == "payment" and line.fee is not None]

    gst_bps = _infer_gst_bps(stated)
    if gst_bps is None:
        return []  # no GST rate candidate reproduces every stated line - no slab can validate

    window_start = min((_to_date(line.created_at) for line in lines), default=None)
    window_end = max((_to_date(line.created_at) for line in lines), default=None)

    by_method: dict[str, list[ReconLine]] = {}
    for line in stated:
        by_method.setdefault(line.method, []).append(line)

    slab_obs: list[tuple[FeeSlab, list[ReconLine]]] = []
    for method, obs in by_method.items():
        if len(obs) < _MIN_BUCKET_OBSERVATIONS:
            continue  # no slab derived, no rate guessed - falls through to timing/tolerance

        bps_values = [_bps(line) for line in obs]
        mode_value, purity = _mode_purity(bps_values)
        if purity >= _SINGLE_SLAB_PURITY:
            dates = [_to_date(line.created_at) for line in obs]
            slab = _validate_slab(method, mode_value, gst_bps, min(dates), max(dates), obs)
            if slab is not None:
                slab_obs.append((slab, obs))
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

        left_slab = _validate_slab(
            method, left_mode, gst_bps, min(left_dates), max(left_dates), left_obs
        )
        if left_slab is not None:
            slab_obs.append((left_slab, left_obs))
        right_slab = _validate_slab(
            method, right_mode, gst_bps, min(right_dates), max(right_dates), right_obs
        )
        if right_slab is not None:
            slab_obs.append((right_slab, right_obs))

    by_method_pairs: dict[str, list[tuple[FeeSlab, list[ReconLine]]]] = {}
    for slab, obs in slab_obs:
        by_method_pairs.setdefault(slab.method, []).append((slab, obs))

    slabs: list[FeeSlab] = []
    for pairs in by_method_pairs.values():
        slabs.extend(_extend_outer_edges_to_window(pairs, window_start, window_end))
    return slabs


def derive_fee(amount: Paise, slab: FeeSlab) -> tuple[Paise, Paise]:
    """§10, §20.4. `fee = round_half_up(amount * bps, 10000)`,
    `tax = round_half_up(fee * gst_bps, 10000)` — the synthetic schedule's
    own formula, with BOTH rates derived from observed data on this slab,
    never a hardcoded literal (CLAUDE.md rule 2, C-018/R-1).
    """
    fee = round_half_up(amount * slab.inferred_bps, 10000)
    tax = round_half_up(fee * slab.gst_bps, 10000)
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
