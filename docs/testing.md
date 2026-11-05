# Testing and source releases

Run Python commands from the repository root, using its environment.

## Offline checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=artifacts/reports/pytest.xml
.\.venv\Scripts\python.exe scripts/validate_portfolio_data.py
.\.venv\Scripts\python.exe scripts/evaluate_portfolio.py
.\.venv\Scripts\python.exe scripts/evaluate_agent.py --mode scripted --output artifacts/agent_transport
.\.venv\Scripts\python.exe scripts/demo_portfolio_gate.py
.\.venv\Scripts\python.exe -m pip check
```

The JUnit parent directory is created by pytest. Reports are grouped under
`artifacts/reports/`; scripted transport and paired-gate runs retain their own directories.

From `dashboard/`:

```powershell
npx playwright install chromium
npx playwright test --workers=2 --reporter=json > ../artifacts/reports/browser-tests.json
npx vite build
```

On Windows the browser suite uses installed Chrome (`channel: chrome`); elsewhere
it uses Playwright Chromium. Tests start isolated servers at 5174/8002 and refuse
to reuse existing servers. Screenshots are written to `artifacts/screenshots/`.

## Opt-in live checks

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_agent.py --mode live
.\.venv\Scripts\python.exe scripts/audit_live_portfolio.py --model gemini-3.5-flash-lite
```

These consume API quota. Live evaluation pauses between cases and stops on rate
failure. Additional acceptance checks cover selected fields, not complete prose
semantics. Historical live evidence is frozen under `artifacts/live/2026-11-02/`;
new live outputs use `artifacts/live/current/` or an explicit `--output`.

The functional audit recorded 163 tests plus 64 subtests, 28 browser checks,
15 tool cases and nine offline ADK cases passing. Real model failures remain
documented in [the audit report](reports/live-audit-2026-11-02.md).

## Package for review

```powershell
.\.venv\Scripts\python.exe scripts/package_component_a.py
```

The default archive is `../releases/component-a-development.zip`. Use `--output`
to choose another file. Optional `--baseline` and `--original-zip` enable explicit
handoff comparison and original-integrity verification. The baseline is a local
reference, not an archive dependency required by another developer.

The archive includes source, English documentation and selected existing evidence.
It excludes credentials, dotenv overrides, dependencies, caches, work helpers,
runtime logs and databases. Actual saved key bytes are checked before publishing
the archive. The generated change manifest is under `artifacts/reports/`.
