"""Hypothesize package aggregator — `propose()`, §12.4, §15, §20.4.

Never raises. Returns `[]` when the client is None, the residual is empty, or
the API is unavailable (§15). Implemented in Phase 6.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from recon.models.facts import DerivedFacts
from recon.models.pipeline import MatchProposal
from recon.models.types import RecordKey

if TYPE_CHECKING:
    from groq import Groq


def propose(
    residual: list[RecordKey],
    db: sqlite3.Connection,
    facts: DerivedFacts,
    client: Groq | None,
    *,
    model: str = "llama-3.3-70b-versatile",
    timeout_s: int = 20,
) -> list[MatchProposal]:
    """§20.4. Implemented in Phase 6."""
    raise NotImplementedError
