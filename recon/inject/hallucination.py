"""`llm-hallucination` failure injection — §24.

A `ChatModel` that ignores the source data entirely and returns a single
confident, plausible-sounding proposal grouping every record key it can see —
with fabricated `claimed_arithmetic`. The verifier recomputes the closing
equation from source and the delta is non-zero, so the proposal is rejected
and its members go to exceptions with this reasoning preserved (§24, §15.6).

The same model backs `--scenario prompt-injection`, with a reasoning string
that echoes the instruction planted in the data — behaviourally the two are
identical to the verifier, which is the point.
"""

from __future__ import annotations

import json
import re

_KEY_RE = re.compile(r'"(recon:[A-Za-z0-9_]+|bank:[A-Za-z0-9_]+|order:[A-Za-z0-9_]+)"')

_DEFAULT_REASONING = (
    "These payments and the bank credit clearly form one settlement - the "
    "amounts align once the unrecorded reversal fee is applied."
)


class HallucinatingModel:
    """See module docstring. `reasoning` overrides the canned explanation."""

    def __init__(self, reasoning: str | None = None) -> None:
        self.reasoning = reasoning or _DEFAULT_REASONING
        self.calls = 0

    def complete(self, system: str, user: str, timeout_s: int) -> str:
        del system, timeout_s
        self.calls += 1
        keys = sorted(set(_KEY_RE.findall(user)))
        return json.dumps(
            {
                "proposed_group": keys,
                "reasoning": self.reasoning,
                "claimed_arithmetic": {"expected_net": 0, "observed_net": 0},
                "confidence": "high",
            }
        )
