# Razorpay AI Buildathon — Master Specification

**This is the single authoritative technical document for this project.** Architecture,
schemas, algorithms, APIs, metrics and deliverables all live here. There is no second
architecture document.

`reference/implementation_guide.md` carries the phase-by-phase build order and refers
back to sections of this file by number. `CLAUDE.md` carries the rules that never change.

If code contradicts this document, the code is wrong. If this document is wrong, say so
and ask — do not resolve the conflict by writing different code.

---

## 1. Problem & Deliverables

### 1.1 The problem

A business's money is described by four systems that never agree, because fees, taxes,
settlement delays, refunds and reversals distort the numbers at every step:

| Source | What it says |
|---|---|
| Merchant order system | "I sold 360 orders for ₹19,56,094" — gross, before deductions |
| Razorpay settlement recon report | Per-transaction detail with fee and tax, grouped into settlements |
| Bank statement | One lump credit per settlement, no itemisation, no order references |
| Accounting ledger | What the accountant recorded — may be late, incomplete, or wrong |

Reconciliation is proving these four describe the same money, and explaining every rupee
of the difference. It is done monthly, by hand, in a spreadsheet, by nearly every
business that takes online payments.

### 1.2 One-line pitch

> Four systems disagree about the same money. This pipeline reconciles 400 records
> across all four, explains every rupee of the gap, and hands back the ones it could not
> resolve — with reasons.

### 1.3 Track and deliverables

**Track 04 — AI Finance Controller**, direction: multi-source reconciliation.
**Deadline: 5 September 2026.**

| Deliverable | Form |
|---|---|
| Working system | Public repo, clone-and-run in under 60 seconds |
| Pitch | ~5-minute video |
| Architecture | This document + README |
| Evidence | `results.json` for four datasets, committed |

The track bar: **throughput, measured accuracy, and an honest exception list. One
cherry-picked match proves nothing.**

### 1.4 Scope exclusions — do not build these

No web server. No authentication. No RBAC. No file upload. No user accounts. No
dashboard framework. No ML model. No vector store. No RAG. No agent framework.

Each of these is scope creep scored at zero by the rubric.

---

## 2. What Wins, and What Loses

Judged on four criteria: **problem taste, build quality, AI judgment, failure recovery.**

The discriminator is AI judgment, and it is tested by **where you refused to use an
LLM**. Most submissions will over-use AI. The signal is a repo where the model does one
narrow thing and deterministic code does everything else.

### 2.1 The philosophy — one line, repeated everywhere

> **The LLM proposes. The arithmetic disposes.**

Every match — from the deterministic cascade *and* from the model — enters the matched
set through a single verifier that recomputes arithmetic from source records. Nothing is
trusted on assertion.

### 2.2 Honesty is the competitive weapon

Three of the five track bars warn against inflated claims. A submission reporting a 91%
match rate with a candid error analysis beats one claiming 99% with no held-out set.

**A false match is worse than an unresolved record.** An unresolved record gets human
attention; a false match never will. Report false match rate prominently, not in a
footnote.

---

## 3. Architectural Style & Folder Structure

### 3.1 Style decisions (locked)

| Decision | Choice | Why |
|---|---|---|
| Style | Modular monolith, pipes-and-filters | Bounded batch over a fixed record set |
| Execution | Offline batch, single process, single-threaded | No request/response path exists |
| Stage coupling | Via SQLite tables, not in-memory handoff | Any stage re-runnable against persisted state |
| Storage | One SQLite file per run | Zero setup; reviewer clones and runs in <60s |
| Frontend | Static, build-time data | Reads a committed JSON artifact; nothing to host |
| Trust model | LLM is an untrusted component | It proposes; a deterministic verifier disposes |

The system has **no runtime network dependency** except one optional LLM call.
`--no-llm` removes even that.

### 3.2 Folder structure

```
razorpay-recon/
├── CLAUDE.md                       # persistent rules
├── README.md                       # written Phase 8, with real numbers
├── LICENSE                         # MIT
├── pyproject.toml
├── requirements.txt                # pinned exact versions
├── .env.example
├── .gitignore
│
├── reference/
│   ├── master_specification.md     # THIS FILE — the only technical spec
│   ├── implementation_guide.md     # phase-by-phase build order
│   └── design.md                   # frontend visual system — see §23
│
├── docs/
│   ├── project-progress.md         # running memory across sessions
│   └── challenges-log.md           # every error and how it was fixed
│
├── recon/
│   ├── __init__.py
│   ├── __main__.py                 # python -m recon
│   ├── cli.py                      # Typer: run / inject / report / validate
│   ├── config.py                   # env loading; every variable optional
│   ├── errors.py                   # exactly 3 exception classes
│   │
│   ├── models/
│   │   ├── __init__.py             # re-exports every public model
│   │   ├── sources.py              # Order, ReconLine, BankTxn, LedgerEntry
│   │   ├── pipeline.py             # MatchProposal, ArithmeticProof, CascadeState
│   │   ├── facts.py                # DerivedFacts, FeeSlab
│   │   └── reasons.py              # ReasonCode enum + UI labels
│   │
│   ├── db/
│   │   ├── schema.sql              # the DDL in §7
│   │   ├── connection.py           # connect, migrate, transaction ctx manager
│   │   └── queries.py              # every SQL string; none inline elsewhere
│   │
│   ├── adapters/
│   │   ├── base.py                 # SourceAdapter protocol
│   │   ├── fixture.py              # reads data/<run>/sources/
│   │   ├── razorpay.py             # live adapter
│   │   └── razorpay_client.py      # HTTP, auth, pagination, retry
│   │
│   ├── ingest/
│   │   ├── validate.py             # malformed row → Exception_ record, never raise
│   │   └── persist.py              # idempotent upserts
│   │
│   ├── match/
│   │   ├── __init__.py             # run_cascade(), PASSES
│   │   ├── base.py                 # Pass protocol
│   │   ├── classify.py             # residual → specific reason codes (§13.7)
│   │   ├── constants.py            # tolerances, each with justifying comment
│   │   ├── money.py                # round_half_up — matcher's OWN copy
│   │   ├── utr.py                  # pass 1
│   │   ├── exact.py                # pass 2
│   │   ├── aggregate.py            # pass 3
│   │   ├── fee_reversal.py         # pass 4 — slab inference
│   │   ├── timing.py               # pass 5 — calendar inference
│   │   └── tolerance.py            # pass 6
│   │
│   ├── hypothesize/
│   │   ├── client.py               # Groq wrapper, timeout, retry
│   │   ├── prompt.py               # system block + untrusted fence
│   │   ├── parse.py                # strict JSON → Hypothesis
│   │   └── cluster.py              # cluster_residual()
│   │
│   ├── verify/
│   │   ├── __init__.py             # verify(), commit()
│   │   ├── arithmetic.py           # the closing equation, ONE place only
│   │   └── proof.py                # ArithmeticProof construction
│   │
│   ├── report/
│   │   ├── scoring.py              # ONLY module that opens answer_key.json
│   │   ├── baseline.py             # naive matcher for comparison
│   │   ├── results.py              # results.json emitter
│   │   ├── html.py                 # Jinja2 static report
│   │   └── templates/report.html.j2
│   │
│   ├── audit/
│   │   ├── __init__.py             # record(), trail()
│   │   └── events.py               # AuditEvent model
│   │
│   ├── inject/
│   │   ├── hallucination.py
│   │   └── unavailable.py
│   │
│   └── generate/                   # OUTSIDE the dependency graph
│       ├── generator.py            # imported by NOTHING in the pipeline
│       └── validate.py
│
├── data/
│   ├── manifest.json
│   ├── clean-august/
│   │   ├── sources/{orders,recon_lines,bank_statement,ledger_entries}.json
│   │   ├── answer_key.json         # sealed — only report/scoring.py opens this
│   │   └── results.json            # committed after Phase 5
│   ├── heavy-refunds/
│   ├── holiday-skew/
│   └── high-ambiguity/
│
├── tests/
│   ├── conftest.py
│   ├── test_firewall.py            # no generator imports
│   ├── test_answer_key_seal.py     # answer key opened only by report/
│   ├── test_money.py               # no floats
│   ├── test_determinism.py
│   ├── test_idempotency.py
│   ├── test_ingest.py
│   ├── test_utr.py
│   ├── test_exact.py
│   ├── test_aggregate.py
│   ├── test_fee_reversal.py
│   ├── test_timing.py
│   ├── test_tolerance.py
│   ├── test_verify.py
│   ├── test_ambiguous.py
│   ├── test_injection.py
│   ├── test_no_llm.py
│   └── fixtures/
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── App.tsx                 # run dropdown + routing
│       ├── types.ts                # asserts schema_version === 1
│       ├── lib/format.ts           # ONLY place paise become rupees
│       ├── screens/{RunOverview,Bridge,MatchExplorer,ExceptionList}.tsx
│       └── components/{RecordDrawer,ProofTable,MetricStrip}.tsx
│
└── .github/workflows/ci.yml        # ruff + pytest + recon validate
```

### 3.3 Dependency direction (locked)

```
models ← adapters ← ingest ← match ← verify ← report
                                ↖ hypothesize ↗
audit ← imported by everything; imports only models
generate ← imported by NOTHING
```

No upward imports. No cycles.

### 3.4 Tech stack (locked)

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Storage | SQLite (stdlib) |
| Schemas | Pydantic v2 |
| Money | Integer paise, no floats |
| Data manipulation | Plain Python — **no pandas** |
| CLI | Typer + Rich |
| LLM | Groq SDK, `llama-3.3-70b-versatile` |
| Templating | Jinja2 |
| HTTP | httpx |
| Tests | pytest; lint: ruff |
| Frontend | Vite + React, static build |

**Five runtime dependencies: pydantic, typer+rich, groq, jinja2, httpx. Do not add more
without asking.** Every dependency is something a reviewer must trust without reading.

---

## 4. Non-Negotiable Invariants

Violating any of these is a correctness bug, not a style issue.

### 4.1 Money is integer paise

All monetary values are Python `int` in paise. ₹1,000.00 is `100000`. **No floats. No
`Decimal`.** Formatting to rupees happens only in `report/` and `frontend/src/lib/format.ts`.

This mirrors the Razorpay API, which expresses ₹1,000 as `amount: 100000`.
Enforced by `tests/test_money.py`.

### 4.2 The generator/matcher firewall

`match/`, `hypothesize/` and `verify/` must **never** import from `recon/generate/`.
No shared constants. If the matcher needs a fee slab or a holiday calendar, it must
**derive it from observed data**.

`match/money.py` holds its own copy of `round_half_up`. **This duplication is
deliberate.** Importing it from the generator silently voids the entire fee-reversal
result. Enforced by `tests/test_firewall.py` — never skip or weaken that test.

### 4.3 The verifier is the only door

`verify/commit()` is the only function in the codebase that writes `match_groups`.
Every proposal, from both origins, traverses identical code. There is no confidence
threshold, no override flag, no "high confidence" bypass.

### 4.4 No silent guessing

A record is either matched with a closing arithmetic proof, or it goes to the exception
list with a specific reason. There is no third state.

### 4.5 The datasets are frozen

`data/*/sources/` and `data/*/answer_key.json` are committed and final. **Never
regenerate them.** If a pass will not converge, fix the pass. Tuning the generator after
seeing your match rate invalidates every number in the submission.

### 4.6 The answer key is sealed

Only `report/scoring.py` may open `answer_key.json`, and only after matching completes.

### 4.7 Tolerances are fixed before measurement

Constants live in `match/constants.py`, each with a comment justifying its value, and
are echoed into `results.json` so they appear in the UI. **Never widen a tolerance to
improve a match rate.** A tolerance you cannot see is a tolerance you can abuse.

### 4.8 Determinism and idempotency

Same seed, byte-identical dataset. Same input, byte-identical `results.json`. Re-running
the pipeline never double-counts — all writes are upserts on `record_key`.

---

## 5. Data Sources & Provenance

### 5.1 Where each source comes from

| Source | Production origin | Current implementation | Count |
|---|---|---|---|
| Orders | Merchant OMS (DB read / internal API) | `sources/orders.json` | 296–360 |
| Recon lines | **Razorpay** `GET /v1/settlements/recon/combined` | `sources/recon_lines.json` | **400** |
| Bank statement | Bank portal (CSV / MT940 / API) | `sources/bank_statement.json` | 51–65 |
| Ledger | Tally / Zoho / QuickBooks export | `sources/ledger_entries.json` | 536–566 |

### 5.2 Field provenance — which source wins

Ambiguity here is how reconciliation systems silently produce wrong answers.

| Quantity | Authoritative source | Others are |
|---|---|---|
| Gross transaction value | Order system | Recon `amount` should agree; disagreement is an exception |
| Fee, tax | Recon report | Ledger is derived; disagreement is an exception |
| Net settled | Recon `credit` − `debit` | — |
| **Cash actually received** | **Bank statement** | Final arbiter. If bank disagrees, bank wins and the delta is investigated |
| Accounting treatment | Ledger | **Never** used to correct the other three |

**The bank is the final arbiter of cash. The ledger is never authoritative for
anything** — it is the source most likely to be wrong, and is reconciled *to* the others.

### 5.3 Identifier conventions

Mirroring Razorpay's public entity ID format. Suffix: 14 chars, `[A-Za-z0-9]`.

| Entity | Prefix | Example |
|---|---|---|
| Order | `order_` | `order_QmT4xK9pLr2vBn` |
| Payment | `pay_` | `pay_QmT4xK9pLr2vBn` |
| Refund | `rfnd_` | `rfnd_QmT9zR3nWq7xCd` |
| Settlement | `setl_` | `setl_QmU1aB5cD8eF2g` |
| Customer | `cust_` | `cust_QmS7hJ4kL9mN3p` |

**UTR:** 12–22 char alphanumeric, e.g. `022011173948`. The only join key between the
settlement report and the bank statement.

**`record_key`:** `"<source>:<id>"` where source ∈ `order | recon | bank | ledger`.

**Timestamps:** integer Unix epoch seconds in API-shaped sources. The bank statement
uses ISO date strings **with no time**, because banks do not give one.

---

## 6. Source Schemas

Pydantic v2. Every monetary field is `int` (paise).

### 6.1 `orders.json`

```python
class Order(BaseModel):
    order_id: str            # order_XXXXXXXXXXXXXX
    receipt: str             # merchant ref, e.g. "RCPT-2026-01042"; ~3% are ""
    customer_id: str
    amount: int              # paise, GROSS
    currency: Literal["INR"]
    status: Literal["paid", "refunded", "partially_refunded"]
    created_at: int          # epoch seconds
    notes: dict[str, str]    # free text — UNTRUSTED, see §15.2
```

### 6.2 `recon_lines.json` — mirrors the Razorpay recon endpoint

```python
class ReconLine(BaseModel):
    entity_id: str                # pay_… | rfnd_…
    type: Literal["payment", "refund", "adjustment"]
    debit: int
    credit: int
    amount: int                   # gross transaction value
    currency: Literal["INR"]
    fee: int | None               # NULL on 41 lines — see §9.3
    tax: int | None               # NULL where fee is NULL
    on_hold: bool
    settled: bool
    created_at: int               # when captured
    settled_at: int | None        # when it entered a settlement
    settlement_id: str | None
    settlement_utr: str | None    # joins to bank statement
    order_id: str | None          # NULL on adjustments, by construction
    order_receipt: str | None
    method: Literal["upi", "card", "netbanking", "wallet"]
    description: str
```

**Arithmetic invariants:**
```
payment:     credit = amount - fee - tax,  debit = 0
refund:      debit  = amount,              credit = 0
adjustment:  debit or credit, order_id IS NULL
```
Where `fee` is NULL the invariant still holds in reality — the matcher must derive `fee`
to verify it. That is the fee-reversal task.

### 6.3 `bank_statement.json` — deliberately impoverished

```python
class BankTxn(BaseModel):
    txn_id: str              # bank's own ref, unrelated to Razorpay IDs
    value_date: str          # "2026-08-14" — DATE ONLY, no time
    description: str         # free text; UTR buried in one of 5 formats
    credit: int
    debit: int
    balance: int
    utr_extracted: str | None = None   # set by match/utr.py, NULL at ingest
```

No order IDs, no payment IDs, no itemisation. One line per settlement payout, plus 5
unrelated business debits per run (rent, salary, vendor, GST, courier) that must be
**excluded, not matched**.

Description formats vary:
```
NEFT CR-RAZORPAY SOFTWARE PVT LTD-022011173948
UPI/022011173948/RAZORPAY/SETTLEMENT
IMPS/P2A/022011173948/RAZORPAY SOF
RTGS CR RAZORPAYSOFTWARE 022011173948 SETTLEMENT
NEFT-022011173948-RAZORPAY SOFTWARE PRIVATE LIM
```

### 6.4 `ledger_entries.json`

```python
class LedgerEntry(BaseModel):
    entry_id: str                    # "JE-2026-00001"
    entry_date: str                  # ISO date
    account: Literal["revenue", "payment_gateway_fees", "gst_input",
                     "bank", "refunds", "suspense"]
    debit: int
    credit: int
    narration: str                   # 5 different formats
    source_ref: str | None           # order receipt, or NULL, or WRONG
```

Revenue is booked gross; fees and GST are separate entries booked per settlement.

---

## 7. Database Schema

SQLite. Full DDL — `recon/db/schema.sql`.

```sql
CREATE TABLE orders (
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

CREATE TABLE recon_lines (
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
CREATE INDEX idx_recon_utr    ON recon_lines(settlement_utr);
CREATE INDEX idx_recon_order  ON recon_lines(order_id);
CREATE INDEX idx_recon_method ON recon_lines(method, created_at);

CREATE TABLE bank_txns (
    record_key    TEXT PRIMARY KEY,
    txn_id        TEXT NOT NULL UNIQUE,
    value_date    TEXT NOT NULL,
    description   TEXT NOT NULL,
    credit        INTEGER NOT NULL,
    debit         INTEGER NOT NULL,
    balance       INTEGER NOT NULL,
    utr_extracted TEXT
);
CREATE INDEX idx_bank_utr ON bank_txns(utr_extracted);

CREATE TABLE ledger_entries (
    record_key  TEXT PRIMARY KEY,
    entry_id    TEXT NOT NULL UNIQUE,
    entry_date  TEXT NOT NULL,
    account     TEXT NOT NULL,
    debit       INTEGER NOT NULL,
    credit      INTEGER NOT NULL,
    narration   TEXT,
    source_ref  TEXT
);
CREATE INDEX idx_ledger_ref ON ledger_entries(source_ref);

CREATE TABLE match_groups (
    group_id    TEXT PRIMARY KEY,
    pass_name   TEXT NOT NULL,
    origin      TEXT NOT NULL CHECK (origin IN ('cascade','llm')),
    proof_json  TEXT NOT NULL,
    closes      INTEGER NOT NULL,
    created_at  INTEGER NOT NULL
);

CREATE TABLE group_members (
    group_id   TEXT NOT NULL REFERENCES match_groups(group_id),
    record_key TEXT NOT NULL,
    PRIMARY KEY (group_id, record_key)
);

CREATE TABLE exceptions (
    record_key   TEXT PRIMARY KEY,
    reason_code  TEXT NOT NULL,
    reason_text  TEXT NOT NULL,
    passes_tried TEXT NOT NULL,        -- JSON array
    candidates   TEXT NOT NULL,        -- JSON array
    created_at   INTEGER NOT NULL
);

-- Append-only. Never UPDATE, never DELETE.
CREATE TABLE audit_log (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          INTEGER NOT NULL,
    stage       TEXT NOT NULL,
    record_key  TEXT,
    action      TEXT NOT NULL,
    detail_json TEXT NOT NULL
);
```

### 7.1 Table ownership — exactly one writer each

| Table | Writer | Readers |
|---|---|---|
| `orders`, `recon_lines`, `bank_txns`, `ledger_entries` | `ingest/` | `match/`, `verify/`, `report/` |
| `match_groups`, `group_members` | **`verify/` only** | `report/` |
| `exceptions` | `ingest/`, `verify/` | `report/` |
| `audit_log` | all stages | `report/` |

### 7.2 Transaction boundaries

**Ingest is one transaction for the whole call, covering all four sources —
not one transaction per source file.** §12.1 requires that a `SourceUnavailable`
raised partway through acquisition leave no partial write: not just from the
source that failed, but from any source already read successfully earlier in
the same call. A per-source transaction scheme cannot give that guarantee —
by the time source 3 of 4 fails, sources 1–2 are already durably committed,
which is a partial write in every sense that matters, even though each
individual source's own transaction is internally clean. A single outer
transaction gives the guarantee atomically: nothing commits until every
source in the call succeeds. Implemented in `recon/ingest/__init__.py` and
covered by
`tests/test_ingest.py::test_source_unavailable_partway_through_leaves_no_partial_write`,
which asserts zero rows in all four source tables (and `audit_log`) after a
simulated failure on the third of four sources.

One transaction per pass in the cascade — a half-applied pass would corrupt
the residual for the next. One per cluster in the LLM stage. `audit_log`
writes participate in the enclosing transaction in all three stages; audit
and effect are never separable.

---

## 8. The Frozen Datasets

Generated by `recon/generate/generator.py`, validated by `recon/generate/validate.py`
with **0 invariant failures**. All four are exactly **400 recon lines**.

### 8.1 Summary

| Run | Orders | Recon | Bank | Ledger | Settlements | Gross | Banked |
|---|---|---|---|---|---|---|---|
| `clean-august` | 360 | 400 | 65 | 566 | 61 | ₹19,56,094 | ₹17,64,527 |
| `heavy-refunds` | 296 | 400 | 51 | 536 | 60 | ₹16,48,402 | ₹11,75,279 |
| `holiday-skew` | 360 | 400 | 59 | 538 | 57 | ₹18,53,424 | ₹16,77,026 |
| `high-ambiguity` | 350 | 400 | 60 | 553 | 60 | ₹19,24,808 | ₹16,51,272 |

Settlements are **daily** (T+2 business days), averaging 6.6–7.0 lines each, largest
23–32. This is why many-to-one aggregation is structural, not an edge case.

### 8.2 Difficulty distribution (measured)

Class = the hardest requirement for a record to be **fully** reconciled across all four
sources, including bank closure.

| Class | clean | heavy | holiday | high-amb |
|---|---|---|---|---|
| `exact` | 138 | 36 | 111 | 76 |
| `many_to_one` | 138 | 260 | 147 | 197 |
| `timing_skew` | 53 | 47 | 71 | 50 |
| `fee_derived` | 41 | 39 | 40 | 38 |
| `tolerance` | 19 | 7 | 20 | 7 |
| **`ambiguous`** | **11** | **11** | **11** | **32** |
| **Resolvable ceiling** | **389 (97.2%)** | **389 (97.2%)** | **389 (97.2%)** | **368 (92.0%)** |

### 8.3 Baseline headroom

Naive matcher = exact `order_id` join **and** stated fee **and** exact UTR **and**
settlement net closes with no derivation.

| Run | Naive baseline | Ceiling | Headroom |
|---|---|---|---|
| `clean-august` | 126/400 (31.5%) | 97.2% | **65.8 pp** |
| `heavy-refunds` | 79/400 (19.8%) | 97.2% | **77.5 pp** |
| `holiday-skew` | 120/400 (30.0%) | 97.2% | **67.2 pp** |
| `high-ambiguity` | 147/400 (36.8%) | 92.0% | **55.2 pp** |

**`high-ambiguity` is designed to score worse.** Four flattering runs would invite
exactly the suspicion the track bar warns about. A visible degradation on harder data is
stronger evidence than a uniformly good number.

### 8.3.1 `manifest.json`

Generator metadata only. **The pipeline reads nothing from it except `run_id` and
`label`.** Other fields are generation statistics; do not build logic on them.

### 8.4 Deliberate data-quality defects

| Defect | Approx count | Where |
|---|---|---|
| Blank order receipt | 14–16 | `orders.receipt = ""` |
| Fee/tax dropped from export | 41 | `recon_lines.fee = null` |
| Ledger entry with no source ref | 78–92 | `ledger_entries.source_ref = null` |
| Ledger ref pointing at wrong order | ~7 | transposition error |
| Suspense entries | 2 (6 in high-amb) | contradictory amount + ref |
| Truncated UTR in bank description | 2 | last 2 digits missing |
| Late ledger posting | ~8% | booked one day after the sale |
| Unrelated bank debits | 5 | rent, salary, vendor, GST, courier |
| **Prompt-injection payload** | **exactly 1** | `orders.notes.customer_note` |

### 8.5 Payment method mix (clean-august)

| Method | Count | Rate period A | Rate period B |
|---|---|---|---|
| UPI | 200 | 0.00% | 0.00% |
| Card | 84 | 2.00% | **1.90%** |
| Wallet | 40 | 2.25% | 2.25% |
| Netbanking | 36 | 1.75% | 1.75% |

UPI-dominant, matching Indian D2C reality. Fee-null lines are weighted toward card,
netbanking and wallet — a dropped fee on a 0% method is trivially derivable. Only 4 of
the 41 are UPI, kept for realism.

---

## 9. Discrepancy Classes & Causal Model

**Discrepancies arise from a simulated business process, never from injected noise.**

### 9.1 `many_to_one` — aggregation

Razorpay batches payments captured in a cycle and pays out one lump sum; the bank sees
one credit. The credit must be decomposed into the exact member set, including refunds
netted off in the same cycle.

**Resolution:** UTR extraction → group recon lines by `settlement_utr` → verify
`Σ(credit) − Σ(debit) == bank.credit`.

### 9.2 `timing_skew` — T+2 boundary

Settlement is T+2 **business** days with an 18:00 IST cutoff. Payments captured Thursday
or Friday, or before a bank holiday, land in a later cycle than naive date arithmetic
suggests. The bank statement has no timestamp, only a date, so skew cannot be resolved
by direct comparison.

**Resolution:** the matcher must infer its own business-day calendar and holiday list
from observed settlement gaps.

### 9.3 `fee_derived` — fee/tax reversal

41 lines have `fee` and `tax` NULL while `credit` remains correct. To verify
`credit = amount − fee − tax` you must first recover the rate.

**The card rate moves from 2.00% to 1.90% partway through the window, unannounced.** A
matcher inferring one global card rate gets ~1.95% and fails to close on **both** sides
of the boundary. This is the single best demonstration of domain literacy in the project.

### 9.4 `ambiguous` — genuinely unresolvable

**These must stay unresolved. Do not let any pass or the LLM "solve" them.**

| Reason code | Count (high-amb) | Why unresolvable |
|---|---|---|
| `AMBIGUOUS_DUPLICATE` | 5 (15) | Two payments, same customer, same amount, same day; the refund was processed via dashboard and carries no order reference. Attribution is a coin flip. |
| `CROSS_PERIOD_UTR` | 4 (11) | Settlement falls outside the export window; the bank record genuinely does not exist in the data. |
| `CONTRADICTORY_LEDGER` | 2 (6) | Suspense entry whose amount and reference contradict the transaction. |

`AMBIGUOUS_DUPLICATE` exceptions **must list both candidates.** Naming the ambiguity
precisely is the deliverable; picking one is the failure.

### 9.5 `tolerance`

Rounding differences ≤2 paise, truncated UTRs, ledger entries posted one day late.
Resolvable within explicit documented windows — see §13.6.

---

## 10. Synthetic Fee Schedule

> **THIS IS SYNTHETIC. It is NOT Razorpay's real pricing and must never be presented as
> such.** The README must state that fee structures are invented to generate a realistic
> reconciliation problem.

| Method | Rate (period A) | Rate (period B) |
|---|---|---|
| `upi` | 0.00% | 0.00% |
| `card` | 2.00% | **1.90%** |
| `netbanking` | 1.75% | 1.75% |
| `wallet` | 2.25% | 2.25% |

**Period boundary:** day 46 of the 90-day window. Unannounced anywhere in the data.

**Tax:** GST at 18% on the fee.

**Rounding:** fee and tax each rounded half-up to the nearest paise, **independently**,
before subtraction.

```
fee    = round_half_up(amount * bps, 10000)
tax    = round_half_up(fee * 1800,  10000)
credit = amount - fee - tax
```

The matcher may not import this table. It must derive it (§13.4).

---

## 11. Record Lifecycle

```
Ingested ──validation fails──> Malformed ──> Exception
    │
    └─validation passes──> Unmatched
                              │
                              ├─not a settlement──> Excluded
                              │
                              ├─pass or LLM proposes──> Proposed ──> Verifying
                              │                                          │
                              │                            proof closes ─┴─> Matched
                              │                            proof fails ─────> back to Unmatched
                              │                                                (or Exception if exhausted)
                              └─cascade + LLM exhausted──> Exception
```

**Terminal states:** `Matched`, `Exception`, `Excluded`.

`Excluded` is distinct from `Exception`, and the distinction matters. The 5 unrelated
bank debits per run are *correctly* not matched. Counting them as exceptions understates
performance; matching them is a false match. They get
`reason_code = "NOT_A_SETTLEMENT"`.

**To be precise:** the denominator is the 400 recon lines. Bank transactions are not recon
lines, so these 5 were never in the scored population. The reason code records that they
were seen and deliberately excluded — it does not place them in any match-rate figure.

---

## 12. Pipeline Stages

```
acquire → ingest → cascade → [hypothesize] → verify → report
```

### 12.1 Acquire

| | |
|---|---|
| In | `run_id`, adapter selection |
| Out | Four raw dict iterators |
| Side effects | `audit_log`: one row per source with a count |
| Failure | `SourceUnavailable` → exit 2, **no partial write** |

### 12.2 Ingest

| | |
|---|---|
| In | Raw dict streams |
| Transform | Pydantic validation; assign `record_key`; assert all money fields are `int` |
| Out | Rows in the four source tables |
| Failure | **A validation failure is recorded, not raised.** `MALFORMED_SOURCE_ROW`; pipeline continues |
| Idempotency | `INSERT ... ON CONFLICT(record_key) DO UPDATE` |

Rationale: real recon exports contain bad rows. A pipeline that dies on row 217 of 400
is useless. One that quarantines it and reports it is the product.

### 12.3 Cascade

| | |
|---|---|
| In | `CascadeState` — unmatched keys per source, empty `DerivedFacts` |
| Transform | Six passes in fixed order; each consumes the previous residual and may enrich `DerivedFacts` |
| Out | `list[MatchProposal]`, `origin="cascade"` |
| Failure | A pass raising is a bug. Caught at the boundary, logged, pass marked failed, **cascade continues** |

`DerivedFacts` is the only channel by which a pass shares what it learned — and
everything in it is *derived from observed data*, never imported. It is the structural
guarantee behind §4.2.

### 12.4 Hypothesise (optional)

| | |
|---|---|
| In | Residual records, clustered; read-only `DerivedFacts` |
| Out | `list[MatchProposal]`, `origin="llm"` |
| Skipped when | `--no-llm`, residual empty, or `GROQ_API_KEY` absent |
| Failure | Never raises. See §15.4 |

### 12.5 Verify

| | |
|---|---|
| In | **Every** proposal, both origins |
| Transform | Re-read members from SQLite by key; recompute from source values |
| Out | `ArithmeticProof` |
| Side effects | Writes `match_groups` + `group_members` on close; `exceptions` otherwise |

### 12.6 Report

| | |
|---|---|
| In | `match_groups`, `exceptions`, `audit_log`, **and only here** the sealed answer key |
| Out | `results.json`, static HTML |
| Side effects | None on the database |
| Failure | Missing answer key → metrics omitted, run still emits |

---

## 13. The Cascade — Pass Algorithms

Every pass implements the same protocol:

```python
class Pass(Protocol):
    name: str
    def run(self, db: Connection, state: CascadeState) -> list[MatchProposal]: ...

PASSES = [UtrPass(), ExactPass(), AggregatePass(),
          FeeReversalPass(), TimingPass(), TolerancePass()]
```

**Pass order is semantically load-bearing.** Each is defined over the residual its
predecessors left.

### 13.1 What a "match" is

A **reconciliation group** is one settlement, reconciled across all four sources:

```
group grp_<settlement>
  ├─ N recon lines      (payments, refunds, adjustments)
  ├─ N orders           (via recon_line.order_id)
  ├─ 1 bank transaction (via settlement_utr)
  └─ M ledger entries
```

**The closing equation — implemented in `verify/arithmetic.py`, and nowhere else:**

```
Σ(order.amount) − Σ(payment.fee) − Σ(payment.tax)
                − Σ(refund.debit) − Σ(adjustment.debit)
= bank.credit
```

### 13.2 Pass 1 — `utr`

```
for each bank txn with credit > 0:
    candidates = re.findall(r"\d{10,22}", description)
    utr = longest candidate           # rules out short date-like runs
    if utr matches a recon settlement_utr exactly → index it
    else → leave for the tolerance pass
```

Bank rows with `debit > 0` and no UTR match are `NOT_A_SETTLEMENT` — **excluded, not
exceptions.** Matching them would be a false match.

### 13.3 Passes 2–3 — `exact` and `aggregate`

**`exact`:** for each indexed UTR, collect recon lines, join orders via `order_id`,
compute closure with **stated** fee/tax only. **Skip any settlement containing
`fee IS NULL`** — that is pass 4.

**`aggregate`:** same equation, for settlements where refunds and adjustments net against
payments. **The fee-null skip applies here too** — any settlement containing a payment with
`fee IS NULL` is deferred to pass 4, in both `exact` and `aggregate`. Adjustments carry `order_id = NULL` by construction and contribute to the net
with no order member.

**Do not attempt to attribute an adjustment to an order.** For the 5 ambiguous
duplicates this is precisely the trap.

### 13.4 Pass 4 — `fee_reversal` (the payments-literacy pass)

**Step 1 — observe.** Filter to `type == "payment" AND fee IS NOT NULL` — **319 lines in
`clean-august`, not 400.** Refunds and adjustments carry `fee = 0` with `amount > 0`;
including them injects 40 spurious 0-bps observations and destroys the change-point scan.

For each: `bps = round_half_up(fee * 10000, amount)`. Bucket by `method`. Discard buckets
with fewer than 3 observations — **no slab is derived for a discarded bucket and no rate
is guessed.** Its fee-null lines fall through to `timing` and `tolerance` like any other
residual, then to `NO_CANDIDATE`. Log the abandoned inference to `audit_log`.

**Step 2 — detect a change point.** If one bps value accounts for ≥95%, single slab.
Otherwise sort by `created_at` and scan candidate splits, maximising mode purity on both
sides. Accept only if both sides reach ≥95% purity **and** have ≥5 observations.

**A candidate split is an index where `bps` differs between consecutive observations** —
not every index boundary, not day boundaries. That keeps the search proportional to the
number of distinct transitions.

**Step 3 — validate before use.** A slab is accepted only if it reproduces
`credit == amount − fee − tax` **exactly** on 100% of stated-fee lines in its period,
with half-up rounding applied to fee and tax independently. **A slab failing this is
rejected outright, never approximated.**

**Step 4 — derive and close.**

Step 3 is what makes the wrong-rate failure loud instead of silent. Emit accepted slabs
to `DerivedFacts.fee_slabs` → `results.json.derived_fee_slabs`, so the UI shows the rate
change was **discovered, not configured**.

### 13.5 Pass 5 — `timing` (calendar inference)

1. Every distinct `settled_at` date is a business day
2. Weekdays inside the window with **no settlement at all** are candidate holidays —
   with ~6.6 lines per settlement day, an empty weekday is evidence, not noise
3. Validate: `add_business_days(capture_date, 2) == settled_date`, where `capture_date`
   rolls forward one day if captured at or after 18:00 IST. Iterate; drop candidates
   causing widespread mismatch
4. Use the calendar to attach ledger entries with `source_ref = NULL` (78–92 per run)

Accept only if the calendar explains ≥95% of payments with both timestamps. Below that,
record low confidence and let affected records fall through to tolerance.

**Never match on `bank_txns.value_date`.** The recon↔bank join is by UTR only. Zero lag
between `settled_at` and `value_date` happens to hold in this data, but a matcher that
depends on it would break on real data.

### 13.6 Pass 6 — `tolerance`

Three narrow allowances. Each is a constant in `match/constants.py` **with a comment
justifying it**, echoed into `results.json`.

| Allowance | Value | Justification |
|---|---|---|
| Amount delta | ≤ 2 paise **per derived-fee line**, 0 otherwise | See below |
| UTR suffix truncation | ≤ 2 digits | Observed bank formatting defect; **requires unique prefix match** |
| Ledger posting lag | ≤ 1 day | Accountants book same-day or next-day |

**The amount allowance is derived, not flat.** A settlement whose member payments all
carry a *stated* fee must close with `delta == 0` exactly — a stated fee cannot drift.
Only a fee recovered in `fee_reversal` can be off, by at most 1 paise on the fee and 1 on
the tax, since both round half-up independently.

```
allowed_delta = 2 * (number of member payments whose fee was DERIVED)
```

For a settlement with no derived fees this is 0. Settlements average 6.6 lines and reach
32, so a flat settlement-level constant of 2 would be simultaneously too tight for a
multi-line derived settlement and far too loose for a single stated one. Scaling by
derived lines only is both tighter and more honest.

Emitted as `tolerance_constants.amount_delta_paise_per_derived_line: 2`.

A truncated UTR matching two settlements is **ambiguity, not a match.**

### 13.7 `classify_residual` — assigning specific reason codes

Runs at the end of `run_cascade()`, after pass 6 and **before** the LLM stage. It does not
match anything. It converts blanket `NO_CANDIDATE` into specific, honest reason codes.

```python
# match/classify.py
def classify_residual(db: Connection, state: CascadeState) -> list[Exception_]
```

| Detection | Emits |
|---|---|
| Unmatched adjustment with `order_id IS NULL`, where ≥2 orders share the same `customer_id`, `amount` and calendar date | `AMBIGUOUS_DUPLICATE`, `candidates` = those order record_keys |
| Unmatched recon line whose `settlement_utr` matches no bank transaction, after both `utr` and `tolerance` have run | `CROSS_PERIOD_UTR` |
| Everything else still unresolved | `NO_CANDIDATE` |

**Never pick one candidate.** Listing both is the deliverable.

`CONTRADICTORY_LEDGER` is **not** detected here — see §13.8.

### 13.8 Known answer-key limitation — report, do not fix

The answer key marks 2 recon payments per run (6 in `high-ambiguity`) as
`CONTRADICTORY_LEDGER`. Those payments have an order, a stated fee, a settlement and a
bank transaction. **They close correctly under the closing equation, which does not
include ledger entries at all.**

The matcher will therefore match them, and scoring will count them as **false matches**.
This is a defect in the answer key, not in the matcher.

**Do not special-case the scorer. Do not attempt to detect them.** Detecting them would
require inferring how the data was generated, which §4.2 forbids.

Expect ~2 false matches per run traceable to this. State it explicitly in the Phase 5
error analysis, in `docs/challenges-log.md`, and in the README. Reporting a known
limitation honestly is a stronger signal than a clean number obtained by special-casing.

---

## 14. The Verifier

```python
def verify(proposal: MatchProposal, db: Connection,
           facts: DerivedFacts) -> ArithmeticProof     # pure: reads, never writes

def commit(proposal: MatchProposal, proof: ArithmeticProof,
           db: Connection) -> None                     # THE ONLY WRITER of match_groups
```

The verifier:
1. Re-reads every member record from SQLite by `record_key`
2. Recomputes the closing equation from source values
3. **Ignores `claimed_arithmetic` entirely** — it is compared for logging, never used
4. Returns a proof with `closes: bool`

A proposal whose proof does not close is rejected; its members go to `exceptions`. **No
override exists.**

```python
class ArithmeticProof(BaseModel):
    gross: int
    fees: int
    tax: int
    refunds: int
    expected_net: int
    observed_net: int
    delta: int                     # expected − observed; must be 0
    closes: bool
    tolerance_applied: int = 0     # nonzero is SURFACED in the UI
```

Splitting `verify()` from `commit()` is what makes "the verifier is the sole writer" a
testable assertion rather than a promise.

---

## 15. The LLM Layer

```python
def propose(residual: list[RecordKey], db: Connection, facts: DerivedFacts,
            client: Groq | None, *, model: str = "llama-3.3-70b-versatile",
            timeout_s: int = 20) -> list[MatchProposal]
```

Runs **only** on what the cascade could not resolve. Returns `[]` when the client is
None, the residual is empty, or the API is unavailable. **Never raises.**

### 15.1 Model justification (for the README and video)

The task is narrow and structured — read a small residual set, propose a candidate
grouping as JSON. Deep reasoning is unnecessary **because the verifier, not the model,
establishes truth.** Groq's inference speed keeps the hypothesis stage from dominating
runtime, and the OpenAI-compatible client means the provider is swappable in one place.
We chose the smallest capable model; escalation is a config change, decided by
measurement, not assumption.

### 15.2 Prompt contract

- System instruction and data are **structurally separated**
- All free text (`notes`, `receipt`, `description`, `narration`) goes inside
  `<untrusted_source_data>` fences, **never interpolated into the instruction section**
- The model is told its proposal will be independently verified by arithmetic. This is
  true, costs nothing, and improves calibration
- Response: JSON only. Prose is a parse failure

```python
class Hypothesis(BaseModel):
    proposed_group: list[RecordKey]
    reasoning: str                        # displayed in UI, never acted on
    claimed_arithmetic: dict[str, int]    # compared, NEVER used
    confidence: Literal["low","medium","high"]   # displayed, gates nothing
```

`claimed_arithmetic` has **no functional purpose.** It exists so the verifier can catch
the model disagreeing with reality, and so that disagreement can be shown in the
frontend as evidence the architecture works.

### 15.3 Clustering

One call per residual cluster, not per record. Clusters are single-digit, so cost and
latency are bounded by ambiguity rather than record count.

**Clustering key:** residual records sharing a `settlement_utr` form one cluster. Records
with no usable UTR cluster by `(customer_id, calendar date)`.

### 15.4 Failure matrix

| Condition | Action | Reason code |
|---|---|---|
| Malformed JSON | 1 repair retry | `HYPOTHESIS_MALFORMED` |
| Schema violation | 1 repair retry | `HYPOTHESIS_MALFORMED` |
| Timeout > 20s | No retry | `HYPOTHESIS_TIMEOUT` |
| API unavailable / 429 | **Pipeline completes** | `HYPOTHESIS_LAYER_UNAVAILABLE` |
| References unknown key | Reject | `PROOF_DOES_NOT_CLOSE` |
| Proof does not close | Reject | `PROOF_DOES_NOT_CLOSE` |

### 15.5 Publish the contribution honestly

If the LLM resolves 4 records out of 400, **say 4.** A small number is evidence *for*
the architecture. Hiding it invites exactly the suspicion this track screens for.

### 15.6 Injection defence

The dataset contains exactly one order whose `notes` carries an instruction-injection
payload. Prompt-level mitigations reduce the chance of a bad proposal; **the verifier is
what makes a bad proposal harmless** — a match requires arithmetic that closes against
source records the model does not control.

Say it in that order: defence in depth, with the deterministic layer as backstop.

---

## 16. Audit Log

```python
def record(db, stage: str, record_key: str | None, action: str, detail: dict) -> None
def trail(db, record_key: str) -> list[AuditEvent]
```

Append-only. Written at: ingest, each pass attempt (matched / no-candidate / deferred),
each LLM call (prompt hash, latency, tokens, outcome), each verification (full proof),
each exception.

Surfaced in the frontend drill-down. **That trail is the reason to believe the match
rate.** A number without a trail is a claim; a number with one is evidence.

---

## 17. Scoring & Metrics

### 17.1 Definitions — use these exact words in code, README and video

| Metric | Definition |
|---|---|
| **Match rate** | matched **and correct against the sealed key** ÷ 400 |
| **Match precision** | correct matches ÷ all matches made |
| **False match rate** | incorrect matches ÷ all matches made |
| **Unresolved rate** | records sent to exceptions ÷ 400 |
| **Throughput** | records/sec, **separately** for cascade and LLM |

The denominator is always the 400 recon lines. Bank transactions marked
`NOT_A_SETTLEMENT` are not recon lines and appear in neither numerator nor denominator.

### 17.2 Required comparisons in every run

1. **Naive baseline** — exact `order_id` + stated fee + exact UTR + net closes
2. **Cascade without LLM** (`--no-llm`)
3. **Cascade with LLM**
4. **Resolvable ceiling** — 97.2% on three runs, 92.0% on `high-ambiguity`

### 17.3 Error analysis

Produce, and record in `docs/project-progress.md`: which classes fail and why. **If a
class fails badly, report it — do not tune the tolerance to hide it.**

---

## 18. `results.json` Contract

The pipeline's only output to the frontend. Static, self-contained, committed.

```jsonc
{
  "schema_version": 1,
  "run_id": "clean-august",
  "label": "Clean month",
  "generated_at": 1756598400,
  "seed": 42,

  "summary": {
    "records_processed": 400,
    "matched": 0,
    "match_rate": 0.0,
    "match_precision": 0.0,
    "false_matches": 0,
    "unresolved": 0,
    "excluded": 5,
    "runtime_ms_cascade": 0,
    "runtime_ms_llm": 0,
    "throughput_per_sec_cascade": 0.0
  },

  "baseline": { "name": "exact_id_and_amount", "matched": 0, "match_rate": 0.0 },
  "ceiling":  { "resolvable": 389, "rate": 0.9725 },

  "llm_contribution": {
    "enabled": true,
    "records_resolved": 0,
    "hypotheses_proposed": 0,
    "hypotheses_rejected_by_verifier": 0
  },

  "source_totals": {
    "orders_gross": 0, "recon_net": 0, "bank_credited": 0, "ledger_revenue": 0
  },

  "bridge": [
    { "label": "Gross orders",         "amount": 0, "sign": "+", "record_keys": [] },
    { "label": "Processing fees",      "amount": 0, "sign": "-", "record_keys": [] },
    { "label": "GST on fees",          "amount": 0, "sign": "-", "record_keys": [] },
    { "label": "Refunds",              "amount": 0, "sign": "-", "record_keys": [] },
    { "label": "Settled next cycle",   "amount": 0, "sign": "-", "record_keys": [] },
    { "label": "Prior cycle spillover","amount": 0, "sign": "+", "record_keys": [] },
    { "label": "Bank credited",        "amount": 0, "sign": "=", "record_keys": [] }
  ],

  "passes": [
    { "name": "utr",          "matched": 0, "runtime_ms": 0 },
    { "name": "exact",        "matched": 0, "runtime_ms": 0 },
    { "name": "aggregate",    "matched": 0, "runtime_ms": 0 },
    { "name": "fee_reversal", "matched": 0, "runtime_ms": 0 },
    { "name": "timing",       "matched": 0, "runtime_ms": 0 },
    { "name": "tolerance",    "matched": 0, "runtime_ms": 0 },
    { "name": "llm_verified", "matched": 0, "runtime_ms": 0 }
  ],

  "records": [
    {
      "record_key": "recon:pay_XXX",
      "source": "recon",
      "display_amount": 0,
      "status": "matched",
      "pass_name": "aggregate",
      "group_id": "grp_0042",
      "member_keys": [],
      "proof": { "gross":0,"fees":0,"tax":0,"refunds":0,
                 "expected_net":0,"observed_net":0,"delta":0,
                 "closes":true,"tolerance_applied":0 },
      "audit": [ { "stage": "match.exact", "action": "no_candidate", "detail": "" } ]
    }
  ],

  "exceptions": [
    {
      "record_key": "recon:rfnd_XXX",
      "reason_code": "AMBIGUOUS_DUPLICATE",
      "reason_text": "Two payments of ₹2,499 from cust_XXX on 14 Aug 2026; refund carries no order reference. Attribution would be a guess.",
      "passes_tried": ["exact","utr","aggregate","fee_reversal","timing","tolerance","llm"],
      "candidates": ["order:order_AAA","order:order_BBB"]
    }
  ],

  "derived_fee_slabs": [
    { "method": "card", "period_start": "2026-06-01", "period_end": "2026-07-15",
      "inferred_bps": 200, "sample_size": 41, "reproduces_all_stated": true }
  ],

  "tolerance_constants": {
    "amount_delta_paise_per_derived_line": 2,
    "utr_truncation_digits": 2,
    "ledger_lag_days": 1
  }
}
```

`tolerance_constants` is included so allowances are visible in the UI. A tolerance you
cannot see is a tolerance you can abuse — including by yourself, on day 3.

---

## 19. CLI Contract

Entry point: `python -m recon`. Typer.

### `run`

```bash
python -m recon run [--dataset clean-august|all] [--no-llm]
                    [--source fixture|razorpay] [--db PATH] [--out PATH]
                    [--fresh] [--quiet]
```

Emits a live Rich table, then a summary:

```
  Pass            In   Matched  Deferred    ms
  utr            400         —         —     3
  exact          400       138       262    11
  aggregate      262       138       124     9
  fee_reversal   124        41        83    14
  timing          83        53        30     7
  tolerance       30        19        11     4
  llm             11         0        11  2140

  Matched N/400   False matches N   Unresolved N
  Cascade Nms · LLM Nms
```

*Formatting illustration only — not claimed results.*

### `inject`

```bash
python -m recon inject --scenario {llm-hallucination|llm-unavailable|prompt-injection}
```

### `report`

```bash
python -m recon report --dataset clean-august [--html]
```

### `validate`

```bash
python -m recon validate --dataset all      # dataset invariant checks; wire into CI
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Configuration error |
| `2` | Source unavailable |
| `3` | Internal error during scoring |

**Data defects and business ambiguity never produce a nonzero exit.** They are the
output, not a failure.

---

## 20. Module API Reference

### 20.1 Type aliases

```python
RecordKey = str      # "<source>:<id>"
RunId     = str      # "clean-august"
GroupId   = str      # "grp_<settlement_suffix>"
Paise     = int      # enforced by tests/test_money.py
```

### 20.2 Pipeline models

```python
class MatchProposal(BaseModel):
    group_id: GroupId
    member_keys: list[RecordKey]
    pass_name: str
    origin: Literal["cascade", "llm"]
    proof: ArithmeticProof | None = None    # filled by verify/, never by proposer

class Exception_(BaseModel):
    record_key: RecordKey
    reason_code: ReasonCode
    reason_text: str
    passes_tried: list[str]
    candidates: list[RecordKey] = []

class FeeSlab(BaseModel):
    method: str
    period_start: date
    period_end: date
    inferred_bps: int
    sample_size: int
    reproduces_all_stated: bool      # False ⇒ slab MUST be rejected

class DerivedFacts(BaseModel):
    fee_slabs: list[FeeSlab] = []
    business_days: set[date] = set()
    inferred_holidays: set[date] = set()
    utr_index: dict[str, RecordKey] = {}
    calendar_confidence: float = 0.0

class CascadeState(BaseModel):
    run_id: RunId
    unmatched_recon: list[RecordKey]
    unmatched_bank: list[RecordKey]
    unmatched_ledger: list[RecordKey]
    derived: DerivedFacts
```

### 20.3 Reason codes (closed enum)

Adding one requires a UI label and a test.

| Code | Meaning |
|---|---|
| `AMBIGUOUS_DUPLICATE` | Two candidates, no distinguishing reference |
| `CROSS_PERIOD_UTR` | Settlement outside export window |
| `CONTRADICTORY_LEDGER` | Source data internally inconsistent |
| `MALFORMED_SOURCE_ROW` | Failed schema validation at ingest |
| `NOT_A_SETTLEMENT` | Unrelated bank debit — **excluded, not an exception** |
| `PROOF_DOES_NOT_CLOSE` | Verifier rejected the proposal |
| `HYPOTHESIS_TIMEOUT` | LLM exceeded 20s |
| `HYPOTHESIS_MALFORMED` | Invalid JSON after one repair retry |
| `HYPOTHESIS_LAYER_UNAVAILABLE` | API down; pipeline still completed |
| `NO_CANDIDATE` | Cascade and LLM exhausted |

### 20.4 Module signatures

```python
# adapters/
class SourceAdapter(Protocol):
    def orders(self) -> Iterator[dict]: ...
    def recon_lines(self) -> Iterator[dict]: ...
    def bank_txns(self) -> Iterator[dict]: ...
    def ledger_entries(self) -> Iterator[dict]: ...

def get_adapter(kind: Literal["fixture","razorpay"], **kw) -> SourceAdapter
def fetch_recon(year: int, month: int, day: int | None = None,
                *, page_size: int = 100) -> Iterator[dict]

# ingest/
def ingest(adapter: SourceAdapter, db: Connection) -> IngestReport

# match/
def run_cascade(db: Connection, run_id: RunId, *, passes=PASSES) -> CascadeResult
def classify_residual(db: Connection, state: CascadeState) -> list[Exception_]
def extract_utr(description: str) -> str | None
def infer_slabs(lines: list[ReconLine]) -> list[FeeSlab]
def derive_fee(amount: Paise, slab: FeeSlab) -> tuple[Paise, Paise]
def infer_calendar(lines: list[ReconLine]) -> tuple[set[date], set[date], float]
def add_business_days(d: date, n: int, business: set[date]) -> date
def round_half_up(numerator: int, denominator: int) -> int   # matcher's OWN copy

# verify/
def verify(proposal, db, facts) -> ArithmeticProof
def commit(proposal, proof, db) -> None

# hypothesize/
def propose(residual, db, facts, client, *, model, timeout_s) -> list[MatchProposal]
def cluster_residual(residual: list[RecordKey], db: Connection) -> list[list[RecordKey]]

# report/
def score(db: Connection, answer_key: Path) -> ScoreReport
def compute_baseline(db: Connection) -> BaselineResult
def emit_results(report: ScoreReport, path: Path) -> None
def emit_html(results: Path, out: Path) -> None

# audit/
def record(db, stage, record_key, action, detail) -> None
def trail(db, record_key) -> list[AuditEvent]
```

Adapters return **raw dicts**, not models — validation belongs to `ingest/` so there is
exactly one place where a malformed row is handled.

---

## 21. Error Taxonomy

```python
class ReconError(Exception): ...
class ConfigurationError(ReconError): ...    # exit 1
class SourceUnavailable(ReconError): ...     # exit 2
class ScoringError(ReconError): ...          # exit 3
```

**That is the complete list.** Data defects and business ambiguity are **not** Python
exceptions — they are `Exception_` *records* written to the database.

| Class | Handling | Terminates run? |
|---|---|---|
| Configuration | Fail fast, clear message | Yes |
| Source unavailable | Fail before any write | Yes |
| Data defect | → `exceptions`, continue | No |
| Business ambiguity | → `exceptions` with reason + candidates | No |
| Model failure | Retry once, then exception | No |
| Verification failure | Reject, members → exceptions | No |
| Internal bug in a pass | Caught at boundary, pass marked failed, cascade continues | No |

---

## 22. Configuration

| Variable | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | No | Absent → LLM stage skipped, run completes |
| `RECON_LLM_MODEL` | No | Default `llama-3.3-70b-versatile` |
| `RECON_LLM_TIMEOUT_S` | No | Default 20 |
| `RAZORPAY_KEY_ID` | No | Only for `--source razorpay` |
| `RAZORPAY_KEY_SECRET` | No | Only for `--source razorpay` |
| `RECON_DB_PATH` | No | Default `data/<run>/run.db` |
| `RECON_OUT_PATH` | No | Default `data/<run>/results.json` |

**Every variable is optional.** A fresh clone with no `.env` runs the full deterministic
pipeline over the frozen datasets and emits complete results. This is deliberate: the
reviewer's first run must succeed with zero setup.

If you add a variable, add it to `.env.example` in the same phase's commit.

---

## 23. Frontend Specification

**Scope boundary:** this section owns **what** each screen contains — the data shown, the
fields, the rules. `reference/design.md` owns **how** it looks — layout, typography,
colour, spacing, component styling. Neither document repeats the other. If they appear to
disagree about screen content, **this section wins**; `design.md` governs visual treatment
only.

Static Vite + React reading `data/<run>/results.json`. **No server, no API, no upload,
no auth.** A dropdown switches between the four runs.

### 23.1 Screen 1 — Run Overview
Headline strip: records processed · match rate · runtime · unresolved. Four source cards
with their totals. One line: *"Four systems, four different totals. N of 400 reconciled
automatically."*

### 23.2 Screen 2 — Reconciliation Bridge
Horizontal waterfall from gross orders to bank credit. Each band clickable, filtering
screen 3. This is the most persuasive screen — it proves every rupee of the gap is
explained.

### 23.3 Screen 3 — Match Explorer
All 400 records, filterable by resolving pass, colour-coded. The visual point lands
without narration: **deterministic passes dominate, the LLM is a sliver.**

### 23.4 Screen 4 — Exception List
Every unresolved record with a **specific** reason and both candidates listed. Badge:
`Requires human review`. Footer: *"These N were not resolved. No guess was recorded."*

Most submissions hide their failures. This one has a screen dedicated to them.

### 23.5 Record drawer
Click any row → all four source records side by side, plus the full audit trail. This is
where the hallucination-rejection moment is visible.

### 23.6 Rules
- **All visual decisions — layout, typography, colour, spacing, component styling — come
  from `reference/design.md`. Read it before writing any frontend code.** This section
  specifies content only and deliberately contains no visual specification
- `src/lib/format.ts` is the **only** place paise become rupees
- `types.ts` asserts `schema_version === 1`
- Display `tolerance_constants`
- No charting library, no dark mode, no animation beyond a spinner

**Build order: screens 1 and 4 first.** They carry most of the signal.

---

## 24. Failure Injection

Failure recovery is a designed component, not documentation written afterwards.

| Scenario | Injection | Detection | Recovery | Visible where |
|---|---|---|---|---|
| `llm-hallucination` | Force a plausible but wrong grouping | Verifier recomputes; delta ≠ 0 | Rejected; members → exceptions with the model's reasoning preserved | Record drawer |
| `llm-unavailable` | Simulate API failure | Timeout / connection error | Pipeline completes; `HYPOTHESIS_LAYER_UNAVAILABLE` | Run Overview banner |
| `prompt-injection` | Already in the data (1 record) | Verifier — arithmetic cannot be forged | Injected record → exceptions | Exception List |

**The demo moment is `llm-hallucination`.** Show the model producing a confident
proposal with plausible reasoning, the verifier recomputing from source, the delta, the
rejection. The AI was wrong and the system caught it — in a component that would exist
in production regardless.

---

## 25. Testing

Every phase ships with its tests passing. `pytest` green before a phase is complete.

| Test | Protects |
|---|---|
| `test_firewall.py` | §4.2 — no generator imports in `match/`, `hypothesize/`, `verify/` |
| `test_answer_key_seal.py` | §4.6 — no module outside `report/` reads `answer_key.json` |
| `test_money.py` | §4.1 — no float in any model or `results.json` |
| `test_determinism.py` | Same seed, byte-identical dataset |
| `test_idempotency.py` | Two runs, identical results, no duplicate rows |
| `test_persistence_regression.py` | Cascade writes survive a real connection close + reopen — not just an in-memory, single-connection assertion (C-006) |
| `test_ingest.py` | Malformed rows recorded, not raised |
| `test_utr/exact/aggregate/timing/tolerance.py` | Per-pass, one fixture per class |
| `test_fee_reversal.py` | Both slabs recovered; an approximate slab is **rejected** |
| `test_verify.py` | Sole writer; rejects a deliberately wrong group |
| `test_ambiguous.py` | All ambiguous records unresolved, none matched |
| `test_injection.py` | The planted record never appears in a match group |
| `test_no_llm.py` | `--no-llm` produces a complete run |

**Never skip, weaken, or xfail:** `test_firewall`, `test_money`, `test_answer_key_seal`,
`test_ambiguous`, `test_injection`, `test_verify`, `test_persistence_regression`.

`test_firewall.py` is the one that erodes under pressure. On day 3, when fee inference
will not converge, importing one constant from the generator will fix it and silently
void the entire result. **The test exists because discipline will not hold at 2am.**

`test_persistence_regression.py` exists because the other six protect against a
mistake someone would *notice* — a wrong number, an imported constant, a widened
tolerance. This one protects against a mistake that produces **no wrong number at
all**: 39/39 tests green, a plausible-looking CLI table, and an empty database the
moment the process exits, because every existing test asserted against the same
long-lived open connection that wrote the data. It must run against a real file on
disk and must close the writing connection before reopening — an in-memory,
single-connection test cannot catch this class of bug by construction (§7.2, C-006).

---

## 26. Security Posture

This is a scheduled internal batch job, not a user-facing service. There is no
multi-user surface, so **there is no auth layer, and adding one would be theatre.** That
sentence belongs in the README — the judgment it demonstrates is worth more than a login
screen.

What *is* addressed:

- **Secrets:** environment only, never in the repo. `.env` gitignored.
- **Untrusted input:** all free-text fields treated as hostile; delimited in prompts,
  never interpolated into instructions
- **LLM as untrusted component:** the verifier assumes the model may be adversarial
- **Idempotency:** re-running never double-counts
- **Auditability:** append-only log, per-record trail
- **Least privilege (documented):** production would run under a read-only merchant
  credential

---

## 27. Razorpay Integration

The pipeline is shaped around `GET /v1/settlements/recon/combined`, which returns settled
payments, refunds, transfers and adjustments for a day or month. The `recon_lines` schema
mirrors its documented fields (§6.2), and the T+2 domestic settlement cycle drives the
timing logic (§13.5).

`adapters/razorpay_client.py`:
- Auth: HTTP Basic from `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET`
- Pagination: `count` / `skip`, drain until short page
- Retry: 3 attempts, exponential backoff with jitter, on **5xx and 429 only**
- **No retry on 4xx** — a 401 is a config error and retrying hides it
- Raises `SourceUnavailable` on exhaustion

> **VERIFY THIS before Phase 2 freezes `models/`:** whether the recon endpoint returns
> data in test mode, and whether test-mode settlements exist without real payment flow.
> Also verify exact field nullability against current Razorpay docs.
>
> If test mode does not support it, `RazorpayAdapter` ships as a documented stub and the
> README says so plainly. **An honest stub behind a clean interface is a better signal
> than a fabricated integration. Never fabricate API behaviour.**

---

## 28. Deployment

**Now:** pipeline runs locally on demand and emits `results.json`. Frontend is a static
build deployed to Vercel or Netlify free tier. Frozen datasets and results are committed.

Nothing is hosted except static files. Nothing can go down, nothing costs money, nothing
needs maintenance — the site is still up in 2027 as a portfolio piece.

**Production shape (documented, not built):** a scheduled daily job after the settlement
window closes, running under a read-only merchant credential, writing to an append-only
store, emailing the exception list to the finance operator.

---

## 29. Scaling Analysis

**Written in Phase 8, after measurement. Never before** — a scaling section full of
guesses is exactly the unsupported claim this track warns against. ~200 words, appended
here as §29.1.

Must contain:
- Measured throughput, per pass
- Which passes partition cleanly (`exact`, `tolerance` — trivially, by settlement cycle)
- **Where it breaks first: many-to-one candidate-set explosion is combinatorial in
  settlement size**, bounded here by the daily window (max 32 lines observed)
- The fix: block on UTR before parallelising

Naming your own bottleneck precisely is the senior move. Claiming you do not have one is
the junior move.

---

## 30. README & Submission Checklist

### 30.1 README — written Phase 8, with real numbers

Opening line: the one-line pitch from §1.2.

Must contain:
- The philosophy: **the LLM proposes, the arithmetic disposes**
- Metric definitions verbatim from §17.1
- Results table: baseline → cascade → +LLM → ceiling, all four datasets
- **The LLM's exact contribution, published**
- The tolerance constants and their justifications
- The honest exception list
- **"Why not the JVM?"** — considering Java for fintech-appropriate reasons and choosing
  Python deliberately
- **"Why no auth?"** — §26's sentence
- Synthetic data disclosure, and that the fee schedule is invented
- **VERIFY status** of the Razorpay test-mode endpoint — stated honestly

### 30.2 Final checklist

- [ ] `pytest` green, `ruff` clean
- [ ] Fresh clone runs with **zero env configuration**
- [ ] All four `results.json` committed
- [ ] No secrets in the repo; `.env` gitignored
- [ ] Commit history incremental with real messages
- [ ] `docs/challenges-log.md` has real entries, written as they happened
- [ ] Someone else clones it cold and runs it
- [ ] Video: problem → why existing systems fail → detection → bounded action →
      injected failure → recovery → measurable results + audit trail

### 30.3 Cut order under time pressure

Frontend polish → LLM layer → extra datasets.

**Never cut:** the verifier, the exception list, honest metrics, or the six protected
tests in §25.

A deterministic pipeline with honest numbers and no LLM beats a flashy one with
unverifiable results. That is not a consolation position — it is the track's actual bar.