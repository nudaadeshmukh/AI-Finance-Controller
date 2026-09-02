"""`score()` — the ONLY module that opens `answer_key.json`, and only after
matching completes (§4.6, CLAUDE.md rule 6, `tests/test_answer_key_seal.py`).
Implemented in Phase 5.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pydantic import BaseModel


class ScoreReport(BaseModel):
    """Return type of `score()` (§20.4). Fields are provisional, sized to
    §17.1's metric definitions and the `summary`/`ceiling` objects in §18's
    `results.json` contract (the parts that require the sealed answer key,
    which only this module may open — §4.6). `extra="forbid"` so a typo'd
    field fails loudly rather than silently validating. Revise when `score()`
    is actually implemented in Phase 5.
    """

    model_config = {"extra": "forbid"}

    records_processed: int = 0
    matched: int = 0
    match_rate: float = 0.0
    match_precision: float = 0.0
    false_matches: int = 0
    unresolved: int = 0
    excluded: int = 0
    runtime_ms_cascade: int = 0
    runtime_ms_llm: int = 0
    throughput_per_sec_cascade: float = 0.0
    ceiling_resolvable: int = 0  # count of answer_key entries with resolvable: true
    ceiling_rate: float = 0.0


def score(db: sqlite3.Connection, answer_key: Path) -> ScoreReport:
    """§20.4. Implemented in Phase 5."""
    raise NotImplementedError
