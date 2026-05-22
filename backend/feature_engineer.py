"""
Technical indicator feature engineering using OCR data + yfinance historical OHLCV.
Indicators computed manually (no pandas-ta dependency).
"""

from typing import Any, Optional

import numpy as np
import pandas as pd
from debug_logging import pipeline_log
from ocr_parser import validate_ma_value
from yfinance_setup import configure_yfinance_cache, safe_ticker_history

configure_yfinance_cache()


DEFAULT_TICKERS = [
    # Large caps
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "NVDA", "META", "SPY", "QQQ",
    # ETFs
    "DIA", "IWM",
    # Mid caps
    "SAIC", "PLTR", "COIN", "INTC",
    # Client tested stocks
    "OCGN", "SNDL", "SLXN", "GRAN",
    # Other volatile
    "MSTR", "GME", "CENN", "MULN",
    # Note: XSLL and PAPL may have limited
    # yfinance history — will skip if < 100 bars
]


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


def _vwap(high, low, close, volume):
    typical_price = (high + low + close) / 3
    return (typical_price * volume).cumsum() / volume.cumsum()


def _adx(high, low, close, length=14):
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    tr = _atr(high, low, close, length)
    plus_di = 100 * (_ema(plus_dm, length) / tr.replace(0, np.nan))
    minus_di = 100 * (_ema(minus_dm, length) / tr.replace(0, np.nan))
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return _ema(dx, length), plus_di, minus_di


def _cci(high, low, close, length=20):
    typical_price = (high + low + close) / 3
    ma = typical_price.rolling(length).mean()
    mad = typical_price.rolling(length).apply(
        lambda x: np.mean(np.abs(x - np.mean(x)))
    )
    return (typical_price - ma) / (0.015 * mad.replace(0, np.nan))


def _pivot_points(high: pd.Series, low: pd.Series,
                  close: pd.Series):
    """Calculate daily pivot points from previous bar's H/L/C."""
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)
    pp = (prev_high + prev_low + prev_close) / 3
    r1 = 2 * pp - prev_low
    s1 = 2 * pp - prev_high
    r2 = pp + (prev_high - prev_low)
    s2 = pp - (prev_high - prev_low)
    return pp, r1, s1, r2, s2


def _support_resistance(close, length=20):
    resistance = close.rolling(length).max()
    support = close.rolling(length).min()
    return resistance, support


def fetch_historical(ticker: str = "SPY", period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    symbol = ticker if ticker != "unknown" else "SPY"
    df = safe_ticker_history(symbol, period=period, interval=interval)
    if df is None or df.empty:
        df = safe_ticker_history("SPY", period=period, interval=interval)
    if df is None or df.empty:
        raise ValueError("Could not fetch historical data from yfinance")
    return df.rename(columns=str.lower)


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

    # VWAP
    out["vwap"] = _vwap(high, low, close, volume)

    # ADX
    adx, plus_di, minus_di = _adx(high, low, close)
    out["adx"] = adx
    out["plus_di"] = plus_di
    out["minus_di"] = minus_di

    # CCI
    out["cci"] = _cci(high, low, close)

    # Pivot Points
    pp, r1, s1, r2, s2 = _pivot_points(high, low, close)
    out["pivot"] = pp
    out["pivot_r1"] = r1
    out["pivot_s1"] = s1
    out["pivot_r2"] = r2
    out["pivot_s2"] = s2

    # Support / Resistance
    out["resistance"] = close.rolling(20).max()
    out["support"] = close.rolling(20).min()

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
    pipeline_log(f"[FEATURE] MA5 received: {ocr_data.get('ma5')}")
    pipeline_log(f"[FEATURE] ma5_from_ocr: {ocr_data.get('ma5_from_ocr')}")
    ticker = ocr_data.get("ticker", "unknown")
    if df is None:
        interval = "1d"
        if ocr_data.get("timeframe") in ("1min", "5min", "15min"):
            interval = "1h"
        df = fetch_historical(ticker, period="6mo", interval=interval)

    df = compute_indicators(df)
    latest = df.iloc[-1]
    ocr_price = ocr_data.get("price")
    if ocr_price is None or float(ocr_price or 0) == 0:
        price = float(latest["close"])
    else:
        price = float(ocr_price)

    def _use_ocr_or_hist(ocr_key: str, hist_key: str) -> float:
        ocr_val = ocr_data.get(ocr_key)
        if ocr_data.get(f"{ocr_key}_from_ocr") and ocr_val is not None:
            chosen = round(float(ocr_val), 4)
            if ocr_key == "ma5":
                pipeline_log(f"[FEATURE] MA5 using OCR (ma5_from_ocr=True): {chosen}")
            return chosen

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

        if ocr_val is not None:
            chosen = float(ocr_val)
            if ocr_key == "ma5":
                pipeline_log(
                    f"[FEATURE] MA5 using OCR (no flag): {chosen} "
                    f"(hist ema_5 was {hist_val})"
                )
            return chosen
        if hist_val is not None:
            chosen = float(hist_val)
            if ocr_key == "ma5":
                pipeline_log(f"[FEATURE] MA5 using yfinance/hist ema_5: {chosen}")
            return chosen
        chosen = float(price)
        if ocr_key == "ma5":
            pipeline_log(f"[FEATURE] MA5 fallback to price: {chosen}")
        return chosen

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

    if ocr_data.get("atr"):
        atr = float(ocr_data["atr"])
    else:
        atr = float(latest["atr"]) if pd.notna(latest.get("atr")) else price * 0.02
    # Scale ATR to OCR price when historical ticker differs in magnitude (e.g. penny stock vs SPY)
    if price > 0 and atr > price * 0.15:
        atr = price * 0.02
    if ocr_data.get("volume"):
        stable_vol = float(ocr_data["volume"])
        vol_sma = float(latest["vol_sma"]) if pd.notna(latest.get("vol_sma")) else stable_vol
        vol_ratio = stable_vol / vol_sma if vol_sma > 0 else 1.0
    else:
        vol_ratio = float(latest["vol_ratio"]) if pd.notna(latest.get("vol_ratio")) else 1.0

    # VWAP
    vwap = float(latest["vwap"]) if pd.notna(latest.get("vwap")) else price
    vwap_signal = "bullish" if price > vwap else "bearish"

    # ADX
    adx = float(latest["adx"]) if pd.notna(latest.get("adx")) else 20.0
    plus_di = float(latest["plus_di"]) if pd.notna(latest.get("plus_di")) else 20.0
    minus_di = float(latest["minus_di"]) if pd.notna(latest.get("minus_di")) else 20.0
    trend_strength = "strong" if adx > 25 else "weak"
    adx_signal = "bullish" if plus_di > minus_di else "bearish"

    # CCI
    cci = float(latest["cci"]) if pd.notna(latest.get("cci")) else 0.0
    cci_signal = (
        "overbought" if cci > 100
        else "oversold" if cci < -100
        else "neutral"
    )

    # Support / Resistance
    resistance = float(latest["resistance"]) if pd.notna(latest.get("resistance")) else price * 1.05
    support = float(latest["support"]) if pd.notna(latest.get("support")) else price * 0.95
    sr_signal = (
        "near_resistance" if price >= resistance * 0.98
        else "near_support" if price <= support * 1.02
        else "middle"
    )

    # Pivot Points
    pivot = float(latest["pivot"]) if pd.notna(
        latest.get("pivot")) else price
    pivot_r1 = float(latest["pivot_r1"]) if pd.notna(
        latest.get("pivot_r1")) else price * 1.01
    pivot_s1 = float(latest["pivot_s1"]) if pd.notna(
        latest.get("pivot_s1")) else price * 0.99
    pivot_r2 = float(latest["pivot_r2"]) if pd.notna(
        latest.get("pivot_r2")) else price * 1.02
    pivot_s2 = float(latest["pivot_s2"]) if pd.notna(
        latest.get("pivot_s2")) else price * 0.98

    # Pivot signal
    if price >= pivot_r2:
        pivot_signal = "above_r2"
        pivot_bias = "strong_bullish"
    elif price >= pivot_r1:
        pivot_signal = "above_r1"
        pivot_bias = "bullish"
    elif price >= pivot:
        pivot_signal = "above_pivot"
        pivot_bias = "bullish"
    elif price >= pivot_s1:
        pivot_signal = "below_pivot"
        pivot_bias = "bearish"
    elif price >= pivot_s2:
        pivot_signal = "below_s1"
        pivot_bias = "bearish"
    else:
        pivot_signal = "below_s2"
        pivot_bias = "strong_bearish"

    # Pivot score for ML
    pivot_score = (
        1.0 if pivot_bias in ("strong_bullish", "bullish")
        else 0.0
    )

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
    roc5_val = float(latest.get("roc_5", 0) or 0)
    momentum = (
        "strong" if abs(roc5_val) > 3
        else "moderate" if abs(roc5_val) > 1
        else "weak"
    )

    features = {
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
    features["vwap"] = vwap
    features["vwap_signal"] = vwap_signal
    features["adx"] = adx
    features["adx_signal"] = adx_signal
    features["trend_strength"] = trend_strength
    features["cci"] = cci
    features["cci_signal"] = cci_signal
    features["resistance"] = resistance
    features["support"] = support
    features["sr_signal"] = sr_signal
    features["bb_score"] = (
        1.0 if bb_pos in ("upper_band_breakout", "upper_half")
        else 0.0
    )
    features["pivot"] = pivot
    features["pivot_r1"] = pivot_r1
    features["pivot_s1"] = pivot_s1
    features["pivot_r2"] = pivot_r2
    features["pivot_s2"] = pivot_s2
    features["pivot_signal"] = pivot_signal
    features["pivot_bias"] = pivot_bias
    features["pivot_score"] = pivot_score
    pipeline_log(f"[FEATURE] MA5 final value used: {features.get('ma5')}")
    return features


def features_to_ml_array(features: dict[str, Any]) -> np.ndarray:
    price = features["price"]
    vwap = features.get("vwap", price)
    vwap_sig = 1.0 if price > vwap else 0.0

    adx = features.get("adx", 20)
    adx_sig = 1.0 if features.get("adx_signal") == "bullish" else 0.0
    adx_strength = 1.0 if features.get("trend_strength") == "strong" else 0.0

    cci = features.get("cci", 0)
    cci_norm = max(-2.0, min(2.0, cci / 100))

    resistance = features.get("resistance", price * 1.05)
    support = features.get("support", price * 0.95)
    sr_pos = (price - support) / (resistance - support + 1e-9)

    return np.array(
        [
            price,
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
            vwap_sig,
            adx_sig,
            adx_strength,
            cci_norm,
            sr_pos,
            features.get("bb_score", 0.5),
            features.get("pivot_score", 0.5),
        ],
        dtype=np.float32,
    ).reshape(1, -1)


FEATURE_NAMES = [
    "price", "ma5", "ma10", "ma20", "rsi", "macd_bullish",
    "atr", "vol_ratio", "ma_signal", "roc_5", "roc_20",
    "long_trend", "change_pct",
    "vwap_signal", "adx_signal", "adx_strength",
    "cci_norm", "sr_position", "bb_score", "pivot_score",
]
