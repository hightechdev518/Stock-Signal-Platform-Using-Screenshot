"""
Trading signal engine: entry, TP, SL, forecasts, risk assessment, full JSON output.
"""

from datetime import datetime, timedelta
import re
from typing import Any, Optional

import pandas as pd

from debug_logging import pipeline_log, setup_debug_logging
from feature_engineer import build_feature_vector, classify_volume, compute_indicators, features_to_ml_array
from market_hours import calculate_trading_time, get_market_status, is_market_open_now
from ml_model import predict_signal
from yfinance_setup import configure_yfinance_cache, safe_ticker_history

setup_debug_logging()
configure_yfinance_cache()


def format_ma_trend(features: dict[str, Any]) -> str:
    price = float(features["price"])
    ma5 = float(features["ma5"])
    ma10 = float(features["ma10"])
    ma20 = float(features["ma20"])

    if price > ma5 and price > ma10 and price > ma20 and ma5 > ma10 > ma20:
        return "Price above all MAs - Strong bullish"
    if price > ma5 and price > ma10 and price > ma20:
        return "Price above all MAs - Bullish"
    if price < ma5 and price < ma10 and price < ma20 and ma5 < ma10 < ma20:
        return "Price below all MAs - Strong bearish"
    if price < ma5 and price < ma10 and price < ma20:
        return "Price below all MAs - Bearish"
    if price > ma20:
        return "Price above MA20 - Moderately bullish"
    return "Mixed MA alignment - Neutral"


def format_volume(features: dict[str, Any]) -> str:
    return features.get("volume_label") or classify_volume(features.get("vol_ratio", 1.0))


def format_bollinger(pos: str) -> str:
    mapping = {
        "upper_band_breakout": "Upper band breakout",
        "lower_band": "Lower band touch",
        "upper_half": "Upper half of bands",
        "lower_half": "Lower half of bands",
    }
    return mapping.get(pos, pos.replace("_", " ").title())


def format_macd(cross: str | None, ocr_data: dict[str, Any] | None = None) -> str | None:
    if not ocr_data or not ocr_data.get("macd_from_ocr"):
        return None
    if ocr_data.get("macd_bullish"):
        return "Bullish crossover"
    if ocr_data.get("macd_bearish"):
        return "Bearish crossover"
    if cross is None:
        return None
    return f"{cross.capitalize()} crossover"


def compute_levels(price: float, atr: float, signal: str) -> tuple[float, float, float, str]:
    """Entry, take profit, stop loss based on ATR multiples."""
    if signal == "BUY":
        entry = price
        tp = round(price + atr * 2.5, 4)
        sl = round(price - atr * 1.2, 4)
    elif signal == "SELL":
        entry = price
        tp = round(price - atr * 2.5, 4)
        sl = round(price + atr * 1.2, 4)
    else:
        entry = price
        tp = round(price + atr * 1.5, 4)
        sl = round(price - atr * 1.0, 4)

    risk = abs(entry - sl)
    reward = abs(tp - entry)
    rr = f"{reward / risk:.1f}:1" if risk > 0 else "N/A"
    return entry, tp, sl, rr


def _forecast_target(price: float, atr: float, signal: str, multiplier: float) -> float:
    if signal == "BUY":
        return round(price + atr * multiplier, 4)
    if signal == "SELL":
        return round(price - atr * multiplier, 4)
    return round(price + atr * multiplier * 0.5, 4)


def _format_clock(value: datetime) -> str:
    hour = value.strftime("%I").lstrip("0") or "12"
    return f"{hour}:{value.strftime('%M')} {value.strftime('%p')}"


_TIMING_DISCLAIMER = "(estimate only)"


def volume_timing_factor(vol_ratio: float) -> float:
    """Scale time-to-target by relative volume (higher volume = faster move)."""
    vol = float(vol_ratio or 1.0)
    if vol > 3.0:
        return 0.4
    if vol > 2.0:
        return 0.6
    if vol > 1.0:
        return 0.8
    if vol >= 0.5:
        return 1.0
    return 1.5


def estimate_days_to_target(
    current_price: float,
    target_price: float,
    daily_atr: float,
    vol_ratio: float,
) -> float | None:
    """Days to reach target using ATR as expected daily range, adjusted by volume."""
    if not daily_atr or daily_atr <= 0 or current_price <= 0:
        return None
    distance = abs(float(target_price) - float(current_price))
    if distance == 0:
        return 0.0
    base_days = distance / float(daily_atr)
    return base_days * volume_timing_factor(vol_ratio)


def format_timing_estimate(estimated_days: float | None, now: datetime) -> str:
    """Calendar date/time using market-hours-aware trading time (includes disclaimer)."""
    if estimated_days is None:
        return f"Timing unclear {_TIMING_DISCLAIMER}"
    if estimated_days > 180:
        return f"Long-term {_TIMING_DISCLAIMER}"

    estimated_hours = max(1.0, float(estimated_days) * 24)
    estimated_time = calculate_trading_time(estimated_hours, now)
    delta_days = (estimated_time.date() - now.date()).days
    date_str = f"{estimated_time.strftime('%b')} {estimated_time.day}, {estimated_time.year}"

    if delta_days == 0:
        return f"~Today {_format_clock(estimated_time)} {_TIMING_DISCLAIMER}"
    if delta_days == 1:
        return f"~Tomorrow {_format_clock(estimated_time)} {_TIMING_DISCLAIMER}"
    if delta_days <= 7:
        return f"~{date_str} {_format_clock(estimated_time)} {_TIMING_DISCLAIMER}"
    return f"~{date_str} {_TIMING_DISCLAIMER}"


def timing_labels_for_target(
    current_price: float,
    target_price: float,
    daily_atr: float,
    vol_ratio: float,
    now: datetime,
) -> tuple[str, str]:
    """Return (timeframe, predicted_by) for a forecast target."""
    days = estimate_days_to_target(current_price, target_price, daily_atr, vol_ratio)
    label = format_timing_estimate(days, now)
    return label, label


def build_forecasts(features: dict[str, Any], signal: str, now: datetime) -> dict[str, dict]:
    """Build short, medium, long (weeks), and monthly forecasts using ATR targets."""
    price = features["price"]
    atr = features["atr"]

    if signal == "BUY":
        directions = {
            "same_day": "Bullish",
            "same_week": "Bullish",
            "short": "Bullish",
            "medium": "Uptrend",
            "long": "Uptrend",
            "monthly": "Bullish",
        }
        notes = {
            "same_day": "Intraday target based on current momentum",
            "same_week": "Weekly target based on ATR projection",
            "short": (
                "Strong momentum breakout above all MAs"
                if features["ma_signal"] == "bullish"
                else "Bullish bias with MA support"
            ),
            "medium": "Price consolidating above MA20 support",
            "long": "Strong bullish trend continuation expected",
            "monthly": "Long-term accumulation zone, strong upside potential",
        }
    elif signal == "SELL":
        directions = {
            "same_day": "Bearish",
            "same_week": "Bearish",
            "short": "Bearish",
            "medium": "Downtrend",
            "long": "Downtrend",
            "monthly": "Bearish",
        }
        notes = {
            "same_day": "Intraday target based on current momentum",
            "same_week": "Weekly target based on ATR projection",
            "short": "Bearish pressure below key moving averages",
            "medium": "Selling pressure intensifying over coming sessions",
            "long": "Extended downtrend likely to continue",
            "monthly": "Long-term distribution pattern forming",
        }
    else:
        directions = {
            "same_day": "Neutral",
            "same_week": "Neutral",
            "short": "Neutral",
            "medium": "Sideways",
            "long": "Sideways",
            "monthly": "Neutral",
        }
        notes = {
            "same_day": "Intraday target based on current momentum",
            "same_week": "Weekly target based on ATR projection",
            "short": "Consolidation - wait for clearer breakout",
            "medium": "Range-bound trading expected",
            "long": "No clear directional bias on weekly chart",
            "monthly": "Long-term trend undecided",
        }

    vol_ratio = float(features.get("vol_ratio") or 1.0)
    horizons = (
        ("same_day_forecast", "same_day", 0.3),
        ("same_week_forecast", "same_week", 0.8),
        ("short_term_forecast", "short", 1.5),
        ("medium_term_forecast", "medium", 3.0),
        ("long_term_forecast", "long", 6.0),
        ("monthly_forecast", "monthly", 10.0),
    )
    forecasts: dict[str, dict] = {}
    for key, direction_key, mult in horizons:
        target = _forecast_target(price, atr, signal, mult)
        timeframe, predicted_by = timing_labels_for_target(
            price, target, atr, vol_ratio, now
        )
        forecasts[key] = {
            "direction": directions[direction_key],
            "target": target,
            "timeframe": timeframe,
            "predicted_by": predicted_by,
            "note": notes[direction_key],
        }
    return forecasts


def build_forecasts_summary(forecasts: dict[str, dict]) -> dict[str, dict]:
    """Compact forecast summary for API consumers."""
    mapping = {
        "same_day": "same_day_forecast",
        "same_week": "same_week_forecast",
        "short_term": "short_term_forecast",
        "medium_term": "medium_term_forecast",
        "long_term": "long_term_forecast",
        "monthly": "monthly_forecast",
    }
    during_market = is_market_open_now()
    summary: dict[str, dict] = {}
    for key, forecast_key in mapping.items():
        fc = forecasts.get(forecast_key, {})
        entry: dict[str, Any] = {
            "target": fc.get("target"),
            "estimate": fc.get("predicted_by"),
        }
        if key == "short_term":
            entry["during_market"] = during_market
        summary[key] = entry
    return summary


def risk_assessment(features: dict[str, Any]) -> str:
    atr_pct = (features["atr"] / features["price"]) * 100 if features["price"] else 0
    vol = features["vol_ratio"]
    if atr_pct > 3 or vol > 2.5:
        return "Medium-High volatility detected"
    if atr_pct > 1.5:
        return "Moderate volatility"
    return "Low volatility - stable conditions"


def build_analysis_signals(indicators: dict[str, Any], risk: str) -> list[dict[str, str]]:
    """Build bullish/warning signal list matching the analysis summary UI."""
    signals: list[dict[str, str]] = []

    ma_trend = str(indicators.get("MA_trend") or "")
    ma_lower = ma_trend.lower()
    if "bullish" in ma_lower or "above" in ma_lower:
        signals.append({"type": "bullish", "text": ma_trend})
    elif "bearish" in ma_lower or "below" in ma_lower:
        signals.append({"type": "warning", "text": ma_trend})
    elif ma_trend:
        signals.append({"type": "warning", "text": ma_trend})

    vol = str(indicators.get("volume") or "")
    if re.search(r"very high|high|3x|2x", vol, re.I):
        signals.append({"type": "bullish", "text": f"High volume breakout ({vol})"})
    elif vol:
        signals.append({"type": "warning", "text": f"Volume: {vol}"})

    rsi = indicators.get("RSI")
    if rsi is not None:
        if rsi > 70:
            signals.append({"type": "warning", "text": f"RSI: {rsi} (overbought)"})
        elif rsi < 30:
            signals.append({"type": "bullish", "text": f"RSI: {rsi} (oversold - potential bounce)"})
        else:
            signals.append({"type": "bullish", "text": f"RSI: {rsi} (neutral - not overbought)"})

    macd = indicators.get("MACD")
    if macd is not None and macd != "":
        macd_text = str(macd)
        if re.search(r"bull", macd_text, re.I):
            signals.append({"type": "bullish", "text": f"MACD: {macd_text}"})
        else:
            signals.append({"type": "warning", "text": f"MACD: {macd_text}"})

    mom = str(indicators.get("momentum") or "")
    if re.search(r"strong", mom, re.I):
        signals.append({"type": "bullish", "text": f"Momentum: {mom}"})
    elif mom:
        signals.append({"type": "warning", "text": f"Momentum: {mom}"})

    bb = str(indicators.get("bollinger") or "")
    if re.search(r"upper|breakout", bb, re.I):
        signals.append({"type": "bullish", "text": f"Bollinger: {bb}"})
    elif bb:
        signals.append({"type": "warning", "text": f"Bollinger: {bb}"})

    if risk:
        is_high = bool(re.search(r"high|medium-high", risk, re.I))
        signals.append({"type": "warning" if is_high else "bullish", "text": risk})

    # VWAP
    vwap_signal = str(indicators.get("vwap_signal") or "")
    if vwap_signal == "bullish":
        signals.append({"type": "bullish",
                        "text": "Price above VWAP - institutional support"})
    elif vwap_signal == "bearish":
        signals.append({"type": "warning",
                        "text": "Price below VWAP - selling pressure"})

    adx_signal = str(indicators.get("adx_signal") or "")
    trend_strength = str(indicators.get("trend_strength") or "")
    if adx_signal == "bullish" and trend_strength == "strong":
        signals.append({"type": "bullish",
                        "text": f"ADX: Strong bullish trend confirmed"})
    elif adx_signal == "bearish" and trend_strength == "strong":
        signals.append({"type": "warning",
                        "text": f"ADX: Strong bearish trend confirmed"})

    cci_signal = str(indicators.get("cci_signal") or "")
    if cci_signal == "oversold":
        signals.append({"type": "bullish",
                        "text": "CCI: Oversold - potential reversal"})
    elif cci_signal == "overbought":
        signals.append({"type": "warning",
                        "text": "CCI: Overbought - potential pullback"})

    sr_signal = str(indicators.get("sr_signal") or "")
    if sr_signal == "near_support":
        signals.append({"type": "bullish",
                        "text": "Price near key support level"})
    elif sr_signal == "near_resistance":
        signals.append({"type": "warning",
                        "text": "Price near key resistance level"})

    # Pivot Points
    pivot_bias = str(indicators.get("pivot_bias") or "")
    pivot_signal = str(indicators.get("pivot_signal") or "")
    pivot_r1 = indicators.get("pivot_r1")
    pivot_s1 = indicators.get("pivot_s1")

    if pivot_bias == "strong_bullish":
        signals.append({"type": "bullish",
            "text": f"Price above R2 pivot — very strong bullish"})
    elif pivot_bias == "bullish" and pivot_signal == "above_r1":
        signals.append({"type": "bullish",
            "text": f"Price above R1 pivot ${pivot_r1:.2f} — bullish"})
    elif pivot_bias == "bullish":
        signals.append({"type": "bullish",
            "text": f"Price above pivot point — bullish bias"})
    elif pivot_bias == "strong_bearish":
        signals.append({"type": "warning",
            "text": f"Price below S2 pivot — very strong bearish"})
    elif pivot_bias == "bearish" and pivot_signal == "below_s1":
        signals.append({"type": "warning",
            "text": f"Price below S1 pivot ${pivot_s1:.2f} — bearish"})
    elif pivot_bias == "bearish":
        signals.append({"type": "warning",
            "text": f"Price below pivot point — bearish bias"})

    return signals


def build_conclusion(
    signals: list[dict[str, str]],
    signal: str = "HOLD",
    confidence: float = 50.0,
) -> str:
    """Derive overall bias and actionable message from signals + ML output."""
    bullish_count = len([s for s in signals if s["type"] == "bullish"])
    warning_count = len([s for s in signals if s["type"] == "warning"])
    total = bullish_count + warning_count
    strength_ratio = bullish_count / total if total > 0 else 0

    if bullish_count > warning_count:
        bias = "BULLISH"
    elif bullish_count == warning_count:
        bias = "NEUTRAL"
    else:
        bias = "BEARISH"

    if signal == "BUY" and bias == "BULLISH":
        if strength_ratio >= 0.75:
            action = "Strong entry signal — ML and indicators fully agree. Consider entering with normal position size."
        elif strength_ratio >= 0.60:
            action = "Moderate entry signal — ML and indicators agree. Consider entering with strict risk management."
        else:
            action = "Weak entry signal — ML says BUY but indicators only partially confirm. Enter with reduced position."
    elif signal == "BUY" and bias == "NEUTRAL":
        action = "ML says BUY but indicators show no clear direction. Wait for confirmation before entering."
    elif signal == "BUY" and bias == "BEARISH":
        action = "ML says BUY but indicators are bearish. Wait for indicator confirmation. High risk of false signal."
    elif signal == "SELL" and bias == "BEARISH":
        if strength_ratio <= 0.25:
            action = "Strong exit signal — ML and indicators fully agree bearish. Consider reducing positions immediately."
        else:
            action = "Moderate exit signal — ML and indicators agree bearish. Reduce exposure cautiously."
    elif signal == "SELL" and bias == "BULLISH":
        action = "ML says SELL but indicators are bullish. Wait for bearish confirmation before exiting."
    elif signal == "HOLD" and bias == "BULLISH":
        action = "Bullish bias but ML is not confident enough. Wait for stronger BUY signal before entering."
    elif signal == "HOLD" and bias == "BEARISH":
        action = "Bearish bias and ML uncertain. Avoid new entries — protect capital."
    else:
        action = "Mixed signals — no clear direction. Stay out until market shows clear setup."

    return (
        f"Based on {bullish_count} bullish signals and {warning_count} warnings, "
        f"the overall bias is {bias}. {action}"
    )


def apply_signal_overrides(features: dict[str, Any], signal: str, confidence: float) -> tuple[str, float]:
    """Use clear screenshot-derived setups to correct signal direction; keep ML confidence."""
    change_pct = features.get("change_pct") or 0
    ma_signal = features.get("ma_signal")
    volume = features.get("vol_ratio", 1.0)
    confidence = float(confidence)

    if ma_signal == "bearish" and change_pct <= -10:
        return "SELL", max(confidence, 78.0)
    if ma_signal == "bullish" and change_pct >= 10:
        return "BUY", max(confidence, 78.0)
    # Flat, low-volume consolidation: downgrade to HOLD but preserve model probability.
    if ma_signal == "neutral" and abs(change_pct) <= 2 and volume < 2.0:
        return "HOLD", confidence
    return signal, confidence


def _ma_trend_category(features: dict[str, Any]) -> str:
    """Mirror format_ma_trend() buckets for signal consistency checks."""
    price = float(features["price"])
    ma5 = float(features["ma5"])
    ma10 = float(features["ma10"])
    ma20 = float(features["ma20"])

    if price > ma5 and price > ma10 and price > ma20 and ma5 > ma10 > ma20:
        return "strong_bullish"
    if price > ma5 and price > ma10 and price > ma20:
        return "bullish"
    if price < ma5 and price < ma10 and price < ma20 and ma5 < ma10 < ma20:
        return "strong_bearish"
    if price < ma5 and price < ma10 and price < ma20:
        return "bearish"
    if price > ma20:
        return "moderately_bullish"
    return "mixed"


def apply_trend_consistency(features: dict[str, Any], signal: str, confidence: float) -> tuple[str, float]:
    """Avoid contradictory signals when MA trend conflicts with ML output."""
    confidence = float(confidence)
    signal = str(signal).upper()
    trend = _ma_trend_category(features)

    if signal == "SELL":
        # Only allow SELL when MAs are bearish or mixed/neutral.
        if trend == "strong_bullish" and confidence < 80:
            return "HOLD", confidence
        if trend in ("strong_bullish", "bullish", "moderately_bullish"):
            return "HOLD", confidence

    if signal == "BUY" and trend in ("bearish", "strong_bearish") and confidence < 70:
        return "HOLD", confidence
    return signal, confidence


def apply_confidence_threshold(signal: str, confidence: float) -> tuple[str, float]:
    """
    Client accuracy rule: only show BUY/SELL at 65%+ confidence.
    50-64% and below always display as HOLD. Applies equally to BUY and SELL.
    """
    confidence = float(confidence)
    signal = str(signal).upper()

    if signal == "SELL" and confidence < 65:
        return "HOLD", confidence
    if signal == "BUY" and confidence < 65:
        return "HOLD", confidence
    if signal in ("BUY", "SELL") and confidence >= 65:
        return signal, confidence
    return "HOLD", confidence


def analyze_live(ticker: str) -> dict[str, Any]:
    """Real-time signal from yfinance 1-minute bars (day-trading focused)."""
    symbol = ticker.strip().upper()
    if not symbol or not symbol.isalnum() or len(symbol) > 10:
        raise ValueError("Invalid ticker symbol")

    hist = safe_ticker_history(symbol, period="5d", interval="1m")
    if hist is None or hist.empty:
        raise ValueError("Ticker not found or live data unavailable")

    hist = hist.rename(columns=str.lower)
    df = compute_indicators(hist)
    latest = df.iloc[-1]
    last_5 = df.iloc[-5:] if len(df) >= 5 else df
    stable_atr = float(last_5["atr"].mean()) if "atr" in last_5.columns else float(latest.get("atr", 0))
    stable_vol = float(last_5["volume"].mean()) if "volume" in last_5.columns else float(latest.get("volume", 0))
    prev = df.iloc[-2] if len(df) > 1 else latest

    current_price = float(latest["close"])
    prev_price = float(prev["close"])
    price_change = ((current_price - prev_price) / prev_price) * 100 if prev_price else 0.0

    macd_val = float(latest["macd"]) if pd.notna(latest.get("macd")) else 0.0
    macd_sig = float(latest["macd_signal"]) if pd.notna(latest.get("macd_signal")) else 0.0
    if macd_val > macd_sig:
        macd_cross = "bullish"
    elif macd_val < macd_sig:
        macd_cross = "bearish"
    else:
        macd_cross = "neutral"

    rsi_val = float(latest["rsi"]) if pd.notna(latest.get("rsi")) else 50.0

    ocr_data = {
        "platform": "Live",
        "ticker": symbol,
        "timeframe": "1min",
        "price": current_price,
        "change_pct": round(price_change, 2),
        "ma5": float(latest["ema_5"]) if pd.notna(latest.get("ema_5")) else current_price,
        "ma10": float(latest["ema_10"]) if pd.notna(latest.get("ema_10")) else current_price,
        "ma20": float(latest["ema_20"]) if pd.notna(latest.get("ema_20")) else current_price,
        "rsi": rsi_val,
        "rsi_from_ocr": True,
        "macd_from_ocr": True,
        "macd_cross": macd_cross,
        "atr": stable_atr,
        "volume": stable_vol,
        "timestamp": datetime.now().isoformat(),
        "ocr_confidence": 100,
        "source": "live",
    }

    result = analyze(ocr_data, df=df)
    direction = "UP" if price_change > 0 else "DOWN" if price_change < 0 else "FLAT"
    result.update(
        {
            "live_mode": True,
            "price": round(current_price, 4),
            "prev_price": round(prev_price, 4),
            "change_pct": round(price_change, 2),
            "direction": direction,
        }
    )
    return result


def _fetch_live_price(ticker: str) -> Optional[float]:
    """Fetch current price from yfinance when OCR did not read a price."""
    if not ticker or ticker.lower() == "unknown":
        return None
    hist = safe_ticker_history(ticker, period="5d")
    if hist is not None and not hist.empty:
        close_col = "Close" if "Close" in hist.columns else "close"
        return round(float(hist[close_col].iloc[-1]), 4)
    return None


def analyze(ocr_data: dict[str, Any], df: Optional[pd.DataFrame] = None) -> dict[str, Any]:
    """Full analysis pipeline: features -> ML -> signal JSON."""
    ocr_data = dict(ocr_data)
    ticker = str(ocr_data.get("ticker") or "unknown").upper()
    ocr_price = ocr_data.get("price")
    live_price = _fetch_live_price(ticker) if ticker != "UNKNOWN" else None

    try:
        parsed_ocr_price = float(ocr_price) if ocr_price is not None else 0.0
    except (TypeError, ValueError):
        parsed_ocr_price = 0.0

    # yfinance fills in only when OCR did not read a price; screenshot C close always wins.
    ocr_has_price = (
        parsed_ocr_price != 0
        or ocr_data.get("price_from_ocr_header")
        or ocr_data.get("price_from_ocr_c_close")
    )
    if live_price is not None and not ocr_has_price:
        ocr_data["price"] = live_price
        ocr_data["price_from_yfinance"] = True

    features = build_feature_vector(ocr_data, df=df)
    ocr_price_val = ocr_data.get("price")
    if ocr_price_val is None or float(ocr_price_val or 0) == 0:
        current_price = float(features["price"])
    else:
        current_price = float(ocr_price_val)
    features["price"] = current_price

    X = features_to_ml_array(features)
    ml_result = predict_signal(X)
    signal = ml_result["signal"]
    confidence = ml_result["confidence"]
    pipeline_log(
        f"[ML] raw signal={signal} confidence={confidence} "
        f"ticker={ticker} ma={features.get('ma_signal')} change_pct={features.get('change_pct')}"
    )
    signal, confidence = apply_signal_overrides(features, signal, confidence)
    pipeline_log(f"[ML] after overrides signal={signal} confidence={confidence}")
    signal, confidence = apply_trend_consistency(features, signal, confidence)
    signal, confidence = apply_confidence_threshold(signal, confidence)

    # Safety net: never emit BUY/SELL below 65% after all overrides
    if str(signal).upper() in ("BUY", "SELL") and float(confidence) < 65:
        signal = "HOLD"

    now = datetime.now()
    entry, tp, sl, rr = compute_levels(current_price, features["atr"], signal)
    forecasts = build_forecasts(features, signal, now)

    platform = ocr_data.get("platform", "Webull")
    indicators = {
        "MA5": round(features["ma5"], 4),
        "MA10": round(features["ma10"], 4),
        "MA20": round(features["ma20"], 4),
        "MA_trend": format_ma_trend(features),
        "volume": format_volume(features),
        "bollinger": format_bollinger(features["bollinger_pos"]),
        "ATR": round(features["atr"], 4),
        "momentum": features["momentum"].capitalize(),
        "vwap": round(features.get("vwap", 0), 4),
        "vwap_signal": features.get("vwap_signal", ""),
        "adx": round(features.get("adx", 0), 2),
        "adx_signal": features.get("adx_signal", ""),
        "trend_strength": features.get("trend_strength", ""),
        "cci": round(features.get("cci", 0), 2),
        "cci_signal": features.get("cci_signal", ""),
        "resistance": round(features.get("resistance", 0), 4),
        "support": round(features.get("support", 0), 4),
        "sr_signal": features.get("sr_signal", ""),
        "pivot": round(features.get("pivot", 0), 4),
        "pivot_r1": round(features.get("pivot_r1", 0), 4),
        "pivot_s1": round(features.get("pivot_s1", 0), 4),
        "pivot_r2": round(features.get("pivot_r2", 0), 4),
        "pivot_s2": round(features.get("pivot_s2", 0), 4),
        "pivot_signal": features.get("pivot_signal", ""),
        "pivot_bias": features.get("pivot_bias", ""),
    }
    if features.get("rsi") is not None:
        indicators["RSI"] = round(features["rsi"], 1)
    pipeline_log(f"[SIGNAL] MA5 in final output: {indicators.get('MA5')}")
    macd = format_macd(features.get("macd_cross"), ocr_data)
    if macd is not None:
        indicators["MACD"] = macd

    risk = risk_assessment(features)
    analysis_signals = build_analysis_signals(indicators, risk)
    conclusion = build_conclusion(
        analysis_signals,
        signal=signal,
        confidence=confidence,
    )

    output = {
        "platform": platform,
        "ticker": ocr_data.get("ticker", "unknown"),
        "timeframe": ocr_data.get("timeframe", "1min"),
        "timestamp": ocr_data.get("timestamp", datetime.now().isoformat()),
        "signal": signal,
        "confidence": round(confidence),
        "entry_price": round(current_price, 4),
        "take_profit": tp,
        "stop_loss": sl,
        "buy_at": {
            "price": round(current_price, 4),
            "time": "Now - Current price",
            "date": now.date().isoformat(),
        },
        "sell_for_profit": {
            "price": tp,
            "predicted_time": forecasts["short_term_forecast"]["predicted_by"],
        },
        "sell_to_cut_loss": {
            "price": sl,
            "note": "Exit immediately if price drops here",
        },
        "risk_reward_ratio": rr,
        **forecasts,
        "forecasts": build_forecasts_summary(forecasts),
        "market_status": get_market_status(now),
        "indicators": indicators,
        "risk_assessment": risk,
        "conclusion": conclusion,
        "ocr_confidence": ocr_data.get("ocr_confidence", 0),
    }
    return output
