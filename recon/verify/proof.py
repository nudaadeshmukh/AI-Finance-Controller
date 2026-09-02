"""`ArithmeticProof` construction — §14.

Decides `closes` from the equation's `delta` *and* from whether the proposal
was even verifiable in the first place (exactly one bank transaction, no
payment with an unresolved fee/tax) — a coincidental `delta == 0` on an
unverifiable proposal must never read as `closes=True`.

`allowed_delta` (§13.6) is the ONLY tolerance concept here — the derived-fee
rounding allowance, computed by the caller as
`AMOUNT_DELTA_PAISE_PER_DERIVED_LINE * (derived lines in this proposal)`,
never a flat constant. A proposal with zero derived lines gets
`allowed_delta == 0`, so a stated-fee settlement still must close exactly.
`tolerance_applied` reports how much of that budget was actually spent
(`0` whenever `delta` was already `0`, even if a nonzero budget existed) —
it is what `results.json` surfaces so a nonzero value is always visible.
"""

from __future__ import annotations

from recon.models.pipeline import ArithmeticProof


def build_proof(
    gross: int,
    fees: int,
    tax: int,
    refunds: int,
    expected_net: int,
    observed_net: int,
    *,
    verifiable: bool,
    allowed_delta: int = 0,
) -> ArithmeticProof:
    delta = expected_net - observed_net
    closes = verifiable and abs(delta) <= allowed_delta
    tolerance_applied = abs(delta) if closes and delta != 0 else 0
    return ArithmeticProof(
        gross=gross,
        fees=fees,
        tax=tax,
        refunds=refunds,
        expected_net=expected_net,
        observed_net=observed_net,
        delta=delta,
        closes=closes,
        tolerance_applied=tolerance_applied,
    )
