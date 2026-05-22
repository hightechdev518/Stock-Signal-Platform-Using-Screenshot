"""
XGBoost + LightGBM ensemble for BUY / SELL / HOLD classification.
"""

import os
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
from sklearn.preprocessing import LabelEncoder

from debug_logging import pipeline_log
from paths import model_path


def _model_path() -> Path:
    """Resolve at call time so PyInstaller frozen runs use _MEIPASS/models."""
    return model_path()

# Label mapping: 0=SELL, 1=HOLD, 2=BUY
SIGNAL_LABELS = ["SELL", "HOLD", "BUY"]


class SignalEnsemble:
    """Ensemble of XGBoost and LightGBM classifiers."""

    def __init__(self):
        self.xgb_model = None
        self.lgb_model = None
        self.label_encoder = LabelEncoder()
        self.label_encoder.fit(SIGNAL_LABELS)
        self.is_trained = False

    def predict(self, X: np.ndarray) -> tuple[str, float]:
        """
        Predict signal and confidence (0-100).
        Uses weighted average of both models' probabilities.
        """
        if not self.is_trained or self.xgb_model is None:
            pipeline_log("[ML] WARNING: rule-based fallback (ensemble not loaded)")
            return self._rule_based_predict(X)

        xgb_proba = self.xgb_model.predict_proba(X)[0]
        lgb_proba = self.lgb_model.predict_proba(X)[0]
        avg_proba = (xgb_proba + lgb_proba) / 2
        class_idx = int(np.argmax(avg_proba))
        confidence = float(avg_proba[class_idx] * 100)
        signal = SIGNAL_LABELS[class_idx]
        return signal, round(confidence, 1)

    def _rule_based_predict(self, X: np.ndarray) -> tuple[str, float]:
        """Fallback when model not loaded."""
        if X.shape[1] < 5:
            return "HOLD", 50.0
        rsi = X[0, 4] if X.ndim == 2 else 50
        ma_sig = X[0, 8] if X.shape[1] > 8 else 0.5
        macd = X[0, 5] if X.shape[1] > 5 else 0.5
        score = 0
        if rsi < 35:
            score += 2
        elif rsi > 65:
            score -= 2
        if ma_sig > 0.7:
            score += 2
        elif ma_sig < 0.3:
            score -= 2
        if macd > 0.5:
            score += 1
        else:
            score -= 1
        if score >= 3:
            return "BUY", min(85.0, 60 + score * 5)
        if score <= -3:
            return "SELL", min(85.0, 60 + abs(score) * 5)
        return "HOLD", 55.0

    def save(self, path: Optional[Path] = None) -> None:
        path = path or _model_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "xgb": self.xgb_model,
                "lgb": self.lgb_model,
                "encoder": self.label_encoder,
                "is_trained": self.is_trained,
            },
            path,
        )

    def load(self, path: Optional[Path] = None) -> bool:
        path = path or _model_path()
        if not path.exists():
            return False
        try:
            data = joblib.load(path)
            self.xgb_model = data["xgb"]
            self.lgb_model = data["lgb"]
            self.label_encoder = data.get("encoder", self.label_encoder)
            self.is_trained = data.get("is_trained", True)
            return True
        except Exception as exc:
            pipeline_log(f"[ML] model load failed ({path}): {exc}")
            return False


_ensemble: Optional[SignalEnsemble] = None


def get_model() -> SignalEnsemble:
    global _ensemble
    if _ensemble is None:
        _ensemble = SignalEnsemble()
        path = _model_path()
        if _ensemble.load(path):
            pipeline_log(f"[ML] ensemble loaded from {path}")
        else:
            pipeline_log(f"[ML] ensemble NOT loaded from {path}")
    return _ensemble


def predict_signal(features_array: np.ndarray) -> dict[str, Any]:
    model = get_model()
    signal, confidence = model.predict(features_array)
    return {"signal": signal, "confidence": confidence}
