"""Strict JSON -> `Hypothesis` — §15.2. Prose is a parse failure.

The model is instructed to return a bare JSON object. We tolerate exactly one
cosmetic deviation - a surrounding ```json ... ``` fence - and nothing else:
leading/trailing prose, multiple objects, or a schema violation all raise
`HypothesisParseError`, which the stage maps to `HYPOTHESIS_MALFORMED` (§15.4)
after one repair retry.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ValidationError

from recon.models.types import RecordKey


class Hypothesis(BaseModel):
    """§15.2. The LLM's proposal shape — `claimed_arithmetic` has no
    functional purpose; it is compared for logging, never used (§14, §15.2).
    """

    proposed_group: list[RecordKey]
    reasoning: str  # displayed in UI, never acted on
    claimed_arithmetic: dict[str, int]  # compared, NEVER used
    confidence: Literal["low", "medium", "high"]  # displayed, gates nothing


class HypothesisParseError(ValueError):
    """Raised when a model response is not a single JSON object matching
    `Hypothesis`. Maps to `HYPOTHESIS_MALFORMED` (§15.4).
    """


def _strip_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text[text.find("\n") + 1 :] if "\n" in text else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def parse_hypothesis(raw: str) -> Hypothesis:
    """§15.2. Strict: the response must be one JSON object and nothing else."""
    text = _strip_fence(raw)
    if not text:
        raise HypothesisParseError("empty response")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HypothesisParseError(f"not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise HypothesisParseError(f"expected a JSON object, got {type(payload).__name__}")
    try:
        return Hypothesis.model_validate(payload)
    except ValidationError as exc:
        raise HypothesisParseError(f"schema violation: {exc}") from exc
