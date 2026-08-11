#requires -Version 5.1
<#
.SYNOPSIS
  One-click debug launcher for a manifest Flow package.

.DESCRIPTION
  Runs a Flow package from manifest/ through the real RPA Runtime
  (scripts/debug_flow_local.py) using the repository virtual environment, so you
  can set breakpoints in flow.py and step through the run.

  Any extra arguments are forwarded to debug_flow_local.py
  (e.g. --headless, --no-cleanup, --channel msedge).

.EXAMPLE
  .\scripts\debug_manifest_flow.ps1
  Runs the default supplier portal Flow 1.2.3 with -PoNo PO12345.

.EXAMPLE
  .\scripts\debug_manifest_flow.ps1 -Package manifest/rpa_flow_login_demo/1.1.0 -PoNo PO123 -Headless
  Runs a different package headless.
#>
[CmdletBinding()]
param(
    [string]$Package = "manifest/rpa_flow_supplier_portal_prepare_erp_order/1.2.3",
    [Parameter(Mandatory = $true)]
    [string]$PoNo,
    [string]$PortalUrl = "http://127.0.0.1:4700",
    [string]$Username,
    [string]$Password,
    [string]$Channel,
    [switch]$Headless,
    [switch]$NoCleanup,
    [string]$Artifacts,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

$ErrorActionPreference = "Stop"

# Resolve paths relative to the repository root (parent of scripts/).
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    $VenvPython = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $VenvPython) {
    Write-Error "Python interpreter not found. Activate the venv or install Python."
}

$PackagePath = Join-Path $RepoRoot $Package
if (-not (Test-Path $PackagePath)) {
    Write-Error "Manifest package not found: $PackagePath"
}

# Build the argument list for the debug harness.
$Runner = Join-Path $RepoRoot "scripts\debug_flow_local.py"
$RunnerArgs = @("--package", $Package, "--po-no", $PoNo, "--portal-url", $PortalUrl)
if ($Username)  { $RunnerArgs += @("--username", $Username) }
if ($Password)  { $RunnerArgs += @("--password", $Password) }
if ($Channel)   { $RunnerArgs += @("--channel", $Channel) }
if ($Headless)  { $RunnerArgs += "--headless" }
if ($NoCleanup) { $RunnerArgs += "--no-cleanup" }
if ($Artifacts) { $RunnerArgs += @("--artifacts", $Artifacts) }
if ($ExtraArgs) { $RunnerArgs += $ExtraArgs }

Write-Host "==> Debugging manifest package" -ForegroundColor Cyan
Write-Host "    package : $Package"
Write-Host "    po_no   : $PoNo"
Write-Host "    portal  : $PortalUrl"
Write-Host "    python  : $VenvPython"
Write-Host ""

& $VenvPython $Runner @RunnerArgs
exit $LASTEXITCODE
