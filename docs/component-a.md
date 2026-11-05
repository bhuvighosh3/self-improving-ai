# Component A architecture

The application retains the team's `src` layout and existing dashboard. The new A
workflow runs independently through its own service and endpoints.

```text
Portfolio Analysis (React)
    -> FastAPI /api/portfolio
        -> explicit Python tools
        -> Gemini / Google ADK -> the same registered tools
```

| Location | Responsibility |
| --- | --- |
| `src/self_improving_ai/agents/portfolio/` | Agent factory, instructions, execution service, model errors, response checks and provenance |
| `src/self_improving_ai/tools/portfolio/` | Holdings, scenarios, allocation, risk, projection and external market adapter |
| `src/self_improving_ai/data/portfolio/` | Draft targets, goals, asset mapping and market assumptions |
| `src/self_improving_ai/dashboard/portfolio.py` | Calculation and Agent routes |
| `src/self_improving_ai/dashboard/connections.py` | Local connection management and bounded probes |
| `src/self_improving_ai/connection_store.py` | Backend-only persistent settings |
| `dashboard/src/PortfolioPanel.jsx` | Analysis form, results and execution evidence |
| `dashboard/src/ConnectionSettings.jsx` | Credential and model dialog |
| `src/self_improving_ai/evaluation/` | Public references, trace binding and structured-answer scoring |
| `src/self_improving_ai/harness/` | Candidate lessons, paired validation, versions and rollback |

The Agent registers seven tools: holdings, scenarios, allocation, risk, projection,
quote and history. It receives current client identity context from fixture data.
The service records real calls/results, run IDs, timing, reported token use and
data/code/lesson fingerprints. Runs are bounded to 12 model calls and 120 seconds.

In the team feature branch, A uses `settings.portfolio_model` and an explicit
Developer API client. Connection save/remove writes only A-specific Gemini keys
and model settings. The shared B/C `agent_model`, `judge_model`, Google key and
Vertex AI configuration remain under team control.

Explicit calculation mode performs no language inference and uses no model tokens.
External data requests remain separate from fixture valuation and market assumptions.

The inherited B/C definitions and demo workflows remain part of the team scaffold.
Offline AgentTool delegation checks establish an interface path; the current A
work does not establish live three-agent integration. The original mock stale-price
trap is retained for isolated research, not registered as a default A tool.

See [Integration](integration.md), [Calculation assumptions](assumptions.md) and
[Evaluation](evaluation.md) for the corresponding contracts and limitations.
