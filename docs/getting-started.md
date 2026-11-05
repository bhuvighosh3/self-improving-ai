# Setup and local launch

Commands below run from the repository root. VS Code is an optional editor;
Python runs the backend, and Node runs the frontend.

## Validated environment

- Windows with Python 3.13; the project declaration is Python >=3.11, but the
  frozen dependency set was validated on 3.13.
- Google ADK 1.32 and 2.13 are checked separately; the shared dependency range accepts both.
- Node and npm. The team package.json and package-lock.json are retained.

## Install on a new computer

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" "google-adk==2.13.0"
cd dashboard
npm ci
cd ..
```

The team npm lock is unchanged. requirements-component-a.lock.txt records the earlier
standalone A environment (ADK 1.32); use it only when reproducing that specific environment.

## Launch and stop

```powershell
.\Start-ComponentA.ps1
.\Stop-ComponentA.ps1
```

The launcher waits for the backend at `127.0.0.1:8000` and frontend at
`127.0.0.1:5173` before reporting readiness. Both are local-only. Logs and recorded
process identities are under `artifacts/server/`. The stop script checks process
identity before stopping the two recorded processes.

PowerShell execution policies are controlled by your computer. A policy error is
separate from application startup; the manual commands below also work.

## Manual launch

In one terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn self_improving_ai.dashboard.app:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd dashboard
npx vite --host 127.0.0.1 --port 5173 --strictPort
```

Choose **Main → Portfolio Analysis**. Configure provider keys in **Connections**
only when using Gemini or external market data. Local calculations need neither key.

The synthetic clients are examples. Model inputs, target weights and financial
assumptions remain draft demonstration data; see [Assumptions](assumptions.md).
