"""
Train XGBoost + LightGBM ensemble on yfinance historical data.
Saves model to ../models/model.pkl
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).parent))

from backtest import generate_labels, row_to_features
from feature_engineer import DEFAULT_TICKERS, compute_indicators, fetch_historical
from ml_model import MODEL_PATH, SignalEnsemble


def build_training_dataset(tickers: list[str] | None = None) -> tuple[np.ndarray, np.ndarray]:
    tickers = tickers or DEFAULT_TICKERS
    X_list, y_list = [], []

    for ticker in tickers:
        print(f"Fetching {ticker}...")
        df = fetch_historical(ticker, period="2y", interval="1d")
        if len(df) < 100:
            continue
        df = compute_indicators(df)
        df = df.dropna()
        labels = generate_labels(df)

        for i in range(50, len(df) - 6):
            row = df.iloc[i]
            label = labels.iloc[i]
            if pd.isna(label):
                continue
            X_list.append(row_to_features(row, df.iloc[:i]))
            y_list.append(label)

    X = np.vstack(X_list)
    y = np.array(y_list)
    print(f"Dataset: {X.shape[0]} samples, {X.shape[1]} features")
    return X, y


def train_and_save():
    X, y = build_training_dataset()
    label_map = {"SELL": 0, "HOLD": 1, "BUY": 2}
    y_enc = np.array([label_map[l] for l in y])

    X_train, X_test, y_train, y_test = train_test_split(X, y_enc, test_size=0.2, random_state=42)

    xgb = XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric="mlogloss",
    )
    lgb = LGBMClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbose=-1,
    )

    print("Training XGBoost...")
    xgb.fit(X_train, y_train)
    print("Training LightGBM...")
    lgb.fit(X_train, y_train)

    xgb_acc = (xgb.predict(X_test) == y_test).mean()
    lgb_acc = (lgb.predict(X_test) == y_test).mean()
    print(f"XGBoost test accuracy: {xgb_acc*100:.1f}%")
    print(f"LightGBM test accuracy: {lgb_acc*100:.1f}%")

    ensemble = SignalEnsemble()
    ensemble.xgb_model = xgb
    ensemble.lgb_model = lgb
    ensemble.is_trained = True
    ensemble.save(MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")

    from backtest import run_backtest

    bt = run_backtest()
    print(bt.get("summary", bt))


if __name__ == "__main__":
    train_and_save()
