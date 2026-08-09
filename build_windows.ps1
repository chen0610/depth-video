param(
    [string]$Python = ".\.venv\Scripts\python.exe",
    [ValidateSet("cpu", "cu126", "cu130")]
    [string]$TorchVariant = "cpu",
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
    $torchIndexUrl = "https://download.pytorch.org/whl/$TorchVariant"
    & $pythonPath -m pip install --upgrade --force-reinstall `
        torch torchvision --index-url $torchIndexUrl
    if ($LASTEXITCODE -ne 0) { throw "PyTorch $TorchVariant installation failed." }

    & $pythonPath -m pip install -r requirements-desktop.txt
    if ($LASTEXITCODE -ne 0) { throw "Desktop dependency installation failed." }
} else {
    Write-Warning "Dependency installation skipped; TorchVariant '$TorchVariant' is not enforced."
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

$archiveVariant = $TorchVariant.ToUpperInvariant()
$variantDistDir = Join-Path $PSScriptRoot "dist\$archiveVariant"

& $pythonPath -m PyInstaller --noconfirm --clean `
    --distpath $variantDistDir depth_video.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$bundleDir = Join-Path $variantDistDir "DepthVideo"
$executable = Join-Path $bundleDir "DepthVideo.exe"
if (-not (Test-Path -LiteralPath $executable)) {
    throw "Build completed without the expected executable: $executable"
}

Copy-Item -LiteralPath (Join-Path $PSScriptRoot "README.md") `
    -Destination (Split-Path -Parent $executable) -Force

if ($Zip) {
    $archiveName = "DepthVideo-Windows-x64-$archiveVariant.zip"
    $zipPath = Join-Path $PSScriptRoot "dist\$archiveName"
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path $bundleDir -DestinationPath $zipPath
    $checksumPath = "$zipPath.sha256"
    $checksum = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash
    "$checksum  $archiveName" | Set-Content -LiteralPath $checksumPath -Encoding ascii
    Write-Host "Portable archive: $zipPath"
    Write-Host "SHA-256: $checksumPath"
}

Write-Host "PyTorch variant: $TorchVariant"
Write-Host "Desktop application: $executable"
