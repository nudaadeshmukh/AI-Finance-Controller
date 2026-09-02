"""Pass 5 — `timing`, calendar inference — §13.5.

The recon<->bank join is by UTR only (§13.2-13.3), never by date — so the
T+2 business-day calendar this pass infers does not gate any recon-line
match. Its job is narrower and precisely scoped: attach ledger entries whose
`source_ref IS NULL` (78-92 per run) to the group their `entry_date` implies,
using the inferred calendar to check "same business cycle" rather than raw
calendar-day arithmetic. Ledger entries are never part of the closing
equation (§13.1), so this never risks a false recon-line match.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta

from recon.db import queries
from recon.models.pipeline import CascadeState, MatchProposal
from recon.models.sources import ReconLine

_IST_OFFSET = timedelta(hours=5, minutes=30)
_CUTOFF_HOUR_IST = 18
_CONFIDENCE_THRESHOLD = 0.95


def _to_date(epoch_seconds: int) -> date:
    return datetime.fromtimestamp(epoch_seconds, tz=UTC).date()


def _capture_date(created_at: int) -> date:
    """The effective capture date for T+2 counting: rolls forward one day if
    captured at or after 18:00 IST (§13.5 step 3).
    """
    ist_dt = datetime.fromtimestamp(created_at, tz=UTC) + _IST_OFFSET
    d = ist_dt.date()
    if ist_dt.hour >= _CUTOFF_HOUR_IST:
        d += timedelta(days=1)
    return d


def add_business_days(d: date, n: int, business: set[date]) -> date:
    """§13.5, §20.4. Walks forward from `d`, counting only dates present in
    `business`, until `n` have been counted.
    """
    current = d
    counted = 0
    while counted < n:
        current += timedelta(days=1)
        if current in business:
            counted += 1
    return current


def _weekdays_in_range(start: date, end: date) -> set[date]:
    days = set()
    d = start
    while d <= end:
        if d.weekday() < 5:  # Mon-Fri
            days.add(d)
        d += timedelta(days=1)
    return days


def _confidence(payments: list[ReconLine], business: set[date]) -> float:
    if not payments:
        return 0.0
    explained = sum(
        1
        for line in payments
        if add_business_days(_capture_date(line.created_at), 2, business)
        == _to_date(line.settled_at)
    )
    return explained / len(payments)


def infer_calendar(lines: list[ReconLine]) -> tuple[set[date], set[date], float]:
    """§13.5, §20.4. Returns `(business_days, inferred_holidays,
    calendar_confidence)`.

    1. Every distinct `settled_at` date is a business day — the initial
       observation.
    2. Weekdays inside the window with no settlement at all are candidate
       holidays.
    3. Validate each candidate via T+2 business-day arithmetic; iterate,
       dropping candidates that don't improve (or that worsen) the
       explained fraction, until confidence stops improving.
    4. `business_days` returned is the reconstructed dense calendar (every
       weekday in the window minus the final holiday set) — what
       `add_business_days` and ledger attachment actually need, not just the
       sparse set of days that happened to see a settlement.
    """
    observed_settlement_days = {
        _to_date(line.settled_at) for line in lines if line.settled_at is not None
    }
    if not observed_settlement_days:
        return set(), set(), 0.0

    window_start, window_end = min(observed_settlement_days), max(observed_settlement_days)
    all_weekdays = _weekdays_in_range(window_start, window_end)
    candidate_holidays = all_weekdays - observed_settlement_days

    payments = [
        line
        for line in lines
        if line.type == "payment" and line.settled_at is not None
    ]

    holidays = set(candidate_holidays)
    business = all_weekdays - holidays
    confidence = _confidence(payments, business)

    # Iterate: a candidate that doesn't help (or hurts) is dropped. Greedy,
    # single pass per candidate — the dataset has few enough holidays that
    # this converges immediately.
    if confidence < _CONFIDENCE_THRESHOLD:
        improved = True
        while improved and holidays:
            improved = False
            for candidate in list(holidays):
                trial_holidays = holidays - {candidate}
                trial_business = all_weekdays - trial_holidays
                trial_confidence = _confidence(payments, trial_business)
                if trial_confidence > confidence:
                    holidays = trial_holidays
                    business = trial_business
                    confidence = trial_confidence
                    improved = True
                    break

    return business, holidays, confidence


class TimingPass:
    name = "timing"

    def run(self, db: sqlite3.Connection, state: CascadeState) -> list[MatchProposal]:
        """Infers the calendar (stored on `state.derived` for the UI/audit
        trail) and attaches orphaned ledger entries to their group. Never
        proposes a recon-line match — see the module docstring for why.
        """
        from recon.ingest.persist import read_recon_line

        keys = [row["record_key"] for row in db.execute(queries.SELECT_ALL_RECON_KEYS)]
        lines = [line for key in keys if (line := read_recon_line(db, key)) is not None]

        business_days, holidays, confidence = infer_calendar(lines)
        state.derived.business_days = business_days
        state.derived.inferred_holidays = holidays
        state.derived.calendar_confidence = confidence

        if confidence >= _CONFIDENCE_THRESHOLD:
            _attach_orphaned_ledger_entries(db, lines)

        return []  # never proposes a recon-line match


def _attach_orphaned_ledger_entries(db: sqlite3.Connection, lines: list[ReconLine]) -> None:
    """Best-effort, informational only: link a `source_ref IS NULL` ledger
    entry to an already-matched group whose settlement date, within the
    ledger-lag tolerance, falls on or one day after the entry's `entry_date`
    (§13.6's `LEDGER_LAG_DAYS`). Never touches `match_groups`/`group_members`
    (only `commit()` may write those) and never affects a recon-line match
    decision — recorded to `audit_log` only. Ambiguous (more than one
    candidate group) is left unattached, not guessed.
    """
    from recon import audit
    from recon.match.constants import LEDGER_LAG_DAYS

    orphaned = db.execute(queries.SELECT_ORPHANED_LEDGER_ENTRIES).fetchall()
    if not orphaned:
        return

    # Map each matched group's own settlement date -> its group_id(s), from
    # any one of its member recon lines (they all share one settlement).
    line_by_key = {f"recon:{line.entity_id}": line for line in lines}
    group_by_settled_date: dict[date, set[str]] = {}
    for row in db.execute(queries.SELECT_MATCHED_RECON_GROUP_MEMBERS):
        line = line_by_key.get(row["record_key"])
        if line is None or line.settled_at is None:
            continue
        settled_date = _to_date(line.settled_at)
        group_by_settled_date.setdefault(settled_date, set()).add(row["group_id"])

    for entry in orphaned:
        entry_date = date.fromisoformat(entry["entry_date"])
        candidate_group_ids: set[str] = set()
        for lag in range(LEDGER_LAG_DAYS + 1):
            lagged_date = entry_date + timedelta(days=lag)
            candidate_group_ids.update(group_by_settled_date.get(lagged_date, set()))
        if len(candidate_group_ids) == 1:
            group_id = next(iter(candidate_group_ids))
            audit.record(
                db,
                "match.timing",
                entry["record_key"],
                "ledger_attached",
                {"group_id": group_id, "entry_date": entry["entry_date"]},
            )
