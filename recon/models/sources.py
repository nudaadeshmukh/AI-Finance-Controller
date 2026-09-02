"""The four source schemas — §6. Pydantic v2. Every monetary field is `int` (paise).

These mirror the Razorpay API shape (§27) and the fixture adapter's raw JSON.
Adapters return raw dicts (§20.4); validating them into these models is
`ingest/`'s job, so there is exactly one place a malformed row is handled.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# §20.1's type aliases (RecordKey, RunId, GroupId, Paise) live in
# models/types.py, not here — this module stays a leaf with no internal
# imports of its own.


class Order(BaseModel):
    """§6.1 — `orders.json`."""

    order_id: str
    receipt: str  # merchant ref, e.g. "RCPT-2026-01042"; ~3% are ""
    customer_id: str
    amount: int  # paise, GROSS
    currency: Literal["INR"]
    status: Literal["paid", "refunded", "partially_refunded"]
    created_at: int  # epoch seconds
    notes: dict[str, str]  # free text — UNTRUSTED, see §15.2


class ReconLine(BaseModel):
    """§6.2 — `recon_lines.json`, mirrors `GET /v1/settlements/recon/combined`.

    Arithmetic invariants (§6.2):
        payment:     credit = amount - fee - tax,  debit = 0
        refund:      debit  = amount,              credit = 0
        adjustment:  debit or credit, order_id IS NULL
    Where `fee` is NULL the invariant still holds in reality — recovering it is
    the fee-reversal task (§13.4).
    """

    entity_id: str  # pay_… | rfnd_…
    type: Literal["payment", "refund", "adjustment"]
    debit: int
    credit: int
    amount: int  # gross transaction value
    currency: Literal["INR"]
    fee: int | None  # NULL on 41 lines — see §9.3
    tax: int | None  # NULL where fee is NULL
    on_hold: bool
    settled: bool
    created_at: int  # when captured
    settled_at: int | None  # when it entered a settlement
    settlement_id: str | None
    settlement_utr: str | None  # joins to bank statement
    order_id: str | None  # NULL on adjustments, by construction
    order_receipt: str | None
    method: Literal["upi", "card", "netbanking", "wallet"]
    description: str


class BankTxn(BaseModel):
    """§6.3 — `bank_statement.json`, deliberately impoverished: no order IDs, no
    payment IDs, no itemisation. One line per settlement payout, plus 5 unrelated
    business debits per run that must be excluded, not matched.
    """

    txn_id: str  # bank's own ref, unrelated to Razorpay IDs
    value_date: str  # "2026-08-14" — DATE ONLY, no time
    description: str  # free text; UTR buried in one of 5 formats
    credit: int
    debit: int
    balance: int
    utr_extracted: str | None = None  # set by match/utr.py, NULL at ingest


class LedgerEntry(BaseModel):
    """§6.4 — `ledger_entries.json`. Revenue is booked gross; fees and GST are
    separate entries booked per settlement. The ledger is never authoritative
    for anything (§5.2) — it is reconciled *to* the other three, never used to
    correct them.
    """

    entry_id: str  # "JE-2026-00001"
    entry_date: str  # ISO date
    account: Literal["revenue", "payment_gateway_fees", "gst_input", "bank", "refunds", "suspense"]
    debit: int
    credit: int
    narration: str  # 5 different formats
    source_ref: str | None  # order receipt, or NULL, or WRONG
