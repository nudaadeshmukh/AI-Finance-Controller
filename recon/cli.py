"""Typer CLI - Section 19. `run`, `inject`, `report`, `validate`.

Phase 3: `run` wires acquire -> ingest -> cascade (passes 1-3) and prints a
Rich table of counts plus a per-pass table. Hypothesize and report are wired
in later phases.

Plain ASCII only in help/output text below - this runs in Windows terminals
using the legacy cp1252 codepage by default, which chokes on arrows, section
signs and em dashes (docs/challenges-log.md C-003).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from recon.adapters import get_adapter
from recon.config import db_path_for, load_config
from recon.db.connection import connect
from recon.errors import ConfigurationError, SourceUnavailable
from recon.ingest import ingest
from recon.match import run_cascade

app = typer.Typer(
    name="recon",
    help="Multi-source financial reconciliation pipeline (Razorpay AI Buildathon 2026).",
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)

_ALL_RUN_IDS = ["clean-august", "heavy-refunds", "holiday-skew", "high-ambiguity"]


def _resolve_run_ids(dataset: str) -> list[str]:
    """§8.3.1: the pipeline reads nothing from manifest.json except run_id and
    label. Read here only to resolve `--dataset all` into the concrete list.
    """
    if dataset != "all":
        return [dataset]
    manifest_path = Path("data") / "manifest.json"
    if not manifest_path.is_file():
        return _ALL_RUN_IDS
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return [entry["run_id"] for entry in manifest]


_DATASET_HELP = "clean-august | heavy-refunds | holiday-skew | high-ambiguity | all"
_FRESH_HELP = "Discard any existing database for this run first."
_NO_LLM_HELP = "Skip the LLM hypothesis stage entirely."
_QUIET_HELP = "Suppress the live progress table."


@app.command()
def run(
    dataset: Annotated[str, typer.Option(help=_DATASET_HELP)] = "clean-august",
    no_llm: Annotated[bool, typer.Option("--no-llm", help=_NO_LLM_HELP)] = False,
    source: Annotated[str, typer.Option(help="fixture | razorpay")] = "fixture",
    db: Annotated[str | None, typer.Option(help="Override the SQLite path.")] = None,
    out: Annotated[str | None, typer.Option(help="Override the results.json output path.")] = None,
    fresh: Annotated[bool, typer.Option("--fresh", help=_FRESH_HELP)] = False,
    quiet: Annotated[bool, typer.Option("--quiet", help=_QUIET_HELP)] = False,
) -> None:
    """Run the full pipeline: acquire, ingest, cascade, (hypothesize), verify, report."""
    del no_llm, out, quiet  # accepted now for the full §19 contract; used from Phase 3+ onward
    config = load_config()

    for run_id in _resolve_run_ids(dataset):
        console.print(f"[bold]{run_id}[/bold]")
        db_path = Path(db) if db else db_path_for(run_id, config)
        if fresh and db_path.exists():
            db_path.unlink()

        try:
            adapter = get_adapter(source, run_id=run_id)  # type: ignore[arg-type]
            conn = connect(db_path)
            try:
                report = ingest(adapter, conn)
                cascade_result = run_cascade(conn, run_id)
            finally:
                conn.close()
        except SourceUnavailable as exc:
            err_console.print(f"[red]SourceUnavailable:[/red] {exc}")
            raise typer.Exit(code=2) from exc
        except ConfigurationError as exc:
            err_console.print(f"[red]ConfigurationError:[/red] {exc}")
            raise typer.Exit(code=1) from exc

        table = Table(title=f"Ingested ({run_id})")
        table.add_column("source")
        table.add_column("count", justify="right")
        for field_name in ("orders", "recon_lines", "bank_txns", "ledger_entries"):
            table.add_row(field_name, str(getattr(report, field_name)))
        table.add_row("malformed", str(report.malformed))
        console.print(table)
        console.print(
            f"Ingested: orders {report.orders} | recon_lines {report.recon_lines} | "
            f"bank_txns {report.bank_txns} | ledger_entries {report.ledger_entries}"
        )

        pass_table = Table(title=f"Cascade ({run_id})")
        pass_table.add_column("pass")
        pass_table.add_column("in", justify="right")
        pass_table.add_column("matched", justify="right")
        pass_table.add_column("deferred", justify="right")
        pass_table.add_column("ms", justify="right")
        for ps in cascade_result.passes:
            pass_table.add_row(
                ps.name, str(ps.in_count), str(ps.matched), str(ps.deferred), str(ps.runtime_ms)
            )
        console.print(pass_table)
        console.print(
            f"Matched {cascade_result.total_matched}/{report.recon_lines}   "
            f"Cascade {cascade_result.runtime_ms}ms"
        )
        console.print(
            "[yellow]STUB[/yellow] hypothesize/verify-remaining/report "
            "not implemented until Phase 4+"
        )

    raise typer.Exit(code=0)


_SCENARIO_HELP = "llm-hallucination | llm-unavailable | prompt-injection"


@app.command()
def inject(
    scenario: Annotated[str, typer.Option(help=_SCENARIO_HELP)],
) -> None:
    """Run a failure-injection scenario - section 24."""
    console.print(f"STUB inject: scenario={scenario!r} -- not implemented until Phase 6")
    raise typer.Exit(code=0)


@app.command()
def report(
    dataset: Annotated[str, typer.Option(help="Run id, e.g. clean-august")] = "clean-august",
    html: Annotated[bool, typer.Option("--html", help="Also emit the static HTML report.")] = False,
) -> None:
    """Re-emit results.json (and optionally the HTML report) for an existing run."""
    console.print(f"STUB report: dataset={dataset!r} html={html} -- not implemented until Phase 5")
    raise typer.Exit(code=0)


@app.command()
def validate(
    dataset: Annotated[str, typer.Option(help="Run id, or 'all'")] = "all",
) -> None:
    """Dataset invariant checks - wired into CI."""
    console.print(f"STUB validate: dataset={dataset!r} -- not implemented yet")
    raise typer.Exit(code=0)
