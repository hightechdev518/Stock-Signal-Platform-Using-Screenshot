# -*- mode: python ; coding: utf-8 -*-
import glob
import hashlib
import os
import shutil

from PyInstaller.utils.hooks import collect_all

block_cipher = None

backend_dir = os.path.dirname(os.path.abspath(SPEC))
project_root = os.path.normpath(os.path.join(backend_dir, ".."))
model_pkl = os.path.join(project_root, "models", "model.pkl")

if not os.path.isfile(model_pkl):
    raise SystemExit(
        f"Missing {model_pkl}. Run: cd backend && python train_model.py"
    )

with open(model_pkl, "rb") as f:
    model_sha = hashlib.sha256(f.read()).hexdigest()[:16]
print(f"Bundling model.pkl (sha256 {model_sha}, mtime {os.path.getmtime(model_pkl):.0f})")

datas = []
for pkl in glob.glob(os.path.join(project_root, "models", "*.pkl")):
    datas.append((pkl, "models"))
for sample in glob.glob(os.path.join(project_root, "data", "sample_screenshots", "*")):
    if os.path.isfile(sample):
        datas.append((sample, "data/sample_screenshots"))

tesseract_dir = os.path.join(backend_dir, "tesseract")
if os.path.isdir(tesseract_dir):
    datas.append((tesseract_dir, "tesseract"))
else:
    raise SystemExit(
        "Missing backend/tesseract/. Run backend/scripts/bundle_tesseract.ps1 before building."
    )

binaries = []
hiddenimports_extra = []
for pkg in ("xgboost", "lightgbm", "sklearn"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports_extra += pkg_hidden
    print(f"collect_all({pkg}): {len(pkg_binaries)} binaries, {len(pkg_hidden)} hidden imports")

a = Analysis(
    ["main.py"],
    pathex=[backend_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "fastapi",
        "xgboost",
        "lightgbm",
        "sklearn",
        "sklearn.utils._typedefs",
        "sklearn.neighbors._partition_nodes",
        "cv2",
        "pytesseract",
        "PIL",
        "pandas",
        "numpy",
        "yfinance",
        "yfinance_setup",
        "platformdirs",
        "engineio.async_drivers",
        "multipart",
        "joblib",
        "joblib.externals.loky",
        "market_hours",
    ] + hiddenimports_extra,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="stock-signal-backend",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)

# Sidecar copy so frozen fallback (exe_dir/models) matches bundled weights.
dist_models = os.path.join(backend_dir, "dist", "models")
os.makedirs(dist_models, exist_ok=True)
shutil.copy2(model_pkl, os.path.join(dist_models, "model.pkl"))
print(f"Copied fresh model.pkl -> {dist_models}")
