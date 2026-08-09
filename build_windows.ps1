param(
    [string]$Python = ".\.venv\Scripts\python.exe",
    [switch]$SkipInstall,
    [switch]$WithoutBundledSmallModel,
    [switch]$Zip
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not $IsWindows) {
    throw "Windows desktop builds must run on Windows."
}

$pythonPath = (Resolve-Path -LiteralPath $Python).Path

if (-not $SkipInstall) {
    & $pythonPath -m pip install -r requirements-desktop.txt
    if ($LASTEXITCODE -ne 0) { throw "Desktop dependency installation failed." }
}

& $pythonPath tools\make_icon.py --output-dir assets
if ($LASTEXITCODE -ne 0) { throw "Icon generation failed." }

$modelDestination = Join-Path $PSScriptRoot ".build_assets\models\small"
if ($WithoutBundledSmallModel) {
    if (Test-Path -LiteralPath $modelDestination) {
        Remove-Item -LiteralPath $modelDestination -Recurse -Force
    }
} else {
    & $pythonPath tools\prepare_bundled_model.py `
        --cache-dir ".cache\huggingface\hub" `
        --destination $modelDestination
    if ($LASTEXITCODE -ne 0) { throw "Small model preparation failed." }
}

& $pythonPath -m PyInstaller --noconfirm --clean depth_video.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$executable = Join-Path $PSScriptRoot "dist\DepthVideo\DepthVideo.exe"
if (-not (Test-Path -LiteralPath $executable)) {
    throw "Build completed without the expected executable: $executable"
}

Copy-Item -LiteralPath (Join-Path $PSScriptRoot "README.md") `
    -Destination (Split-Path -Parent $executable) -Force

if ($Zip) {
    $zipPath = Join-Path $PSScriptRoot "dist\DepthVideo-Windows-x64.zip"
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $PSScriptRoot "dist\DepthVideo") -DestinationPath $zipPath
    $checksumPath = "$zipPath.sha256"
    $checksum = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash
    "$checksum  DepthVideo-Windows-x64.zip" | Set-Content -LiteralPath $checksumPath -Encoding ascii
    Write-Host "Portable archive: $zipPath"
    Write-Host "SHA-256: $checksumPath"
}

Write-Host "Desktop application: $executable"
