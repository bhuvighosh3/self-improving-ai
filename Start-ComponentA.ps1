$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
$pythonExe = Join-Path $projectDir '.venv\Scripts\python.exe'
$nodeExe = (Get-Command node -ErrorAction Stop).Source
$logDir = Join-Path $projectDir 'artifacts\server'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Create the project virtual environment first.' }
foreach ($port in @(8000, 5173)) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $open = $client.ConnectAsync('127.0.0.1', $port)
        if ($open.Wait(500) -and $client.Connected) { throw "Port $port is already in use. Stop the existing server first." }
    } catch [System.AggregateException] {
        # A refused connection means the port is available.
    } finally { $client.Dispose() }
}
$env:PYTHONPATH = Join-Path $projectDir 'src'
$env:PYTHONUTF8 = '1'
$backend = Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','self_improving_ai.dashboard.app:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $projectDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'backend.log') -RedirectStandardError (Join-Path $logDir 'backend-error.log')
try {
    $frontend = Start-Process -FilePath $nodeExe -ArgumentList @('node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory (Join-Path $projectDir 'dashboard') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'frontend.log') -RedirectStandardError (Join-Path $logDir 'frontend-error.log')
} catch { Stop-Process -Id $backend.Id; throw }
@($backend,$frontend) | ForEach-Object { @{id=$_.Id;path=$_.Path;started=$_.StartTime.ToUniversalTime().Ticks} } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logDir 'processes.json') -Encoding utf8
$ready = $false
$startupTimer = [System.Diagnostics.Stopwatch]::StartNew()
while ($startupTimer.Elapsed.TotalSeconds -lt 20) {
    try {
        $apiCheck = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 2
        $pageCheck = Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 2
        if ($apiCheck.StatusCode -eq 200 -and $pageCheck.StatusCode -eq 200) { $ready = $true; break }
    } catch {
        Start-Sleep -Milliseconds 300
    }
}
if (-not $ready) {
    & (Join-Path $projectDir 'Stop-ComponentA.ps1')
    throw 'The local application did not become ready. Check artifacts/server logs.'
}
Write-Output 'Open http://127.0.0.1:5173 and select Portfolio Analysis. Servers are local only.'
