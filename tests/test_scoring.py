"""Phase 5 — `report/scoring.py`. §17.1 metric definitions, the
resolvable-key-set correctness rule, and the §13.8 / C-009 false-match
handling.

Not a protected test, but it pins the exact scoring semantics for Phase 5:
**strict whole-group equality** — a committed group is correct only if its
recon-key set is IDENTICAL to the answer key's true cluster. A group
containing any `resolvable: false` record can never equal a true cluster, so
the whole group (poisoned record and resolvable settlement-mates alike)
scores as a false match. No reason code is recognised or carved out (PROJECT_RULES.md
rule 13). The softer "resolvable-only" reading was tried and rejected — see
docs/project-progress.md Phase 5.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from recon.report.scoring import score


def _commit_group(db: sqlite3.Connection, group_id: str, members: list[str]) -> None:
    db.execute(
        "INSERT INTO match_groups (group_id, pass_name, origin, proof_json, closes, created_at) "
        "VALUES (?, 'exact', 'cascade', '{}', 1, 0)",
        (group_id,),
    )
    for key in members:
        db.execute(
            "INSERT INTO group_members (group_id, record_key) VALUES (?, ?)", (group_id, key)
        )


def _entry(rk: str, gid: str | None, resolvable: bool, reason: str | None = None) -> dict:
    return {
        "record_key": rk,
        "true_group_id": gid,
        "true_class": "exact" if resolvable else "ambiguous",
        "resolvable": resolvable,
        "member_keys": [],
        "reason_code": reason,
        "candidates": [],
    }


def _write_key(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "answer_key.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def test_exact_resolvable_set_match_is_correct(db: sqlite3.Connection, tmp_path: Path) -> None:
    _commit_group(db, "grp_a", ["recon:p1", "recon:p2", "recon:p3"])
    key = _write_key(
        tmp_path,
        [
            _entry("recon:p1", "grp_TRUE", True),
            _entry("recon:p2", "grp_TRUE", True),
            _entry("recon:p3", "grp_TRUE", True),
        ],
    )
    report = score(db, key)
    assert report.matched == 3
    assert report.false_matches == 0
    assert report.match_precision == 1.0


def test_missing_one_true_member_is_a_split_all_wrong(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    _commit_group(db, "grp_a", ["recon:p1", "recon:p2"])  # p3 grouped elsewhere / not at all
    key = _write_key(
        tmp_path,
        [
            _entry("recon:p1", "grp_TRUE", True),
            _entry("recon:p2", "grp_TRUE", True),
            _entry("recon:p3", "grp_TRUE", True),
        ],
    )
    report = score(db, key)
    assert report.matched == 0
    assert report.false_matches == 2  # split penalises every committed member


def test_poisoned_record_makes_the_whole_group_a_false_match(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """§13.8 / C-009: a CONTRADICTORY_LEDGER (or CROSS_PERIOD_UTR) record
    closes arithmetically and lands in a real settlement group. Under strict
    whole-group equality the committed set {p1, p2, bad} != true {p1, p2},
    so the ENTIRE group — including the resolvable settlement-mates — is a
    false match.
    """
    _commit_group(db, "grp_a", ["recon:p1", "recon:p2", "recon:bad"])
    key = _write_key(
        tmp_path,
        [
            _entry("recon:p1", "grp_TRUE", True),
            _entry("recon:p2", "grp_TRUE", True),
            _entry("recon:bad", None, False, "CONTRADICTORY_LEDGER"),
        ],
    )
    report = score(db, key)
    assert report.matched == 0
    assert report.false_matches == 3
    assert report.contradictory_ledger_false_matches == 1


def test_ceiling_and_unresolved_counts(db: sqlite3.Connection, tmp_path: Path) -> None:
    _commit_group(db, "grp_a", ["recon:p1"])
    db.execute(
        "INSERT INTO exceptions "
        "(record_key, reason_code, reason_text, passes_tried, candidates, created_at) "
        "VALUES ('recon:p2', 'AMBIGUOUS_DUPLICATE', 't', '[]', '[]', 0)"
    )
    db.execute(
        "INSERT INTO exceptions "
        "(record_key, reason_code, reason_text, passes_tried, candidates, created_at) "
        "VALUES ('bank:x', 'NOT_A_SETTLEMENT', 't', '[]', '[]', 0)"
    )
    key = _write_key(
        tmp_path,
        [
            _entry("recon:p1", "grp_TRUE", True),
            _entry("bank:settled", "grp_TRUE", True),  # grp_TRUE has a bank txn -> achievable
            _entry("recon:p2", None, False, "AMBIGUOUS_DUPLICATE"),
            _entry("bank:x", None, False, "NOT_A_SETTLEMENT"),
        ],
    )
    report = score(db, key)
    assert report.ceiling_resolvable == 1  # only recon:p1 is resolvable
    assert report.ceiling_achievable == 1  # its true group has a bank record to close against
    assert report.unresolved == 1  # recon:p2 (bank:x is excluded, not an exception)
    assert report.excluded == 1


def test_ceiling_achievable_excludes_a_settlement_with_no_bank_record(
    db: sqlite3.Connection, tmp_path: Path
) -> None:
    """C-018: `resolvable: true` means a human could attribute the record —
    it does not mean the settlement has a bank transaction to close against
    at all. S13.1's closing equation requires exactly one; a settlement with
    none can never be matched, regardless of matcher capability. Such a
    record still counts toward `ceiling_resolvable` (the key does mark it
    resolvable) but must NOT count toward `ceiling_achievable`.
    """
    key = _write_key(
        tmp_path,
        [
            _entry("recon:p1", "grp_TRUE", True),  # has a bank txn -> achievable
            _entry("bank:settled", "grp_TRUE", True),
            _entry("recon:p2", "grp_UNBACKED", True),  # NO bank txn anywhere -> not achievable
        ],
    )
    report = score(db, key)
    assert report.ceiling_resolvable == 2  # both p1 and p2 are key-resolvable
    assert report.ceiling_achievable == 1  # only p1's settlement has a bank record
    assert report.ceiling_achievable_rate < report.ceiling_rate
