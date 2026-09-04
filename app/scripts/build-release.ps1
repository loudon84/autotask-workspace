# AutoTask 在线更新发版：打包 → 校验 → 暂存到 release/autotask/<版本>/
# 用法：powershell -File scripts/build-release.ps1
# 可选环境变量：AUTOTASK_UPDATE_URL（覆盖烧进安装包的更新地址，默认 https://release.superic.com/autotask/stable/）
$ErrorActionPreference = "Stop"

$appRoot = Split-Path -Parent $PSScriptRoot
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

$makeDir = Join-Path $appRoot "out\make\nsis\x64"
$exe = Join-Path $makeDir "AutoTask-Studio-$version-setup.exe"
$blockmap = "$exe.blockmap"
$latestYml = Join-Path $makeDir "latest.yml"

foreach ($f in @($exe, $blockmap, $latestYml)) {
    if (-not (Test-Path $f)) { throw "缺少产物: $f" }
}

# 校验 latest.yml 里的版本
$yml = Get-Content $latestYml -Raw
if ($yml -notmatch "version:\s*$([regex]::Escape($version))") { throw "latest.yml 版本不是 $version" }

# 校验 latest.yml 里的 sha512 与 exe 实际一致（防产物错配）
if ($yml -match "sha512:\s*(\S+)") {
    $expected = $Matches[1]
    $actual = [Convert]::ToBase64String([System.Security.Cryptography.SHA512]::Create().ComputeHash([System.IO.File]::ReadAllBytes($exe)))
    if ($expected -ne $actual) { throw "latest.yml 的 sha512 与 exe 不一致" }
    Write-Host "==> latest.yml sha512 校验通过"
} else {
    throw "latest.yml 里没有 sha512"
}

# 暂存
$stage = Join-Path $appRoot "release\autotask\$version"
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Path $stage | Out-Null
Copy-Item $exe, $blockmap, $latestYml $stage

# 校验和
$hash = (Get-FileHash $exe -Algorithm SHA256).Hash.ToLower()
"$hash  $(Split-Path $exe -Leaf)" | Out-File -Encoding ascii (Join-Path $stage "SHA256SUMS.txt")

Write-Host ""
Write-Host "==> 完成。产物已暂存到 $stage"
Write-Host "    手动发布："
Write-Host "    1. 把整个 $version 文件夹拷到服务器 /data/smc-release/autotask/staging/$version-manual/"
Write-Host "    2. 服务器上执行: bash /data/smc-release/autotask/promote-autotask-release.sh $version $version-manual"
Write-Host "    3. 验证: https://release.superic.com/autotask/stable/latest.yml 版本应为 $version"
