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
| **Current phase** | Phase 0 complete |
| **Next phase** | Phase 1 — Project Foundation |
| **Deadline** | 5 September 2026 |
| **Pipeline runs?** | No |
| **Latest match rate** | Not yet measured |

| Phase | Status |
|---|---|
| 0 — Specification + datasets | ✅ complete |
| 1 — Project foundation | ⬜ not started |
| 2 — Data layer | ⬜ not started |
| 3 — Verifier + passes 1–3 | ⬜ not started |
| 4 — Passes 4–6 | ⬜ not started |
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
| 1 | **VERIFY:** does `GET /v1/settlements/recon/combined` return data in test mode? Do test-mode settlements exist without real payment flow? | High | Phase 2 — before `models/` freezes |
| 2 | **VERIFY:** exact field nullability on the live recon endpoint against current Razorpay docs | High | Phase 2 |
| 3 | Tolerance constants must be chosen and justified **before** measurement, never tuned after | High | Phase 4 |
| 4 | Business-day/holiday calendar inference method must be documented in the README | Medium | Phase 8 |
| 5 | Settlements came out **daily** (~60/run), not the ~12 originally assumed. Daily is correct for T+2; the spec reflects the measured reality | Low | — |
| 6 | Fee schedule is **synthetic and invented**. README must state this explicitly and must never present it as Razorpay's real pricing | Medium | Phase 8 |

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
| `claude-haiku-4-5` | Task is narrow and structured; the verifier, not the model, establishes truth |
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
