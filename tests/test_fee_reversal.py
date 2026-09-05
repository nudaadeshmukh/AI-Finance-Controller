"""Pass 4 — `fee_reversal` — §13.4. Step 3 (validate before use) is the piece
that matters most in this whole cascade: a slab that does not reproduce
`credit == amount - fee - tax` exactly on 100% of its stated-fee lines must
be rejected outright, never approximated. This file tests that rule
directly, not just the happy path.
"""

from __future__ import annotations

import datetime

from recon.match.fee_reversal import derive_fee, infer_slabs
from recon.models.facts import FeeSlab
from recon.models.sources import ReconLine


def _payment(
    entity_id: str, amount: int, fee: int, tax: int, method: str, created_at: int
) -> ReconLine:
    return ReconLine(
        entity_id=entity_id,
        type="payment",
        debit=0,
        credit=amount - fee - tax,
        amount=amount,
        currency="INR",
        fee=fee,
        tax=tax,
        on_hold=False,
        settled=True,
        created_at=created_at,
        settled_at=created_at + 100_000,
        settlement_id="setl_feetestAAAAAAAA",
        settlement_utr="123412341234",
        order_id=f"order_{entity_id}",
        order_receipt=f"RCPT-{entity_id}",
        method=method,
        description="Card payment",
    )


def _bps_to_fee_tax(amount: int, bps: int) -> tuple[int, int]:
    fee = (amount * bps + 5000) // 10000  # half-up
    tax = (fee * 1800 + 5000) // 10000
    return fee, tax


def test_infers_a_single_slab_for_an_unchanging_rate() -> None:
    lines = []
    for i in range(10):
        amount = 100000 + i * 1000
        fee, tax = _bps_to_fee_tax(amount, 175)  # netbanking, 1.75%
        lines.append(_payment(f"pay_fee{i:03d}", amount, fee, tax, "netbanking", 1_780_000_000 + i))

    slabs = infer_slabs(lines)
    assert len(slabs) == 1
    assert slabs[0].method == "netbanking"
    assert slabs[0].inferred_bps == 175
    assert slabs[0].reproduces_all_stated is True
    assert slabs[0].sample_size == 10


def test_infers_two_slabs_across_an_unannounced_rate_change() -> None:
    """The card-rate scenario: 2.00% for the first half of observations,
    1.90% for the second half, with no signal anywhere marking the boundary.
    """
    lines = []
    for i in range(15):
        amount = 200000 + i * 1000
        fee, tax = _bps_to_fee_tax(amount, 200)
        created_at = 1_780_000_000 + i * 86400
        lines.append(_payment(f"pay_feeA{i:03d}", amount, fee, tax, "card", created_at))
    for i in range(15):
        amount = 200000 + i * 1000
        fee, tax = _bps_to_fee_tax(amount, 190)
        lines.append(
            _payment(f"pay_feeB{i:03d}", amount, fee, tax, "card", 1_780_000_000 + (20 + i) * 86400)
        )

    slabs = infer_slabs(lines)
    card_slabs = sorted((s for s in slabs if s.method == "card"), key=lambda s: s.period_start)
    assert len(card_slabs) == 2
    assert card_slabs[0].inferred_bps == 200
    assert card_slabs[1].inferred_bps == 190
    assert card_slabs[0].reproduces_all_stated is True
    assert card_slabs[1].reproduces_all_stated is True
    assert card_slabs[0].period_end < card_slabs[1].period_start


def test_a_slab_that_does_not_reproduce_all_stated_lines_is_rejected() -> None:
    """A single global rate across a real rate change would fail Step 3's
    validation exactly, on purpose - not approximated, not emitted at all.
    """
    lines = []
    for i in range(15):
        amount = 200000
        fee, tax = _bps_to_fee_tax(amount, 200)
        created_at = 1_780_000_000 + i * 3600
        lines.append(_payment(f"pay_bad{i:03d}", amount, fee, tax, "card", created_at))
    # A minority of lines at a DIFFERENT rate, small enough to still leave a
    # >=95% mode purity (so Step 2 accepts a single slab) but that slab then
    # fails Step 3 against these outliers.
    for i in range(1):
        amount = 200000
        fee, tax = _bps_to_fee_tax(amount, 175)  # inconsistent with the 200bps mode
        created_at = 1_780_000_000 + 999999
        lines.append(_payment(f"pay_outlier{i:03d}", amount, fee, tax, "card", created_at))

    slabs = infer_slabs(lines)
    # The single dominant slab must have been rejected outright - it does
    # NOT reproduce the outlier's stated credit - so nothing is emitted for
    # this bucket, and no rate is guessed.
    assert not any(s.method == "card" for s in slabs)


def test_a_bucket_with_fewer_than_three_observations_is_skipped() -> None:
    lines = [
        _payment("pay_tiny0", 50000, *_bps_to_fee_tax(50000, 225), "wallet", 1_780_000_000),
        _payment("pay_tiny1", 60000, *_bps_to_fee_tax(60000, 225), "wallet", 1_780_000_100),
    ]
    slabs = infer_slabs(lines)
    assert slabs == []


def test_refund_and_adjustment_lines_never_pollute_the_bps_observations() -> None:
    """Refunds/adjustments carry fee=0 with amount>0 (§13.4 step 1) - if they
    leaked into the bps sample, they'd inject spurious 0-bps observations.
    """
    lines = []
    for i in range(10):
        amount = 100000
        fee, tax = _bps_to_fee_tax(amount, 175)
        created_at = 1_780_000_000 + i
        lines.append(_payment(f"pay_pollute{i:03d}", amount, fee, tax, "netbanking", created_at))

    refund = ReconLine(
        entity_id="rfnd_pollute0",
        type="refund",
        debit=50000,
        credit=0,
        amount=50000,
        currency="INR",
        fee=0,
        tax=0,
        on_hold=False,
        settled=True,
        created_at=1_780_000_500,
        settled_at=1_780_100_500,
        settlement_id="setl_feetestAAAAAAAA",
        settlement_utr="123412341234",
        order_id="order_pollute0",
        order_receipt="RCPT-pollute0",
        method="netbanking",
        description="Refund",
    )

    slabs = infer_slabs([*lines, refund])
    assert len(slabs) == 1
    assert slabs[0].inferred_bps == 175  # unaffected by the refund's fee=0


_DAY = 86_400
_BASE = 1_780_000_000  # arbitrary; only relative days matter


def _d(epoch: int) -> datetime.date:
    """UTC calendar date — matches `fee_reversal._to_date`."""
    return datetime.datetime.fromtimestamp(epoch, tz=datetime.UTC).date()


def _fee_null_payment(entity_id: str, amount: int, method: str, created_at: int) -> ReconLine:
    line = _payment(entity_id, amount, 0, 0, method, created_at)
    return line.model_copy(update={"fee": None, "tax": None, "credit": amount})


def test_c011_earliest_slab_extends_back_to_the_data_window_start() -> None:
    """C-011: the earliest stated fee for a method sits well inside the
    ingest window (sparse evidence). The slab's period_start must extend to
    the window edge, not stop at first-observed — otherwise a fee-null line
    dated before the first stated fee can never be derived.
    """
    lines: list[ReconLine] = []
    # A fee-null card line on window day 0 — the record C-011 was about.
    lines.append(_fee_null_payment("pay_c011null", 1_699_800, "card", _BASE + 0 * _DAY))
    # Stated card fees only from day 10 onward — one unchanging rate.
    for i in range(8):
        amount = 200000 + i * 1000
        fee, tax = _bps_to_fee_tax(amount, 200)
        ts = _BASE + (10 + i) * _DAY
        lines.append(_payment(f"pay_c011s{i:02d}", amount, fee, tax, "card", ts))

    slabs = infer_slabs(lines)
    card = [s for s in slabs if s.method == "card"]
    assert len(card) == 1
    assert card[0].inferred_bps == 200
    assert card[0].reproduces_all_stated is True
    # Extended back to the window edge (day 0), not clamped to day 10.
    assert card[0].period_start == _d(_BASE)
    # The fee-null line is now inside the slab's period.
    assert card[0].period_start <= _d(_BASE) <= card[0].period_end


def test_c011_only_outer_edges_move_inner_ambiguous_gap_is_preserved() -> None:
    """The gap between two slabs of the same method (an unannounced rate
    change) is genuinely ambiguous for the day or two between the last
    observation of one rate and the first of the next — it must NOT be
    filled by the window-edge extension.
    """
    lines: list[ReconLine] = []
    for i in range(8):  # 200 bps, days 5..12
        amount = 200000 + i * 1000
        fee, tax = _bps_to_fee_tax(amount, 200)
        ts = _BASE + (5 + i) * _DAY
        lines.append(_payment(f"pay_gapA{i:02d}", amount, fee, tax, "card", ts))
    for i in range(8):  # 190 bps, days 20..27
        amount = 200000 + i * 1000
        fee, tax = _bps_to_fee_tax(amount, 190)
        ts = _BASE + (20 + i) * _DAY
        lines.append(_payment(f"pay_gapB{i:02d}", amount, fee, tax, "card", ts))
    # Window-defining lines at day 0 and day 40.
    lines.append(_fee_null_payment("pay_edge0", 100000, "upi", _BASE + 0 * _DAY))
    lines.append(_fee_null_payment("pay_edge40", 100000, "upi", _BASE + 40 * _DAY))

    card = sorted(
        (s for s in infer_slabs(lines) if s.method == "card"), key=lambda s: s.period_start
    )
    assert len(card) == 2
    # Outer edges reached the window; inner gap between day 12 and day 20 stayed open.
    assert card[0].period_start == _d(_BASE)
    assert card[1].period_end == _d(_BASE + 40 * _DAY)
    assert card[0].period_end < card[1].period_start
    gap_days = (card[1].period_start - card[0].period_end).days
    assert gap_days >= 1  # the change-point gap is not papered over


def test_c011_widened_slab_still_passes_reproduces_all_stated() -> None:
    """Widening the period never changes `inferred_bps`, so validation still
    holds — but the gate is real: the widened slab is the one returned, and
    it reproduces every stated line."""
    lines = []
    for i in range(6):
        amount = 300000 + i * 1000
        fee, tax = _bps_to_fee_tax(amount, 175)
        ts = _BASE + (12 + i) * _DAY
        lines.append(_payment(f"pay_w{i:02d}", amount, fee, tax, "netbanking", ts))
    lines.append(_fee_null_payment("pay_wnull", 250000, "netbanking", _BASE + 0 * _DAY))

    nb = [s for s in infer_slabs(lines) if s.method == "netbanking"]
    assert len(nb) == 1
    assert nb[0].reproduces_all_stated is True
    assert nb[0].period_start == _d(_BASE)
    assert nb[0].inferred_bps == 175
    fee, tax = derive_fee(250000, nb[0])
    assert (fee, tax) == _bps_to_fee_tax(250000, 175)  # the pre-slab line derives at the real rate


def test_gst_bps_is_derived_from_stated_lines_not_hardcoded() -> None:
    """C-018/R-1: the pipeline must derive the GST rate from observed
    (fee, tax) pairs, never assume 1800. Construct stated lines at a
    DIFFERENT, deliberately unrealistic GST rate and confirm infer_slabs
    still validates against it correctly."""
    lines = []
    for i in range(6):
        amount = 100000 + i * 1000
        fee = (amount * 175 + 5000) // 10000
        tax = (fee * 1200 + 5000) // 10000  # 12% GST, not the real 18%
        lines.append(_payment(f"pay_g{i:02d}", amount, fee, tax, "netbanking", 1_780_000_000 + i))

    slabs = infer_slabs(lines)
    nb = [s for s in slabs if s.method == "netbanking"]
    assert len(nb) == 1
    assert nb[0].gst_bps == 1200  # derived from this run's own data, not the real-world 18%
    fee, tax = derive_fee(105000, nb[0])
    assert tax == (fee * 1200 + 5000) // 10000


def test_derive_fee_matches_the_synthetic_formula() -> None:
    slab = FeeSlab(
        method="card",
        period_start=datetime.date(2026, 6, 1),
        period_end=datetime.date(2026, 7, 16),
        inferred_bps=200,
        gst_bps=1800,
        sample_size=10,
        reproduces_all_stated=True,
    )
    fee, tax = derive_fee(499900, slab)
    assert fee == 9998  # round_half_up(499900*200, 10000) = round_half_up(99980000,10000)=9998
    assert tax == 1800  # round_half_up(9998*1800, 10000) = round_half_up(17996400,10000)=1800
