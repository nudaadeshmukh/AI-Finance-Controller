"""`score()` — the ONLY module that opens `answer_key.json`, and only after
matching completes (§4.6, PROJECT_RULES.md rule 6, `tests/test_answer_key_seal.py`).

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
of them (PROJECT_RULES.md rule 13). §13.8's `CONTRADICTORY_LEDGER` records and the
analogous `CROSS_PERIOD_UTR` settlement (`docs/challenges-log.md` C-009) close
arithmetically and get matched into a real settlement — so that settlement
scores entirely as a false match.

A softer "compare only the resolvable members, count the poisoned record as
one standalone false match" reading was tried and **rejected** — it produced
materially higher precision and was only attractive *after* seeing the strict
number, which is exactly the shape of choice PROJECT_RULES.md rule 7 exists to catch.
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
    # results.json (that would be new schema surface, PROJECT_RULES.md rule 12) and
    # NOT used to adjust any score above. §13.8 / C-008.
    contradictory_ledger_false_matches: int = 0


def check_scope_only_accounted(db: sqlite3.Connection) -> None:
    """§14.1/C-008's runtime invariant, enforced here rather than only in
    CI. Every `record_key` appearing in any closed group's
    `proof_json.scope_only_keys` must, by the time this runs (end of run,
    after `classify_residual`), have a row in `exceptions`. If one doesn't,
    the pipeline refuses to score or emit `results.json` — PROJECT_RULES.md rule 4
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
