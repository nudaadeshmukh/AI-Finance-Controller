"""`score()` — the ONLY module that opens `answer_key.json`, and only after
matching completes (§4.6, CLAUDE.md rule 6, `tests/test_answer_key_seal.py`).
Implemented in Phase 5.

`check_scope_only_accounted()` was pulled forward into Phase 4, a phase
early, acknowledged as a deliberate exception to "do not build ahead" — the
same pattern as `match/classify.py`'s `has_ambiguous_adjustment()` in Phase 3.
§14.1/C-008 requires this invariant to be enforced at runtime, not only by
the test suite: `score()` is where it lives, since it's the pipeline's exit
gate before `results.json` is emitted (the same place, and same spirit, as
rule 6's answer-key gate) — but it needs no answer key itself, so it's
implemented now rather than deferred with the rest of `score()`.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pydantic import BaseModel

from recon.db import queries
from recon.errors import ScoringError
from recon.models.types import RecordKey


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


def check_scope_only_accounted(db: sqlite3.Connection) -> None:
    """§14.1/C-008's runtime invariant, enforced here rather than only in
    CI. Every `record_key` appearing in any closed group's
    `proof_json.scope_only_keys` must, by the time this runs (end of run,
    after `classify_residual`), have a row in `exceptions`. If one doesn't,
    the pipeline refuses to score or emit `results.json` — CLAUDE.md rule 4
    ("no third state") enforced at the exit gate, not just documented.
    """
    exception_keys: set[RecordKey] = {
        row["record_key"] for row in db.execute(queries.SELECT_EXCEPTION_RECORD_KEYS)
    }
    unaccounted: list[tuple[str, str]] = []  # (group_id, record_key)
    for row in db.execute(queries.SELECT_CLOSED_MATCH_GROUP_PROOFS):
        proof = json.loads(row["proof_json"])
        for scope_only_key in proof.get("scope_only_keys", []):
            if scope_only_key not in exception_keys:
                unaccounted.append((row["group_id"], scope_only_key))
    if unaccounted:
        detail = ", ".join(f"{key!r} (group {group_id!r})" for group_id, key in unaccounted)
        raise ScoringError(
            "arithmetic_scope invariant violated (§14.1/C-008): the following "
            f"scope-only keys were counted toward a closed proof but have no "
            f"exceptions row: {detail}"
        )


def score(db: sqlite3.Connection, answer_key: Path) -> ScoreReport:
    """§20.4. Implemented in Phase 5."""
    check_scope_only_accounted(db)
    raise NotImplementedError
