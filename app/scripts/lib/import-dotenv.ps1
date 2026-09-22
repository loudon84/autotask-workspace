# 发版脚本共用：读 dotenv，默认不覆盖进程里已有变量；-Override 时后读的文件为准。
function Import-DotEnvFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [switch]$Override
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    foreach ($line in Get-Content -LiteralPath $Path -Encoding utf8) {
        if ($line -match '^\s*(?:#.*)?$') {
            continue
        }
        if ($line -notmatch '^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
            continue
        }
        $name = $Matches[1]
        $value = $Matches[2].Trim()
        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        if (
            -not $Override -and
            -not [string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($name))
        ) {
            continue
        }
        Set-Item -Path "Env:$name" -Value $value
    }
}

function Import-ReleaseDotEnv {
    param([Parameter(Mandatory = $true)][string]$AppRoot)

    Import-DotEnvFile (Join-Path $AppRoot ".env")
}
