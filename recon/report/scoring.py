"""`score()` — the ONLY module that opens `answer_key.json`, and only after
matching completes (§4.6, CLAUDE.md rule 6, `tests/test_answer_key_seal.py`).

`score()` produces the sealed-key metric numbers and nothing else (§17.1). It
does not assemble `results.json` — that is `report/results.py`'s job, which
takes this `ScoreReport` as one input among several.

`check_scope_only_accounted()` was pulled forward into Phase 4, a phase
early, acknowledged as a deliberate exception to "do not build ahead" — the
same pattern as `match/classify.py`'s `has_ambiguous_adjustment()` in Phase 3.
§14.1/C-008 requires this invariant to be enforced at runtime, not only by
the test suite: `score()` is where it lives, since it's the pipeline's exit
gate before `results.json` is emitted (the same place, and same spirit, as
rule 6's answer-key gate).

## What "correct against the sealed key" means (§17.1)

**Strict whole-group equality.** A committed match group is correct **only if
its recon-key member set is IDENTICAL to the answer key's true cluster** —
every recon key present in one and present in the other, no more and no less.
Partial overlap is a false match on **every** member of the committed group,
not partial credit; split and merge both penalise every member on both sides.
The true cluster is built by grouping the key on `true_group_id` (resolvable
recon entries only), never read off a single entry's `member_keys` (which, by
construction, lists a different `order:` key per sibling recon line and is not
self-consistent across siblings).

A record the key marks `resolvable: false` (`true_group_id: null`,
`member_keys: []`) is in no true cluster, so any committed group containing
one can never equal a true cluster — the **whole group** is a false match,
poisoned record and genuinely-resolvable settlement-mates alike. This is the
general rule for every `resolvable: false` reason code
(`AMBIGUOUS_DUPLICATE`, `CROSS_PERIOD_UTR`, `CONTRADICTORY_LEDGER`,
`out_of_scope`); the scorer does **not** recognise, forgive, or carve out any
of them (CLAUDE.md rule 13). §13.8's `CONTRADICTORY_LEDGER` records and the
analogous `CROSS_PERIOD_UTR` settlement (`docs/challenges-log.md` C-009) close
arithmetically and get matched into a real settlement — so that settlement
scores entirely as a false match.

A softer "compare only the resolvable members, count the poisoned record as
one standalone false match" reading was tried and **rejected** — it produced
materially higher precision and was only attractive *after* seeing the strict
number, which is exactly the shape of choice CLAUDE.md rule 7 exists to catch.
The harder number is the headline (see `docs/project-progress.md` Phase 5).
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel

from recon.db import queries
from recon.errors import ScoringError
from recon.models.types import RecordKey

_RECON_PREFIX = "recon:"


def _is_recon(key: str) -> bool:
    return key.startswith(_RECON_PREFIX)


# S8.2's measured difficulty distribution and resolvable-ceiling range, echoed
# here (not re-derived from prose) so `validate_key_and_ceiling` can catch the
# key drifting from the published table. Update both together if S8.2 changes.
_SECTION_8_2_CLASS_COUNTS: dict[str, dict[str, int]] = {
    "clean-august": {
        "exact": 138, "many_to_one": 138, "timing_skew": 53,
        "fee_derived": 41, "tolerance": 19, "ambiguous": 11,
    },
    "heavy-refunds": {
        "exact": 36, "many_to_one": 260, "timing_skew": 47,
        "fee_derived": 39, "tolerance": 7, "ambiguous": 11,
    },
    "holiday-skew": {
        "exact": 111, "many_to_one": 147, "timing_skew": 71,
        "fee_derived": 40, "tolerance": 20, "ambiguous": 11,
    },
    "high-ambiguity": {
        "exact": 76, "many_to_one": 197, "timing_skew": 50,
        "fee_derived": 38, "tolerance": 7, "ambiguous": 32,
    },
}
_SECTION_8_2_CEILING_RANGE: dict[str, tuple[int, int]] = {
    "clean-august": (389, 391),
    "heavy-refunds": (389, 391),
    "holiday-skew": (389, 391),
    "high-ambiguity": (368, 374),
}


def validate_key_and_ceiling(run_id: str) -> list[str]:
    """The two `recon validate` checks that need the sealed key (CLAUDE.md
    Commands, docs/challenges-log.md C-016): (a) the key covers every recon
    line in the frozen source, and (d) S8.2's class counts and ceiling range
    are still consistent with what is on disk.

    This is a passive, read-only integrity check on the frozen dataset and
    the key itself — it is never consulted by match/, hypothesize/, or
    verify/, and never wired into a match decision, so it does not undermine
    what rule 6's "only after matching completes" guards against (the
    matcher tuning itself to the key). It runs independently of any
    completed run.db on purpose: a corrupt frozen dataset should be
    catchable before a run is ever attempted. Kept here, not in a new
    module, because this file is the only one allowed to open
    answer_key.json (rule 6, tests/test_answer_key_seal.py).
    """
    problems: list[str] = []
    key_path = sealed_key_for(run_id)
    if key_path is None:
        return [f"{run_id}: no answer_key.json found"]
    key_rows = json.loads(key_path.read_text(encoding="utf-8"))

    recon_path = Path("data") / run_id / "sources" / "recon_lines.json"
    if not recon_path.is_file():
        return [f"{run_id}: missing sources/recon_lines.json"]
    recon_rows = json.loads(recon_path.read_text(encoding="utf-8"))

    # (a) coverage
    key_recon = {row["record_key"] for row in key_rows if _is_recon(row["record_key"])}
    recon_keys = {f"recon:{row['entity_id']}" for row in recon_rows}
    missing = recon_keys - key_recon
    extra = key_recon - recon_keys
    if missing:
        problems.append(
            f"{run_id}: answer key is missing {len(missing)} recon line(s), "
            f"e.g. {sorted(missing)[:3]}"
        )
    if extra:
        problems.append(
            f"{run_id}: answer key has {len(extra)} recon key(s) absent from source, "
            f"e.g. {sorted(extra)[:3]}"
        )

    # (d) S8.2 class counts and ceiling range
    class_counts: dict[str, int] = defaultdict(int)
    for row in key_rows:
        if _is_recon(row["record_key"]):
            class_counts[row["true_class"]] += 1
    expected_classes = _SECTION_8_2_CLASS_COUNTS.get(run_id, {})
    for cls, expected_n in expected_classes.items():
        actual_n = class_counts.get(cls, 0)
        if actual_n != expected_n:
            problems.append(
                f"{run_id}: S8.2 class {cls!r} expected {expected_n}, key has {actual_n}"
            )

    resolvable = sum(
        1 for row in key_rows if _is_recon(row["record_key"]) and row["resolvable"]
    )
    lo, hi = _SECTION_8_2_CEILING_RANGE.get(run_id, (0, 400))
    if not (lo <= resolvable <= hi):
        problems.append(
            f"{run_id}: S8.2 ceiling {resolvable} outside expected range {lo}-{hi}"
        )

    return problems


def sealed_key_for(run_id: str) -> Path | None:
    """The sealed key path for `run_id`, or `None` if it is not present
    (§12.6: a missing key omits metrics, it does not fail the run).

    This helper lives here, in the one module allowed to touch the sealed
    key (§4.6, `tests/test_answer_key_seal.py`), so that `cli.py` and every
    other caller can ask "is there a key?" and "where is it?" without naming
    the file — the seal test greps the literal filename, and only this file
    is exempt.
    """
    path = Path("data") / run_id / "answer_key.json"
    return path if path.is_file() else None


class ScoreReport(BaseModel):
    """Return type of `score()` (§20.4). The sealed-key metric numbers only —
    §17.1's definitions and the answer-key-derived parts of §18's `summary`
    and `ceiling`. Runtime / throughput are NOT here: `score()` cannot see
    them; `report/results.py` fills those from the `CascadeResult`.
    `extra="forbid"` so a typo'd field fails loudly.
    """

    model_config = {"extra": "forbid"}

    records_processed: int = 400
    matched: int = 0  # matched AND correct against the sealed key (§17.1)
    match_rate: float = 0.0  # matched / 400
    match_precision: float = 0.0  # correct / all matches made
    false_matches: int = 0  # incorrect matches made
    unresolved: int = 0  # recon records sent to exceptions
    excluded: int = 0  # NOT_A_SETTLEMENT bank debits (§9, rule 9)
    ceiling_resolvable: int = 0  # answer-key recon entries with resolvable: true
    ceiling_rate: float = 0.0
    # Informational, for the Phase 5 error analysis — NOT surfaced in
    # results.json (that would be new schema surface, CLAUDE.md rule 12) and
    # NOT used to adjust any score above. §13.8 / C-008.
    contradictory_ledger_false_matches: int = 0


def check_scope_only_accounted(db: sqlite3.Connection) -> None:
    """§14.1/C-008's runtime invariant, enforced here rather than only in
    CI. Every `record_key` appearing in any closed group's
    `proof_json.scope_only_keys` must, by the time this runs (end of run,
    after `classify_residual`), have a row in `exceptions`. If one doesn't,
    the pipeline refuses to score or emit `results.json` — CLAUDE.md rule 4
    ("no third state") enforced at the exit gate, not just documented.
    """
    exception_keys: set[RecordKey] = {
        row["record_key"] for row in db.execute(queries.SELECT_EXCEPTION_RECORD_KEYS)
    }
    unaccounted: list[tuple[str, str]] = []  # (group_id, record_key)
    for row in db.execute(queries.SELECT_CLOSED_MATCH_GROUP_PROOFS):
        proof = json.loads(row["proof_json"])
        for scope_only_key in proof.get("scope_only_keys", []):
            if scope_only_key not in exception_keys:
                unaccounted.append((row["group_id"], scope_only_key))
    if unaccounted:
        detail = ", ".join(f"{key!r} (group {group_id!r})" for group_id, key in unaccounted)
        raise ScoringError(
            "arithmetic_scope invariant violated (§14.1/C-008): the following "
            f"scope-only keys were counted toward a closed proof but have no "
            f"exceptions row: {detail}"
        )


def score(db: sqlite3.Connection, answer_key: Path) -> ScoreReport:
    """§20.4. Score committed match groups against the sealed answer key.

    Called only after matching (cascade + optional LLM) completes. The first
    thing it does is enforce §14.1/C-008's scope-only invariant — if that
    fails the run emits nothing.
    """
    check_scope_only_accounted(db)

    key_rows = json.loads(answer_key.read_text(encoding="utf-8"))
    key: dict[str, dict] = {row["record_key"]: row for row in key_rows}

    # True recon-key set per true_group_id — resolvable recon entries only.
    true_recon_by_gid: dict[str, set[str]] = defaultdict(set)
    for record_key, entry in key.items():
        if _is_recon(record_key) and entry["resolvable"] and entry["true_group_id"] is not None:
            true_recon_by_gid[entry["true_group_id"]].add(record_key)

    # Committed groups -> their recon-key member sets.
    group_recon: dict[str, set[str]] = defaultdict(set)
    for row in db.execute(queries.SELECT_MATCHED_RECON_GROUP_MEMBERS):
        group_recon[row["group_id"]].add(row["record_key"])

    correct = 0
    false_matches = 0
    contradictory_ledger = 0
    for members in group_recon.values():
        # The true cluster this group claims to be — from its resolvable
        # members' shared true_group_id. A group with no resolvable member,
        # or members spanning >1 true cluster, claims nothing coherent, so
        # its target is the empty set (never equal to a real committed group).
        resolvable_gids = {
            key[m]["true_group_id"]
            for m in members
            if (e := key.get(m)) is not None and e["resolvable"]
        }
        if len(resolvable_gids) == 1 and None not in resolvable_gids:
            true_cluster = true_recon_by_gid.get(next(iter(resolvable_gids)), set())
        else:
            true_cluster = set()

        if members == true_cluster:
            correct += len(members)  # IDENTICAL to the true cluster — the only way to be correct
        else:
            false_matches += len(members)  # any deviation poisons the whole group
            contradictory_ledger += sum(
                1
                for m in members
                if (e := key.get(m)) is not None and e["reason_code"] == "CONTRADICTORY_LEDGER"
            )

    matches_made = correct + false_matches
    unresolved = sum(1 for _ in db.execute(queries.SELECT_EXCEPTION_RECON_KEYS))
    excluded = db.execute(queries.SELECT_NOT_A_SETTLEMENT_COUNT).fetchone()["n"]
    ceiling_resolvable = sum(
        1 for k, e in key.items() if _is_recon(k) and e["resolvable"]
    )

    return ScoreReport(
        records_processed=400,
        matched=correct,
        match_rate=round(correct / 400, 4),
        match_precision=round(correct / matches_made, 4) if matches_made else 0.0,
        false_matches=false_matches,
        unresolved=unresolved,
        excluded=excluded,
        ceiling_resolvable=ceiling_resolvable,
        ceiling_rate=round(ceiling_resolvable / 400, 4),
        contradictory_ledger_false_matches=contradictory_ledger,
    )
