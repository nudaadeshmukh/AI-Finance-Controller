"""`recon validate` (PROJECT_RULES.md Commands, docs/challenges-log.md C-016).

`recon validate` was a silently-passing stub through Phase 8 — CI's
`Validate frozen datasets` step called it and always exited 0 without
checking anything. This test runs the real replacement against the actual
committed frozen datasets, not a synthetic fixture, so a regression here is
caught the same way the original gap should have been.
"""

from __future__ import annotations

from recon.report.validate import _ALL_RUN_IDS, validate_datasets


def test_all_frozen_datasets_pass_validation() -> None:
    results = validate_datasets("all")
    assert set(results) == set(_ALL_RUN_IDS)
    for run_id, problems in results.items():
        assert problems == [], f"{run_id}: {problems}"


def test_single_dataset_selection() -> None:
    results = validate_datasets("clean-august")
    assert set(results) == {"clean-august"}
    assert results["clean-august"] == []


def test_a_broken_payment_invariant_is_caught(tmp_path, monkeypatch) -> None:
    import json
    import shutil
    from pathlib import Path

    run_id = "clean-august"
    fixture_dir = tmp_path / "data" / "_broken"
    shutil.copytree(Path("data") / run_id, fixture_dir)

    recon_path = fixture_dir / "sources" / "recon_lines.json"
    rows = json.loads(recon_path.read_text(encoding="utf-8"))
    for row in rows:
        if row["type"] == "payment" and row["fee"] is not None:
            row["credit"] += 1
            break
    recon_path.write_text(json.dumps(rows), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    results = validate_datasets("_broken")
    assert any("S6.2 payment invariant" in p for p in results["_broken"])
