# API and integration contract

The backend runs at `http://127.0.0.1:8000`. Interactive schemas are available at
`/docs`. The frontend proxies `/api` to that local service.

## Explicit tools

`POST /api/portfolio/execute` accepts a task and task-specific parameters:

```json
{"task":"allocation","client_id":"CLI-001","target_stock_weight":0.6}
```

```json
{"task":"projection","client_id":"CLI-003","target_amount":2000000,"years":10,"annual_contribution":30000,"num_simulations":5000,"seed":42}
```

```json
{"task":"history","symbol":"AAPL","start_date":"2026-10-26","end_date":"2026-10-30"}
```

Supported tasks: `holdings`, `scenarios`, `allocation`, `risk`, `projection`, `quote`,
`history`. Results contain status, run ID, explicit execution mode, actual tool result,
trace, timing and provenance. Unsupported scenario parameters are rejected rather
than silently ignored. No Gemini call occurs in this mode.

## Agent

`POST /api/portfolio/agent` accepts:

```json
{"message":"Show Garcia CLI-001 allocation drift against its draft 60/40 target."}
```

The response includes actual model identity, text, call/result trace, timing and
reported tokens. A completed model transport is not proof of financial correctness.
Empty/placeholder answers and unsupported dollar amounts produce structured errors.
The currency check does not establish complete semantic validation.

The original `PortfolioResult(answer_value, unit, reasoning)` schema remains for
existing importers. The independent endpoint envelope is represented separately
by `PortfolioRun`; callers should choose the contract they consume explicitly.

For future B/C consumers, use the explicit `result` or call-ID-bound tool responses
in the trace. Do not parse free-form explanations as a stable data interface. Live
tests observed JSON envelope deviations despite correct financial values; a machine
consumer needs an enforced output contract and validation.

## Connections

Routes under `/api/portfolio/connections` provide public status and per-provider
save, remove and test actions. Status returns configured flags, not credentials.
These routes require local clients and approved origins. Probes may consume quota;
saving does not call a provider. Tests do not change the saved key/model.

## CLI

```powershell
.\.venv\Scripts\python.exe scripts/run_portfolio_agent.py --task allocation --client CLI-001 --save
.\.venv\Scripts\python.exe scripts/run_portfolio_agent.py --mode agent --message "Analyze CLI-001 allocation." --save
```

CLI `--save` writes runs under `artifacts/runs/`. The standalone A interface is ready
for later team alignment; live B/C integration is not part of this delivery.
