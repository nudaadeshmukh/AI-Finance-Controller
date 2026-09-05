"""The matcher's OWN copy of `round_half_up` — PROJECT_RULES.md rule 2.

This duplication is deliberate. `match/`, `hypothesize/` and `verify/` must
never import from `recon/generate/`, even for a helper as small as this one —
that single import would silently void the entire fee-reversal result.
`tests/test_firewall.py` enforces this.

Not called anywhere in passes 1-3 (which only use stated fee/tax); exists now
because Phase 3's "Implement" list requires it, and Phase 4's
`fee_reversal.py` needs it to recover the synthetic bps rate.
"""

from __future__ import annotations


def round_half_up(numerator: int, denominator: int) -> int:
    """Half-up rounding of `numerator / denominator`, matching the synthetic
    fee schedule's own convention (§10): `fee = round_half_up(amount * bps,
    10000)`. Both inputs are non-negative in this domain (money, basis
    points) — no fractional/negative handling is needed or provided.
    """
    if denominator <= 0:
        raise ValueError(f"denominator must be positive, got {denominator}")
    if numerator < 0:
        raise ValueError(f"numerator must be non-negative, got {numerator}")
    return (numerator + denominator // 2) // denominator
