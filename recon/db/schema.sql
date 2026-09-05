-- recon/db/schema.sql — the DDL from master_specification.md §7.
-- SQLite. Applied once per run's database by db/connection.py.

CREATE TABLE IF NOT EXISTS orders (
    record_key   TEXT PRIMARY KEY,      -- "order:order_XXX"
    order_id     TEXT NOT NULL UNIQUE,
    receipt      TEXT,
    customer_id  TEXT NOT NULL,
    amount       INTEGER NOT NULL,
    currency     TEXT NOT NULL DEFAULT 'INR',
    status       TEXT NOT NULL,
    created_at   INTEGER NOT NULL,
    notes_json   TEXT,
    CHECK (amount >= 0)
);

CREATE TABLE IF NOT EXISTS recon_lines (
    record_key      TEXT PRIMARY KEY,   -- "recon:pay_XXX"
    entity_id       TEXT NOT NULL UNIQUE,
    type            TEXT NOT NULL CHECK (type IN ('payment','refund','adjustment')),
    debit           INTEGER NOT NULL,
    credit          INTEGER NOT NULL,
    amount          INTEGER NOT NULL,
    fee             INTEGER,            -- NULL is meaningful
    tax             INTEGER,
    on_hold         INTEGER NOT NULL,
    settled         INTEGER NOT NULL,
    created_at      INTEGER NOT NULL,
    settled_at      INTEGER,
    settlement_id   TEXT,
    settlement_utr  TEXT,
    order_id        TEXT,
    order_receipt   TEXT,
    method          TEXT NOT NULL,
    description     TEXT,
    CHECK (amount >= 0 AND debit >= 0 AND credit >= 0)
);
CREATE INDEX IF NOT EXISTS idx_recon_utr    ON recon_lines(settlement_utr);
CREATE INDEX IF NOT EXISTS idx_recon_order  ON recon_lines(order_id);
CREATE INDEX IF NOT EXISTS idx_recon_method ON recon_lines(method, created_at);

CREATE TABLE IF NOT EXISTS bank_txns (
    record_key    TEXT PRIMARY KEY,
    txn_id        TEXT NOT NULL UNIQUE,
    value_date    TEXT NOT NULL,
    description   TEXT NOT NULL,
    credit        INTEGER NOT NULL,
    debit         INTEGER NOT NULL,
    balance       INTEGER NOT NULL,
    utr_extracted TEXT
);
CREATE INDEX IF NOT EXISTS idx_bank_utr ON bank_txns(utr_extracted);

CREATE TABLE IF NOT EXISTS ledger_entries (
    record_key  TEXT PRIMARY KEY,
    entry_id    TEXT NOT NULL UNIQUE,
    entry_date  TEXT NOT NULL,
    account     TEXT NOT NULL,
    debit       INTEGER NOT NULL,
    credit      INTEGER NOT NULL,
    narration   TEXT,
    source_ref  TEXT
);
CREATE INDEX IF NOT EXISTS idx_ledger_ref ON ledger_entries(source_ref);

CREATE TABLE IF NOT EXISTS match_groups (
    group_id    TEXT PRIMARY KEY,
    pass_name   TEXT NOT NULL,
    origin      TEXT NOT NULL CHECK (origin IN ('cascade','llm')),
    proof_json  TEXT NOT NULL,
    closes      INTEGER NOT NULL,
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS group_members (
    group_id   TEXT NOT NULL REFERENCES match_groups(group_id),
    record_key TEXT NOT NULL,
    PRIMARY KEY (group_id, record_key)
);

CREATE TABLE IF NOT EXISTS exceptions (
    record_key   TEXT PRIMARY KEY,
    reason_code  TEXT NOT NULL,
    reason_text  TEXT NOT NULL,
    passes_tried TEXT NOT NULL,        -- JSON array
    candidates   TEXT NOT NULL,        -- JSON array
    created_at   INTEGER NOT NULL
);

-- Append-only. Never UPDATE, never DELETE.
CREATE TABLE IF NOT EXISTS audit_log (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          INTEGER NOT NULL,
    stage       TEXT NOT NULL,
    record_key  TEXT,
    action      TEXT NOT NULL,
    detail_json TEXT NOT NULL
);
