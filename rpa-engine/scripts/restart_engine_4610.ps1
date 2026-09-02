# Kill whatever is LISTENING on 4610, then start Engine in this window.
# Success = you see "Uvicorn running on http://0.0.0.0:4610" and NO WinError 10048.
$ErrorActionPreference = "Stop"
$Port = 4610
$EngineRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $EngineRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Missing $Python. Create the venv first."
}

function Get-ListenPids {
    @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
}

$old = Get-ListenPids
if ($old.Count -eq 0) {
    Write-Host "4610 is free"
} else {
    foreach ($procId in $old) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue
        Write-Host "stopping pid=$procId $($proc.CommandLine)"
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    $deadline = (Get-Date).AddSeconds(10)
    while ((Get-Date) -lt $deadline) {
        if ((Get-ListenPids).Count -eq 0) { break }
        Start-Sleep -Milliseconds 300
    }
    $still = Get-ListenPids
    if ($still.Count -gt 0) {
        throw "4610 still held by pid=$($still -join ',')"
    }
    Write-Host "4610 is free (killed pid=$($old -join ','))"
}

Write-Host "Starting Engine. Must see: Uvicorn running on http://0.0.0.0:4610"
Write-Host "Must NOT see: WinError 10048"
Write-Host "Verify in another window: irm http://127.0.0.1:4610/health/live"
Set-Location $EngineRoot
& $Python -m nodeskclaw_rpa_engine
