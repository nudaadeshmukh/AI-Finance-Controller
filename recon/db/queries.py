"""Every SQL string used anywhere in the pipeline lives here as a named
constant — PROJECT_RULES.md conventions: "no inline SQL anywhere else."

Populated starting Phase 2 (ingest + audit). Every INSERT into the four
source tables and `exceptions` is an upsert on `record_key`
(`INSERT ... ON CONFLICT DO UPDATE`) so re-running never double-counts (§4.8).
"""

from __future__ import annotations

UPSERT_ORDER = """
INSERT INTO orders
    (record_key, order_id, receipt, customer_id, amount, currency, status, created_at, notes_json)
VALUES
    (:record_key, :order_id, :receipt, :customer_id, :amount, :currency, :status, :created_at,
     :notes_json)
ON CONFLICT(record_key) DO UPDATE SET
    order_id = excluded.order_id,
    receipt = excluded.receipt,
    customer_id = excluded.customer_id,
    amount = excluded.amount,
    currency = excluded.currency,
    status = excluded.status,
    created_at = excluded.created_at,
    notes_json = excluded.notes_json
"""

UPSERT_RECON_LINE = """
INSERT INTO recon_lines
    (record_key, entity_id, type, debit, credit, amount, fee, tax, on_hold, settled,
     created_at, settled_at, settlement_id, settlement_utr, order_id, order_receipt,
     method, description)
VALUES
    (:record_key, :entity_id, :type, :debit, :credit, :amount, :fee, :tax, :on_hold, :settled,
     :created_at, :settled_at, :settlement_id, :settlement_utr, :order_id, :order_receipt,
     :method, :description)
ON CONFLICT(record_key) DO UPDATE SET
    entity_id = excluded.entity_id,
    type = excluded.type,
    debit = excluded.debit,
    credit = excluded.credit,
    amount = excluded.amount,
    fee = excluded.fee,
    tax = excluded.tax,
    on_hold = excluded.on_hold,
    settled = excluded.settled,
    created_at = excluded.created_at,
    settled_at = excluded.settled_at,
    settlement_id = excluded.settlement_id,
    settlement_utr = excluded.settlement_utr,
    order_id = excluded.order_id,
    order_receipt = excluded.order_receipt,
    method = excluded.method,
    description = excluded.description
"""

UPSERT_BANK_TXN = """
INSERT INTO bank_txns
    (record_key, txn_id, value_date, description, credit, debit, balance, utr_extracted)
VALUES
    (:record_key, :txn_id, :value_date, :description, :credit, :debit, :balance, :utr_extracted)
ON CONFLICT(record_key) DO UPDATE SET
    txn_id = excluded.txn_id,
    value_date = excluded.value_date,
    description = excluded.description,
    credit = excluded.credit,
    debit = excluded.debit,
    balance = excluded.balance,
    utr_extracted = excluded.utr_extracted
"""

UPSERT_LEDGER_ENTRY = """
INSERT INTO ledger_entries
    (record_key, entry_id, entry_date, account, debit, credit, narration, source_ref)
VALUES
    (:record_key, :entry_id, :entry_date, :account, :debit, :credit, :narration, :source_ref)
ON CONFLICT(record_key) DO UPDATE SET
    entry_id = excluded.entry_id,
    entry_date = excluded.entry_date,
    account = excluded.account,
    debit = excluded.debit,
    credit = excluded.credit,
    narration = excluded.narration,
    source_ref = excluded.source_ref
"""

UPSERT_EXCEPTION = """
INSERT INTO exceptions
    (record_key, reason_code, reason_text, passes_tried, candidates, created_at)
VALUES
    (:record_key, :reason_code, :reason_text, :passes_tried, :candidates, :created_at)
ON CONFLICT(record_key) DO UPDATE SET
    reason_code = excluded.reason_code,
    reason_text = excluded.reason_text,
    passes_tried = excluded.passes_tried,
    candidates = excluded.candidates,
    created_at = excluded.created_at
"""

SELECT_ORDER_BY_KEY = "SELECT * FROM orders WHERE record_key = :record_key"
SELECT_RECON_LINE_BY_KEY = "SELECT * FROM recon_lines WHERE record_key = :record_key"
SELECT_BANK_TXN_BY_KEY = "SELECT * FROM bank_txns WHERE record_key = :record_key"
SELECT_LEDGER_ENTRY_BY_KEY = "SELECT * FROM ledger_entries WHERE record_key = :record_key"

INSERT_AUDIT_LOG = """
INSERT INTO audit_log (ts, stage, record_key, action, detail_json)
VALUES (:ts, :stage, :record_key, :action, :detail_json)
"""

UPSERT_MATCH_GROUP = """
INSERT INTO match_groups (group_id, pass_name, origin, proof_json, closes, created_at)
VALUES (:group_id, :pass_name, :origin, :proof_json, :closes, :created_at)
ON CONFLICT(group_id) DO UPDATE SET
    pass_name = excluded.pass_name,
    origin = excluded.origin,
    proof_json = excluded.proof_json,
    closes = excluded.closes,
    created_at = excluded.created_at
"""

UPSERT_GROUP_MEMBER = """
INSERT INTO group_members (group_id, record_key)
VALUES (:group_id, :record_key)
ON CONFLICT(group_id, record_key) DO NOTHING
"""

DELETE_EXCEPTION_BY_KEY = "DELETE FROM exceptions WHERE record_key = :record_key"

# match/ — cascade residual construction and settlement grouping.
SELECT_UNMATCHED_RECON_KEYS = """
SELECT record_key FROM recon_lines
WHERE record_key NOT IN (SELECT record_key FROM group_members)
"""

SELECT_UNMATCHED_BANK_KEYS = """
SELECT record_key FROM bank_txns
WHERE record_key NOT IN (SELECT record_key FROM group_members)
  AND record_key NOT IN (
      SELECT record_key FROM exceptions WHERE reason_code = 'NOT_A_SETTLEMENT'
  )
"""

SELECT_UNMATCHED_LEDGER_KEYS = """
SELECT record_key FROM ledger_entries
WHERE record_key NOT IN (SELECT record_key FROM group_members)
"""

SELECT_DISTINCT_RECON_SETTLEMENT_UTRS = """
SELECT DISTINCT settlement_utr FROM recon_lines WHERE settlement_utr IS NOT NULL
"""

SELECT_RECON_LINES_BY_SETTLEMENT_UTR = """
SELECT * FROM recon_lines WHERE settlement_utr = :settlement_utr
"""

# match/fee_reversal.py's infer_slabs() — needs every recon line, matched or
# not, as evidence: a matched line's stated fee is just as valid a data point
# as an unmatched one for learning the rate.
SELECT_ALL_RECON_KEYS = "SELECT record_key FROM recon_lines"

# match/timing.py's _attach_orphaned_ledger_entries() — informational only,
# never affects a recon-line match decision.
SELECT_ORPHANED_LEDGER_ENTRIES = "SELECT * FROM ledger_entries WHERE source_ref IS NULL"

SELECT_MATCHED_RECON_GROUP_MEMBERS = """
SELECT group_id, record_key FROM group_members WHERE record_key LIKE 'recon:%'
"""

# match/classify.py's has_ambiguous_adjustment() / ambiguous_adjustment_keys()
# — §13.7's detection condition (record_key needed since §14.1/C-008:
# build_settlement_proposal excludes these specific keys from member_keys).
SELECT_ADJUSTMENTS_BY_SETTLEMENT_ID = """
SELECT record_key, amount, order_id FROM recon_lines
WHERE settlement_id = :settlement_id AND type = 'adjustment'
"""

# Does >=2 orders share the same customer_id, amount and calendar date, for
# a given amount? (§13.7: "≥2 orders share the same customer_id, amount and
# calendar date".) date() on an epoch-seconds column returns UTC 'YYYY-MM-DD'.
SELECT_DUPLICATE_ORDER_BUCKET_COUNT = """
SELECT COUNT(*) AS n FROM (
    SELECT customer_id, amount, date(created_at, 'unixepoch') AS order_date
    FROM orders
    WHERE amount = :amount
    GROUP BY customer_id, amount, order_date
    HAVING COUNT(*) >= 2
)
"""

# match/classify.py's classify_residual() — the order_ids behind a
# SELECT_DUPLICATE_ORDER_BUCKET_COUNT hit, for the AMBIGUOUS_DUPLICATE
# exception's `candidates` list.
SELECT_DUPLICATE_ORDER_IDS_BY_AMOUNT = """
SELECT order_id FROM orders
WHERE amount = :amount
  AND (customer_id, amount, date(created_at, 'unixepoch')) IN (
      SELECT customer_id, amount, date(created_at, 'unixepoch') AS order_date
      FROM orders
      WHERE amount = :amount
      GROUP BY customer_id, amount, order_date
      HAVING COUNT(*) >= 2
  )
"""

# report/scoring.py's check_scope_only_accounted() — §14.1/C-008's runtime
# invariant: every scope-only key in a closed group's proof must have an
# exceptions row by end-of-run.
SELECT_CLOSED_MATCH_GROUP_PROOFS = """
SELECT group_id, proof_json FROM match_groups WHERE closes = 1
"""

SELECT_EXCEPTION_RECORD_KEYS = "SELECT record_key FROM exceptions"

# report/ — Phase 5. `report/` is a reader of every table (§7.1); it writes
# nothing. These back scoring, the naive baseline, and results.json assembly.
SELECT_ALL_ORDERS = "SELECT record_key, order_id, amount FROM orders"
SELECT_ALL_RECON_LINES_FULL = "SELECT * FROM recon_lines"
SELECT_ALL_BANK_TXNS_FULL = """
SELECT record_key, description, credit, debit FROM bank_txns
"""
SELECT_ALL_MATCH_GROUPS = """
SELECT group_id, pass_name, origin, proof_json, closes FROM match_groups
"""
SELECT_ALL_GROUP_MEMBERS = "SELECT group_id, record_key FROM group_members"
SELECT_ALL_EXCEPTIONS = """
SELECT record_key, reason_code, reason_text, passes_tried, candidates FROM exceptions
"""
SELECT_EXCEPTION_RECON_KEYS = "SELECT record_key FROM exceptions WHERE record_key LIKE 'recon:%'"
SELECT_NOT_A_SETTLEMENT_COUNT = """
SELECT COUNT(*) AS n FROM exceptions WHERE reason_code = 'NOT_A_SETTLEMENT'
"""
SELECT_NOT_A_SETTLEMENT_KEYS = """
SELECT record_key FROM exceptions WHERE reason_code = 'NOT_A_SETTLEMENT'
"""
SELECT_ORDERS_GROSS = "SELECT COALESCE(SUM(amount), 0) AS n FROM orders"
SELECT_RECON_NET = """
SELECT COALESCE(SUM(credit), 0) - COALESCE(SUM(debit), 0) AS n FROM recon_lines
"""
SELECT_BANK_CREDITED = "SELECT COALESCE(SUM(credit), 0) AS n FROM bank_txns"
SELECT_LEDGER_REVENUE = """
SELECT COALESCE(SUM(credit), 0) AS n FROM ledger_entries WHERE account = 'revenue'
"""
SELECT_MAX_RECON_CREATED_AT = "SELECT COALESCE(MAX(created_at), 0) AS n FROM recon_lines"
# Recon lines resolved per pass — the persistent truth (match_groups.pass_name),
# not the transient per-invocation cascade counter, so a re-run or `report`
# against an already-matched db still reports which pass owns each record
# (§18 `passes[].matched`, §23.3's "filterable by resolving pass").
SELECT_RECON_MEMBERS_BY_PASS = """
SELECT mg.pass_name AS pass_name, COUNT(*) AS n
FROM group_members gm
JOIN match_groups mg ON mg.group_id = gm.group_id
WHERE gm.record_key LIKE 'recon:%'
GROUP BY mg.pass_name
"""

SELECT_AUDIT_TRAIL = """
SELECT seq, ts, stage, record_key, action, detail_json
FROM audit_log
WHERE record_key = :record_key
ORDER BY seq ASC
"""

COUNT_TABLE_ROWS = {
    "orders": "SELECT COUNT(*) AS n FROM orders",
    "recon_lines": "SELECT COUNT(*) AS n FROM recon_lines",
    "bank_txns": "SELECT COUNT(*) AS n FROM bank_txns",
    "ledger_entries": "SELECT COUNT(*) AS n FROM ledger_entries",
    "exceptions": "SELECT COUNT(*) AS n FROM exceptions",
}
