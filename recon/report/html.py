"""`emit_html()` — a static, single-file HTML report rendered from an
already-emitted `results.json` (§12.6, §20.4).

This is the terminal-free artifact a reviewer opens without `npm install` —
not the Vite/React frontend (that is Phase 7, `reference/design.md`). It
reads `results.json` and nothing else, so it can never disagree with the
JSON the frontend consumes. Rupee formatting happens here and in
`frontend/src/lib/format.ts` only (PROJECT_RULES.md rule 1).
"""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _rupees(paise: int | None) -> str:
    """Paise int -> "12,34,567.89" (Indian grouping). One of exactly two
    places money becomes rupees (PROJECT_RULES.md rule 1)."""
    if paise is None:
        return "--"
    sign = "-" if paise < 0 else ""
    whole, frac = divmod(abs(paise), 100)
    digits = str(whole)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        parts.insert(0, head)
        digits = ",".join([*parts, tail])
    return f"{sign}{digits}.{frac:02d}"


def _pct(rate: float | None) -> str:
    return "--" if rate is None else f"{rate * 100:.1f}%"


def emit_html(results: Path, out: Path) -> None:
    """§20.4. Render `results` (a `results.json` path) to a static HTML file
    at `out`."""
    doc = json.loads(Path(results).read_text(encoding="utf-8"))
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    env.filters["rupees"] = _rupees
    env.filters["pct"] = _pct
    html = env.get_template("report.html.j2").render(doc=doc)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(html, encoding="utf-8")
