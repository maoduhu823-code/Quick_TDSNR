$ErrorActionPreference = "Stop"

$appRoot = Split-Path -Parent $PSScriptRoot
$spec = Join-Path $appRoot "Quick_TDSNR.spec"
if (-not (Test-Path -LiteralPath $spec)) {
    throw "未找到 PyInstaller 配置：$spec"
}

Push-Location $appRoot
try {
    python -m PyInstaller --noconfirm --clean $spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller 构建失败，退出码：$LASTEXITCODE"
    }

    $releaseDir = Join-Path $appRoot "dist\Quick_TDSNR"
    $releaseExe = Join-Path $releaseDir "Quick_TDSNR.exe"
    if (-not (Test-Path -LiteralPath $releaseExe)) {
        throw "构建完成但未找到程序：$releaseExe"
    }

    Write-Host "正在验证打包程序的运行时依赖..."
    $runtimeCheck = Start-Process -FilePath $releaseExe `
        -ArgumentList "--runtime-check" `
        -Wait `
        -PassThru
    if ($runtimeCheck.ExitCode -ne 0) {
        throw "打包程序运行时依赖检查失败，退出码：$($runtimeCheck.ExitCode)"
    }

    Write-Host "运行时依赖检查通过。" -ForegroundColor Green
    Write-Host "发布目录：$releaseDir"
} finally {
    Pop-Location
}
