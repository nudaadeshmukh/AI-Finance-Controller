"""Reads `data/<run>/sources/*.json` and returns iterators of raw dicts —
§20.4. Each source file is loaded eagerly on the method call (not lazily on
first iteration), so a missing/unreadable file surfaces as `SourceUnavailable`
immediately, before any per-source ingest transaction begins.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from recon.errors import SourceUnavailable


class FixtureAdapter:
    """`SourceAdapter` reading the frozen fixtures at `data/<run_id>/sources/`."""

    def __init__(self, run_id: str, data_root: Path | str = Path("data")) -> None:
        self._sources_dir = Path(data_root) / run_id / "sources"

    def orders(self) -> Iterator[dict]:
        return self._read("orders.json")

    def recon_lines(self) -> Iterator[dict]:
        return self._read("recon_lines.json")

    def bank_txns(self) -> Iterator[dict]:
        return self._read("bank_statement.json")

    def ledger_entries(self) -> Iterator[dict]:
        return self._read("ledger_entries.json")

    def _read(self, filename: str) -> Iterator[dict]:
        path = self._sources_dir / filename
        try:
            raw_text = path.read_text(encoding="utf-8")
            rows = json.loads(raw_text)
        except OSError as exc:
            raise SourceUnavailable(f"fixture source unreadable: {path}") from exc
        except json.JSONDecodeError as exc:
            raise SourceUnavailable(f"fixture source is not valid JSON: {path}") from exc
        if not isinstance(rows, list):
            raise SourceUnavailable(f"fixture source is not a JSON array: {path}")
        return iter(rows)
