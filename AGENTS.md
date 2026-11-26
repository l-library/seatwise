# AGENTS.md — Seatwise

Working rules for AI agents in this repo. Human-facing version (Chinese): [CONVENTION.md](CONVENTION.md). Product background: [README.md](README.md). Both carry the same rules; when they drift, CONVENTION.md wins.

## Project layout

```
seatwise/
├── .agents/    project-level agent skills, versioned and shared by all members
├── backend/    Spring Boot (Java 25, Maven Wrapper), package root com.seatwise
│   ├── src/main/java/com/seatwise/...   source, layered controller → service → repository
│   ├── src/main/resources/              config (application.yaml)
│   └── src/test/java/...                JUnit 5 tests, mirroring source layout
├── frontend/   React 19 + TypeScript 6 + Vite 8, package manager pnpm
│   └── src/                             pages, components, API calls
├── ml/         offline training and data scripting (Python 3.14, uv + pyproject)
└── docs/       requirement and design baseline: Markdown, figures, PlantUML sources
```

- `docs/SRS.md` is the requirement baseline and `docs/DESIGN.md` the design baseline. Clause numbers used in code and reviews (7.6.1, R8, ADR-3) refer to those two files. `docs/` holds sources only — no PDF, ppt, or raw data.
- `ml/` is offline training and data scripting, never in the runtime path; capabilities reach users through backend endpoints.
- `.agents/` is never gitignored: it is part of the repo and of member collaboration, shared by every human and agent working here.
- API contracts live in `docs/openapi.yaml` (Apifox imports from it; frontend types are generated from it). Contract-first: change the contract, then the implementation, both in the same PR.
- Deployment is Docker Compose (planned): web, api, worker and MySQL with an artifact volume; compose files go at the repo root.

## Environment and commands

Prerequisites: JDK 25, Node.js ≥ 24 with pnpm, Python 3.14 with uv, MySQL 8 (not needed until the DB is wired in).

| | frontend | backend | ml |
|---|---|---|---|
| install | `pnpm install` | — (wrapper downloads deps) | `uv sync` |
| run | `pnpm dev` | `./mvnw spring-boot:run` | `uv run main.py` |
| lint | `pnpm lint` (oxlint) | `./mvnw checkstyle:check` (Checkstyle) | — |
| build | `pnpm build` (`tsc -b && vite build`) | `./mvnw package` | — |
| test | `pnpm test` (vitest + Testing Library) | `./mvnw test` (JUnit 5) | none yet — pytest as dev dependency when introduced |

On Windows use `mvnw.cmd`. Use pnpm only in `frontend/`; mixing npm/yarn pollutes the lockfile.

**Verification bar.** For any code change, run lint + build + test for the modules you touched and report the actual output in the PR. "Should work" is not done.

## Git

### Branch model — only `main` and `feat/*`

- `main` is the single long-lived branch: always buildable and releasable. Never push to it directly; everything lands via PR.
- `feat/<slug>` branches are cut from `main` (e.g. `feat/booking-state-machine`, `feat/12-credit-rules`, with issue number when one exists). Bug fixes use `feat/` branches too — the type lives in the commit message.
- Flow: cut `feat/x` from `main` → develop and self-verify → PR back to `main` → review → squash merge → delete `feat/x`.
- Keep branches short-lived (merge within days), one concern per PR. Sync with `git rebase main`, not merge commits.

### Commit messages — Conventional Commits

```
<type>(<scope>): <subject>

[body]

[footer]
```

- `type`: `feat` `fix` `docs` `style` `refactor` `perf` `test` `build` `ci` `chore` `revert`.
- `scope`: `backend` `frontend` `ml` `docs` `ci`, optional.
- `subject`: English imperative mood, lowercase, no trailing period, ≤ 50 chars — `feat(backend): add seat hold transaction`.
- `body`: explains why, not what; Chinese is fine; optional.
- `footer`: `Refs #12` to link, `Closes #12` to close an issue. Breaking changes: add `!` after type and a `BREAKING CHANGE: <description>` footer.
- One commit does one thing; never mix formatting or renames with behavior changes.

### Issues

Title: `<type>: <summary>` — `bug: concurrent booking not blocked at peak`, `feat: reservation hold transaction with row lock`.

- Bug: environment/versions / reproduction steps / expected / actual / logs or screenshots.
- Feature: motivation / approach sketch / acceptance criteria / explicit non-goals.
- New features, cross-module changes, and behavior changes start with an issue.
- Adding a project-level skill under `.agents/` starts with an issue — discuss and agree there before the skill lands.

### Pull requests

- Title is exactly one Conventional Commit (it becomes the squashed commit on `main`).
- Description template:

  ```markdown
  ## What changed
  ## Why (Refs #x)
  ## Verification (commands run and their results)
  ## Checklist
  ```

- Checklist:

  ```markdown
  - [ ] lint / build / test pass
  - [ ] OpenAPI contract updated where the API changed
  - [ ] no secrets, tokens, or personal config committed
  - [ ] text files are UTF-8 + LF
  - [ ] no unrelated changes (refactors, formatting)
  ```

- One approving review minimum, then squash merge, then delete the branch.

## Encoding and whitespace

- Every text file is **UTF-8 (no BOM) + LF**. Sole exception: `*.bat` / `*.cmd` use CRLF.
- Spaces, never tabs. Widths come from `.editorconfig`: Java/Python/XML 4, TS/JS/CSS/HTML/YAML 2.
- Files end with exactly one newline; strip trailing whitespace (Markdown excepted).
- `.editorconfig` and `.gitattributes` are the machine enforcement — enable EditorConfig support in your editor, and run `git diff --check` before committing.
- Never reformat a whole file in the same commit as a behavior change.

## Coding rules

### Before editing

- Verify, never assume: read the file and its callers first; understand the flow you are about to change.
- Stay inside the requested scope. No opportunistic refactors, reformatting, or unrelated fixes — note them and move on.

### Implementation

- Decision ladder, stop at the first rung that fully solves the task: does this need to exist → reuse an existing implementation in the repo → standard library → native platform feature → already-installed dependency → one clear line → minimum code that works.
- Prefer deletion over addition. Fewest files, smallest correct diff.
- Boring code over clever code. No unrequested abstractions, single-implementation interfaces, speculative configuration, or scaffolding for future needs.
- Fix root causes, not symptoms. Before changing shared behavior, inspect every caller and fix the common path.
- Comments explain why, not what; a good name beats a comment.

### Never compromise

- Trust-boundary input validation, error handling that prevents data loss, security controls, accessibility, and correctness on relevant edge cases survive every simplification.
- Secrets, tokens, and personal config never enter the repo; use `.env` (already gitignored).
- Non-trivial new logic ships with one minimal runnable check (test or script); trivial changes need none.
- Tests mirror the code they test in layout and naming, with concrete inputs and outputs — no abstract placeholder data.

### Project-specific

- Requirements and design: `docs/SRS.md` and `docs/DESIGN.md` are the baseline; change them together with the code and keep clause numbers valid.
- Module boundaries: one package per capability — booking, credit, policy, insight, prediction, plus identity/audit. Modules call each other through application service interfaces only; no cross-module table reads.
- Contract-first: update the OpenAPI document before the implementation, both in the same PR.
- Concurrency: booking state changes run in a DB transaction with row locks; release operations are idempotent; timeout and grace period are configurable. Every write uses the idempotency key `(business key, op, version)`.
- Prediction isolation: models and simulations read business tables through a read-only DB account and write only `occupancy_prediction`, `waste_estimate` and `simulation_report`. Booking, credit, release and quota decisions stay deterministic.
- Prediction output: a probability always carries `zone` / `slot` / `feature_as_of` / `model_version` / `band` / `coverage`. Values inferred from WiFi or access control are proxy metrics and must say so. When data or models are unavailable, show no numbers and fall back to the rule version.
- Credit: the score is derived from append-only ledger entries; no endpoint writes it. Corrections append a reversal entry.
- The LLM is optional (L1: natural language → filter parameters, default off, fills the form only). Core flows work without any LLM.
- Privacy: booking data stays in-domain; no output may reveal other users' bookings; aggregate outputs use groups of at least 5.

### Done means verified

Every acceptance point checked against reality — commands run, output seen — with results reported in the PR. Do not commit or push unless the operator asks; when you do, follow the commit format above.
