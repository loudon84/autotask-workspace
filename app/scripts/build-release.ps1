# AutoTask 在线更新发版：打包 → 校验 → 暂存到 release/autotask/<版本>/
# 用法：powershell -File scripts/build-release.ps1
# 可选环境变量：AUTOTASK_UPDATE_URL（覆盖烧进安装包的更新地址，默认 https://release.superic.com/autotask/stable/）
# 不做代码签名门、不写 Publisher。产出与 work 同一套文件：exe、blockmap、latest.yml、SHA256SUMS.txt
$ErrorActionPreference = "Stop"

$appRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "lib\import-dotenv.ps1")
Import-ReleaseDotEnv $appRoot
Set-Location $appRoot

$version = (Get-Content package.json -Raw | ConvertFrom-Json).version
$updateUrl = if ($env:AUTOTASK_UPDATE_URL) { $env:AUTOTASK_UPDATE_URL } else { "https://release.superic.com/autotask/stable/" }
Write-Host "版本: $version"
Write-Host "更新地址: $updateUrl"

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

Write-Host ""
Write-Host "==> 完成"
Write-Host "    产物: $stage"
Write-Host "    更新源: $updateUrl"
