"""Resolve data paths for dev, venv, and PyInstaller-frozen runs."""

import os
import sys
from pathlib import Path


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def models_dir() -> Path:
    if getattr(sys, "frozen", False):
        bundled = resource_root() / "models"
        bundled_pkl = bundled / "model.pkl"
        if bundled_pkl.is_file():
            return bundled
        env_dir = os.environ.get("STOCK_SIGNAL_MODELS_DIR")
        if env_dir:
            path = Path(env_dir)
            path.mkdir(parents=True, exist_ok=True)
            return path
        sidecar = Path(sys.executable).resolve().parent / "models"
        if (sidecar / "model.pkl").is_file():
            return sidecar
        path = sidecar
        path.mkdir(parents=True, exist_ok=True)
        return path
    return Path(__file__).resolve().parent.parent / "models"


def model_path() -> Path:
    return models_dir() / "model.pkl"
