$ErrorActionPreference = 'Stop'
$recordPath = Join-Path $PSScriptRoot 'artifacts\server\processes.json'
if (-not (Test-Path -LiteralPath $recordPath)) { Write-Output 'No managed server record.'; exit }
Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json | ForEach-Object {
    $process = Get-Process -Id $_.id -ErrorAction SilentlyContinue
    if ($process -and $process.Path -eq $_.path -and $process.StartTime.ToUniversalTime().Ticks -eq $_.started) {
        Stop-Process -Id $process.Id
    }
}
Write-Output 'Stopped matching Component A server processes.'
