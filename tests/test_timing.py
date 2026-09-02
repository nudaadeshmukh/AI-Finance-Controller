"""Pass 5 — `timing` — §13.5. Calendar inference never gates a recon-line
match (the recon<->bank join is by UTR only); it's tested here purely on its
own terms — business-day arithmetic, holiday inference, and the IST 18:00
capture-date rollover.
"""

from __future__ import annotations

import datetime

from recon.match.timing import _capture_date, add_business_days, infer_calendar
from recon.models.sources import ReconLine


def _payment(entity_id: str, created_at: int, settled_at: int) -> ReconLine:
    return ReconLine(
        entity_id=entity_id,
        type="payment",
        debit=0,
        credit=100000,
        amount=100000,
        currency="INR",
        fee=0,
        tax=0,
        on_hold=False,
        settled=True,
        created_at=created_at,
        settled_at=settled_at,
        settlement_id="setl_timingtestAAAA",
        settlement_utr="999988887777",
        order_id=f"order_{entity_id}",
        order_receipt=f"RCPT-{entity_id}",
        method="upi",
        description="UPI payment",
    )


def _epoch(y: int, m: int, d: int, hour: int = 10) -> int:
    return int(
        datetime.datetime(y, m, d, hour, 0, 0, tzinfo=datetime.UTC).timestamp()
    ) - 5 * 3600 - 30 * 60  # shift so the IST wall-clock hour equals `hour`


def test_add_business_days_skips_dates_not_in_the_business_set() -> None:
    business = {
        datetime.date(2026, 8, 3),
        datetime.date(2026, 8, 4),
        datetime.date(2026, 8, 5),
        datetime.date(2026, 8, 6),
        # 2026-08-7/8/9 deliberately excluded (weekend)
        datetime.date(2026, 8, 10),
    }
    result = add_business_days(datetime.date(2026, 8, 4), 2, business)
    assert result == datetime.date(2026, 8, 6)


def test_infer_calendar_finds_a_consistent_t_plus_2_pattern() -> None:
    lines = []
    # Every weekday Jun 1 - Jun 30 2026 has a settlement exactly 2 business
    # days after capture (captured well before the 18:00 IST cutoff).
    day = datetime.date(2026, 6, 1)
    business_days: list[datetime.date] = []
    while day <= datetime.date(2026, 6, 30):
        if day.weekday() < 5:
            business_days.append(day)
        day += datetime.timedelta(days=1)

    for idx, capture_day in enumerate(business_days[:-2]):
        settle_day = business_days[idx + 2]
        created_at = _epoch(capture_day.year, capture_day.month, capture_day.day, hour=10)
        settled_at = _epoch(settle_day.year, settle_day.month, settle_day.day, hour=10)
        lines.append(_payment(f"pay_timing{idx:03d}", created_at, settled_at))

    business, holidays, confidence = infer_calendar(lines)
    assert confidence >= 0.95
    assert business  # non-empty


def test_capture_after_1800_ist_rolls_to_the_next_business_day() -> None:
    """A payment captured at/after 18:00 IST is treated as captured the next
    day for T+2 counting (§13.5 step 3).
    """
    late_created_at = _epoch(2026, 8, 3, hour=19)  # 19:00 IST, after cutoff
    assert _capture_date(late_created_at) == datetime.date(2026, 8, 4)


def test_capture_before_1800_ist_does_not_roll_over() -> None:
    on_time_created_at = _epoch(2026, 8, 3, hour=17)  # 17:00 IST, before cutoff
    assert _capture_date(on_time_created_at) == datetime.date(2026, 8, 3)


def test_infer_calendar_with_no_settlements_returns_empty() -> None:
    business, holidays, confidence = infer_calendar([])
    assert business == set()
    assert holidays == set()
    assert confidence == 0.0
