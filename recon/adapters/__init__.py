"""Adapter package aggregator — `get_adapter()`, §20.4."""

from __future__ import annotations

from typing import Literal

from recon.adapters.base import SourceAdapter
from recon.adapters.fixture import FixtureAdapter
from recon.adapters.razorpay import RazorpayAdapter
from recon.errors import ConfigurationError


def get_adapter(kind: Literal["fixture", "razorpay"], **kw: object) -> SourceAdapter:
    """§20.4. `kind="fixture"` expects `run_id=...` (and optionally
    `data_root=...`); `kind="razorpay"` accepts and ignores any kwargs
    (documented stub, §27).
    """
    if kind == "fixture":
        return FixtureAdapter(**kw)  # type: ignore[arg-type]
    if kind == "razorpay":
        return RazorpayAdapter(**kw)
    raise ConfigurationError(f"unknown adapter kind: {kind!r}")
