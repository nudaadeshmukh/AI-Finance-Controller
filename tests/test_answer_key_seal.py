"""§4.6, PROJECT_RULES.md rule 6 — only `report/scoring.py` may open `answer_key.json`,
and only after matching completes. No other module reads it, references it, or
imports from a module that does.

The failure mode this guards is not malice — it is a debugging session on
day 3 with a stuck match rate, where eyeballing the key "just to see" feels
harmless. It isn't: it would invalidate the measured numbers with no way to
tell from the outside. `recon/generate/` is exempt — it is the origin of the
answer key and lives outside the pipeline's dependency graph entirely (§3.3),
never imported by anything this test protects.

Stated limitation (docs/challenges-log.md C-016): this is a textual grep for
the literal string "answer_key", not an import-graph analysis — it verifies
that no file *names* the sealed key, not that no code path could reach it
some other way (e.g. via a passed-in path or a re-exported constant). A
docstring merely mentioning the filename is enough to trip it.
"""

from __future__ import annotations

from pathlib import Path

RECON_ROOT = Path(__file__).parent.parent / "recon"
ALLOWED_FILE = RECON_ROOT / "report" / "scoring.py"
EXEMPT_DIR = RECON_ROOT / "generate"


def test_only_scoring_module_references_answer_key() -> None:
    violations: list[str] = []
    for py_file in RECON_ROOT.rglob("*.py"):
        if py_file == ALLOWED_FILE or py_file.is_relative_to(EXEMPT_DIR):
            continue
        text = py_file.read_text(encoding="utf-8")
        if "answer_key" in text:
            violations.append(str(py_file.relative_to(RECON_ROOT.parent)))

    assert not violations, (
        "Only report/scoring.py may reference answer_key.json, and only after "
        "matching completes (§4.6). Violations:\n" + "\n".join(violations)
    )
