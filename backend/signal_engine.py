"""
Trading signal engine: entry, TP, SL, forecasts, risk assessment, full JSON output.
"""

from datetime import datetime
from typing import Any

from feature_engineer import build_feature_vector, classify_volume, features_to_ml_array
from ml_model import predict_signal


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


def build_forecasts(features: dict[str, Any], signal: str) -> dict[str, dict]:
    """Build short, medium, long (weeks), and monthly forecasts using ATR targets."""
    price = features["price"]
    atr = features["atr"]
    tf = features.get("timeframe", "1min")

    if signal == "BUY":
        directions = {
            "short": "Bullish",
            "medium": "Uptrend",
            "long": "Uptrend",
            "monthly": "Bullish",
        }
        notes = {
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
            "short": "Bearish",
            "medium": "Downtrend",
            "long": "Downtrend",
            "monthly": "Bearish",
        }
        notes = {
            "short": "Bearish pressure below key moving averages",
            "medium": "Selling pressure intensifying over coming sessions",
            "long": "Extended downtrend likely to continue",
            "monthly": "Long-term distribution pattern forming",
        }
    else:
        directions = {
            "short": "Neutral",
            "medium": "Sideways",
            "long": "Sideways",
            "monthly": "Neutral",
        }
        notes = {
            "short": "Consolidation - wait for clearer breakout",
            "medium": "Range-bound trading expected",
            "long": "No clear directional bias on weekly chart",
            "monthly": "Long-term trend undecided",
        }

    short_tf = "2-4 hours" if tf in ("1min", "5min", "15min") else "1-2 days"

    return {
        "short_term_forecast": {
            "direction": directions["short"],
            "target": _forecast_target(price, atr, signal, 1.5),
            "timeframe": short_tf,
            "note": notes["short"],
        },
        "medium_term_forecast": {
            "direction": directions["medium"],
            "target": _forecast_target(price, atr, signal, 3.0),
            "timeframe": "3-7 days",
            "note": notes["medium"],
        },
        "long_term_forecast": {
            "direction": directions["long"],
            "target": _forecast_target(price, atr, signal, 6.0),
            "timeframe": "2-4 weeks",
            "note": notes["long"],
        },
        "monthly_forecast": {
            "direction": directions["monthly"],
            "target": _forecast_target(price, atr, signal, 10.0),
            "timeframe": "1-3 months",
            "note": notes["monthly"],
        },
    }


def risk_assessment(features: dict[str, Any]) -> str:
    atr_pct = (features["atr"] / features["price"]) * 100 if features["price"] else 0
    vol = features["vol_ratio"]
    if atr_pct > 3 or vol > 2.5:
        return "Medium-High volatility detected"
    if atr_pct > 1.5:
        return "Moderate volatility"
    return "Low volatility - stable conditions"


def apply_signal_overrides(features: dict[str, Any], signal: str, confidence: float) -> tuple[str, float]:
    """Use clear screenshot-derived setups to correct model overconfidence."""
    change_pct = features.get("change_pct") or 0
    ma_signal = features.get("ma_signal")
    volume = features.get("vol_ratio", 1.0)

    if ma_signal == "bearish" and change_pct <= -10:
        return "SELL", max(float(confidence), 78.0)
    if ma_signal == "bullish" and change_pct >= 10:
        return "BUY", max(float(confidence), 78.0)
    if ma_signal == "neutral" and abs(change_pct) <= 2 and volume < 2.0:
        return "HOLD", max(70.0, min(float(confidence), 76.0))
    return signal, confidence


def analyze(ocr_data: dict[str, Any]) -> dict[str, Any]:
    """Full analysis pipeline: features -> ML -> signal JSON."""
    features = build_feature_vector(ocr_data)
    current_price = float(ocr_data.get("price") or features["price"])
    features["price"] = current_price

    X = features_to_ml_array(features)
    ml_result = predict_signal(X)
    signal = ml_result["signal"]
    confidence = ml_result["confidence"]
    signal, confidence = apply_signal_overrides(features, signal, confidence)

    entry, tp, sl, rr = compute_levels(current_price, features["atr"], signal)
    forecasts = build_forecasts(features, signal)

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
    }
    if features.get("rsi") is not None:
        indicators["RSI"] = round(features["rsi"], 1)
    macd = format_macd(features.get("macd_cross"), ocr_data)
    if macd is not None:
        indicators["MACD"] = macd

    output = {
        "platform": platform,
        "ticker": ocr_data.get("ticker", "unknown"),
        "timeframe": ocr_data.get("timeframe", "1min"),
        "timestamp": ocr_data.get("timestamp", datetime.now().isoformat()),
        "signal": signal,
        "confidence": int(confidence),
        "entry_price": round(current_price, 4),
        "take_profit": tp,
        "stop_loss": sl,
        "risk_reward_ratio": rr,
        **forecasts,
        "indicators": indicators,
        "risk_assessment": risk_assessment(features),
        "ocr_confidence": ocr_data.get("ocr_confidence", 0),
    }
    return output
