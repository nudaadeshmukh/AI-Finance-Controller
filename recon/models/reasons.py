"""`ReasonCode` — the closed enum from §20.3, plus its UI labels.

Adding a code requires a UI label here and a test (§20.3). This enum is the
complete set — data defects, business ambiguity, and LLM-layer failures all map
into it. Nothing outside this file invents a reason code (CLAUDE.md rule 12).
"""

from __future__ import annotations

from enum import StrEnum


class ReasonCode(StrEnum):
    AMBIGUOUS_DUPLICATE = "AMBIGUOUS_DUPLICATE"
    CROSS_PERIOD_UTR = "CROSS_PERIOD_UTR"
    CONTRADICTORY_LEDGER = "CONTRADICTORY_LEDGER"
    MALFORMED_SOURCE_ROW = "MALFORMED_SOURCE_ROW"
    NOT_A_SETTLEMENT = "NOT_A_SETTLEMENT"
    PROOF_DOES_NOT_CLOSE = "PROOF_DOES_NOT_CLOSE"
    HYPOTHESIS_TIMEOUT = "HYPOTHESIS_TIMEOUT"
    HYPOTHESIS_MALFORMED = "HYPOTHESIS_MALFORMED"
    HYPOTHESIS_LAYER_UNAVAILABLE = "HYPOTHESIS_LAYER_UNAVAILABLE"
    NO_CANDIDATE = "NO_CANDIDATE"


# §20.3's "Meaning" column, verbatim — the label shown in the frontend's
# Exception List (§23.4) and record drawer (§23.5).
REASON_LABELS: dict[ReasonCode, str] = {
    ReasonCode.AMBIGUOUS_DUPLICATE: "Two candidates, no distinguishing reference",
    ReasonCode.CROSS_PERIOD_UTR: "Settlement outside export window",
    ReasonCode.CONTRADICTORY_LEDGER: "Source data internally inconsistent",
    ReasonCode.MALFORMED_SOURCE_ROW: "Failed schema validation at ingest",
    ReasonCode.NOT_A_SETTLEMENT: "Unrelated bank debit — excluded, not an exception",
    ReasonCode.PROOF_DOES_NOT_CLOSE: "Verifier rejected the proposal",
    ReasonCode.HYPOTHESIS_TIMEOUT: "LLM exceeded 20s",
    ReasonCode.HYPOTHESIS_MALFORMED: "Invalid JSON after one repair retry",
    ReasonCode.HYPOTHESIS_LAYER_UNAVAILABLE: "API down; pipeline still completed",
    ReasonCode.NO_CANDIDATE: "Cascade and LLM exhausted",
}
