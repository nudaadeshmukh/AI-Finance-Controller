"""Typer CLI - Section 19. `run`, `inject`, `report`, `validate`.

Phase 5: `run` wires acquire -> ingest -> cascade -> scoring -> results.json
(+ optional HTML). `report` re-emits those artifacts from an existing run.db
without re-running the cascade. Hypothesize (LLM) is still Phase 6.

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
from recon.config import db_path_for, load_config, out_path_for
from recon.db.connection import connect
from recon.errors import ConfigurationError, ScoringError, SourceUnavailable
from recon.hypothesize import LLMStageResult, run_hypothesis_stage
from recon.hypothesize.client import build_chat_model
from recon.ingest import ingest
from recon.inject import InjectionReport, run_injection
from recon.match import CascadeResult, run_cascade
from recon.report.baseline import compute_baseline
from recon.report.html import emit_html
from recon.report.results import emit_results
from recon.report.scoring import check_scope_only_accounted, score, sealed_key_for

app = typer.Typer(
    name="recon",
    help="Multi-source financial reconciliation pipeline (Razorpay AI Buildathon 2026).",
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)

_ALL_RUN_IDS = ["clean-august", "heavy-refunds", "holiday-skew", "high-ambiguity"]


def _resolve_run_meta(dataset: str) -> list[dict]:
    """Resolve `--dataset` to a list of {run_id, label, seed}.

    §8.3.1 says the pipeline reads only `run_id` and `label` from
    `manifest.json`; `seed` is read here too, solely for `results.json`'s
    §18 provenance block (documented deviation - see docs/project-progress.md).
    """
    manifest_path = Path("data") / "manifest.json"
    entries: list[dict] = []
    if manifest_path.is_file():
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_id = {e["run_id"]: e for e in entries}

    run_ids = _ALL_RUN_IDS if dataset == "all" else [dataset]
    out: list[dict] = []
    for run_id in run_ids:
        entry = by_id.get(run_id, {})
        out.append(
            {
                "run_id": run_id,
                "label": entry.get("label", run_id),
                "seed": int(entry.get("seed", 0)),
            }
        )
    return out


def _cascade_json_path(run_id: str, config) -> Path:
    return db_path_for(run_id, config).parent / "cascade.json"


def _residual_state(conn, run_id: str, cascade_result: CascadeResult):
    """Rebuild the post-cascade residual as a CascadeState for the LLM stage —
    `run_cascade` returns counts, not the leftover keys."""
    from recon.db import queries
    from recon.models.pipeline import CascadeState

    return CascadeState(
        run_id=run_id,
        unmatched_recon=[
            r["record_key"] for r in conn.execute(queries.SELECT_UNMATCHED_RECON_KEYS)
        ],
        unmatched_bank=[],
        unmatched_ledger=[],
        derived=cascade_result.derived,
    )


def _run_llm_stage(
    conn, run_id: str, cascade_result: CascadeResult, config, *, no_llm: bool
) -> LLMStageResult | None:
    """§12.4. Skipped entirely for `--no-llm` or when no GROQ_API_KEY is set —
    in both cases the deterministic run is already complete."""
    if no_llm:
        return None
    chat = build_chat_model(config.groq_api_key, config.recon_llm_model)
    if chat is None:
        console.print("[yellow]GROQ_API_KEY absent; skipping LLM stage.[/yellow]")
        return None
    state = _residual_state(conn, run_id, cascade_result)
    result = run_hypothesis_stage(
        conn, state, chat,
        model=config.recon_llm_model, timeout_s=config.recon_llm_timeout_s,
    )
    if result.layer_unavailable:
        err_console.print(
            "[yellow]LLM layer unavailable; pipeline completed "
            "(HYPOTHESIS_LAYER_UNAVAILABLE).[/yellow]"
        )
    console.print(
        f"LLM: {result.records_resolved} resolved / {result.hypotheses_proposed} proposed / "
        f"{result.hypotheses_rejected_by_verifier} rejected by verifier "
        f"({result.clusters} clusters, {result.runtime_ms}ms)"
    )
    return result


_DATASET_HELP = "clean-august | heavy-refunds | holiday-skew | high-ambiguity | all"
_FRESH_HELP = "Discard any existing database for this run first."
_NO_LLM_HELP = "Skip the LLM hypothesis stage entirely."
_QUIET_HELP = "Suppress the live progress table."


def _emit_artifacts(
    conn,
    run_meta: dict,
    cascade_result: CascadeResult,
    config,
    *,
    out_override: str | None,
    html: bool,
    llm: LLMStageResult | None = None,
) -> dict:
    """Shared by `run` and `report`: scope-only gate -> score -> baseline ->
    results.json (+ optional HTML). Returns the summary dict written."""
    run_id = run_meta["run_id"]
    check_scope_only_accounted(conn)  # §14.1/C-008 exit gate - raises ScoringError

    sealed_key = sealed_key_for(run_id)
    score_report = score(conn, sealed_key) if sealed_key is not None else None
    if score_report is None:
        err_console.print(f"[yellow]No sealed key for {run_id}; metrics omitted (S12.6).[/yellow]")

    baseline = compute_baseline(conn)
    out_path = Path(out_override) if out_override else out_path_for(run_id, config)
    emit_results(
        conn,
        score_report,
        baseline,
        cascade_result,
        cascade_result.derived,
        out_path,
        run_id=run_id,
        label=run_meta["label"],
        seed=run_meta["seed"],
        llm=llm,
    )
    if html:
        emit_html(out_path, out_path.parent / "report.html")

    doc = json.loads(out_path.read_text(encoding="utf-8"))
    return {"summary": doc["summary"], "baseline": doc["baseline"], "ceiling": doc["ceiling"]}


@app.command()
def run(
    dataset: Annotated[str, typer.Option(help=_DATASET_HELP)] = "clean-august",
    no_llm: Annotated[bool, typer.Option("--no-llm", help=_NO_LLM_HELP)] = False,
    source: Annotated[str, typer.Option(help="fixture | razorpay")] = "fixture",
    db: Annotated[str | None, typer.Option(help="Override the SQLite path.")] = None,
    out: Annotated[str | None, typer.Option(help="Override the results.json output path.")] = None,
    html: Annotated[bool, typer.Option("--html", help="Also emit the static HTML report.")] = False,
    fresh: Annotated[bool, typer.Option("--fresh", help=_FRESH_HELP)] = False,
    quiet: Annotated[bool, typer.Option("--quiet", help=_QUIET_HELP)] = False,
) -> None:
    """Run the full pipeline: acquire, ingest, cascade, (hypothesize), verify, report."""
    del quiet  # accepted for the full S19 contract; live table is always shown for now
    config = load_config()

    for run_meta in _resolve_run_meta(dataset):
        run_id = run_meta["run_id"]
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
                llm_result = _run_llm_stage(conn, run_id, cascade_result, config, no_llm=no_llm)
                _cascade_json_path(run_id, config).write_text(
                    cascade_result.model_dump_json(indent=2), encoding="utf-8"
                )
                summary = _emit_artifacts(
                    conn, run_meta, cascade_result, config,
                    out_override=out, html=html, llm=llm_result,
                )
            finally:
                conn.close()
        except SourceUnavailable as exc:
            err_console.print(f"[red]SourceUnavailable:[/red] {exc}")
            raise typer.Exit(code=2) from exc
        except ConfigurationError as exc:
            err_console.print(f"[red]ConfigurationError:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        except ScoringError as exc:
            err_console.print(f"[red]ScoringError:[/red] {exc}")
            raise typer.Exit(code=3) from exc

        _print_ingest(report, run_id)
        _print_cascade(cascade_result, report.recon_lines, run_id)
        _print_summary(summary)

    raise typer.Exit(code=0)


def _print_ingest(report, run_id: str) -> None:
    table = Table(title=f"Ingested ({run_id})")
    table.add_column("source")
    table.add_column("count", justify="right")
    for field_name in ("orders", "recon_lines", "bank_txns", "ledger_entries"):
        table.add_row(field_name, str(getattr(report, field_name)))
    table.add_row("malformed", str(report.malformed))
    console.print(table)


def _print_cascade(cascade_result: CascadeResult, recon_lines: int, run_id: str) -> None:
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


def _print_summary(summary: dict) -> None:
    s = summary["summary"]
    matched = s["matched"] if s["matched"] is not None else "--"
    false_matches = s["false_matches"] if s["false_matches"] is not None else "--"
    ceiling = summary["ceiling"]["resolvable"]
    console.print(
        f"Matched {matched}/400   False matches {false_matches}   Unresolved {s['unresolved']}"
    )
    console.print(
        f"Baseline {summary['baseline']['matched']}/400   "
        f"Ceiling {ceiling if ceiling is not None else '--'}/400   "
        f"Cascade {s['runtime_ms_cascade']}ms"
    )


_SCENARIO_HELP = "llm-hallucination | llm-unavailable | prompt-injection"


@app.command()
def inject(
    scenario: Annotated[str, typer.Option(help=_SCENARIO_HELP)],
    dataset: Annotated[str, typer.Option(help="Dataset to run the scenario on.")] = "clean-august",
) -> None:
    """Run a failure-injection scenario - section 24.

    Runs the real pipeline (ingest -> cascade) then a doctored hypothesis
    stage, and reports what the system did about the injected failure. The
    invariant across all three scenarios: no LLM-origin match is committed
    without arithmetic that closes against source (S15.6).
    """
    try:
        report: InjectionReport = run_injection(scenario, dataset=dataset)
    except ConfigurationError as exc:
        err_console.print(f"[red]ConfigurationError:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"[bold]inject: {report.scenario} ({report.dataset})[/bold]")
    for line in report.observations:
        console.print(f"  - {line}")
    console.print(
        f"  planted order {report.planted_order_id}: "
        f"matched_by={report.planted_matched_origin or 'none'} "
        f"reason_code={report.planted_reason_code or '-'}"
    )
    console.print(
        f"  unverified LLM matches committed: {report.unverified_llm_matches} "
        "(must be 0)"
    )
    if report.unverified_llm_matches != 0:  # structurally impossible; guard anyway
        err_console.print("[red]INVARIANT VIOLATED: an LLM match closed without a proof[/red]")
        raise typer.Exit(code=3)
    raise typer.Exit(code=0)


@app.command()
def report(
    dataset: Annotated[str, typer.Option(help="Run id, e.g. clean-august")] = "clean-august",
    html: Annotated[bool, typer.Option("--html", help="Also emit the static HTML report.")] = False,
    db: Annotated[str | None, typer.Option(help="Override the SQLite path.")] = None,
    out: Annotated[str | None, typer.Option(help="Override the results.json output path.")] = None,
) -> None:
    """Re-emit results.json (and optionally HTML) from an existing run.db.

    Requires `run` to have been executed first: reads `run.db` plus the
    `cascade.json` sidecar (the learned fee slabs / per-pass timings, which
    are not persisted to any table).
    """
    config = load_config()
    for run_meta in _resolve_run_meta(dataset):
        run_id = run_meta["run_id"]
        db_path = Path(db) if db else db_path_for(run_id, config)
        cascade_json = _cascade_json_path(run_id, config)
        if not db_path.exists() or not cascade_json.is_file():
            err_console.print(
                f"[red]No prior run for {run_id}[/red] - "
                f"run `python -m recon run --dataset {run_id}` first."
            )
            raise typer.Exit(code=1)

        cascade_result = CascadeResult.model_validate_json(
            cascade_json.read_text(encoding="utf-8")
        )
        conn = connect(db_path)
        try:
            summary = _emit_artifacts(
                conn, run_meta, cascade_result, config, out_override=out, html=html
            )
        except ScoringError as exc:
            err_console.print(f"[red]ScoringError:[/red] {exc}")
            raise typer.Exit(code=3) from exc
        finally:
            conn.close()
        console.print(f"[bold]{run_id}[/bold]")
        _print_summary(summary)
    raise typer.Exit(code=0)


@app.command()
def validate(
    dataset: Annotated[str, typer.Option(help="Run id, or 'all'")] = "all",
) -> None:
    """Dataset invariant checks - wired into CI."""
    console.print(f"STUB validate: dataset={dataset!r} -- not implemented yet")
    raise typer.Exit(code=0)
