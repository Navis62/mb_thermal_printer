---
name: tech-debt-audit
description: "Thorough, user-invoked tech debt and architecture audit of the current codebase. Produces TECH_DEBT_AUDIT.md with file-cited findings, severity, effort estimates, and a required \"looks bad but is actually fine\" section. Use when the user asks for a debt audit, codebase health check, architecture review, or code quality assessment of an entire repo. Does not auto-invoke."
disable-model-invocation: true
---

# Tech Debt Audit

A Claude Code skill that conducts a deliberate, opinionated audit of an entire codebase and produces `TECH_DEBT_AUDIT.md` with cited findings.


## Operating principles

Find what's actually wrong. Not diplomatic. Not surface-only. Don't pattern-match to generic best practices without grounding in this specific repo. No sycophancy. No "overall the codebase is well-structured" filler.

Cite `file:line` for every concrete finding. Vague claims like "the code generally..." don't count. Read code before judging it — a pattern that looks wrong in isolation may be load-bearing.

## Phase 1: Orient

Do not skip this. Forming opinions before understanding the system produces bad audits.

1. Read the README, package manifest (`package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod`), and any architecture docs in `/docs` or `/adr`.
2. Map the directory structure and identify the major modules / layers.
3. Run `git log --oneline -200` and `git log --stat --since="6 months ago"` to see what's actually changing and where churn concentrates.
4. Identify entry points, hot paths, and cold corners.
5. List the top 20 largest files by line count, and the 20 files most frequently modified in the last 6 months. The intersection is where debt usually hides.
6. Use `TodoWrite` to publish a plan so the user can see progress through the phases.

Write a 1–2 paragraph mental model of the architecture before proceeding. If your model contradicts the README, flag it — that itself is a finding.

## Phase 2: Audit across these dimensions

Use `rg`, `ast-grep`, and language-native tooling to find concrete examples. Cite `path/to/file.ext:LINE` for every finding.

1. **Architectural decay** — circular deps, layering violations, god files (>500 LOC) and god functions, duplicated logic across 3+ sites where an abstraction should exist, abstractions that exist but nobody uses, dead code (unused exports, unreachable branches, stale commented-out blocks).

2. **Consistency rot** — multiple ways of doing the same thing (HTTP clients, error handling, logging, config loading, validation, date handling). Naming drift. Folder structure that no longer reflects what the code actually does.

3. **Type & contract debt** — `any` / `unknown` / `as any` / `# type: ignore` / loose dicts. Untyped API boundaries. Missing schema validation at trust boundaries.

4. **Test debt** — run coverage if available; identify gaps on critical paths. Tests that assert implementation rather than behavior. Skipped or flaky tests. High-churn files with no tests.

5. **Dependency & config debt** — `npm audit` / `pip-audit` / `cargo audit` for CVEs. Unused deps. Duplicate deps doing the same job. Env var sprawl (referenced but not documented; defaults inconsistent across envs).

6. **Performance & resource hygiene** — N+1 queries, sync work in async paths, blocking I/O on hot paths, uncleaned listeners or handles, unnecessary serialization.

7. **Error handling & observability** — swallowed exceptions, blanket catches, errors logged but not handled, inconsistent error shapes across modules, missing structured logs on critical paths.

8. **Security hygiene** — hardcoded secrets, string-concat SQL, missing input validation at trust boundaries, permissive auth or CORS, weak crypto.

9. **Documentation drift** — README claims that don't match reality, comments that contradict adjacent code, public APIs without docstrings.

## Phase 3: Deliverable

Write to `TECH_DEBT_AUDIT.md` in the repo root with this structure:

- **Executive summary** — max 10 bullets, ranked by impact.
- **Architectural mental model** — your understanding of the system as it actually is.
- **Findings table** — columns: `ID | Category | File:Line | Severity (Critical/High/Medium/Low) | Effort (S/M/L) | Description | Recommendation`. Aim for 30–80 findings; padding past that is noise.
- **Top 5 "if you fix nothing else, fix these"** — with concrete diff sketches or refactor outlines, not vague advice.
- **Quick wins** — Low effort × Medium+ severity, as a checklist.
- **Things that look bad but are actually fine** — calls you considered flagging and chose not to, with reasoning. **This section is required.** If it's empty, you didn't look hard enough.
- **Open questions for the maintainer** — things you couldn't tell were debt vs. intentional.

## Rules

- Cite `file:line` for every concrete finding.
- If unsure whether something is debt or intentional, ask in the open questions section — don't assert.
- Don't recommend rewrites. Recommend specific, scoped changes.
- Don't pad. If a category has nothing material, write "Nothing material" and move on.
- No sycophancy. Tell the user what's broken.

## Stack-specific tooling

Detect the stack from the manifest and run the relevant tools. Run them in parallel when possible.

- **TypeScript / JavaScript** — `npm audit`, `npx knip` (dead exports), `npx madge --circular` (circular deps), `npx depcheck` (unused deps), `tsc --noEmit` for type drift.
- **Python** — `pip-audit`, `ruff check`, `vulture` (dead code), `pydeps --show-cycles`, `mypy --strict` for type drift.
- **Rust** — `cargo audit`, `cargo udeps`, `cargo machete`, `cargo clippy -- -W clippy::pedantic`.
- **Go** — `govulncheck`, `go vet`, `staticcheck`, `golangci-lint run`.

If a tool isn't installed, note it in the audit and move on rather than blocking. Do not install dev tools globally without permission.

## Large repos: spawn subagents

If the repo is >50k LOC or has >5 top-level modules, dispatch subagents (Task tool) in parallel — one per module — and synthesize their reports. Serial reading on a large repo eats the context window before findings can be written.

Each subagent gets: scope (one module), the dimensions list above, the citation requirement, and a 200-finding cap. The main agent merges, dedupes, and ranks.

## Repeat-run mode

If `TECH_DEBT_AUDIT.md` already exists in the repo, read it first. Mark resolved findings as `RESOLVED`, update stale ones, and tag new findings with `NEW`. This turns the audit into a living document tracked over time.


## mb_thermal_printer-specific dimensions

Add these to Phase 2 for this repo (small Python project: `momir_basic.py` on the Pi, a `scripts/` pipeline driven
by `update.sh`, `setup.sh` + a systemd unit, `settings.cfg`, unittest suite in `tests/`):

10. **Hardware assumptions** — pin numbers, baud rate, I2C address, OLED geometry (`ssd1306` created at its default
    size for a 128x32 panel), printer width (384 px), button polarity (`BUTTONS_ACTIVE_LOW`), the `/home/pi`
    template in `deploy/momir.service`. Cite each one; propose a setting, not a rewrite.
11. **Pipeline fidelity** — the creature filter in `scripts/get_image_urls_from_scryfall.py` (double-faced cards whose
    front face is not a creature, legality, Arena-only, `A-`), cards lost silently, parallelism against the Scryfall
    rules, file name sanitising collisions, `find`/glob patterns in `update.sh` and `convert_images.py` that reach
    beyond the `<cmc>/` folders, conversion cost on a Pi Zero 2 (pure-Python Atkinson dithering).
12. **Runtime robustness on the Pi** — the polling loop in `momir_basic.py`: debounce and auto-repeat, missing or
    empty `converted_files/`, `settings.cfg` missing at import, systemd giving up after 5 failed starts.
13. **Reproducibility** — unpinned `requirements.txt`, apt vs pip packages in `setup.sh` (`RPi.GPIO` vs
    `rpi-lgpio`), steps that live only in the README, tests that need Pillow/requests in the `.venv`.

Write the audit in French (the maintainer's language); keep the section headings above.
