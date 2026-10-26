# Self-Improving AI — Wealth Management Copilot

A self-improving AI copilot for wealth management advisors, built with [Google ADK](https://google.github.io/adk-docs/) and Gemini. The system learns from execution errors and advisor feedback to improve planning, tool use, and task performance over time.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Gemini API key from [AI Studio](https://aistudio.google.com/apikey)

### Setup

```bash
git clone https://github.com/bhuvighosh3/self-improving-ai.git
cd self-improving-ai
pip install -e .
```

Create a `.env` file in the project root:

```
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=your-api-key-here
```

### Run the Orchestrator (CLI)

```bash
python -m self_improving_ai "Get me ready for my 2pm with the Garcias"
```

### Run the Dashboard

Start both the FastAPI backend and React frontend:

```bash
# Terminal 1 — Backend
uvicorn self_improving_ai.dashboard.app:app --port 8000

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

## Architecture

Three agents connected via Google ADK's `AgentTool`:

- **Request Orchestrator** (Component C) — parses advisor requests, plans workflows, and delegates to sub-agents
- **Portfolio Estimation Agent** (Component A) — handles numeric portfolio questions (risk/return, projections, drift, tax impact)
- **Meeting Briefing Agent** (Component B) — prepares client meeting briefings from CRM, portfolio, and market data

```
Advisor request
      ↓
┌─────────────────────┐
│  Request Orchestrator│ ← Gemini 2.5 Flash
│  (LlmAgent)         │
└──┬──────────────┬───┘
   │              │
   ▼              ▼
┌──────────┐  ┌──────────┐
│ Portfolio │  │ Briefing │
│ Agent     │  │ Agent    │
└──────────┘  └──────────┘
```

The orchestrator uses `AgentTool` to call sub-agents. Each agent's instructions contain `{placeholder}` variables resolved from `session.state` at runtime, enabling learned knowledge injection without modifying agent definitions.

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
- **LLM**: Gemini 2.5 Flash via Developer API
- **Backend**: FastAPI + Uvicorn
- **Frontend**: React + Vite (light theme, DM Sans / JetBrains Mono)
- **Testing**: Playwright (11 automated tests)
- **Telemetry**: OpenTelemetry

## Dashboard

The dashboard provides 7 pages:

- **Copilot** — chat interface with the orchestrator, suggestion chips, execution trace visualization
- **Overview** — AUM, client count, intent breakdown
- **Clients** — 5 synthetic households with detail views
- **Requests** — request history table
- **Tools** — mock tool catalog (14 tools with realistic traps)
- **News** — market news feed
- **Agents** — agent cards showing configuration and status

---

## Detailed Design

The sections below describe the full system design, evaluation plan, and improvement harness.

---

## Project Details

### Problem and Goals

Today's advisor-facing agents repeat their mistakes: a wrong tool, irrelevant data or a wasteful plan recurs on the next run because nothing carries over. Learning from experience could fix this, but a system that changes itself can also degrade or behave unpredictably, which a regulated firm cannot accept.

Our goals, mapped to LPL's success measures:

1. **Learn from execution outcomes.** Capture successes, failures, retries and simulated advisor corrections, and turn them into better tool choice, planning and context selection.
2. **Generalize.** Show gains on task types, tools and conditions the agent has never seen, not just replays of solved tasks.
3. **Prove it against a baseline.** Compare every learning agent to the same agent with learning switched off, under identical tasks and seeds.
4. **Stay safe.** Adopt changes only after validation, block regressions, and keep everything in a sandbox with mock tools and synthetic clients.
5. **Show it.** A live dashboard that replays the agents' learning cycles for a professional audience.

---

## The Improvement Harness Inside Every Component

Rather than developing three independent improvement harnesses, we propose a shared self-improvement infrastructure across all components. This infrastructure will provide standardized execution tracing, feedback collection, candidate evaluation, versioning, and rollback.

Each specialized agent may implement its own improvement strategies and evaluation metrics, while relying on the shared infrastructure to validate and manage proposed changes. This approach reduces duplicated development effort and enables consistent evaluation across the integrated system.

Every harness includes:

- **Experience store.** Every run logged as a full trace: request, plan, tool calls, outputs, score, cost and any advisor correction.
- **Candidate testing.** The current agent and a proposed change (a new lesson, rewritten prompt, saved skill or tool preference) run on the same validation tasks and seeds. A paired statistical test decides whether the gain is real or noise.
- **Regression suite.** Tasks the agent already solves. A change that raises the average but breaks these is rejected.
- **Safety checks.** Changes that remove compliance rules, call disallowed tools or attempt a trade are blocked.
- **Versioning and rollback.** Every adopted change gets a version and an audit-log entry, so any version can be restored.
- **Dashboard panel.** Learning curves, learner versus baseline, and accepted or rejected changes with reasons.

What differs is the scoring, which each component section describes. To avoid teams grading their own work, each pair writes the hidden test set for another pair's component (A tests B, B tests C, C tests A).

---

## System Architecture

The orchestrator receives the advisor's request and calls the other two agents; all three run against one shared sandbox.

```
Advisor request, in plain language
        ↓
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  A: Portfolio    │  │  C: Request     │  │  B: Meeting     │
│  Estimation     │  │  Orchestrator   │  │  Briefing       │
│  Agent          │  │  Agent          │  │  Agent          │
│                 │  │                 │  │                 │
│  Risk,          │  │  Intent, tool   │  │  Retrieves,     │
│  projections,   │  │  discovery      │  │  writes brief   │
│  drift          │  │  Plans and      │  │  Learns useful  │
│  Learns tools   │  │  calls A and B  │  │  context        │
│  and steps      │  │                 │  │                 │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
   ↓ traces ↑ adopted   ↓ traces ↑ adopted   ↓ traces ↑ adopted
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Improvement    │  │  Improvement    │  │  Improvement    │
│  harness        │  │  harness        │  │  harness        │
│                 │  │                 │  │                 │
│  Exact numeric  │  │  Intent and     │  │  Checklist and  │
│  scoring        │  │  plan accuracy  │  │  LLM judge      │
│  Test vs frozen │  │  Test vs frozen │  │  Test vs frozen │
│  baseline       │  │  baseline       │  │  baseline       │
│  Regression     │  │  Regression     │  │  Regression     │
│  suite          │  │  suite          │  │  suite          │
│  Adopt or       │  │  Adopt or       │  │  Adopt or       │
│  roll back      │  │  roll back      │  │  roll back      │
└─────────────────┘  └─────────────────┘  └─────────────────┘

Sandbox: mock tools, synthetic clients, mock news. No live data, no real trades.
```

The final product will provide a single advisor-facing interface, where the orchestrator coordinates specialized agents to complete end-to-end workflows. Integration will begin from the initial development phase rather than being deferred until the final stage.

---

## Component A: Portfolio Estimation Agent

Component A answers an advisor's numeric questions about a synthetic client's portfolio, and learns which tools, steps and checks produce correct answers. Its strength as a research testbed is that every task has a ground-truth answer computed by our own reference code, so we can score it exactly.

### Task Families

| Family | Example Advisor Request | What Gets Estimated |
|--------|------------------------|---------------------|
| Risk and return | "What's the expected return and volatility of the Smiths' portfolio?" | Weighted return, volatility from a covariance matrix |
| Goal projection | "Will this client reach $2M by 65?" | Monte Carlo probability of success, median ending value |
| Drift and rebalancing | "How far is this account from its 60/40 target, and what trades fix it?" | Drift per asset class, trade list |
| Tax impact | "What's the capital-gains cost of rebalancing?" | Gains by tax lot, estimated tax |
| Income | "How much can she safely withdraw each year?" | Sustainable withdrawal under a success threshold |
| Fee drag (held out) | "How much do fees cost him over 20 years?" | Value with and without fees |

### Mock Tools

About 15 to 20 simulated APIs: holdings lookup, price history, capital market assumptions, covariance builder, Monte Carlo engine, tax-lot lookup, calculator and a document search. We add realistic traps: a deprecated price API returning stale data, near-duplicate tool names, percent-versus-decimal unit mismatches, missing tickers and occasional timeouts. These make tool choice matter.

### How It Improves

We combine three mechanisms and test each one separately:

1. **Reflective lessons (Reflexion-style).** After a failed or inefficient run, the agent writes a short lesson, such as "convert yield to decimal before compounding". Relevant lessons are retrieved into future runs.
2. **Skill library.** Successful multi-step plans are saved as reusable procedures ("compute portfolio volatility") that the agent can call on new task families.
3. **Tool-preference learning.** Running success and cost statistics per tool and task type, so the agent learns, for example, to avoid the stale price API.

### Harness Metrics

Answer accuracy within tolerance, tool-selection accuracy against a reference trajectory, steps and retries per task, cost in tokens, and accuracy on the held-out family.

---

## Component B: Client Meeting Briefing Agent

Component B prepares a one-page briefing before an advisor meets a client, and learns what to retrieve, what to leave out and how to write it. This is the scenario LPL describes in the brief, and it tests the open-ended side of agent work where Component A tests the exact side.

### The Workflow

Pull the client profile and CRM notes, retrieve holdings and performance, find relevant market news, run a few calculations (often by calling Component A), then write the briefing: recent changes, talking points, open action items and compliance flags.

### Data

About 50 synthetic client households with profiles, goals and meeting notes, plus a mock news feed. The feed is seeded with relevant items and many distractors, such as news about stocks the client doesn't hold.

### How It Improves

1. **Prompt and instruction evolution (GEPA-style).** The system reviews failed briefings, proposes edits to its own instructions, and keeps the versions that score better on a validation set.
2. **Context-selection learning.** It learns which sources and news items actually end up in good briefings, and stops retrieving the rest.
3. **Advisor-correction memory.** Simulated advisors give feedback ("always mention upcoming RMDs for clients over 73"). The agent stores these and applies them to similar clients.

### Scoring

Each test briefing has a checklist of facts that must appear and facts that must not (hallucinated holdings, return guarantees). We score with automated fact checks plus an LLM judge, and validate the judge against our own hand-labels on a sample of about 100 briefings.

### Harness Metrics

Checklist recall, factual errors, irrelevant retrievals per task, tool calls per briefing, and compliance-flag violations.

---

## Component C: Advisor Request Orchestrator

Component C turns an advisor's free-text request into a working plan: what the advisor wants, which tools or agents to use, and in what order. It covers the brief's first exploration area (intent understanding, dynamic tool discovery, workflow planning and context selection) and is the front door that calls Components A and B.

### Example

"Get me ready for my 2pm with the Garcias and check whether they're still on track for retirement" should become: look up the client, call the briefing agent, call the portfolio agent for a goal projection, merge the results.

### Data

About 300 synthetic advisor requests across 20 or more intents, written in varied, messy language, each labelled with the correct intent and a reference plan. A tool catalog of 30 to 50 mock tools with descriptions, including overlapping and outdated ones.

### How It Improves

1. **Intent memory.** Misread requests and their corrections are stored and retrieved for similar future requests.
2. **Tool-description learning.** The agent rewrites its own notes on what each tool is actually good for, based on outcomes, rather than trusting the catalog's descriptions.
3. **Plan templates.** Plans that worked are saved as templates and adapted to new intents.

### Generalization Tests

New intents never seen in training, plus a changed tool catalog mid-experiment: tools renamed, added, deprecated or swapped for a new version.

### Harness Scoring

Intent accuracy, tool-selection precision and recall against the reference plan, plan validity (steps in a runnable order), and end-to-end success when the plan is executed.

---

## Evaluation Plan

In addition to evaluating individual agents, we will assess the performance of the integrated system on complete advisor workflows. This end-to-end evaluation will measure task completion, cross-agent coordination, unnecessary tool calls, execution efficiency, and the overall quality of the final output.

Component-level evaluations will help identify the source of errors, while end-to-end evaluations will determine whether improvements to individual agents translate into meaningful product-level gains.

We count a gain only if a learning agent beats every baseline on held-out tasks, across at least five random seeds.

### Baselines

| Baseline | What It Is | What Beating It Shows |
|----------|-----------|----------------------|
| Static agent | Same model and tools, learning off | Learning helps at all |
| Hand-tuned agent | Static agent with prompts we improve by hand for the same effort | Self-improvement beats a human engineer's tuning |
| Retrieval-only | Static agent that retrieves similar past successful runs as examples, no reflection | Reflection adds more than simple memory |

### Data Splits

Training tasks drive learning. A validation set is used only by each component's harness to accept or reject changes. A held-out test set, written and kept by another pair, includes three kinds of novelty:

- **New tasks**: unseen task families (fee drag for A, a new client type for B, new intents for C)
- **Changed tools**: renamed tools, a new API version, or a tool removed mid-experiment
- **Changed conditions**: noisier data, more distractor news, stricter compliance rules

### Ablations

Turn each improvement mechanism off in turn, to show which one carries the gain.

### Metrics Reported for Every Run

Task completion rate, tool-selection accuracy, unnecessary actions and retries, tokens and time per task, the improvement curve across cycles, the gap between seen and unseen tasks, and regressions caught versus missed.

### Planner and Tool-Call Evaluation

Every run is scored stage by stage, not just on the final answer, so we can see where an agent went wrong and which stage learning actually fixed. Each test task carries a reference plan: the expected intent, the steps, and the tool calls with their arguments. Where several orders are valid, the reference stores the allowed orderings so a correct alternative plan is not penalized.

| Stage | What We Check | How It Is Scored |
|-------|--------------|-----------------|
| 1. Intent | Did the planner identify what the advisor asked for? | Exact match to the labelled intent |
| 2. Decomposition | Are the planned steps complete, with none missing or extra? | Step precision and recall against the reference plan |
| 3. Tool selection | Was the correct tool chosen for each step, and no wrong or deprecated tool? | Tool precision and recall; count of wrong-tool calls |
| 4. Arguments | Were the tool calls filled in correctly (account ID, dates, units)? | Argument-by-argument match, in the style of the Berkeley Function Calling Leaderboard |
| 5. Ordering | Were dependent steps called in a valid order (prices before volatility)? | Check against the allowed orderings |
| 6. Efficiency | Were there unnecessary calls, repeats or retries? | Extra calls and retries beyond the reference |
| 7. Outcome | Is the final answer or end state correct? | Numeric tolerance (A), checklist (B), end-state comparison in the style of τ-bench (C) |

The harness reports these scores per stage for the learner and each baseline. A learning curve per stage then shows, for example, whether gains came from better tool selection or from better arguments.
