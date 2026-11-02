# Component A feature-branch integration

Prepared locally on `feat/component-a-workflow`, based on team `main` commit
`45c9c8b`. This document describes the branch preparation, separate from the
earlier standalone prototype's live audit.

## Included work

The branch contains the handoff market adapter/data/tests plus A calculations,
Agent service, Portfolio Analysis, local connection management, independent
references, scoring, a lesson gate, scripts and English documentation.
Generated artifacts, historical investigation helpers, environments and private
settings were not copied into the Git changes.

## Shared-file decisions

- The team's root README, PRODUCT.md and DESIGN.md remain. The README gains A
  navigation and links rather than being replaced with an A-only description.
- The npm package definition and package-lock.json remain byte-for-byte at the
  team version. No pnpm lock/config is added to the branch.
- Shared `agent_model` and `judge_model` retain the team's defaults. A uses
  `portfolio_model`, `SIA_PORTFOLIO_MODEL` and `SIA_PORTFOLIO_API_KEY`.
- A's explicit Gemini Developer API client does not rewrite shared Google keys
  or Vertex AI mode. Without a local A override, shared Gemini keys may be read
  as a fallback; removing A explicitly disables that fallback for A only.
- The ADK dependency accepts versions >=1.32,<3 instead of pinning the whole
  project to 1.32. A full suite was run with 1.32 and 2.13 separately.
- NumPy is a direct dependency. Windows tzdata is declared after a fresh
  environment exposed the missing dependency in the existing meeting workflow.
- The original `PortfolioResult(answer_value, unit, reasoning)` remains. A's
  richer endpoint envelope uses a separate `PortfolioRun` schema.
- Existing B/C business definitions and core dashboard workflows remain.
  Adjacent changes are UTF-8 reads, a form label, tool discovery path and additive
  A routes/navigation. Successful holdings retain their original fields and add
  provenance; structured errors are documented in the A contract.

## Verification

| Check | Result |
| --- | --- |
| Full Python suite, ADK 1.32 | 166 passed plus 64 subtests |
| Full Python suite, ADK 2.13 | 166 passed plus 64 subtests |
| Browser regression on branch / ADK 2.13 | 28 passed, no flaky results |
| Handoff public tool cases | 15/15 passed |
| Scripted ADK cases | 9/9 passed |
| Frontend build | Passed |
| Dependency consistency | Passed |

The browser suite launched the branch backend and frontend on isolated test
ports. It reused already installed frontend dependencies because the team package
definition and lock are unchanged; this is not a fresh npm-install benchmark.

The first fresh ADK 2.13 run had three missing-tzdata failures in existing meeting
tests. Adding the Windows dependency resolved them. The initial failed report is
local engineering output, not a model answer failure.

No live provider request was rerun during this integration: the standalone copy's
saved keys were empty when checked. The new explicit-client wiring is verified
with intercepted provider calls and isolation tests. The prior real model/market
audit remains historical evidence, not a claim that this branch was live-tested.

Actual local test output is under ignored `artifacts/reports/`. Credential scans
cover the candidate Git files; private settings, dotenv overrides, environments,
logs and temporary outputs stay excluded.

## Delivery boundary

The changes are prepared in the local branch for inspection, commit and push.
No remote push, PR or merge is performed by this preparation step. Full live B/C
delegation, ADK 2.13 meeting-feature integration, research baselines, hidden tests
and demonstrated learning gain remain later team work.
