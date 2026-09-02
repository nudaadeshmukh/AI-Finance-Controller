"""Tolerance constants, each with a comment justifying its value — §13.6.

Fixed before measurement, never widened after (CLAUDE.md rule 7). If you find
yourself wanting to widen one to lift a match rate, stop and say so instead —
that impulse is the thing the rule exists to catch.
"""

from __future__ import annotations

# Amount delta: NOT a flat constant (§13.6) — a settlement whose member
# payments all carry a *stated* fee must close with delta == 0 exactly, since
# a stated fee cannot drift. Only a fee recovered by fee_reversal can be off,
# by at most 1 paise on the fee and 1 on the tax, since both round half-up
# independently. The per-settlement budget is therefore
# `AMOUNT_DELTA_PAISE_PER_DERIVED_LINE * (number of member payments whose fee
# was DERIVED)` — computed in verify/__init__.py, not a lookup here.
AMOUNT_DELTA_PAISE_PER_DERIVED_LINE = 2

# UTR suffix truncation: an observed bank formatting defect drops the last
# few digits of the UTR in some description strings. 2 digits covers the
# defect actually observed in the frozen datasets (manifest.json's
# truncated_utr count is 2 per run) without opening the door to guessing a
# whole UTR from a short prefix. Requires a UNIQUE prefix match — see
# match/tolerance.py; a truncated UTR matching two settlements is ambiguity,
# not a match.
UTR_TRUNCATION_DIGITS = 2

# Ledger posting lag: accountants book same-day or next-day, per observed
# practice (§8.4: "Late ledger posting ~8% ... booked one day after the
# sale"). This only ever widens which ledger ENTRY gets attached to an
# already-resolved group for display — it never affects the closing equation
# or a recon-line match decision.
LEDGER_LAG_DAYS = 1
