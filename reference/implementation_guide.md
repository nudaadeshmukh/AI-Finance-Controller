# Implementation Guide

**The phase-by-phase build blueprint.** Build exactly what the current phase specifies,
not ahead of it and not behind it.

Technical detail lives in `reference/master_specification.md` — referenced here by section
number. Persistent rules live in `PROJECT_RULES.md`. **Deadline: 5 September 2026. Budget: ~4 days.**

---

## How to use this document

For each phase:

1. Read `docs/project-progress.md` for current state
2. Read this phase's section, and **only the master-spec sections it lists**
3. Implement
4. Run `pytest` and `ruff check .` — both must be clean
5. Append an entry to `docs/project-progress.md`
6. **Stop and report.** Do not continue to the next phase unprompted.

Log every error to `docs/challenges-log.md` **as it happens**, not at phase end.

**Phases 2 onward begin with:** *"Modify the existing codebase. Do NOT regenerate the
project structure. Only change the files necessary for this phase."*

### Reading budget

Do not re-read the whole master specification every session. Each phase lists exactly
which sections it needs. This is the main lever on keeping four days on schedule.

---

## Phase map

| Phase | Deliverable | Est. | Day |
|---|---|---|---|
| **1** | Skeleton compiles, CLI runs, nothing works | 2h | 1 |
| **2** | Data layer — models, DB, ingest, audit | 3h | 1 |
| **3** | Verifier + cascade passes 1–3 | 4h | 1–2 |
| **4** | Cascade passes 4–6 — the hard tail | 4h | 2 |
| **5** | Scoring, baseline, `results.json` — **first real numbers** | 3h | 2–3 |
| **6** | LLM layer + failure injection | 3h | 3 |
| **7** | Frontend | 4h | 3–4 |
| **8** | README, error analysis, scaling section | 2h | 4 |

**Phase 5 comes before Phase 6 deliberately.** You must know the deterministic match rate
before adding AI. If time runs out at Phase 5, the submission is complete and honest — the
LLM is upside, not foundation.

---

# PHASE 1 — Project Foundation

**Read:** master spec §3 (structure, stack), §6 (source schemas), §7 (DDL), §20 (types),
§21 (errors), §22 (config) · `PROJECT_RULES.md`

## Goal
Create the entire project skeleton. It compiles and the CLI runs. Nothing reconciles yet.

## Includes
- Full folder structure per §3.2
- `pyproject.toml`, `requirements.txt` with **pinned exact versions**
- `.env.example`, `.gitignore`, `LICENSE` (MIT)
- `recon/errors.py` — the three classes from §21, nothing more
- `recon/config.py` — env loading per §22; **every variable optional**
- `recon/models/` — all models from §6 and §20.2, fully written
- `recon/db/schema.sql` — the DDL from §7, fully written
- `recon/db/connection.py` — connect, apply schema, transaction context manager
- `recon/cli.py` — Typer with `run`, `inject`, `report`, `validate` registered per §19.
  Each prints a stub message and exits 0.
- Every other module: `__init__.py` with the exact signatures from §20.4, bodies raising
  `NotImplementedError`
- `tests/conftest.py` with an in-memory DB fixture
- `tests/test_firewall.py`, `tests/test_money.py` and `tests/test_answer_key_seal.py` —
  **written and passing now**
- `.github/workflows/ci.yml` — ruff + pytest

## Frontend in this phase
Create the `frontend/` directory skeleton only — `package.json`, `vite.config.ts`,
`index.html`, and empty `src/` subdirectories per §3.2. **No screens, no components, no
styling.** If you write any frontend file beyond the build config, read
`reference/design.md` first — it is authoritative for all visual decisions in every phase,
not just Phase 7.

## Explicitly NOT in this phase
No matching logic. No ingest logic. No LLM. No frontend screens, components or styling.

## Acceptance
```bash
pip install -r requirements.txt
python -m recon --help                        # shows 4 commands
python -m recon run --dataset clean-august    # stub message, exit 0
pytest                                        # green
ruff check .                                  # clean
```

## Result
Project compiles. Nothing fancy works yet.

---

# PHASE 2 — Data Layer

> Modify the existing codebase. Do NOT regenerate the project structure. Only change the
> files necessary for this phase.

**Read:** master spec §5 (sources, provenance), §6 (schemas), §7 (DDL, ownership,
transactions), §12.1–12.2 (acquire, ingest), §16 (audit), §27 (Razorpay)

## Goal
The four sources load into SQLite, validated, idempotently, with an audit trail.

## Implement
- `adapters/base.py` — `SourceAdapter` protocol (§20.4)
- `adapters/fixture.py` — reads `data/<run>/sources/*.json`, returns **iterators of raw
  dicts**, not models
- `adapters/__init__.py` — `get_adapter()`
- `adapters/razorpay.py` + `razorpay_client.py` — **stub only.** Correct signature, raises
  `SourceUnavailable("live adapter not implemented")`. Add
  `# VERIFY: test-mode recon endpoint behaviour` at the top.
- `ingest/validate.py` — Pydantic validation. **A failure is recorded, not raised:** write
  an `Exception_` with `MALFORMED_SOURCE_ROW` and continue.
- `ingest/persist.py` — `INSERT ... ON CONFLICT(record_key) DO UPDATE`
- `audit/` — `record()` and `trail()`, append-only, participating in the enclosing
  transaction
- `db/queries.py` — all SQL as named constants
- `cli.py run` — wires acquire → ingest, prints a Rich table of counts

## Key rules
- One transaction for the whole `ingest()` call, covering all four sources —
  not one per source file. A `SourceUnavailable` partway through acquisition
  must leave zero rows from *any* source for that call, not just the failed
  one: a per-source scheme would leave earlier sources' writes committed,
  which is a partial write in every sense that matters. See master spec
  §7.2 and §12.1. Implemented and tested —
  `tests/test_ingest.py::test_source_unavailable_partway_through_leaves_no_partial_write`.
- Running twice produces identical state and no duplicate rows
- `bank_txns.utr_extracted` stays NULL here — Phase 3 populates it

## Blocking TODO — resolve before freezing `models/`
**VERIFY:** whether `GET /v1/settlements/recon/combined` returns data in test mode, and
exact field nullability against current Razorpay docs (§27). This is a research task, not
a coding one. If unresolvable, the stub ships and the README says so.

## Tests
`test_ingest.py`, `test_idempotency.py`, `test_determinism.py`

## Acceptance
```bash
python -m recon run --dataset clean-august
# Ingested: orders 360 · recon_lines 400 · bank_txns 65 · ledger_entries 566
python -m recon run --dataset clean-august   # rerun: identical, no duplicates
```

---

# PHASE 3 — Verifier + Cascade Passes 1–3

> Modify the existing codebase. Do NOT regenerate the project structure.

**Read:** master spec §11 (lifecycle), §13.1–13.3 (match definition, passes 1–3),
§14 (verifier), §12.3, §12.5

## Goal
The first real matches. Build the verifier **first**, before any pass.

## Order of work — do not reorder
1. `verify/arithmetic.py` — the closing equation (§13.1), in exactly one place
2. `verify/proof.py` — `ArithmeticProof` construction
3. `verify/__init__.py` — `verify()` (pure) and `commit()` (**sole writer** of
   `match_groups`)
4. `tests/test_verify.py` — including a deliberately wrong group that must be rejected
5. Only then: passes 1–3

**Rationale:** a verifier written after the matcher gets shaped to accept it. Written
first, everything has to earn its way through.

## Implement
- `match/base.py` (Pass protocol), `match/constants.py`, `match/money.py`
  (**own copy** of `round_half_up` — see `PROJECT_RULES.md` rule 2), `match/__init__.py`
  (`run_cascade`)
- `match/utr.py` — pass 1 per §13.2. **Bank rows with `debit > 0` and no UTR match are
  `NOT_A_SETTLEMENT` — excluded, not exceptions.** 5 per run.
- `match/exact.py` — pass 2 per §13.3. **Skip any settlement containing `fee IS NULL`.**
- `match/aggregate.py` — pass 3 per §13.3. **Do not attempt to attribute an adjustment to
  an order.** The fee-null skip applies here too, not just in `exact`.

## Tests
`test_utr.py`, `test_exact.py`, `test_aggregate.py`, `test_verify.py`

## Acceptance
Cascade runs, matches a meaningful fraction, reports per-pass counts. Match rate will be
well short of the ceiling — passes 4–6 are missing. That is expected.

---

# PHASE 4 — Cascade Passes 4–6 (the hard tail)

> Modify the existing codebase. Do NOT regenerate the project structure.

**Read:** master spec §8 (dataset facts), §9 (discrepancy classes), §10 (fee schedule),
§13.4–13.6

## Goal
The passes that demonstrate domain understanding. **This is the phase that differentiates
the submission.** Budget the most care here; it is also the phase most likely to run long.

## `match/fee_reversal.py` — slab inference (§13.4)
Four steps: observe → detect change point → **validate before use** → derive and close.

**Step 3 is the one that matters.** A slab is accepted only if it reproduces
`credit == amount − fee − tax` **exactly** on 100% of stated-fee lines in its period. A
slab failing this is **rejected outright, never approximated.**

The card rate moves 2.00% → 1.90% partway through the window, unannounced. A matcher
inferring one global rate gets ~1.95% and fails on both sides. Step 3 makes that failure
loud instead of silent.

Emit accepted slabs to `DerivedFacts.fee_slabs` → `results.json.derived_fee_slabs`.

## `match/timing.py` — calendar inference (§13.5)
Infer business days and holidays from observed settlement gaps. Accept only if the
calendar explains ≥95% of payments with both timestamps.

## `match/tolerance.py` — three narrow allowances (§13.6)
Each a constant in `match/constants.py` **with a comment justifying it**, echoed into
`results.json`. **Never widen one to lift a match rate** (`PROJECT_RULES.md` rule 7).

## `match/classify.py` — specific reason codes (§13.7)
New module. Runs at the end of `run_cascade()`, after pass 6, before the LLM stage. It
matches nothing; it converts blanket `NO_CANDIDATE` into `AMBIGUOUS_DUPLICATE` (with both
candidates listed) and `CROSS_PERIOD_UTR`.

## Known answer-key limitation (§13.8)
`CONTRADICTORY_LEDGER` records close correctly and **will** be matched, scoring ~2 false
matches per run. **Do not detect them, do not special-case the scorer.** Log it in
`docs/challenges-log.md` when first observed and report it in Phase 5.

## Tests
`test_fee_reversal.py` (both slabs recovered; an approximate slab is **rejected**),
`test_timing.py`, `test_tolerance.py`, `test_ambiguous.py`

## Acceptance
All four datasets run. Ambiguous records unresolved. No tolerance was widened.

---

# PHASE 5 — Scoring, Baseline, results.json

> Modify the existing codebase. Do NOT regenerate the project structure.

**Read:** master spec §8.2–8.3 (ceilings, baselines), §17 (metrics), §18 (results.json)

## Goal
**The first real numbers.** After this phase the submission is viable even if nothing else
gets built.

## Implement
- `report/scoring.py` — **the only module that opens `answer_key.json`**, and only after
  matching completes
- `report/baseline.py` — the naive matcher from §8.3
- `report/results.py` — emit per §18, with `"schema_version": 1`
- `report/html.py` + `templates/report.html.j2`
- `cli.py report`

## Metric definitions
Use §17.1 verbatim — in code, README and video. Excluded records leave both numerator and
denominator.

## Required comparisons (§17.2)
Naive baseline · cascade without LLM · cascade with LLM (`null` until Phase 6) ·
resolvable ceiling.

## Error analysis
Record in `docs/project-progress.md`: which classes fail and why. **If a class fails
badly, report it — do not tune the tolerance to hide it.**

## Acceptance
```bash
python -m recon run --dataset all --no-llm
```
Four `results.json` files, all metrics populated, false match rate reported prominently.
Commit them.

---

# PHASE 6 — LLM Layer + Failure Injection

> Modify the existing codebase. Do NOT regenerate the project structure.

**Read:** master spec §15 (LLM layer), §24 (failure injection)

## Goal
The narrow, bounded AI layer — and the demonstration that it cannot do damage.

## Implement
- `hypothesize/client.py` — Groq wrapper, `openai/gpt-oss-20b` (C-013: original
  `llama-3.3-70b-versatile` retired by Groq mid-build), 20s timeout
- `hypothesize/prompt.py` — system block + `<untrusted_source_data>` fence (§15.2).
  **Free text is never interpolated into the instruction section.**
- `hypothesize/parse.py` — strict JSON → `Hypothesis`. Prose is a parse failure.
- `hypothesize/cluster.py` — one call per cluster, not per record. **Cluster key:**
  shared `settlement_utr`; records with no usable UTR cluster by `(customer_id, date)`
- `inject/hallucination.py`, `inject/unavailable.py`
- `cli.py inject`

## Key points
- `claimed_arithmetic` has **no functional purpose** — it exists so the verifier can catch
  the model disagreeing with reality, and so that disagreement can be shown in the UI
- `confidence` is displayed and **gates nothing**
- `propose()` **never raises**; `--no-llm` runs the full pipeline deterministically
- Failure matrix: §15.4

## Publish the contribution honestly (§15.5)
If the LLM resolves 4 records out of 400, **say 4.** A small number is evidence *for* the
architecture.

## Tests
`test_no_llm.py`, `test_injection.py`

---

# PHASE 7 — Frontend

> Modify the existing codebase. Do NOT regenerate the project structure.

**Read:** master spec §18 (results.json), §23 (frontend spec), §28 (deployment) ·
`reference/design.md`

**Document boundary — do not blur it.** §23 is authoritative for **what** each screen
contains: which data, which fields, which rules. `design.md` is authoritative for **how**
it looks: layout, typography, colour, spacing, component styling. If they appear to
disagree about screen content, §23 wins. Do not copy screen content into `design.md`, and
do not add visual specifications to §23.

## Goal
Static Vite + React reading `results.json`. **No server, no API, no upload, no auth.**

## Build order — screens 1 and 4 first
They carry most of the signal. If time runs short, ship those two and skip 2 and 3.

Screens per §23.1–23.5. Rules per §23.6: `src/lib/format.ts` is the only place paise
become rupees; `types.ts` asserts `schema_version === 1`; display `tolerance_constants`;
no charting library, no dark mode, no animation beyond a spinner.

---

# PHASE 8 — README, Error Analysis, Scaling

**Read:** master spec §29 (scaling), §30 (README + checklist) · `reference/design.md`
(if producing screenshots or any final styling pass)

## README — write it last, with real numbers
Contents per §30.1. Opening line is the pitch from §1.2.

## Scaling section → master spec §29.1, ~200 words
**Write after measuring, never before.** Measured throughput per pass; which passes
partition cleanly; **where it breaks first — many-to-one candidate-set explosion,
combinatorial in settlement size**; the fix.

## Final checklist
§30.2. Including: fresh clone runs with **zero env configuration**, and
`docs/challenges-log.md` has real entries written as they happened.

---

## Cut order under time pressure

Frontend polish → LLM layer → extra datasets.

**Never cut:** the verifier, the exception list, honest metrics, or the eight protected
tests in §25.