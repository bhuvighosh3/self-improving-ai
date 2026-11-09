# Self-Improving AI — Wealth Management Copilot

A self-improving AI copilot for wealth management advisors, built with [Google ADK](https://google.github.io/adk-docs/) and Gemini. The system learns from execution errors and advisor feedback to improve planning, tool use, and task performance over time. Deployed on GCP Cloud Run with tracing via Cloud Trace.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- GCP project with Vertex AI and Firestore enabled
- [Application Default Credentials](https://cloud.google.com/docs/authentication/provide-credentials-adc) configured (`gcloud auth application-default login`)

### Setup

```bash
git clone https://github.com/bhuvighosh3/self-improving-ai.git
cd self-improving-ai
pip install -e .
```

Create a `.env` file in the project root:

```
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=self-improving-ai-513915
GOOGLE_CLOUD_LOCATION=global
SIA_GOOGLE_CLOUD_PROJECT=self-improving-ai-513915
SIA_WORKSPACE_STORE=firestore
SIA_OTEL_EXPORTER=gcp
```

### Run the Dashboard (Local)

```bash
# Terminal 1 — Backend
uvicorn self_improving_ai.dashboard.app:app --env-file .env --port 8000

# Terminal 2 — Frontend
cd dashboard
npm install
npx vite --port 5173
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

### Run Tests

```bash
cd dashboard
npx playwright install
npx playwright test
```

## Deployment

The app is deployed on **GCP Cloud Run** with continuous deployment from the `main` branch. Every push triggers a build via the multi-stage Dockerfile (Node frontend + Python backend).

**Live URL:** [self-improving-ai-git-470264573612.europe-west1.run.app](https://self-improving-ai-git-470264573612.europe-west1.run.app)

**Observability:** All copilot requests are traced via **GCP Cloud Trace**. Each trace captures the full request lifecycle — query text, tool calls with arguments and results, completion checker verdicts, loop count, timing, and the final response. View traces at [Cloud Trace Explorer](https://console.cloud.google.com/traces/list?project=self-improving-ai-513915).

## Architecture

### Overall System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GCP Cloud Run                                │
│  ┌──────────────┐    ┌──────────────────────────────────────────┐   │
│  │  React SPA   │───▶│         FastAPI Backend                  │   │
│  │  (Vite)      │    │  /api/chat  /api/calendar  /api/email    │   │
│  └──────────────┘    └─────────────────┬────────────────────────┘   │
│                                        │                            │
│  ┌─────────────────────────────────────▼────────────────────────┐   │
│  │              Google ADK Agent Runtime                         │   │
│  │  ┌──────────────────────────────────────────────────────┐    │   │
│  │  │          Request Orchestrator (Gemini 3.8 Flash)     │    │   │
│  │  │  Direct Tools: calendar, email, CRM, client, holdings│    │   │
│  │  │  Sub-Agents: Portfolio Agent, Briefing Agent         │    │   │
│  │  └──────────────────────┬───────────────────────────────┘    │   │
│  │                         │                                     │   │
│  │  ┌──────────────────────▼───────────────────────────────┐    │   │
│  │  │     run_copilot() — ReAct Plan-Execute-Check Loop    │    │   │
│  │  │     Completion Checker (Gemini 3.5 Flash Lite)       │    │   │
│  │  └──────────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                        │                            │
│  ┌─────────────────────────────────────▼────────────────────────┐   │
│  │              Observability                                    │   │
│  │  OpenTelemetry → GCP Cloud Trace                              │   │
│  │  Spans: query, tool calls, checker verdict, response, timing  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │    Cloud Firestore          │
                    │  clients, CRM, calendar,    │
                    │  email, holdings             │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │    Vertex AI (Gemini)       │
                    │  gemini-3.8-flash           │
                    │  gemini-3.5-flash-lite      │
                    └────────────────────────────┘
```

### Agent Architecture

Three agents connected via Google ADK's `AgentTool`:

- **Request Orchestrator** (Component C) — parses advisor requests, uses direct workspace tools (calendar, email, CRM, client info, holdings) for simple lookups, delegates complex tasks to sub-agents, and runs a ReAct plan-execute-check loop with a lightweight completion checker
- **Portfolio Estimation Agent** (Component A) — handles numeric portfolio questions (risk/return, projections, drift, tax impact)
- **Meeting Briefing Agent** (Component B) — prepares client meeting briefings from CRM, portfolio, and market data

```
Advisor request
      ↓
┌──────────────────────────────────────┐
│  Request Orchestrator                │ ← Gemini 3.8 Flash
│  ┌────────────────────────────────┐  │
│  │ Direct Tools (fast lookups)    │  │
│  │ calendar, email, CRM, client,  │  │
│  │ holdings, tool catalog         │  │
│  └────────────────────────────────┘  │
│  ┌────────────────────────────────┐  │
│  │ Sub-Agents (complex tasks)     │  │
│  │ portfolio_agent, briefing_agent│  │
│  └────────────────────────────────┘  │
└──────────────┬───────────────────────┘
               ↓
┌──────────────────────────────────────┐
│ Completion Checker (Flash Lite)      │
│ → complete (confidence ≥ 0.5)? STOP  │
│ → incomplete? feed gap back → retry  │
│ → max loops (2) hit? STOP            │
└──────────────────────────────────────┘
```

The orchestrator uses `AgentTool` to call sub-agents and plain functions for direct data lookups. A ReAct plan-execute-check loop (`run_copilot`) wraps each request: the orchestrator executes, then a lightweight completion checker (Gemini Flash Lite) verifies the response covers the full request. If incomplete, the gap is fed back for a retry, bounded by `max_loops=2` and `max_llm_calls=25` per run.

### Copilot Test Results (10 Questions)

| # | Question | Tools Used | Time | Result |
|---|----------|-----------|------|--------|
| Q1 | When is my next meeting with Garcia? | get_upcoming_events | 8.5s | PASS |
| Q2 | Recent emails from Thompson family | get_recent_emails | 26.9s | PASS |
| Q3 | Garcia's risk tolerance and goals? | get_client_info, get_crm_summary | 28.0s | PASS |
| Q4 | What is a Roth IRA? (domain knowledge) | none (answered directly) | 32.0s | PASS |
| Q5 | Garcia's current holdings | get_client_holdings | 23.8s | PASS |
| Q6 | Latest CRM notes for Thompson | get_crm_summary | 21.0s | PASS |
| Q7 | Holdings + upcoming meetings | get_client_holdings, get_upcoming_events | 19.3s | PASS |
| Q8 | Prepare meeting brief for Garcia | meeting_briefing_agent + 5 tools | 209s | PASS (truncated) |
| Q9 | Risk profile of Garcia's portfolio | portfolio_estimation_agent | 90.6s | PASS |
| Q10 | Explain tax-loss harvesting (domain) | none (answered directly) | 36.7s | PASS |

**10/10 passed.** Q8 correctly routed to the briefing sub-agent and gathered all data (calendar, CRM, client info, holdings), but the response was truncated by Gemini's output token limit. The completion checker detected the truncation and retried twice before returning best-effort.

## Self-Improvement Mechanisms

Each agent improves through different strategies, all gated by the shared improvement harness (candidate testing, regression checks, safety checks, versioning):

| Agent | Strategy | Session State Variable |
|-------|----------|----------------------|
| Portfolio | Reflective lessons | `relevant_lessons` |
| Portfolio | Reusable skill library | `skill_procedures` |
| Portfolio | Tool success/cost stats | `tool_preferences` |
| Briefing | Prompt evolution (GEPA) | `context_preferences` |
| Briefing | Advisor correction memory | `advisor_corrections` |
| Orchestrator | Intent corrections | `intent_corrections` |
| Orchestrator | Tool description notes | `tool_notes` |
| Orchestrator | Saved plan templates | `plan_templates` |

## Tech Stack

- **Agent framework**: Google ADK v1.32.0 (`LlmAgent`, `AgentTool`, `Runner`)
- **LLM**: Gemini 3.8 Flash via Vertex AI (fallback: Gemini 3.5 Flash Lite)
- **Database**: Cloud Firestore (clients, CRM, calendar, email, holdings)
- **Backend**: FastAPI + Uvicorn
- **Frontend**: React + Vite
- **Deployment**: GCP Cloud Run (continuous deployment from `main`)
- **Observability**: OpenTelemetry → GCP Cloud Trace
- **Testing**: Playwright

## Dashboard

The dashboard provides the following pages:

- **Copilot** — chat interface powered by the live ADK orchestrator (Gemini), suggestion chips, execution trace visualization
- **Inbox** — inbox/sent/archive views with compose, reply, star, search, and category labels
- **Calendar** — timed Monday–Sunday calendar with week navigation and create/edit/delete modal
- **Meeting Prep** — meeting inputs, a six-section brief, inspectable sources, ranked news, advisor edits and review, and PDF export
- **Portfolio Analysis** — deterministic calculations and Gemini-powered portfolio agent
- **Clients** — 5 synthetic households with detail views
- **Overview** — AUM, client count, intent breakdown
- **Tools** — tool catalog (19 tools, including live Twelve Data news and rule-based compliance)

### Copilot Chat

The Copilot chat interface is connected to the live ADK orchestrator via a ReAct plan-execute-check loop. Simple lookups (calendar, email, client profile, CRM notes, holdings) are answered directly using workspace tools — no sub-agent overhead. Complex tasks (portfolio analysis, meeting briefings) are delegated to sub-agents. Generic domain questions (e.g. "What is a Roth IRA?") are answered directly from the model's training. After each execution, a lightweight completion checker (Gemini Flash Lite) verifies the response covers the full request. Stopping criteria: confidence ≥ 0.5, no identified gaps, or max 2 retry loops.

### Meeting Prep

The ADK briefing agent applies three business skills, records evidence and calculations, and the dashboard AI service performs independent quality review with bounded repairs. Client profiles, CRM notes, meeting context and CRM source records are stored in Firestore collections, seeded by `scripts/seed_crm.py`.

## Component A: Portfolio Estimation Agent

Answers an advisor's numeric questions about a synthetic client's portfolio and learns which tools, steps, and checks produce correct answers. Every task has a ground-truth answer computed by reference code, so it can be scored exactly.

**Task families:** Risk/return, goal projection, drift/rebalancing, tax impact, income, fee drag (held out).

**How it improves:**
1. **Reflective lessons** — after a failed run, the agent writes a short lesson retrieved into future runs
2. **Skill library** — successful multi-step plans saved as reusable procedures
3. **Tool-preference learning** — success/cost statistics per tool to avoid bad APIs

## Component B: Client Meeting Briefing Agent

Prepares a one-page briefing before an advisor meets a client. Pulls client profile, CRM notes, holdings, performance, and relevant market news, then writes the briefing with talking points, action items, and compliance flags.

**Data:** 5 client households in Firestore. Market news from live Twelve Data API.

**How it improves:**
1. **Prompt evolution (GEPA-style)** — reviews failed briefings, proposes instruction edits
2. **Context-selection learning** — learns which sources end up in good briefings
3. **Advisor-correction memory** — stores and applies advisor feedback to similar clients

## Component C: Advisor Request Orchestrator

Turns an advisor's free-text request into a working plan: intent, tools/agents, and execution order. Front door that calls Components A and B.

**Data:** ~300 synthetic advisor requests across 20+ intents. Tool catalog of 30-50 mock tools.

**How it improves:**
1. **Intent memory** — misread requests and corrections stored for retrieval
2. **Tool-description learning** — rewrites tool notes based on outcomes
3. **Plan templates** — successful plans saved and adapted to new intents

### Running the Component C experiment

```bash
pip install -e ".[dev,eval]"

# Offline smoke run
python -m self_improving_ai.evaluation.orchestrator --planner keyword --seeds 2

# Gemini run
python -m self_improving_ai.evaluation.orchestrator --planner gemini --seeds 1 --cycles 2 --gate-seeds 3 --test-limit 40

# Full run with promotion
python -m self_improving_ai.evaluation.orchestrator --planner gemini --seeds 5 --promote
```

## Evaluation

Each agent is evaluated against three baselines: static (learning off), hand-tuned (manually improved prompts), and retrieval-only (similar past runs as examples). A gain counts only if the learning agent beats every baseline on held-out tasks across at least five random seeds.

Every run is scored stage by stage: intent accuracy, step decomposition, tool selection, argument correctness, ordering, efficiency, and outcome. The harness reports learning curves per stage for learner vs. baseline.
