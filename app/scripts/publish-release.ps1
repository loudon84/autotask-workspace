# AutoTask 在线更新发版：上传暂存目录到 release.superic.com 并切换 stable 软链
# 用法：powershell -File scripts/publish-release.ps1 [-Version 0.1.2]
# 环境变量（默认值按 smc 服务器约定）：
#   AUTOTASK_RELEASE_HOST    默认 release.superic.com
#   AUTOTASK_RELEASE_USER    默认 $env:USERNAME
#   AUTOTASK_RELEASE_ROOT    默认 /data/smc-release/autotask
# 前置：先跑 build-release.ps1；本机有 ssh/scp 且对目标主机免密。
param([string]$Version = "")
$ErrorActionPreference = "Stop"

$appRoot = Split-Path -Parent $PSScriptRoot
if (-not $Version) {
    $Version = (Get-Content (Join-Path $appRoot "package.json") -Raw | ConvertFrom-Json).version
}

$host_ = if ($env:AUTOTASK_RELEASE_HOST) { $env:AUTOTASK_RELEASE_HOST } else { "release.superic.com" }
$user = if ($env:AUTOTASK_RELEASE_USER) { $env:AUTOTASK_RELEASE_USER } else { $env:USERNAME }
$root = if ($env:AUTOTASK_RELEASE_ROOT) { $env:AUTOTASK_RELEASE_ROOT } else { "/data/smc-release/autotask" }

$stage = Join-Path $appRoot "release\autotask\$Version"
if (-not (Test-Path $stage)) { throw "未找到暂存目录 $stage，先跑 build-release.ps1" }

$stagingId = "$Version-$(Get-Date -Format yyyyMMddHHmmss)"
$remote = "${user}@${host_}"

Write-Host "==> 上传 $Version 到 ${remote}:$root/staging/$stagingId"
ssh $remote "mkdir -p $root/staging/$stagingId"
if ($LASTEXITCODE -ne 0) { throw "ssh 建目录失败" }
scp -q "$stage\*" "${remote}:$root/staging/$stagingId/"
if ($LASTEXITCODE -ne 0) { throw "scp 上传失败" }

Write-Host "==> 服务器 promote（移入 releases 并切 stable 软链）"
ssh $remote "bash $root/promote-autotask-release.sh '$Version' '$stagingId'"
if ($LASTEXITCODE -ne 0) { throw "promote 失败" }

Write-Host "==> 验证线上 latest.yml"
$latest = curl.exe -s "https://release.superic.com/autotask/stable/latest.yml"
if ($latest -notmatch "version:\s*$([regex]::Escape($Version))") { throw "线上 latest.yml 版本不对：`n$latest" }

Write-Host ""
Write-Host "==> 发布完成：AutoTask $Version 已上线 stable。客户端最迟 6 小时内会看到更新。"
