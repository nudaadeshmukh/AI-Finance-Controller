# Project Progress Log

**Purpose:** this file is the running memory of the project across Claude Code sessions.
Read it first at the start of any new session, before reading anything else, to know
exactly what already exists. Update it last, at the end of every phase, after the phase's
code is actually working.

**Rules for updating this file:**
- Append a new entry per phase. Never edit or delete a previous phase's entry, even if
  something built in that phase later gets changed — add a note in the *current* phase's
  entry instead ("Phase 3's verifier signature was adjusted here because...").
- Be concrete: file paths, not vague descriptions. "Added `infer_slabs()` in
  `recon/match/fee_reversal.py`" — not "added fee logic."
- "Known issues / TODOs" is not optional even if a phase felt complete — note anything
  deferred, simplified, or assumed, however small. This is what prevents small gaps from
  silently compounding across a four-day build.
- Record measured numbers when a phase produces them. Never record a number you did not
  actually measure.
- Errors and challenges go in `docs/challenges-log.md`, logged as they happen — not here.
  This file is state; that file is history.

---

## Current state

| | |
|---|---|
| **Current phase** | Phase 4 complete |
| **Next phase** | Phase 5 — Scoring, Baseline, results.json |
| **Deadline** | 5 September 2026 |
| **Pipeline runs?** | `run` does acquire+ingest+cascade(all 6 passes)+classify_residual for real; hypothesize/report still stubbed |
| **Latest match rate** | Not yet scored against the answer key (Phase 5). Raw matched-count/400: clean-august 350, heavy-refunds 257, holiday-skew 326, high-ambiguity 256 |

| Phase | Status |
|---|---|
| 0 — Specification + datasets | ✅ complete |
| 1 — Project foundation | ✅ complete |
| 2 — Data layer | ✅ complete |
| 3 — Verifier + passes 1–3 | ✅ complete |
| 4 — Passes 4–6 | ✅ complete |
| 5 — Scoring + results.json | ⬜ not started |
| 6 — LLM layer + injection | ⬜ not started |
| 7 — Frontend | ⬜ not started |
| 8 — README + scaling | ⬜ not started |

---

## Phase 0 — Specification & Datasets

**Status:** complete

Architecture, schemas, pass algorithms, API contracts, metrics and all 8 phases were
fully designed and locked before any pipeline code was written. See
`reference/master_specification.md` (the single technical source of truth),
`reference/implementation_guide.md`, and `CLAUDE.md`.

**Completed features:**
- `reference/master_specification.md` — 30 sections; architecture, schemas, DDL, pass
  algorithms, LLM contract, metrics, `results.json`, CLI, frontend spec
- `reference/implementation_guide.md` — 8 phases, each naming the spec sections it needs
- `CLAUDE.md` — 12 non-negotiable rules
- `recon/generate/generator.py` — synthetic generator built on a simulated business
  process, not injected noise
- `recon/generate/validate.py` — 9 independent invariant checks, re-deriving everything
  from emitted JSON rather than trusting the generator
- Four frozen datasets, each **exactly 400 recon lines**

**Files modified:**
```
CLAUDE.md
reference/master_specification.md
reference/implementation_guide.md
docs/project-progress.md
docs/challenges-log.md
.env.example
.gitignore
recon/generate/generator.py
recon/generate/validate.py
data/manifest.json
data/{clean-august,heavy-refunds,holiday-skew,high-ambiguity}/sources/*.json
data/{clean-august,heavy-refunds,holiday-skew,high-ambiguity}/answer_key.json
```

**Measured results:**

| Run | Orders | Recon | Bank | Ledger | Naive baseline | Resolvable ceiling |
|---|---|---|---|---|---|---|
| `clean-august` | 360 | 400 | 65 | 566 | 126/400 (31.5%) | 389/400 (97.2%) |
| `heavy-refunds` | 296 | 400 | 51 | 536 | 79/400 (19.8%) | 389/400 (97.2%) |
| `holiday-skew` | 360 | 400 | 59 | 538 | 120/400 (30.0%) | 389/400 (97.2%) |
| `high-ambiguity` | 350 | 400 | 60 | 553 | 147/400 (36.8%) | 368/400 (92.0%) |

55–78 percentage points of headroom between naive and ceiling. Validation: **0 failures
across all four runs.**

**Remaining work:**
Everything in Phases 1–8. Critical path is Phases 1 → 5; after Phase 5 the submission is
viable even if nothing else ships.

**Known issues / TODOs:**

| # | Item | Priority | Blocking |
|---|---|---|---|
| 1 | ✅ RESOLVED — `GET /v1/settlements/recon/combined` authenticates with test-mode
keys and returns a valid `{"entity":"collection","count":0,"items":[]}`. Test mode
generates no settlements, since settlements require real money movement to a verified
bank account. `RazorpayAdapter` ships as a documented stub per Phase 2. Verified
1 September 2026.  | - | Closed |
| 2 | ✅ CLOSED — field nullability could not be observed empirically (no items
returned). Schema in master spec §6.2 stands, derived from the documented response
example. | - | Closed |
| 3 | Tolerance constants must be chosen and justified **before** measurement, never tuned after | High | Phase 4 |
| 4 | Business-day/holiday calendar inference method must be documented in the README | Medium | Phase 8 |
| 5 | Settlements came out **daily** (~60/run), not the ~12 originally assumed. Daily is correct for T+2; the spec reflects the measured reality | Low | — |
| 6 | Fee schedule is **synthetic and invented**. README must state this explicitly and must never present it as Razorpay's real pricing | Medium | Phase 8 |

---

## Phase 1 — Project Foundation

**Status:** complete

**Completed features:**
- Full folder structure per §3.2: `recon/{models,db,adapters,ingest,match,
  hypothesize,verify,report,audit,inject}`, `tests/`, `frontend/` skeleton
- `pyproject.toml`, `requirements.txt` — five runtime deps pinned exact
  (pydantic 2.13.5, typer 0.27.2, rich 15.0.0, groq 1.7.0, jinja2 3.1.6) plus
  httpx 0.28.1; dev deps pytest 8.4.2, ruff 0.16.5
- `LICENSE` (MIT)
- `recon/errors.py` — the 3 exception classes from §21
- `recon/config.py` — env loading + `.env` loader, every variable optional
- `recon/models/` — `Order`, `ReconLine`, `BankTxn`, `LedgerEntry` (§6);
  `MatchProposal`, `ArithmeticProof`, `CascadeState`, `Exception_` (§20.2,
  `pipeline.py`); `DerivedFacts`, `FeeSlab` (§20.2, `facts.py`); `ReasonCode` +
  `REASON_LABELS` (§20.3, `reasons.py`); type aliases `RecordKey`/`RunId`/
  `GroupId`/`Paise` (§20.1, defined in `sources.py` — see Known issues)
- `recon/db/schema.sql` — the full DDL from §7; `connection.py` (connect,
  apply schema, `transaction()` context manager)
- `recon/cli.py` — Typer `run`/`inject`/`report`/`validate` per §19, each a
  stub that prints and exits 0
- Every other module stubbed with the exact signatures from §20.4 (and §13's
  `Pass` protocol, §14's `verify`/`commit`, §15.2's `Hypothesis`), bodies
  raising `NotImplementedError`
- `tests/conftest.py` (in-memory DB fixture), `test_firewall.py` (AST-based:
  scans `match/`, `hypothesize/`, `verify/` for any import referencing
  `recon.generate`, plus a whole-tree check that `generate/` is imported by
  nothing), `test_money.py` (money fields are int-typed on the real models;
  pydantic rejects a fractional float on an `Order.amount`; a committed
  `results.json`'s money fields, if present, are JSON ints), `test_answer_key_
  seal.py` (text-scans every `.py` under `recon/` except `report/scoring.py`
  and `recon/generate/` for the string `answer_key`) — all written and passing
- `.github/workflows/ci.yml` — ruff, pytest, `recon validate --dataset all`
- `frontend/` skeleton only: `package.json`, `vite.config.ts`, `index.html`,
  empty `src/{screens,components,lib}/` (`.gitkeep`d) — no screens, no
  components, no styling, per Phase 1 scope
- Fixed a stale doc/comment inconsistency found while re-reading the updated
  spec: `.env.example`'s `RECON_LLM_MODEL` comment still said `claude-haiku-4-5`
  after CLAUDE.md/§22 were corrected to `llama-3.3-70b-versatile`

**Files modified:**
```
pyproject.toml, requirements.txt, LICENSE, .env.example
recon/__init__.py, __main__.py, cli.py, errors.py, config.py
recon/models/{__init__,sources,pipeline,facts,reasons}.py
recon/db/{__init__,schema.sql,connection,queries}.py
recon/adapters/{__init__,base,fixture,razorpay,razorpay_client}.py
recon/ingest/{__init__,validate,persist}.py
recon/match/{__init__,base,classify,constants,money,utr,exact,aggregate,
             fee_reversal,timing,tolerance}.py
recon/hypothesize/{__init__,client,prompt,parse,cluster}.py
recon/verify/{__init__,arithmetic,proof}.py
recon/report/{__init__,scoring,baseline,results,html}.py,
             report/templates/report.html.j2
recon/audit/{__init__,events}.py
recon/inject/{__init__,hallucination,unavailable}.py
tests/{conftest,test_firewall,test_money,test_answer_key_seal}.py
tests/fixtures/.gitkeep
.github/workflows/ci.yml
frontend/{package.json,vite.config.ts,index.html}
frontend/src/{screens,components,lib}/.gitkeep
docs/project-progress.md, docs/challenges-log.md
```

**Tests:**
- pytest: 6 passed
- ruff: clean

**Measured results:** none — no matching logic exists yet.

**Remaining work:**
Phases 2–8, per the implementation guide. Phase 2 (Data Layer) is next.

**Known issues / TODOs:**
- §3.2's folder comments don't assign a home to `Exception_`, `IngestReport`,
  `CascadeResult`, `ScoreReport`, `BaselineResult`, `AuditEvent`, or the §20.1
  type aliases. Placed by inference, not spec instruction — flagging per
  CLAUDE.md rule 12 rather than silently deciding and staying quiet:
  - `Exception_` → `models/pipeline.py` (grouped with the other pipeline
    output types; it's a data-defect *record*, not a Python exception)
  - `RecordKey`/`RunId`/`GroupId`/`Paise` → **`models/types.py`** (moved here
    on user review, corrected same session — see below)
  - `IngestReport`, `CascadeResult`, `ScoreReport`, `BaselineResult` → real
    provisional fields with `extra="forbid"` (moved off `extra="allow"` on
    user review, corrected same session — see below), defined alongside the
    function that returns them (`ingest/__init__.py`, `match/__init__.py`,
    `report/scoring.py`, `report/baseline.py` respectively)
  - `AuditEvent` → `audit/events.py`, fields copied verbatim from the
    `audit_log` DDL columns (§7), since that's the only documented shape
- **Two corrections applied after user review, same session:**
  1. `RecordKey`/`RunId`/`GroupId`/`Paise` moved out of `models/sources.py`
     into a new `models/types.py` (zero internal imports). `sources.py` now
     depends on nothing internal, as a leaf describing the four raw external
     schemas should; every module that previously imported the aliases from
     `sources.py` (`models/{pipeline,facts,__init__}.py`,
     `hypothesize/{__init__,parse,cluster}.py`, `audit/{__init__,events}.py`,
     `match/{__init__,fee_reversal}.py`) now imports them from `types.py`.
  2. `IngestReport`, `CascadeResult`, `ScoreReport`, `BaselineResult` changed
     from `extra="allow"` to `extra="forbid"` with real (if provisional)
     fields, since `extra="allow"` means a typo'd field validates silently —
     directly contradicting §4.4 (no third state, no silent guessing) and the
     whole premise behind sealing the answer key. Fields were sized to what
     each function's actual downstream consumer needs:
     - `IngestReport`: `orders`/`recon_lines`/`bank_txns`/`ledger_entries`/
       `malformed` counts — matches Phase 2's acceptance line exactly
       (`Ingested: orders 360 · recon_lines 400 · ...`)
     - `CascadeResult`: a new `PassStat` (`name`, `in_count`, `matched`,
       `deferred`, `runtime_ms`) per pass, plus `total_matched`/`runtime_ms` —
       matches §19's per-pass CLI table and §18's `passes` array
     - `ScoreReport`: the full §17.1/§18 `summary` metric set plus
       `ceiling_resolvable`/`ceiling_rate` (the answer-key-derived numbers
       only this module is allowed to compute)
     - `BaselineResult`: `name`/`matched`/`match_rate` — this one was already
       fully specified by §18's `baseline` example, not actually a guess
  All four are still provisional and will be revised (fields added/renamed,
  not the `extra="forbid"` posture) when each function is implemented in its
  real phase — noted at the top of each class's docstring.
- `match/__init__.py`'s `PASSES` list is empty — the six concrete pass classes
  (`UtrPass` etc.) don't exist yet; populating it now would be building ahead
  of Phase 3/4 scope
- Windows terminal here defaults to the legacy cp1252 codepage, which cannot
  render `→`/`—`/`§` — `recon/cli.py`'s help text and all `console.print()`
  output had to be plain ASCII, or Rich crashes with `UnicodeEncodeError`
  trying to render the `--help` screen. Also: Typer/Rich's help renderer
  interprets a literal `[hypothesize]` in a docstring as markup and eats it —
  had to write `(hypothesize)` instead. Logged in challenges-log.
- Added `pythonpath = ["."]` to `[tool.pytest.ini_options]` in `pyproject.toml`
  so `pytest` can `import recon` without an editable install — the Phase 1
  acceptance block only lists `pip install -r requirements.txt`, which
  installs runtime deps but not the `recon` package itself
- `pyproject.toml`'s ruff config excludes `recon/generate/` from linting —
  it's outside the pipeline's dependency graph (CLAUDE.md rule 2) and was
  built in Phase 0; not re-linted to this phase's conventions
- `design.md` was replaced by the user this session with a dashboard-specific
  design system; confirmed it covers every component §23 needs (status
  badges, proof table, waterfall, data table, drawer) before proceeding

---

## Phase 2 — Data Layer

**Status:** complete

**Completed features:**
- `recon/db/queries.py` — every SQL string as a named constant: one
  `UPSERT_*` per source table (`INSERT ... ON CONFLICT(record_key) DO
  UPDATE`), `UPSERT_EXCEPTION`, `INSERT_AUDIT_LOG`, `SELECT_AUDIT_TRAIL`
- `recon/audit/__init__.py` — `record()` (participates in the caller's
  transaction, never opens its own) and `trail()`, both implemented for real
- `recon/adapters/fixture.py` — `FixtureAdapter` reads `data/<run_id>/
  sources/*.json` eagerly per method call (not lazily on first iteration), so
  a missing/unreadable file raises `SourceUnavailable` immediately rather
  than partway through an ingest transaction
- `recon/adapters/razorpay.py` — documented stub; every method raises
  `SourceUnavailable("live adapter not implemented")` immediately. The
  VERIFY task from §27 is already closed per Phase 0's progress-log entry
  (test-mode recon endpoint returns an empty collection; nothing for a live
  adapter to return in this environment)
- `recon/adapters/__init__.py` — `get_adapter()` dispatches `fixture` |
  `razorpay`; unknown kind raises `ConfigurationError`
- `recon/ingest/validate.py` — `validate_row()` (pydantic validation, returns
  an `Exception_` instead of raising) and `best_effort_key()` (a positional
  fallback record_key — `"<source>:MALFORMED-<index>"` — so two malformed
  rows in the same source never collide on `exceptions`' primary key)
- `recon/ingest/persist.py` — one `upsert_*` function per source table plus
  `persist_exception()`, all via the named queries above
- `recon/ingest/__init__.py` — `ingest()` implemented: one transaction per
  source file, malformed rows recorded and skipped (never raised), an
  `audit.record()` call per source (action `"ingested"`, count + malformed)
  and per malformed row (action `"malformed"`)
- `recon/cli.py run` — wired acquire (`get_adapter`) -> ingest for real;
  supports `--dataset all` (reads `run_id` out of `data/manifest.json`, per
  §8.3.1's "the pipeline reads nothing from it except run_id and label"),
  `--fresh` (deletes the existing db file first), `--db` override; prints a
  Rich table of counts plus an `Ingested: orders N | recon_lines N | ...`
  summary line; `SourceUnavailable` -> exit 2, `ConfigurationError` -> exit 1
  (§21); cascade/hypothesize/verify/report remain stubbed post-ingest
- `tests/conftest.py` — added `make_db()` (a second standalone in-memory
  connection, for cross-run determinism checks) and `MockAdapter` (a
  `SourceAdapter` built from plain lists, so ingest tests don't need to touch
  real fixture files)
- `tests/test_ingest.py`, `test_idempotency.py`, `test_determinism.py` —
  written and passing (11 new tests; see Known issues for how the latter two
  were interpreted)

**Files modified:**
```
recon/db/queries.py, recon/db/connection.py (unchanged, reused)
recon/audit/__init__.py
recon/adapters/{__init__,fixture,razorpay}.py
recon/ingest/{__init__,validate,persist}.py
recon/cli.py
tests/conftest.py, tests/{test_ingest,test_idempotency,test_determinism}.py
docs/project-progress.md, docs/challenges-log.md
```

**Tests:**
- pytest: 17 passed (6 from Phase 1 + 11 new)
- ruff: clean

**Measured results (real, from running the CLI against the frozen fixtures):**

| Dataset | orders | recon_lines | bank_txns | ledger_entries | malformed |
|---|---|---|---|---|---|
| clean-august | 360 | 400 | 65 | 566 | 0 |
| heavy-refunds | 296 | 400 | 51 | 536 | 0 |
| holiday-skew | 360 | 400 | 59 | 538 | 0 |
| high-ambiguity | 350 | 400 | 60 | 553 | 0 |

All four match Phase 0's measured counts exactly. Re-running `python -m recon
run --dataset clean-august` (no `--fresh`) a second time leaves every table's
row count unchanged — verified directly via `sqlite3` against the real
`run.db`, not just in the pytest suite.

**Remaining work:**
Phases 3-8. Phase 3 (Verifier + Cascade Passes 1-3) is next — per the
implementation guide, build `verify()`/`commit()` first, before any pass.

**Known issues / TODOs:**
- `test_determinism.py`'s literal protection per §25 is "Same seed,
  byte-identical dataset" — a Phase 0 (dataset generation) concern already
  closed. For Phase 2, I applied the same determinism *principle* to the
  layer actually being built: two independent fresh databases, ingesting the
  same input once each, must produce byte-identical table content. This is a
  judgment call, not a literal reading of the test's original description —
  flagging it rather than silently reinterpreting the test's protection.
- `test_idempotency.py` is deliberately distinct from `test_determinism.py`:
  idempotency re-ingests into the *same* database twice (no duplicate rows);
  determinism ingests into *two separate* databases once each (identical
  output). Both matter and neither subsumes the other.
- `audit_log` rows carry a real wall-clock `int(time.time())` timestamp, not
  a seeded/deterministic one. This does not threaten `results.json`
  byte-identity (§18's per-record `audit` array carries only
  `stage`/`action`/`detail`, never `ts` or `record_key`), but it does mean
  `audit_log` itself grows differently run to run in real time — confirmed
  this is fine since audit_log is explicitly append-only and its row count
  is not a determinism target.
- **RESOLVED, same session, on user direction — and the spec itself is now
  updated to match, not just this log.** The §7.2 vs §12.1 tension above is
  settled in favor of §12.1. `ingest()` wraps all four sources in **one**
  transaction, not one per source. `reference/master_specification.md` §7.2
  and `reference/implementation_guide.md`'s Phase 2 "Key rules" were both
  rewritten to state this as the actual rule (with the reasoning), so a
  future session reading either document cold gets the same answer the code
  actually implements — this is no longer documented anywhere as an open
  question or a deviation. Chosen over the alternative (explicitly deleting
  already-committed rows for this run_id on failure) because a single outer
  transaction is atomic by construction and, unlike a delete-after-the-fact
  cleanup, can never touch data a *different*, already-closed successful
  `ingest()` call left behind — only this call's own uncommitted work rolls
  back. `audit_log` writes still participate in the same enclosing
  transaction, preserving that half of §7.2. Covered by a test,
  `test_source_unavailable_partway_through_leaves_no_partial_write`
  in `test_ingest.py`: a source-3-of-4 failure leaves zero rows in all four
  source tables *and* `audit_log`, verified directly against a real db, not
  just in-memory. Logged as C-004 in `docs/challenges-log.md`.
- `_resolve_run_ids()` in `cli.py` falls back to a hardcoded list of the four
  known run ids if `data/manifest.json` is missing, so `--dataset all` still
  works even without the manifest. Not spec-mandated; a defensive default.
- Ran the full `--dataset all` flow and a `--source razorpay` /
  `--source bogus` error-path check manually against the real fixtures (not
  just pytest) to confirm exit codes 2 and 1 respectively. No challenges-log
  entry for Phase 2 — nothing broke; C-003 from Phase 1 remains the only
  entry so far.

---

## Phase 3 — Verifier + Cascade Passes 1-3

**Status:** complete

**Completed features:**
- `verify/arithmetic.py` — `compute_closing_equation(orders, recon_lines) ->
  (gross, fees, tax, refunds, expected_net)`, the closing equation from
  §13.1 in exactly one place. `refund.debit` and `adjustment.debit` are
  summed together into the single `refunds` field `ArithmeticProof` provides
  (no separate adjustments field exists in the schema) — documented as a
  naming choice, not a simplification of the equation.
- `verify/proof.py` — `build_proof()`: decides `closes` from `delta == 0`
  **and** a `verifiable` flag, so a coincidental zero delta on an
  unverifiable proposal (missing bank txn, unresolved fee) can never read as
  closing.
- `verify/__init__.py` — `verify()` (pure, re-reads every member by
  `record_key`, never writes) and `commit()` (the sole writer of
  `match_groups`/`group_members`; on rejection writes nothing to
  `exceptions` — per §11's lifecycle a rejected proposal returns to
  Unmatched, only cascade+LLM exhaustion in Phase 4's `classify_residual`
  produces a permanent exception; clears any stale exception for a key that
  now matches, since a record can't be both per rule 4)
- `ingest/persist.py` — added `read_order/read_recon_line/read_bank_txn/
  read_ledger_entry`, the read-back inverse of the existing `upsert_*`
  writers, used by `verify()` (an allowed forward import, `ingest ← match ←
  verify` per §3.3)
- `match/money.py` — `round_half_up()` implemented (matcher's own copy, not
  called by anything yet — passes 1-3 only use stated fee/tax; Phase 4's
  `fee_reversal.py` is the first real caller)
- `match/utr.py` — `extract_utr()` and `UtrPass`: indexes UTR matches into
  `DerivedFacts.utr_index`, excludes unrelated bank debits as
  `NOT_A_SETTLEMENT`, never proposes a match itself
- `match/exact.py` — `ExactPass` and the shared `build_settlement_proposal()`
  (also used by `aggregate.py`): builds one `MatchProposal` per settlement
  UTR, stated fee/tax only, skips any settlement with a null-fee payment or
  a refund/adjustment line
- `match/aggregate.py` — `AggregatePass`: same equation, for settlements
  that do contain refund/adjustment lines; never attributes an adjustment
  to an order (`order_id` stays `NULL` for those, per §6.2)
- `match/classify.py` — **`has_ambiguous_adjustment(db, settlement_id)`
  added a phase early** (§13.7's detection condition only — no reason code,
  no candidate list). See C-005: `aggregate`, built literally per §13.3,
  produced confirmed false matches on ambiguous adjustments when run
  against real data; this function is the guard `build_settlement_proposal`
  calls to defer (not exclude) those settlements for Phase 4's
  `classify_residual` to pick up and classify properly. `classify_residual`
  itself remains `NotImplementedError`, unchanged from Phase 1's stub.
- `match/__init__.py` — `run_cascade()` implemented: `PASSES = [UtrPass(),
  ExactPass(), AggregatePass()]`; one transaction per pass (§7.2, unchanged
  for the cascade); routes every cascade proposal through the same
  `verify()`/`commit()` a future LLM proposal will use (rule 3); a failing
  pass's transaction rolls back and `state`'s residual is rebuilt from the
  database rather than trusted from pre-exception in-memory mutations
- `db/queries.py` — added `SELECT_*_BY_KEY` read queries, `UPSERT_MATCH_GROUP`,
  `UPSERT_GROUP_MEMBER`, `DELETE_EXCEPTION_BY_KEY`,
  `SELECT_UNMATCHED_{RECON,BANK,LEDGER}_KEYS`,
  `SELECT_DISTINCT_RECON_SETTLEMENT_UTRS`,
  `SELECT_RECON_LINES_BY_SETTLEMENT_UTR`,
  `SELECT_ADJUSTMENTS_BY_SETTLEMENT_ID`, `SELECT_DUPLICATE_ORDER_BUCKET_COUNT`
- `cli.py run` — wired cascade after ingest for real: prints a per-pass Rich
  table (pass/in/matched/deferred/ms) and a `Matched N/400  Cascade Nms`
  summary line, matching §19's illustration
- `tests/test_verify.py`, `test_utr.py`, `test_exact.py`, `test_aggregate.py`,
  `test_persistence_regression.py` — written and passing (42 total, up from
  6 at end of Phase 1)
- `verify/arithmetic.py` — **C-007 fix**: `compute_closing_equation()` now
  derives the payment-order set from `recon_lines` itself (only orders
  referenced by a `payment` line), rather than summing every `Order` object
  a caller passes in — a refund's `order_id` can point at an order paid in a
  wholly different, earlier settlement, and summing that order's full
  amount into `gross` again was double-counting it

**Files modified:**
```
recon/verify/{__init__,arithmetic,proof}.py
recon/ingest/persist.py (read_* additions)
recon/match/{__init__,money,utr,exact,aggregate,classify}.py
recon/db/queries.py
recon/cli.py
tests/{test_verify,test_utr,test_exact,test_aggregate,test_persistence_regression}.py
CLAUDE.md, reference/master_specification.md (§25, §7.2 comment)
docs/project-progress.md, docs/challenges-log.md
```

**Tests:**
- pytest: 42 passed
- ruff: clean

**Measured results (real, against all four frozen datasets — raw matched
count, NOT validated against the answer key; that's Phase 5. Corrected after
the C-007 fix; earlier numbers in this entry's first draft were low by
exactly the double-counted amount):**

| Dataset | recon_lines | utr matched | exact matched | aggregate matched | Total matched |
|---|---|---|---|---|---|
| clean-august | 400 | 0 | 88 | 38 | 126 |
| heavy-refunds | 400 | 0 | 30 | 50 | 80 |
| holiday-skew | 400 | 0 | 76 | 38 | 114 |
| high-ambiguity | 400 | 0 | 55 | 70 | 125 |

`utr` matches 0 recon lines by design — it only indexes UTRs and excludes
unrelated bank debits, never proposes. **`clean-august`'s 126/400 now equals
the naive baseline (126/400) exactly** — expected, and worth stating
explicitly so nobody reads it as a coincidence or a regression later: naive
credits a record if it independently satisfies exact-join + stated-fee +
exact-UTR + net-closes, with no requirement that the *whole settlement*
close together; `exact`+`aggregate` correctly defer every settlement
containing even one fee-null payment line entirely to Phase 4's
`fee_reversal` (41 fee-null lines' settlements pull in far more than 41
lines once the whole settlement is deferred). At exactly this ceiling, the
two methods agree by construction — but getting there required fixing
C-007 first, since before that fix `aggregate` was 0 in two of four runs
and matching only 88/400 overall in clean-august, which was genuinely
*below* what the null-fee-defer explanation alone predicted. The
null-fee-defer explanation was real but incomplete; C-007 was the rest of
the gap.

**Remaining work:**
Phases 4-8. Phase 4 (Passes 4-6: `fee_reversal`, `timing`, `tolerance`, plus
finishing `classify_residual`) is next — expected to raise the matched
counts substantially, since most of the current residual is fee-null or
timing-skewed, per §8.2's difficulty distribution.

**Known issues / TODOs:**
- **C-005** (see challenges-log): `match/classify.py`'s
  `has_ambiguous_adjustment()` was built a phase early as a deliberate,
  narrow exception to "do not build ahead" — a confirmed false-match risk,
  not a hypothetical one. Phase 4 must import and reuse this function in
  `classify_residual` rather than re-deriving the detection condition.
- **C-006** (see challenges-log): the cascade's writes were never actually
  committed to disk for the entire time Phase 3 was being built — 39/39
  tests were green throughout, because every test asserted against the same
  long-lived open connection that wrote the data, which lets SQLite read
  back its own uncommitted writes. Caught only by manually running the CLI
  twice and inspecting `run.db` directly. Fixed by wrapping each pass in
  `with transaction(db):`; the class of bug is now permanently guarded by
  the new protected test `test_persistence_regression.py` (added to
  CLAUDE.md's and §25's never-skip list, the seventh protected test).
  **This is the single most important lesson from Phase 3**: an all-green
  in-memory test suite proved the matching *logic* was right and said
  nothing about whether the *persistence* was real.
- **C-007** (see challenges-log): `compute_closing_equation()` double-counted
  a refunded order's full amount when that order's original payment settled
  in a *different* settlement — found by refusing to accept the first
  plausible-sounding explanation for why 88/400 was below the 126/400 naive
  baseline, and instead measuring the gap directly against source data.
  Fixed, and covered by a new regression test in `test_aggregate.py`,
  verified load-bearing by temporarily reintroducing the bug and confirming
  the test fails with the original symptom.
- `match/exact.py`'s `group_id_for_settlement()` derives the group id from
  the 8 characters following `setl_` in `settlement_id`, matching the
  pattern observed in the answer keys read back in the very first
  documentation-review session (before this phase's work began) — this was
  not re-derived from the sealed answer key during matching; it's a
  convention inferred from the `settlement_id` string shape itself, which is
  ordinary source data, not sealed.
- `run_cascade()`'s per-pass exception handling rebuilds `state`'s residual
  lists from the database on any pass failure, but `state.derived`
  (`DerivedFacts`, e.g. `utr_index`) is deliberately left as-is rather than
  rolled back — it isn't persisted, so there's nothing to roll back to, and
  a partially-enriched value is low-risk to carry into the next pass. Not
  exercised by a dedicated test yet (no pass currently raises in practice).
- `PassStat`/`CascadeResult` (in `match/__init__.py`) count "matched" in
  terms of recon lines, matching §19's illustrative CLI table
  (`exact 400 138 262 11`) — not settlement/group counts. Worth
  double-checking this convention still reads correctly once `results.json`
  is built in Phase 5 against §18's `passes` array.

---

## Phase 4 — Cascade Passes 4-6 (the hard tail)

**Status:** complete

**Completed features:**
- `match/constants.py` — the three §13.6 tolerance constants, each with a
  justifying comment: `AMOUNT_DELTA_PAISE_PER_DERIVED_LINE = 2`,
  `UTR_TRUNCATION_DIGITS = 2`, `LEDGER_LAG_DAYS = 1`
- `match/fee_reversal.py` — `infer_slabs()` (observe -> change-point scan ->
  Step 3 validate-before-use -> reject outright on any failure),
  `derive_fee()`, `FeeReversalPass`. Verified against real data: correctly
  discovers UPI 0%, netbanking 1.75%, wallet 2.25% as single slabs, and the
  card rate as **two** slabs (2.00% up to 2026-07-16, 1.90% from 2026-07-17),
  matching §10's synthetic schedule exactly — discovered, never imported
  (rule 2). Every fee_reversal-derived match closed at `delta == 0` in all
  four real datasets; the derived-fee tolerance budget exists but was never
  actually needed to close anything measured so far.
- `match/base.py` — added `find_applicable_slab()` (shared by `verify()` and
  `build_settlement_proposal`; lives here, not in `fee_reversal.py`, to avoid
  a circular import — see Known issues)
- `verify/__init__.py` — `verify()` now resolves a null-fee payment line via
  `facts.fee_slabs` if a validated slab covers it, and computes
  `allowed_delta = AMOUNT_DELTA_PAISE_PER_DERIVED_LINE * (derived lines in
  this proposal)` automatically for ANY caller (cascade or future LLM) — the
  tolerance is not a pass-specific mode switch
- `verify/proof.py` — `build_proof()` takes `allowed_delta` instead of
  assuming strict equality; `closes = verifiable and abs(delta) <=
  allowed_delta`; `tolerance_applied` reports what was actually spent (0 if
  delta was already 0, even with budget available)
- `match/exact.py` — `build_settlement_proposal()` now accepts
  `require_refund_or_adjustment: bool | None` (`None` = fee_reversal/
  tolerance: attempt regardless of composition) and relaxes the fee-null
  skip to a per-line `find_applicable_slab` check instead of a blanket defer
- `match/timing.py` — `infer_calendar()` (business days from observed
  `settled_at` dates, candidate holidays from settlement-free weekdays,
  greedy validation against T+2 arithmetic), `add_business_days()`,
  `_capture_date()` (18:00 IST rollover), `TimingPass` (never proposes a
  recon-line match — the recon<->bank join is UTR-only by design, so no
  match decision depends on calendar math; only attaches orphaned
  `source_ref IS NULL` ledger entries, informationally, via `audit_log`).
  Verified: converges to >=95% confidence on all four datasets, discovering
  4 shared holidays present in every run plus dataset-specific extras in
  `holiday-skew` (aptly named — 7 holidays found there vs 4-5 elsewhere)
- `match/tolerance.py` — `TolerancePass`: extends UTR indexing to catch
  bank descriptions missing up to `UTR_TRUNCATION_DIGITS` trailing digits of
  the true settlement UTR, matching only on a unique prefix (a truncated UTR
  matching two settlements is left unresolved, not guessed)
- `match/classify.py` — finished `classify_residual()`: priority order is
  `AMBIGUOUS_DUPLICATE` (reusing `has_ambiguous_adjustment`, listing every
  candidate order, never picking one) -> `CROSS_PERIOD_UTR` (settlement_utr
  never indexed by either `utr` or `tolerance`) -> `NO_CANDIDATE` (catch-all)
- `match/__init__.py` — `PASSES` now holds all six passes in the fixed §13
  order; `run_cascade()` calls `classify_residual()` once after the pass
  loop (its own transaction, its own `persist_exception`/`audit.record`
  calls — not one of the six `PassStat` rows, since it matches nothing)
- `db/queries.py` — added `SELECT_ALL_RECON_KEYS`,
  `SELECT_ADJUSTMENTS_BY_SETTLEMENT_ID` (moved forward from Phase 3),
  `SELECT_DUPLICATE_ORDER_BUCKET_COUNT` (moved forward from Phase 3),
  `SELECT_DUPLICATE_ORDER_IDS_BY_AMOUNT`, `SELECT_ORPHANED_LEDGER_ENTRIES`,
  `SELECT_MATCHED_RECON_GROUP_MEMBERS`
- `tests/test_fee_reversal.py`, `test_timing.py`, `test_tolerance.py`,
  `test_ambiguous.py` — written and passing (59 total, up from 42 at end of
  Phase 3). `test_ambiguous.py` originally tested the whole-settlement-
  deferred behavior described in the first version of C-008 below; both it
  and `test_aggregate.py`'s C-005 regression test were later rewritten (see
  the C-008 update further down) once §14.1 resolved that behavior — they
  now assert the corrected outcome, not a narrower claim
- **C-008 resolved, same session:** `MatchProposal.arithmetic_scope` /
  `ArithmeticProof.scope_only_keys` (§14.1, `reference/master_specification.md`)
  — `verify()` can now sum over a wider scope than what `commit()` writes as
  `group_members`, so a settlement's clean payments match even when it also
  contains one ambiguous adjustment; the excluded adjustment falls through to
  `classify_residual` as `AMBIGUOUS_DUPLICATE`, unchanged. Closes the
  audit-transparency gap this creates via three committed-data-only signals:
  `proof_json.scope_only_keys`, an extra `audit_log` entry per scope-only key
  (`"counted_not_committed"`), and a runtime-enforced invariant —
  `report/scoring.check_scope_only_accounted()` (pulled a phase early, same
  pattern as `has_ambiguous_adjustment` in Phase 3), raising `ScoringError`
  and refusing to emit `results.json` if a scope-only key ever lacks an
  `exceptions` row by end-of-run. New 8th protected test:
  `tests/test_scope_only_accounted.py`. See the C-008 entry in
  `docs/challenges-log.md` for the full resolution trace.

**Files modified:**
```
recon/match/{constants,fee_reversal,base,exact,timing,tolerance,classify,__init__}.py
recon/verify/{__init__,proof}.py
recon/db/queries.py
tests/{test_fee_reversal,test_timing,test_tolerance,test_ambiguous}.py
docs/project-progress.md, docs/challenges-log.md

# C-008 resolution, same session, added after the above:
recon/models/pipeline.py                — MatchProposal.arithmetic_scope, ArithmeticProof.scope_only_keys
recon/verify/{__init__,proof}.py        — verify() scope-vs-membership split, commit() audit entry
recon/match/classify.py                 — ambiguous_adjustment_keys() (has_ambiguous_adjustment now a wrapper)
recon/match/exact.py                    — build_settlement_proposal() no longer defers whole settlement
recon/db/queries.py                     — record_key added to SELECT_ADJUSTMENTS_BY_SETTLEMENT_ID;
                                           SELECT_CLOSED_MATCH_GROUP_PROOFS, SELECT_EXCEPTION_RECORD_KEYS added
recon/report/scoring.py                 — check_scope_only_accounted(), pulled forward a phase early
tests/test_scope_only_accounted.py      — new, 8th protected test
tests/{test_ambiguous,test_aggregate}.py — rewritten to assert the corrected (not deferred-whole) outcome
reference/master_specification.md       — new §14.1; §20.2 model fields; §13.7 note; §25 8th test;
                                           §8.2 ceiling corrected to a range (see below)
CLAUDE.md                               — protected-test list, seven -> eight
```

**Tests:**
- pytest: 64 passed (was 59; +5 for `test_scope_only_accounted.py`)
- ruff: clean

**Measured results (real, against all four frozen datasets, post-§14.1 fix —
raw matched count, NOT yet validated against the answer key; that's Phase 5):**

| Dataset | exact | aggregate | fee_reversal | timing | tolerance | Total matched | AMBIGUOUS_DUPLICATE | CROSS_PERIOD_UTR | NOT_A_SETTLEMENT |
|---|---|---|---|---|---|---|---|---|---|
| clean-august | 88 | 38 | 244 | 0 | 20 | **390/400** | 5 | 5 | 5 |
| heavy-refunds | 30 | 50 | 222 | 0 | 10 | **312/400** | 5 | 69 | 5 |
| holiday-skew | 76 | 44 | 232 | 0 | 25 | **377/400** | 5 | 13 | 5 |
| high-ambiguity | 55 | 93 | 211 | 0 | 7 | **366/400** | 15 | 16 | 5 |

(The original table here showed 350/257/326/256 with a large `NO_CANDIDATE` column —
that was the pre-§14.1 state, before C-008's fix; `NO_CANDIDATE` is now 0 in all four
runs, since every previously-`NO_CANDIDATE` collateral record either matches now or is
correctly named `AMBIGUOUS_DUPLICATE`/`CROSS_PERIOD_UTR`.)

`timing` still matches 0 recon lines in every run — by design, unchanged. `high-ambiguity`'s
`AMBIGUOUS_DUPLICATE = 15` and clean/heavy/holiday's `= 5` each match §9.4's documented count
exactly, confirming the fix recovers precisely the collateral records and resolves no
genuine ambiguity. `heavy-refunds`' `CROSS_PERIOD_UTR = 69` is unchanged from Phase 4's
original measurement (genuine cross-period data, verified directly against source bank
data at the time, unaffected by this session's change).

**clean-august's 390/400 exceeds §8.2's originally-published flat ceiling of 389 — traced
and explained, not a bug:** a blast-radius diff (every key `arithmetic_scope` could possibly
have newly matched vs. everything outside that set) shows the 40 newly-matched records are
exactly and only inside the fix's 4 known settlements, and the other 350 matched records are
byte-identical, by count and by key, to the pre-fix baseline — `match/{aggregate,tolerance,
fee_reversal,utr}.py` and `verify/arithmetic.py` have zero diff this session. So the +1 over
389 predates this session's work entirely. Source-data trace (never the sealed key): each
dataset's `ledger_entries` has exactly 2 `account='suspense'` rows (6 in `high-ambiguity`)
with a `source_ref` matching no real order receipt — the exact §6.4/§9.4 `CONTRADICTORY_LEDGER`
signature, in the exact designed count, in all four runs. §13.8 already states these close
correctly and will be matched; the ceiling's 389/368 assumed 0 of them ever would, understating
the honestly-achievable range by 0-2 (0-6). **§8.2 corrected to a range (389-391 / 368-374)
for this reason** — see `reference/master_specification.md` §8.2 and `docs/challenges-log.md`
C-008 for the full trace.

**Remaining work:**
Phases 5-8. Phase 5 (Scoring, Baseline, `results.json`) is next and will be
the first time these numbers are actually checked against the sealed answer
key — that's when true match rate, precision, and false-match rate become
knowable, including the honest ~1-2 `CONTRADICTORY_LEDGER` false matches per
run flagged in §13.8 (circumstantially confirmed present in the data this
session, not yet formally scored against the key).

**Known issues / TODOs:**
- C-008 is resolved (see above and `docs/challenges-log.md`) — no longer an
  open issue. Kept here, struck through in spirit rather than deleted, so the
  phase's history stays honest: the original architectural finding (whole-
  settlement deferral, a genuine 39-record ceiling miss) was real, measured,
  and reported before the fix existed; it was not assumed resolvable in
  advance.
- `match/base.py` now hosts `find_applicable_slab()` instead of
  `fee_reversal.py` (where §20.4 nominally places it) specifically to avoid
  a circular import: `match/__init__.py` imports `verify`/`commit` from
  `recon.verify` at module level, and `recon.verify` needs
  `find_applicable_slab`/`derive_fee`/`AMOUNT_DELTA_PAISE_PER_DERIVED_LINE`
  — importing any `recon.match.X` submodule requires first executing
  `recon/match/__init__.py`, which would try to import from `recon.verify`
  while it's still mid-import. Resolved by making `verify()`'s three
  `match.*` imports local (inside the function, not module-level) and moving
  `find_applicable_slab` to `match/base.py`, the one `match/` submodule nothing
  else in `match/` depends on. Documented in both modules' docstrings.
- `infer_calendar()`'s "iterate, drop candidates causing widespread mismatch"
  (§13.5 step 3) is implemented as a greedy single-candidate-at-a-time
  removal, converging when no further removal improves confidence. Not the
  only possible interpretation of "iterate" — reasonable and it measurably
  converges to >=95% on all four real datasets, but worth flagging as a
  judgment call, not a literal spec transcription.
- `TimingPass`'s ledger attachment is informational-only (writes to
  `audit_log`, never to any table `commit()` owns) and is not yet exercised
  by a dedicated test — the four real datasets' `timing` pass ran without
  error, but ledger-attachment correctness specifically wasn't measured
  against source data the way fee-slab and calendar correctness were.
- `TolerancePass.run()` re-attempts every entry already in `utr_index` each
  cascade run (not just newly-truncation-indexed ones) — harmless and
  idempotent at this dataset size (400 records), a correctness-over-
  performance choice, not optimized.

---

## Decisions log

Locked decisions and why. Append here when a decision changes; never rewrite history.

| Decision | Reason |
|---|---|
| Track 04, multi-source reconciliation | Widest average-to-exceptional gap. Arithmetic ground truth means no self-grading credibility cliff |
| Python, not Spring Boot | Role is AI Builder Intern; the stack is itself a signal. Domain literacy is shown through fee/T+2 logic, not the runtime |
| SQLite, not Postgres | Reviewer must clone and run in under 60 seconds |
| Static frontend, no server | Rubric scores throughput, accuracy, exception list — not UI. Zero-setup clone matters more |
| No auth, no RBAC | No multi-user surface. Auth would be theatre, and bad auth in a fintech repo is worse than none |
| No ML model | No prediction task exists. Reconciliation is constraint satisfaction over arithmetic |
| Groq, `llama-3.3-70b-versatile` | Task is narrow and structured; the verifier, not the model, establishes truth. Groq inference speed keeps the hypothesis stage cheap. |
| Scoring (Phase 5) before LLM (Phase 6) | Must know the deterministic match rate before adding AI |
| `high-ambiguity` designed to score worse | Four flattering runs would invite the suspicion the track bar warns about |

---

<!--
Copy the block below for each phase as it completes. Keep phases in order, oldest first.

## Phase N — <name>

**Status:** complete | in progress | blocked

**Completed features:**
-

**Files modified:**
-

**Tests:**
- pytest: N passed, N failed
- ruff: clean / N issues

**Measured results:** (if the phase produced any — never record an unmeasured number)

| Dataset | Match rate | Precision | False matches | Unresolved |
|---|---|---|---|---|

**Remaining work:**
-

**Known issues / TODOs:**
-

**Deviations from the implementation guide:**
- None / <what and why>
-->
