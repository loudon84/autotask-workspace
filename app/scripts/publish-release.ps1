# AutoTask release publish: scp to staging, server promote, flip stable.
# Usage: powershell -File scripts/publish-release.ps1 [-Version 0.1.2]
# Reads app/.env only. ssh/scp may prompt for password.
param([string]$Version = "")
$ErrorActionPreference = "Stop"

$appRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "lib\import-dotenv.ps1")
Import-ReleaseDotEnv $appRoot
if (-not $Version) {
    $Version = (Get-Content (Join-Path $appRoot "package.json") -Raw | ConvertFrom-Json).version
}

function Get-FirstEnv([string[]]$Names) {
    foreach ($name in $Names) {
        $value = [Environment]::GetEnvironmentVariable($name)
        if ($value) { return $value }
    }
    return $null
}

$sshHost = Get-FirstEnv @("SMC_RELEASE_HOST", "AUTOTASK_RELEASE_HOST", "SMC_WORK_RELEASE_HOST")
if (-not $sshHost) { $sshHost = "release.superic.com" }
$user = Get-FirstEnv @("SMC_RELEASE_USER", "AUTOTASK_RELEASE_USER", "SMC_WORK_RELEASE_USER")
if (-not $user) { $user = $env:USERNAME }
$dataRoot = Get-FirstEnv @("SMC_RELEASE_ROOT")
if (-not $dataRoot) { $dataRoot = "/data/smc-release" }
$root = Get-FirstEnv @("AUTOTASK_RELEASE_ROOT")
if (-not $root) { $root = "$dataRoot/autotask" }

$stage = Join-Path $appRoot "release\autotask\$Version"
if (-not (Test-Path $stage)) {
    throw "Missing stage dir $stage. Run release:build first."
}

# Traceability gate (aligned with Work): manifest must exist, version must match, gitCommit non-empty.
# NOTE: keep this file pure ASCII - Windows PowerShell 5.1 misreads UTF-8-no-BOM Chinese and breaks parsing.
$manifestPath = Join-Path $stage "release-manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "Missing release-manifest.json in $stage. Run release:build first."
}
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
if ($manifest.version -ne $Version) {
    throw "release-manifest.json version mismatch: $($manifest.version) != $Version"
}
if (-not $manifest.gitCommit) {
    throw "release-manifest.json missing gitCommit"
}
if ($manifest.gitDirty -eq $true) {
    Write-Warning "release-manifest.json gitDirty=true: this build contains uncommitted changes"
}

$stagingId = "$Version-$(Get-Date -Format yyyyMMddHHmmss)"
$remote = "${user}@${sshHost}"
$publicFeed = "https://release.superic.com/autotask/stable/"
$installerName = "AutoTask-Studio-$Version-setup.exe"
$remoteStaging = "${remote}:${root}/staging/${stagingId}/"

Write-Host "==> upload $Version to $remoteStaging"
ssh $remote "mkdir -p $root/staging/$stagingId"
if ($LASTEXITCODE -ne 0) { throw "ssh mkdir failed" }

$files = @(Get-ChildItem -LiteralPath $stage -File | ForEach-Object { $_.FullName })
if ($files.Count -eq 0) { throw "No files in $stage" }
& scp.exe -q @files $remoteStaging
if ($LASTEXITCODE -ne 0) { throw "scp failed" }

Write-Host "==> promote staging to releases and flip stable"
ssh $remote "bash $root/promote-autotask-release.sh '$Version' '$stagingId'"
if ($LASTEXITCODE -ne 0) { throw "promote failed" }

Write-Host "==> verify live latest.yml and installer"
$latest = (curl.exe -s "${publicFeed}latest.yml" | Out-String)
if ($latest -notmatch "version:\s*$([regex]::Escape($Version))") {
    throw "live latest.yml version mismatch:`n$latest"
}
$head = (curl.exe -sI "${publicFeed}$installerName" | Out-String)
if ($head -notmatch "(?m)^HTTP/.*\s200\s") {
    throw "installer HEAD is not 200:`n$head"
}

Write-Host ""
Write-Host "==> published AutoTask $Version to stable"
