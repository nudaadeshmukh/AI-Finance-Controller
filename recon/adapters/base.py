"""`SourceAdapter` protocol — §20.4. Adapters return raw dicts, not models;
validation belongs to `ingest/`, so there is exactly one place a malformed row
is handled.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol


class SourceAdapter(Protocol):
    def orders(self) -> Iterator[dict]: ...
    def recon_lines(self) -> Iterator[dict]: ...
    def bank_txns(self) -> Iterator[dict]: ...
    def ledger_entries(self) -> Iterator[dict]: ...
