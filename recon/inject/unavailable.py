"""`llm-unavailable` failure injection — §24.

A `ChatModel` whose every call raises `LLMUnavailable`, simulating a
connection-level outage (§24's "Timeout / connection error" detection
signal) — not a single call's rate limit, which is `LLMCallFailed` and
skips just that cluster (docs/challenges-log.md C-017). The hypothesis
stage catches this on the first cluster, records
`HYPOTHESIS_LAYER_UNAVAILABLE`, and the pipeline completes with the full
deterministic result intact (§15.4, §24).
"""

from __future__ import annotations

from recon.hypothesize.client import LLMUnavailable


class UnavailableModel:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, system: str, user: str, timeout_s: int) -> str:
        del system, user, timeout_s
        self.calls += 1
        raise LLMUnavailable("injected: simulated API failure / 429")
