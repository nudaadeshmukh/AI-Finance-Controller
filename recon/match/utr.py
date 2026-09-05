"""Pass 1 — `utr` — §13.2.

Never proposes a match itself. It only enriches `DerivedFacts.utr_index`
(`{utr: bank_record_key}`) for passes 2-3 to consume, and directly excludes
unrelated bank debits as `NOT_A_SETTLEMENT` — excluded, not an exception
(§11, PROJECT_RULES.md rule 9).
"""

from __future__ import annotations

import re
import sqlite3

from recon import audit
from recon.db import queries
from recon.ingest.persist import persist_exception
from recon.models.pipeline import CascadeState, Exception_, MatchProposal
from recon.models.reasons import REASON_LABELS, ReasonCode

_UTR_PATTERN = re.compile(r"\d{10,22}")


def extract_utr(description: str) -> str | None:
    """§13.2, §20.4. The longest run of 10-22 digits in `description` — rules
    out short date-like runs. `None` if no candidate is present.
    """
    candidates = _UTR_PATTERN.findall(description)
    if not candidates:
        return None
    return max(candidates, key=len)


class UtrPass:
    name = "utr"

    def run(self, db: sqlite3.Connection, state: CascadeState) -> list[MatchProposal]:
        recon_utrs = {
            row["settlement_utr"]
            for row in db.execute(queries.SELECT_DISTINCT_RECON_SETTLEMENT_UTRS)
        }

        for bank_key in list(state.unmatched_bank):
            row = db.execute(queries.SELECT_BANK_TXN_BY_KEY, {"record_key": bank_key}).fetchone()
            if row is None:
                continue

            if row["credit"] > 0:
                utr = extract_utr(row["description"])
                if utr is not None and utr in recon_utrs:
                    state.derived.utr_index[utr] = bank_key
                # else: no exact match — left for the tolerance pass (Phase 4)
            elif row["debit"] > 0:
                exc = Exception_(
                    record_key=bank_key,
                    reason_code=ReasonCode.NOT_A_SETTLEMENT,
                    reason_text=REASON_LABELS[ReasonCode.NOT_A_SETTLEMENT],
                    passes_tried=[self.name],
                    candidates=[],
                )
                persist_exception(db, exc)
                detail = {"reason_code": exc.reason_code.value}
                audit.record(db, "match.utr", bank_key, "excluded", detail)
                state.unmatched_bank.remove(bank_key)

        return []  # this pass never proposes a MatchProposal
