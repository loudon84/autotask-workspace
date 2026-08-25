# Kill whatever is LISTENING on 4520, then start Task in this window.
# Success = you see "Uvicorn running on http://0.0.0.0:4520" and NO WinError 10048.
$ErrorActionPreference = "Stop"
$Port = 4520
$ServiceRoot = Split-Path -Parent $PSScriptRoot

function Get-ListenPids {
    @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
}

$old = Get-ListenPids
if ($old.Count -eq 0) {
    Write-Host "4520 is free"
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
        throw "4520 still held by pid=$($still -join ',')"
    }
    Write-Host "4520 is free (killed pid=$($old -join ','))"
}

Write-Host "Starting Task. Must see: Uvicorn running on http://0.0.0.0:4520"
Write-Host "Must NOT see: WinError 10048"
Write-Host "Verify in another window: irm http://127.0.0.1:4520/health"
Set-Location $ServiceRoot
& uv run uvicorn app.main:app --host 0.0.0.0 --port $Port
