"""Dataset invariant checks - PROJECT_RULES.md Commands section, S6.2/S8.2.

`recon validate` was a stub from Phase 1 through Phase 8 (docs/challenges-log.md
C-016) even though CI's `Validate frozen datasets` step called it as if it were
real. This module replaces the stub with the four checks PROJECT_RULES.md documents:

  (a) the sealed key covers every recon line              -> scoring.py
  (b) no float appears anywhere in a source file           -> here
  (c) S6.2's arithmetic invariants hold on stated-fee lines -> here
  (d) S8.2's class counts and ceiling are still consistent  -> scoring.py

(a) and (d) need the sealed key, so they live in `report/scoring.py` - the
only module rule 6 allows to open the sealed key file. This module never
opens that file itself and never imports recon/generate (rule 2 firewall):
it re-derives (b) and (c) independently from the committed source JSON, the
same "don't trust the other implementation" posture as match/money.py's
deliberate duplication of round_half_up.
"""

from __future__ import annotations

import json
from pathlib import Path

from recon.report.scoring import validate_key_and_ceiling

_ALL_RUN_IDS = ["clean-august", "heavy-refunds", "holiday-skew", "high-ambiguity"]

_SOURCE_FILES = ("orders", "recon_lines", "bank_statement", "ledger_entries")


def _find_floats(obj: object, path: str) -> list[str]:
    if isinstance(obj, bool):
        return []  # bool is a subclass of int, not what we're hunting for
    if isinstance(obj, float):
        return [f"float at {path}"]
    if isinstance(obj, dict):
        found: list[str] = []
        for k, v in obj.items():
            found.extend(_find_floats(v, f"{path}.{k}"))
        return found
    if isinstance(obj, list):
        found = []
        for i, v in enumerate(obj):
            found.extend(_find_floats(v, f"{path}[{i}]"))
        return found
    return []


def validate_run(run_id: str) -> list[str]:
    """Independent invariant checks for one frozen dataset. Returns a list of
    human-readable problems; an empty list means the dataset is clean."""
    problems: list[str] = []
    src_dir = Path("data") / run_id / "sources"
    sources: dict[str, list[dict]] = {}
    for name in _SOURCE_FILES:
        path = src_dir / f"{name}.json"
        if not path.is_file():
            problems.append(f"{run_id}: missing sources/{name}.json")
            continue
        sources[name] = json.loads(path.read_text(encoding="utf-8"))

    if len(sources) < len(_SOURCE_FILES):
        return problems  # can't check arithmetic without every source present

    # (b) no float anywhere in any source file - PROJECT_RULES.md rule 1, echoed to data
    for name, rows in sources.items():
        problems.extend(f"{run_id}: {p}" for p in _find_floats(rows, name))

    # (c) S6.2 arithmetic invariants
    for row in sources["recon_lines"]:
        entity = row.get("entity_id", "?")
        if row["type"] == "payment":
            if row["debit"] != 0:
                problems.append(f"{run_id}: {entity} is a payment with non-zero debit")
            if row["fee"] is not None:
                expected_credit = row["amount"] - row["fee"] - row["tax"]
                if row["credit"] != expected_credit:
                    problems.append(
                        f"{run_id}: {entity} violates S6.2 payment invariant "
                        f"(credit={row['credit']}, amount-fee-tax={expected_credit})"
                    )
        elif row["type"] == "refund":
            if row["credit"] != 0 or row["debit"] != row["amount"]:
                problems.append(
                    f"{run_id}: {entity} violates S6.2 refund invariant "
                    f"(debit={row['debit']}, credit={row['credit']}, amount={row['amount']})"
                )
        elif row["type"] == "adjustment":
            if row["order_id"] is not None:
                problems.append(f"{run_id}: {entity} is an adjustment with a non-null order_id")

    # (a) / (d) - the two checks that need the sealed key (report/scoring.py only)
    problems.extend(validate_key_and_ceiling(run_id))

    return problems


def validate_datasets(dataset: str) -> dict[str, list[str]]:
    """`dataset='all'` checks every frozen run; otherwise just the one named."""
    run_ids = _ALL_RUN_IDS if dataset == "all" else [dataset]
    return {run_id: validate_run(run_id) for run_id in run_ids}
