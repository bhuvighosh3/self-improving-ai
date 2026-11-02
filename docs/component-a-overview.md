# Self-Improving AI — Component A

Standalone portfolio analysis prototype built with Python, Google ADK, Gemini,
FastAPI and React. It extends the team's starter and the market-data handoff with
portfolio calculations, a local interface and evaluation tools.

## Start here

On the existing Windows environment, run from this directory:

```powershell
.\Start-ComponentA.ps1
```

Open **http://127.0.0.1:5173/** and choose **Main → Portfolio Analysis**.
Use `Stop-ComponentA.ps1` to stop the recorded local services.
For a new computer, follow [Setup](getting-started.md).

| Workflow | What runs | Credential |
| --- | --- | --- |
| Holdings, allocation drift, risk/return, goal projection | Local Python tools and synthetic fixtures | None |
| External quote or historical prices | Twelve Data adapter | Twelve Data key |
| Ask Portfolio Agent | Gemini selects tools through Google ADK | Gemini key; market key for external lookups |

Configure credentials in **Connections**. A saved Gemini key works across the
listed models. Test checks the current form; Save applies changes. Saved keys are
kept in backend-only local storage and are excluded from Git and release archives.

## Implemented behavior

- Asset-class allocation drift and hypothetical stock/bond adjustments.
- Annual expected return and volatility from explicit draft market assumptions.
- Seeded goal projections with annual contributions/withdrawals and sampling intervals.
- Explicit scenario overrides, including zero cash flows, with recorded input sources.
- Real tool traces, client identity context, bounded requests and actionable errors.
- Independent numerical references, trajectory scoring and a versioned lesson gate.

This is an independent A prototype. Three-agent integration, full research
evaluation, tax and sustainable-income tools remain future work. Draft assumptions
are unapproved; live quotes do not revalue the synthetic portfolio automatically.
The lesson gate has been exercised, but learning improvement has not been demonstrated.

## Repository layout

```text
src/self_improving_ai/   Python application, agents, tools, data and evaluation
dashboard/              React interface and browser tests
scripts/                Supported run, evaluation, validation and packaging commands
tests/                  Python tests
docs/                   Setup, usage, contracts, audit reports and design references
examples/               Original handoff examples and historical provider samples
artifacts/              Generated reports, screenshots, live evidence and runtime logs
work/                   Ignored historical investigation helpers
```

`artifacts/`, `work/`, local credentials, environments and dependencies are not
source files to commit. The packager can include selected test evidence separately.

## Verification

The latest functional audit recorded **163 Python tests plus 64 subtests**, **28
browser tests**, **15 handoff tool cases** and **nine scripted ADK cases** passing.
Actual quote/history coverage and a real browser workflow were also checked.
Live model rate limits and output-format deviations are retained in the
[live audit](reports/live-audit-2026-11-02.md); these are not an all-pass claim.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=artifacts/reports/pytest.xml
.\.venv\Scripts\python.exe scripts/evaluate_portfolio.py
```

See [Testing](testing.md) for browser, offline ADK and opt-in live commands.
Ordinary regression tests do not consume provider quota.

## Documentation

- [Setup and local launch](getting-started.md)
- [Interface and connection settings](usage.md)
- [Component A architecture](component-a.md)
- [Assumptions and calculation contract](assumptions.md)
- [API and integration contract](integration.md)
- [Market-data adapter](market-data.md)
- [Evaluation and lesson validation](evaluation.md)
- [Testing and source releases](testing.md)
- [Live audit and requirement review](reports/live-audit-2026-11-02.md)
- [Original team scope](reference/project-scope.md) — design target, not completion status.
