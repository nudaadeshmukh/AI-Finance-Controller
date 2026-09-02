"""The closing equation — §13.1 — implemented in exactly ONE place in the
whole codebase.

    Σ(order.amount) − Σ(payment.fee) − Σ(payment.tax)
                    − Σ(refund.debit) − Σ(adjustment.debit)
    = bank.credit

`ArithmeticProof` (§14) has a single `refunds` field, not separate
refund/adjustment fields. `refund.debit` and `adjustment.debit` are both
net-reducing debit lines with no fee/tax component of their own, so they are
summed together into `refunds` for the proof — a naming choice forced by the
fixed schema, not a simplification of the equation: both terms are still
subtracted exactly as written above.

`gross` is `Σ(order.amount)` for orders being PAID in this settlement — i.e.
orders referenced by a `payment`-type recon line — never orders referenced
only by a `refund` line. A refund's `order_id` links back to whichever order
it refunds, which very often paid (and settled) in an *earlier*, unrelated
cycle; that order's full amount was already credited to gross when *that*
settlement closed. Summing it again here would double-count it and corrupt
every mixed (refund/adjustment-bearing) settlement's closure. This function
derives the payment-order set itself from `recon_lines` rather than trusting
whatever `orders` list a caller passes in, so an extra, informational,
refund-linked order in that list can never leak into the sum.
"""

from __future__ import annotations

from recon.models.sources import Order, ReconLine


def compute_closing_equation(
    orders: list[Order], recon_lines: list[ReconLine]
) -> tuple[int, int, int, int, int]:
    """Pure sum over already-read source rows. Never touches the database.

    Returns `(gross, fees, tax, refunds, expected_net)`.

    A payment line with `fee`/`tax` still `None` (unresolved — no slab has
    derived it) contributes 0 to the sum here. This function never decides
    whether that makes a proposal unverifiable — it only sums what it is
    given. `verify()` is responsible for recognising a `None` fee/tax and
    forcing `closes=False` regardless of what this arithmetic returns.
    """
    payment_order_ids = {
        line.order_id for line in recon_lines if line.type == "payment" and line.order_id
    }
    orders_by_id = {order.order_id: order for order in orders}
    gross = sum(
        orders_by_id[order_id].amount
        for order_id in payment_order_ids
        if order_id in orders_by_id
    )
    fees = sum((line.fee or 0) for line in recon_lines if line.type == "payment")
    tax = sum((line.tax or 0) for line in recon_lines if line.type == "payment")
    refunds = sum(line.debit for line in recon_lines if line.type in ("refund", "adjustment"))
    expected_net = gross - fees - tax - refunds
    return gross, fees, tax, refunds, expected_net
