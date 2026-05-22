# Bundle a portable Python runtime next to the venv (works on client PCs without dev Python).
$ErrorActionPreference = "Stop"
$backend = Resolve-Path (Join-Path $PSScriptRoot "..\..\backend")
$venv = Join-Path $backend "venv"
$scripts = Join-Path $venv "Scripts"
$runtime = Join-Path $backend "python-runtime"
$python = Join-Path $scripts "python.exe"

if (-not (Test-Path $python)) {
  Write-Error "venv not found at $venv. Run INSTALL.bat first."
}

$basePrefix = & $python -c "import sys; print(sys.base_prefix)"
Write-Host "Creating portable runtime from: $basePrefix"

if (Test-Path $runtime) {
  Remove-Item -Recurse -Force $runtime
}
New-Item -ItemType Directory -Path $runtime | Out-Null

# Standard library + extension modules (required when Python is not installed on the target PC).
Copy-Item (Join-Path $basePrefix "Lib") (Join-Path $runtime "Lib") -Recurse
$dllsDir = Join-Path $basePrefix "DLLs"
if (Test-Path $dllsDir) {
  Copy-Item $dllsDir (Join-Path $runtime "DLLs") -Recurse
  Write-Host "  Copied DLLs/"
}
foreach ($exe in @("python.exe", "pythonw.exe")) {
  $src = Join-Path $basePrefix $exe
  if (Test-Path $src) {
    Copy-Item $src $runtime -Force
    Write-Host "  Copied $exe to runtime"
  }
}

$dlls = @("python3.dll", "python314.dll", "python313.dll", "python312.dll", "vcruntime140.dll", "vcruntime140_1.dll")
foreach ($dll in $dlls) {
  $src = Join-Path $basePrefix $dll
  if (Test-Path $src) {
    Copy-Item $src $runtime -Force
    Copy-Item $src $scripts -Force
    Write-Host "  Copied $dll"
  }
}

Write-Host "Portable runtime ready at $runtime"
Write-Host "pyvenv.cfg home is set at app startup (electron.js)."
