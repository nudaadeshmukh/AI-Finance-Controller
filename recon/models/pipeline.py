"""`MatchProposal`, `ArithmeticProof`, `CascadeState` — §20.2, and `Exception_`.

`Exception_` is a data-defect/business-ambiguity *record*, not a Python
exception (PROJECT_RULES.md rule 10) — it belongs alongside the other pipeline output
models rather than in `errors.py`, which holds only the three real exception
classes. Not explicitly assigned to a file in §3.2's folder comments; grouped
here as the other pipeline-stage output type.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from recon.models.facts import DerivedFacts
from recon.models.reasons import ReasonCode
from recon.models.types import GroupId, RecordKey, RunId


class ArithmeticProof(BaseModel):
    """§14 — the verifier's output. `closes` is the sole gate on `commit()`."""

    gross: int
    fees: int
    tax: int
    refunds: int
    expected_net: int
    observed_net: int
    delta: int  # expected − observed; must be 0 (within any applied tolerance)
    closes: bool
    tolerance_applied: int = 0  # nonzero is SURFACED in the UI


class MatchProposal(BaseModel):
    """A candidate group, from either the cascade or the LLM — §20.2.

    `proof` is filled by `verify/`, never by the proposer. Neither origin has
    any special standing: both traverse identical verification code (§14).
    """

    group_id: GroupId
    member_keys: list[RecordKey]
    pass_name: str
    origin: Literal["cascade", "llm"]
    proof: ArithmeticProof | None = None


class Exception_(BaseModel):
    """A record that did not reach a closing proof — §11, §20.2.

    A record is either matched with a closing arithmetic proof, or it is an
    `Exception_` with a specific reason. There is no third state (PROJECT_RULES.md
    rule 4).
    """

    record_key: RecordKey
    reason_code: ReasonCode
    reason_text: str
    passes_tried: list[str]
    candidates: list[RecordKey] = []


class CascadeState(BaseModel):
    """The residual carried from pass to pass — §12.3, §20.2."""

    run_id: RunId
    unmatched_recon: list[RecordKey]
    unmatched_bank: list[RecordKey]
    unmatched_ledger: list[RecordKey]
    derived: DerivedFacts
