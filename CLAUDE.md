# CLAUDE.md

This file is persistent project context. Read it before every task in this repo. It does
not change between phases — `reference/implementation_guide.md` carries the phase-specific
detail and `reference/master_specification.md` carries the technical contract; this file
carries the rules that never change.

## Project

A multi-source financial reconciliation pipeline for the **Razorpay AI Buildathon 2026,
Track 04 (AI Finance Controller)**, direction: multi-source reconciliation. **Deadline:
5 September 2026.**

Four systems disagree about the same money — the merchant's order system, Razorpay's
settlement recon report, the bank statement, and the accounting ledger. This pipeline
reconciles 400 records across all four, explains every rupee of the gap, and hands back
the ones it could not resolve, with reasons.

Assignment context: **this is a judged submission, not a product.** The repository itself
is evaluated on four criteria — problem taste, build quality, AI judgment, failure
recovery. Correctness, restraint, and honest measurement are what's being graded; favor
getting these right over feature breadth or visual polish.

## The philosophy — one line, and it governs every decision

> **The LLM proposes. The arithmetic disposes.**

If you are ever unsure whether something should use an LLM, the answer is almost
certainly no. This project wins on **restraint**, not on AI surface area.

## Non-negotiable rules — never violate these, even if a phase prompt doesn't repeat them

1. **All money is `int` paise. No floats, no `Decimal`, anywhere.** ₹1,000.00 is
   `100000`. Formatting to rupees happens in exactly two places: `report/` and
   `frontend/src/lib/format.ts`. If you are writing a function that returns a rupee
   value, it returns paise, and its name or type says so. `tests/test_money.py` enforces
   this and it must never be skipped.

2. **`match/`, `hypothesize/` and `verify/` must NEVER import from `recon/generate/`.**
   No shared constants, no shared helpers, no exceptions. If the matcher needs a fee slab
   or a holiday calendar, it must **derive it from observed data**. `match/money.py` holds
   its own copy of `round_half_up` — **this duplication is deliberate, do not "fix" it.**
   That single import would silently void the entire fee-reversal result, and nothing
   would visibly break. `tests/test_firewall.py` enforces this. This is the most important
   rule in this codebase.

3. **`verify/commit()` is the only function that writes `match_groups`.** Every proposal,
   from the deterministic cascade and from the LLM, traverses identical verification code.
   There is no confidence threshold, no override flag, no "high confidence" bypass, no
   fast path. `verify()` reads and computes; `commit()` writes. Keeping them separate is
   what makes this a testable assertion rather than a promise.

4. **A record is either matched with a closing arithmetic proof, or it goes to the
   exception list with a specific reason. There is no third state.** Never guess, never
   record a partial match, never pick one of two candidates to improve a number. **A false
   match is worse than an unresolved record** — an unresolved record gets human attention,
   a false match never will.

5. **The datasets in `data/` are frozen and committed. Never regenerate them.** If a
   matching pass will not converge, fix the pass. Tuning the generator after seeing your
   match rate invalidates every number in the submission, and there would be no way to
   tell from the outside — which is exactly why the rule is absolute.

6. **Only `report/scoring.py` may open `answer_key.json`, and only after matching
   completes.** No other module reads it, references it, or imports from a module that
   does. `tests/test_answer_key_seal.py` enforces this. The failure mode is not malice —
   it is a debugging session on day 3 with a stuck match rate, where eyeballing the key
   "just to see" feels harmless. It isn't.

7. **Tolerance constants are fixed before measurement, never widened after.** They live in
   `match/constants.py`, each with a comment justifying its value, and are echoed into
   `results.json` so they appear in the UI. The amount allowance is **derived, not flat**:
   2 paise per member payment whose fee was derived, and 0 otherwise — a stated fee cannot
   drift, so a settlement of stated fees must close exactly (§13.6). If you find yourself
   wanting to widen anything to lift a match rate, **stop and say so instead** — that
   impulse is the thing the rule exists to catch.

8. **The 11 ambiguous records per run (32 in `high-ambiguity`) must stay unresolved.**
   They are the deliverable, not a failure. `AMBIGUOUS_DUPLICATE` exceptions must list
   both candidates — naming the ambiguity precisely is the point; picking one is the
   failure. `tests/test_ambiguous.py` enforces this.

9. **The 5 unrelated bank debits per run are `NOT_A_SETTLEMENT` — excluded, not
   exceptions.** They leave both numerator and denominator. Counting them as exceptions
   understates performance; matching them is a false match.

10. **Only three Python exception classes exist:** `ConfigurationError`,
    `SourceUnavailable`, `ScoringError`. Data defects and business ambiguity are **not**
    Python exceptions — they are `Exception_` *records* written to the database. A
    malformed row at ingest is recorded and the pipeline continues. **A pipeline that dies
    on row 217 of 400 is useless; one that quarantines it and reports it is the product.**

11. **Never fabricate Razorpay API behaviour, metrics, or results.** If the recon
    endpoint's test-mode behaviour is unknown, ship an honest stub behind a clean interface
    and say so in the README. Flag anything needing external checking with **VERIFY THIS**.
    An honest stub is a better signal than a fabricated integration.

12. **Do not invent new modules, signatures, reason codes, or `results.json` fields that
    aren't in `reference/master_specification.md`.** If a phase seems to need one that isn't
    documented, stop and ask rather than improvising. This project is graded partly on
    architecture discipline, and undocumented surface breaks that.

13. **Two records per run will score as false matches, and that is expected.** The answer
    key marks 2 payments (6 in `high-ambiguity`) `CONTRADICTORY_LEDGER` on the basis of a
    ledger entry the closing equation does not include. They close correctly and will be
    matched. **Do not special-case the scorer and do not try to detect them** — that would
    require inferring how the data was generated, which rule 2 forbids. Report it in the
    Phase 5 error analysis, `docs/challenges-log.md`, and the README. See §13.8.

14. **Never use force operations without explicit permission** — no `git push --force`
    or `--force-with-lease`, no `git reset --hard` on commits not made this session, no
    `rm -rf`, no overwriting a file the user didn't ask to overwrite, no destructive
    database operation outside the schema this spec defines. If a task seems to need one,
    stop and ask, and say exactly what the force operation would do and to what. This
    matters more than usual here because the repository and its commit history are
    graded artifacts — a force-push that rewrites history is itself a problem, not just a
    risk to working code.
    
## Scope exclusions (locked)

**Do not build:** web server, authentication, RBAC, file upload, user accounts, dashboard
framework, ML model, vector store, RAG, agent framework, pandas, LangChain, ORM, message
queue, Docker.

Each of these is scope creep scored at zero by the rubric. There is no auth in this system
because there is no multi-user surface — adding one would be theatre, and that sentence
goes in the README.

## Architecture

Modular monolith, pipes-and-filters, single process, single-threaded. One SQLite file per
run. Static frontend reading a committed JSON artifact. No runtime network dependency
except one optional LLM call, which `--no-llm` removes.

```
acquire → ingest → cascade (6 passes) → [hypothesize] → verify → report
```

Dependency direction — **never import upward, no cycles:**

```
models ← adapters ← ingest ← match ← verify ← report
                                ↖ hypothesize ↗
audit ← imported by everything; imports only models
generate ← imported by NOTHING
```

Full folder structure: `reference/master_specification.md` §3.2.

## Tech stack (locked)

Python 3.11+ · SQLite (stdlib) · Pydantic v2 · Typer + Rich · Groq SDK
(`llama-3.3-70b-versatile`) · Jinja2 · httpx · pytest + ruff · Vite + React (static)

**Five runtime dependencies. Do not add more without asking.** Every dependency is
something a reviewer must trust without reading. Four reads as deliberate; thirty reads as
assembled.

## Conventions

- `record_key` is `"<source>:<id>"` — `order:`, `recon:`, `bank:`, `ledger:`
- Razorpay ID prefixes: `order_`, `pay_`, `rfnd_`, `setl_`, `cust_` + 14 alnum chars
- Timestamps: integer epoch seconds. Bank statement uses ISO date strings with **no time**
- **All SQL lives in `db/queries.py`.** No inline SQL anywhere else
- **The closing equation exists in exactly one place:** `verify/arithmetic.py`
- Adapters return raw dicts, not models — validation belongs to `ingest/` so there is one
  place where a malformed row is handled
- Every table gets an index on any column a query filters by
- Frontend: `master_specification.md` §23 owns screen **content**; `reference/design.md`
  owns **visual treatment**. Never describe screen content in `design.md`, and never
  specify colours, spacing or typography in §23 — duplicated content across two documents
  is how they drift apart
- Environment variables: read from `.env`, documented in `.env.example` — if you add one,
  add it to `.env.example` in the same phase's commit. **Every variable is optional**; a
  fresh clone with no `.env` must run the full deterministic pipeline successfully

## Reliability rules

- Never guess the contents of a file — read it first.
- Never overwrite working code unless explicitly requested.
- Make the smallest possible change to accomplish each task.
- If a command fails, diagnose and fix the root cause before continuing. Do not patch
  around it.
- Before ending a phase, verify `pytest` is green and `ruff` is clean.
- If a required dependency or tool is missing, tell the user exactly what to install
  instead of assuming it exists.
- If an instruction is wrong or will hurt the submission, say so plainly. Do not agree
  just because something was asked for.

## Commands

- `python -m recon run --dataset clean-august` — full pipeline
- `python -m recon run --dataset all --no-llm` — all four runs, deterministic only
- `python -m recon inject --scenario llm-hallucination` — failure injection
- `python -m recon report --dataset clean-august [--html]` — re-emit artifacts
- `python -m recon validate --dataset all` — dataset invariant checks (wire into CI)
- `pytest` — full test suite
- `ruff check .` — lint
- `cd frontend && npm run dev` — frontend (Phase 7 onward)

## Reference documents

- **`reference/master_specification.md`** — the single authoritative technical document.
  Architecture, schemas, algorithms, APIs, metrics, deliverables. There is no second
  architecture file. If code contradicts it, the code is wrong; if it is wrong, say so and
  ask rather than resolving the conflict by writing different code.
- **`reference/implementation_guide.md`** — the phase-by-phase blueprint. Build exactly
  what the current phase specifies, not ahead of it and not behind it. If a phase needs
  something an earlier phase was supposed to deliver and didn't, flag it — don't silently
  build around the gap.
- **`reference/design.md`** — the frontend design system: visual language, layout,
  typography, colour, component styling. Authoritative for **how** the frontend looks.
  It is **not** authoritative for what the screens contain — `master_specification.md`
  §23 owns screen content, data shown, and rules. If the two ever appear to disagree
  about *what* a screen shows, §23 wins; `design.md` only governs *how* it looks.
  **Read it before writing any frontend code, not just before Phase 7** — this includes
  the `frontend/` skeleton in Phase 1 and any screenshot or styling work in Phase 8.
- **`docs/project-progress.md`** — running memory across sessions.
- **`docs/challenges-log.md`** — every error and challenge, logged as it happens.

## How to work within a phase

- After Phase 1, **never regenerate the project structure.** Only touch the files a
  phase's scope requires. If achieving a phase's goal seems to require restructuring
  something built in an earlier phase, stop and explain why before doing it.
- Do not build ahead. Do not add features from a later phase.
- Do not refactor working code from an earlier phase unless the current phase requires it.
- If the user's prompt for a phase conflicts with `reference/implementation_guide.md`, the
  user's explicit instruction wins for that phase — but note the deviation in your
  response so it's visible, don't silently absorb it.
- **Each phase lists exactly which sections of the master specification to read.** Do not
  load the whole document every session — the context budget has to last four days.
- **At the start of every session**, read `docs/project-progress.md` first, before reading
  anything else, to pick up where the last phase left off. Don't ask the user to
  re-explain what's already built.
- **At the end of every phase**, update `docs/project-progress.md` with: Completed
  features, Files modified, Remaining work, Known issues/TODOs — appended as a new entry,
  never overwriting earlier phases. Do this as the last step, after the code works.
  Then **stop and report.** Do not roll into the next phase unprompted.

## Challenges log — update this in the moment, not at phase end

`docs/challenges-log.md` is a **graded artifact**, not documentation. "What broke, and
what you did about it" is one of the four judging criteria.

**Log every error, failure, wrong turn, and surprise as it happens** — not from memory at
the end of a phase, because the diagnosis is the interesting part and it's the first thing
you forget. One row per challenge: phase, what broke, root cause, fix, prevention, and
whether it's demo-relevant.

The entries that carry signal are the ones you caused: the tolerance you were tempted to
widen, the generator constant you nearly imported, the pass that silently matched wrong
and how you noticed. A log containing only dependency-install problems is worthless.

## Commit discipline

The repository is judged directly. Commit in logical increments with real messages — one
per meaningful unit of work, never one giant "initial commit". This cannot be faked
afterwards.

Format: `<area>: <what changed>` — e.g. `match: infer fee slabs with change-point detection`

## Time budget

**~4 days.** Phases 1–5 are the submission; Phases 6–8 are upside.

Cut order under pressure: frontend polish → LLM layer → extra datasets.
**Never cut:** the verifier, the exception list, honest metrics, or the seven protected
tests (`test_firewall`, `test_money`, `test_answer_key_seal`, `test_ambiguous`,
`test_injection`, `test_verify`, `test_persistence_regression`).

A deterministic pipeline with honest numbers and no LLM beats a flashy one with
unverifiable results. That is not a consolation position — it is the track's actual bar.