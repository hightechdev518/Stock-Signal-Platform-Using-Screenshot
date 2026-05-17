"""
Technical indicator feature engineering using OCR data + yfinance historical OHLCV.
Indicators computed manually (no pandas-ta dependency).
"""

from typing import Any, Optional

import numpy as np
import pandas as pd
import yfinance as yf

from ocr_parser import validate_ma_value


DEFAULT_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "SPY", "QQQ"]


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def _rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(length).mean()
    loss = (-delta.clip(upper=0)).rolling(length).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    macd_line = ema12 - ema26
    signal = _ema(macd_line, 9)
    hist = macd_line - signal
    return macd_line, signal, hist


def _bbands(close: pd.Series, length: int = 20, std: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = _sma(close, length)
    rolling_std = close.rolling(length).std()
    upper = mid + std * rolling_std
    lower = mid - std * rolling_std
    return upper, mid, lower


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(length).mean()


def fetch_historical(ticker: str = "SPY", period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    try:
        t = yf.Ticker(ticker if ticker != "unknown" else "SPY")
        df = t.history(period=period, interval=interval)
        if df.empty:
            t = yf.Ticker("SPY")
            df = t.history(period=period, interval=interval)
    except Exception:
        t = yf.Ticker("SPY")
        df = t.history(period=period, interval=interval)
    df = df.rename(columns=str.lower)
    return df


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    close = out["close"]
    high = out["high"]
    low = out["low"]
    volume = out["volume"]

    out["rsi"] = _rsi(close)
    macd_line, macd_sig, macd_hist = _macd(close)
    out["macd"] = macd_line
    out["macd_signal"] = macd_sig
    out["macd_hist"] = macd_hist
    bb_u, bb_m, bb_l = _bbands(close)
    out["bb_upper"] = bb_u
    out["bb_mid"] = bb_m
    out["bb_lower"] = bb_l
    out["ema_5"] = _ema(close, 5)
    out["ema_10"] = _ema(close, 10)
    out["ema_20"] = _ema(close, 20)
    out["sma_50"] = _sma(close, 50)
    out["sma_200"] = _sma(close, 200)
    out["atr"] = _atr(high, low, close)
    out["vol_sma"] = volume.rolling(20).mean()
    out["vol_ratio"] = volume / out["vol_sma"].replace(0, np.nan)
    out["roc_5"] = close.pct_change(5) * 100
    out["roc_20"] = close.pct_change(20) * 100
    return out


def ma_crossover_signal(ma5: float, ma10: float, ma20: float, price: float) -> str:
    if ma5 and ma10 and ma20 and price:
        price = float(price)
        ma5 = float(ma5)
        ma10 = float(ma10)
        ma20 = float(ma20)

        if price > ma5 and price > ma10 and price > ma20:
            return "bullish"
        if price < ma5 and price < ma10 and price < ma20:
            return "bearish"
    return "neutral"


def classify_volume(vol_ratio: float) -> str:
    """Classify volume vs 20-period average using demo-calibrated thresholds."""
    if vol_ratio > 3.0:
        return f"Very High - {vol_ratio:.1f}x average"
    if vol_ratio > 2.0:
        return f"High - {vol_ratio:.1f}x average"
    if vol_ratio > 1.5:
        return "Above Average"
    if vol_ratio >= 1.0:
        return "Normal volume"
    if vol_ratio < 0.8:
        return "Low volume"
    return "Normal volume"


def resolve_volume_ratio(
    vol_ratio: float,
    ocr_data: dict[str, Any],
    ma_signal: str,
    change_pct: float,
) -> float:
    """
    Adjust volume ratio using OCR hints and breakout context.
    Ensures client-style bullish volume spikes are detected.
    """
    vol_text = str(ocr_data.get("volume", "")).lower()
    if ocr_data.get("volume_spike") or "high" in vol_text or "spike" in vol_text:
        vol_ratio = max(vol_ratio, 2.5)
    if abs(change_pct or 0) >= 15 and ma_signal == "bullish":
        vol_ratio = max(vol_ratio, 2.5)
    if abs(change_pct or 0) >= 20:
        vol_ratio = max(vol_ratio, 3.0)
    return vol_ratio


def bollinger_position(close: float, upper: float, mid: float, lower: float) -> str:
    if pd.isna(upper) or pd.isna(lower):
        return "unknown"
    if close >= upper:
        return "upper_band_breakout"
    if close <= lower:
        return "lower_band"
    if close > mid:
        return "upper_half"
    return "lower_half"


def build_feature_vector(ocr_data: dict[str, Any], df: Optional[pd.DataFrame] = None) -> dict[str, Any]:
    ticker = ocr_data.get("ticker", "unknown")
    if df is None:
        interval = "1d"
        if ocr_data.get("timeframe") in ("1min", "5min", "15min"):
            interval = "1h"
        df = fetch_historical(ticker, period="6mo", interval=interval)

    df = compute_indicators(df)
    latest = df.iloc[-1]
    price = ocr_data.get("price") or float(latest["close"])

    def _use_ocr_or_hist(ocr_key: str, hist_key: str) -> float:
        ocr_val = ocr_data.get(ocr_key)
        if ocr_val is not None:
            ocr_val = validate_ma_value(ocr_val, price)
        hist_raw = float(latest.get(hist_key, price) or price)
        hist_val = validate_ma_value(hist_raw, price)

        # For penny/low-price stocks, never use hist if it's orders of magnitude off
        if price and 0.1 <= price <= 10.0:
            if hist_val is None or (hist_val and hist_val > price * 5):
                hist_val = None
            if ocr_val is not None:
                return float(ocr_val)

        if ocr_val is not None and hist_val is not None:
            if price > 0 and abs(ocr_val - price) / price < abs(hist_val - price) / max(price, 1e-9):
                return float(ocr_val)
            if abs(hist_val - price) / max(price, 1e-9) > 0.5:
                return float(ocr_val)
        if ocr_val is not None:
            return float(ocr_val)
        if hist_val is not None:
            return float(hist_val)
        return float(price)

    ma5 = _use_ocr_or_hist("ma5", "ema_5")
    ma10 = _use_ocr_or_hist("ma10", "ema_10")
    ma20 = _use_ocr_or_hist("ma20", "ema_20")

    rsi = float(ocr_data["rsi"]) if ocr_data.get("rsi_from_ocr") and ocr_data.get("rsi") is not None else None
    rsi_for_ml = rsi if rsi is not None else 50.0

    macd_val = float(latest["macd"]) if pd.notna(latest.get("macd")) else 0
    macd_sig = float(latest["macd_signal"]) if pd.notna(latest.get("macd_signal")) else 0
    if ocr_data.get("macd_from_ocr") and ocr_data.get("macd_cross"):
        macd_cross = ocr_data["macd_cross"]
    elif ocr_data.get("macd_from_ocr") and ocr_data.get("macd_bullish"):
        macd_cross = "bullish"
    elif ocr_data.get("macd_from_ocr") and ocr_data.get("macd_bearish"):
        macd_cross = "bearish"
    else:
        macd_cross = None
    macd_for_ml = macd_cross or "neutral"

    bb_upper = latest.get("bb_upper", np.nan)
    bb_mid = latest.get("bb_mid", np.nan)
    bb_lower = latest.get("bb_lower", np.nan)
    bb_pos = bollinger_position(price, bb_upper, bb_mid, bb_lower)

    atr = float(latest["atr"]) if pd.notna(latest.get("atr")) else price * 0.02
    # Scale ATR to OCR price when historical ticker differs in magnitude (e.g. penny stock vs SPY)
    if price > 0 and atr > price * 0.15:
        atr = price * 0.02
    vol_ratio = float(latest["vol_ratio"]) if pd.notna(latest.get("vol_ratio")) else 1.0
    sma50 = float(latest["sma_50"]) if pd.notna(latest.get("sma_50")) else price
    sma200 = float(latest["sma_200"]) if pd.notna(latest.get("sma_200")) else price

    ma_signal = ma_crossover_signal(ma5, ma10, ma20, price)
    vol_ratio = resolve_volume_ratio(
        vol_ratio,
        ocr_data,
        ma_signal,
        ocr_data.get("change_pct", 0) or 0,
    )
    volume_label = classify_volume(vol_ratio)
    rsi_zone = None if rsi is None else ("overbought" if rsi > 70 else ("oversold" if rsi < 30 else "neutral"))
    long_trend = "uptrend" if sma50 > sma200 else "downtrend"
    momentum = "strong" if abs(ocr_data.get("change_pct") or 0) > 5 else "moderate"

    return {
        "price": price,
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "rsi": rsi,
        "rsi_for_ml": rsi_for_ml,
        "rsi_zone": rsi_zone,
        "macd_cross": macd_cross,
        "macd_for_ml": macd_for_ml,
        "macd_val": macd_val,
        "macd_sig": macd_sig,
        "bollinger_pos": bb_pos,
        "atr": atr,
        "vol_ratio": vol_ratio,
        "volume_label": volume_label,
        "ma_signal": ma_signal,
        "long_trend": long_trend,
        "momentum": momentum,
        "roc_5": float(latest.get("roc_5", 0) or 0),
        "roc_20": float(latest.get("roc_20", 0) or 0),
        "sma50": sma50,
        "sma200": sma200,
        "change_pct": ocr_data.get("change_pct", 0),
        "timeframe": ocr_data.get("timeframe", "1min"),
    }


def features_to_ml_array(features: dict[str, Any]) -> np.ndarray:
    return np.array(
        [
            features["price"],
            features["ma5"],
            features["ma10"],
            features["ma20"],
            features.get("rsi_for_ml", 50.0),
            1.0 if features.get("macd_for_ml") == "bullish" else (0.0 if features.get("macd_for_ml") == "bearish" else 0.5),
            features["atr"],
            features["vol_ratio"],
            1.0 if features["ma_signal"] == "bullish" else (0.0 if features["ma_signal"] == "bearish" else 0.5),
            features["roc_5"],
            features["roc_20"],
            1.0 if features["long_trend"] == "uptrend" else 0.0,
            features.get("change_pct", 0) or 0,
        ],
        dtype=np.float32,
    ).reshape(1, -1)


FEATURE_NAMES = [
    "price", "ma5", "ma10", "ma20", "rsi", "macd_bullish",
    "atr", "vol_ratio", "ma_signal", "roc_5", "roc_20", "long_trend", "change_pct",
]
