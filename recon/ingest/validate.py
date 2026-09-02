"""Pydantic validation of raw adapter dicts — §12.2.

A validation failure is recorded as a `MALFORMED_SOURCE_ROW` exception, never
raised — "a pipeline that dies on row 217 of 400 is useless" (CLAUDE.md rule 10).
"""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

from recon.models.pipeline import Exception_
from recon.models.reasons import REASON_LABELS, ReasonCode
from recon.models.types import RecordKey


def best_effort_key(source_prefix: str, raw: dict, id_field: str, index: int) -> RecordKey:
    """A `record_key` for `raw`, even when validation will fail. Falls back to
    a positional key so two malformed rows in the same source never collide
    on the `exceptions` table's `record_key` primary key.
    """
    value = raw.get(id_field)
    if isinstance(value, str) and value:
        return f"{source_prefix}:{value}"
    return f"{source_prefix}:MALFORMED-{index}"


def validate_row(
    model_cls: type[BaseModel], raw: dict, record_key: RecordKey
) -> tuple[BaseModel, None] | tuple[None, Exception_]:
    """Validate one raw dict into `model_cls`.

    Returns `(model_instance, None)` on success, or `(None, Exception_)` on
    failure — the caller persists the `Exception_` and moves on to the next
    row. Never raises `ValidationError` outward.
    """
    try:
        return model_cls(**raw), None
    except ValidationError as exc:
        first_error = exc.errors()[0]
        field = ".".join(str(part) for part in first_error["loc"]) or "<root>"
        detail = f"{field}: {first_error['msg']}"
        return None, Exception_(
            record_key=record_key,
            reason_code=ReasonCode.MALFORMED_SOURCE_ROW,
            reason_text=f"{REASON_LABELS[ReasonCode.MALFORMED_SOURCE_ROW]} ({detail})",
            passes_tried=[],
            candidates=[],
        )
