"""`emit_results()` — the `results.json` emitter, §18, §20.4. Implemented in
Phase 5.
"""

from __future__ import annotations

from pathlib import Path

from recon.report.scoring import ScoreReport


def emit_results(report: ScoreReport, path: Path) -> None:
    """§20.4. Implemented in Phase 5."""
    raise NotImplementedError
