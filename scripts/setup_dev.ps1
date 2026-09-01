$ErrorActionPreference = "Stop"

$appRoot = Split-Path -Parent $PSScriptRoot
$coreRoot = Join-Path (Split-Path -Parent $appRoot) "sipi-sparam-core"

if (-not (Test-Path -LiteralPath (Join-Path $coreRoot "pyproject.toml"))) {
    throw "未找到公共核心：$coreRoot"
}

python -m pip install -e "$coreRoot[dev]"
python -m pip install -e "$appRoot[dev]"

Write-Host "开发环境已就绪。可执行：qts"

