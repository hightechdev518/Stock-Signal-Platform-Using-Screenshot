# Copy Tesseract OCR + tessdata into backend/tesseract for PyInstaller bundling.
# Requires Tesseract installed on build machine (UB Mannheim Windows build):
# https://github.com/UB-Mannheim/tesseract/wiki

$ErrorActionPreference = "Stop"
$src = "C:\Program Files\Tesseract-OCR"
$dest = Join-Path $PSScriptRoot "..\tesseract" | Resolve-Path -ErrorAction SilentlyContinue
if (-not $dest) {
    $dest = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path + "\tesseract"
}

if (-not (Test-Path "$src\tesseract.exe")) {
    Write-Error "Install Tesseract from https://github.com/UB-Mannheim/tesseract/wiki then re-run this script."
}

if (Test-Path $dest) {
    Remove-Item $dest -Recurse -Force
}
New-Item -ItemType Directory -Path $dest -Force | Out-Null

robocopy $src $dest /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
if (-not (Test-Path "$dest\tesseract.exe")) {
    Write-Error "Copy failed — tesseract.exe not found in $dest"
}
if (-not (Test-Path "$dest\tessdata\eng.traineddata")) {
    Write-Error "Copy failed — tessdata/eng.traineddata missing"
}

$mb = [math]::Round((Get-ChildItem $dest -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 1)
Write-Host "Bundled Tesseract to $dest ($mb MB)"
