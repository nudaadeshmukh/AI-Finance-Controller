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


def test_derive_fee_matches_the_synthetic_formula() -> None:
    slab = FeeSlab(
        method="card",
        period_start=datetime.date(2026, 6, 1),
        period_end=datetime.date(2026, 7, 16),
        inferred_bps=200,
        sample_size=10,
        reproduces_all_stated=True,
    )
    fee, tax = derive_fee(499900, slab)
    assert fee == 9998  # round_half_up(499900*200, 10000) = round_half_up(99980000,10000)=9998
    assert tax == 1800  # round_half_up(9998*1800, 10000) = round_half_up(17996400,10000)=1800
