# 检查在线更新安装包落点。默认不启动安装程序。
# 用法（在用户电脑或本机）:
#   powershell -ExecutionPolicy Bypass -File scripts/verify-update-stage.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/verify-update-stage.ps1 -CopyToRoot
#   powershell -ExecutionPolicy Bypass -File scripts/verify-update-stage.ps1 -Open
param(
    [switch]$CopyToRoot,
    [switch]$Open
)
$ErrorActionPreference = "Stop"

$smcRoot = "D:\Programs\SMC"
$updates = "D:\Programs\SMC\AutoTask\updates"
$pending = Join-Path $env:LOCALAPPDATA "AutoTask-updater\pending"
$installed = "D:\Programs\SMC\AutoTask\AutoTaskStudio.exe"

function Get-Setups([string]$dir) {
    if (-not (Test-Path $dir)) {
        return @()
    }
    return @(Get-ChildItem -LiteralPath $dir -Filter "*-setup.exe" -File -ErrorAction SilentlyContinue)
}

function Show-Place([string]$title, [string]$dir, [string]$verdict) {
    Write-Host ""
    Write-Host "== $title =="
    Write-Host "   $dir"
    $files = Get-Setups $dir
    if ($files.Count -eq 0) {
        Write-Host "   (no *-setup.exe)"
        return $files
    }
    foreach ($file in $files) {
        Write-Host ("   {0}  {1:N0} bytes  {2}  [{3}]" -f $file.Name, $file.Length, $file.LastWriteTime, $verdict)
    }
    return $files
}

Write-Host "AutoTask update stage check (does not install unless -Open)"

if (Test-Path $installed) {
    $info = (Get-Item $installed).VersionInfo
    Write-Host ("Installed AutoTaskStudio.exe FileVersion={0}" -f $info.FileVersion)
} else {
    Write-Host "Installed AutoTaskStudio.exe not found"
}

$pendingFiles = Show-Place "C pending (AV blocked)" $pending "do not launch"
$updateFiles = Show-Place "AutoTask\updates (AV blocked)" $updates "do not launch"
$rootFiles = Show-Place "D:\Programs\SMC root (AV allow)" $smcRoot "ok to launch"

$source = $null
if ($pendingFiles.Count -gt 0) {
    $source = $pendingFiles | Sort-Object LastWriteTime -Descending | Select-Object -First 1
} elseif ($updateFiles.Count -gt 0) {
    $source = $updateFiles | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

if ($CopyToRoot) {
    if ($source -eq $null) {
        throw "No setup.exe in pending or updates to copy"
    }
    if (-not (Test-Path $smcRoot)) {
        throw "Missing $smcRoot"
    }
    $dest = Join-Path $smcRoot $source.Name
    Copy-Item -LiteralPath $source.FullName -Destination $dest -Force
    Write-Host ""
    Write-Host "Copied to $dest"
    $rootFiles = Get-Setups $smcRoot
}

$rootLaunch = $rootFiles | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($Open) {
    if ($rootLaunch -eq $null) {
        throw "No setup.exe in $smcRoot. Run with -CopyToRoot first, or copy manually."
    }
    Write-Host ""
    Write-Host "Opening $($rootLaunch.FullName) (Explorer-style, no /S)"
    Start-Process -FilePath $rootLaunch.FullName
    exit 0
}

Write-Host ""
if ($rootLaunch -eq $null) {
    Write-Host "FAIL: no installer in D:\Programs\SMC root. Copy there, do not run from pending/updates."
    exit 1
}

Write-Host "PASS: root has $($rootLaunch.Name)"
Write-Host "To install: fully quit AutoTask, then double-click that file."
Write-Host "Or: powershell -ExecutionPolicy Bypass -File scripts/verify-update-stage.ps1 -Open"
exit 0
