# AutoTask 在线更新发版：打包 → 校验 → 暂存到 release/autotask/<版本>/
# 用法：powershell -File scripts/build-release.ps1
# 可选环境变量：AUTOTASK_UPDATE_URL（覆盖烧进安装包的更新地址，默认 https://release.superic.com/autotask/stable/）
#               AUTOTASK_RELEASE_ALLOW_DIRTY=1（允许带未提交改动打包，仅调试用，正式发版不要用）
# 不做代码签名门、不写 Publisher。产出与 work 同一套文件：exe、blockmap、latest.yml、SHA256SUMS.txt、release-manifest.json
# release-manifest.json 记录 gitCommit/gitBranch，线上任意一版可追回到确切源码提交（对齐 Work）
$ErrorActionPreference = "Stop"

$appRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "lib\import-dotenv.ps1")
Import-ReleaseDotEnv $appRoot
Set-Location $appRoot

$version = (Get-Content package.json -Raw | ConvertFrom-Json).version
$updateUrl = if ($env:AUTOTASK_UPDATE_URL) { $env:AUTOTASK_UPDATE_URL } else { "https://release.superic.com/autotask/stable/" }
Write-Host "版本: $version"
Write-Host "更新地址: $updateUrl"

# git 身份门禁（对齐 Work）：正式发版必须能追回到确切提交
$gitCommit = (git -C $appRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or -not $gitCommit) { throw "git rev-parse HEAD 失败，无法记录构建身份" }
$gitBranch = (git -C $appRoot rev-parse --abbrev-ref HEAD).Trim()
$gitDirty = [bool](git -C $appRoot status --porcelain)
if ($gitDirty -and $env:AUTOTASK_RELEASE_ALLOW_DIRTY -ne "1") {
    throw "工作区有未提交改动，拒绝打包（产物无法追溯到确切提交）。先 git commit，或设 AUTOTASK_RELEASE_ALLOW_DIRTY=1 强制（仅调试）"
}
if ($gitDirty) { Write-Warning "AUTOTASK_RELEASE_ALLOW_DIRTY=1：本次构建含未提交改动，gitCommit 不代表完整源码状态" }
Write-Host "git: $gitBranch @ $gitCommit$(if ($gitDirty) { ' (dirty)' })"

if ($updateUrl -notmatch "^https://release\.superic\.com/autotask/") {
    throw "AUTOTASK_UPDATE_URL 必须是 https://release.superic.com/autotask/ 下的路径，当前: $updateUrl"
}

Write-Host "==> electron-forge make (nsis)"
npm run make
if ($LASTEXITCODE -ne 0) { throw "make 失败" }

$makeDir = Join-Path $appRoot "out-pkg\make\nsis\x64"
if (-not (Test-Path $makeDir)) {
    $makeDir = Join-Path $appRoot "out\make\nsis\x64"
}
$exeName = "AutoTask-Studio-$version-setup.exe"
$exe = Join-Path $makeDir $exeName
$blockmapName = "$exeName.blockmap"
$blockmap = Join-Path $makeDir $blockmapName
$latestYml = Join-Path $makeDir "latest.yml"

foreach ($f in @($exe, $blockmap, $latestYml)) {
    if (-not (Test-Path $f)) { throw "缺少产物: $f" }
}

$yml = Get-Content $latestYml -Raw
if ($yml -notmatch "version:\s*$([regex]::Escape($version))") { throw "latest.yml 版本不是 $version" }

if ($yml -match "sha512:\s*(\S+)") {
    $expected = $Matches[1]
    $actual = [Convert]::ToBase64String([System.Security.Cryptography.SHA512]::Create().ComputeHash([System.IO.File]::ReadAllBytes($exe)))
    if ($expected -ne $actual) { throw "latest.yml 的 sha512 与 exe 不一致" }
    Write-Host "==> latest.yml sha512 校验通过"
} else {
    throw "latest.yml 里没有 sha512"
}

$stage = Join-Path $appRoot "release\autotask\$version"
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Path $stage | Out-Null
Copy-Item $exe, $blockmap, $latestYml $stage

$sums = @(
    "$((Get-FileHash $exe -Algorithm SHA256).Hash.ToLowerInvariant())  $exeName"
    "$((Get-FileHash $blockmap -Algorithm SHA256).Hash.ToLowerInvariant())  $blockmapName"
    "$((Get-FileHash $latestYml -Algorithm SHA256).Hash.ToLowerInvariant())  latest.yml"
)
$sums | Set-Content -LiteralPath (Join-Path $stage "SHA256SUMS.txt") -Encoding ascii

# release-manifest.json：版本 → 源码提交的可追溯清单（对齐 Work 的 smc.work.release.v1，去掉签名/publisher 字段）
$manifest = [ordered]@{
    schema        = "autotask.release.v1"
    version       = $version
    gitCommit     = $gitCommit
    gitBranch     = $gitBranch
    gitDirty      = $gitDirty
    platform      = "windows"
    arch          = "x64"
    updateChannel = "stable"
    updateUrl     = $updateUrl
    installer     = $exeName
    sha256        = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLowerInvariant()
    createdAt     = [DateTime]::UtcNow.ToString("o")
}
$manifestPath = Join-Path $stage "release-manifest.json"
[System.IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 5), (New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "==> 完成"
Write-Host "    产物: $stage"
Write-Host "    更新源: $updateUrl"
