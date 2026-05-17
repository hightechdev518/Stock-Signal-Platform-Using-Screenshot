"""Test TradingView OCR extraction on simulated screenshot."""
import json
from pathlib import Path

from create_tradingview_sample import out as TV_IMAGE
from ocr_parser import parse_screenshot
from signal_engine import analyze

# Ensure sample exists
if not TV_IMAGE.exists():
    import create_tradingview_sample  # noqa: F401

print("=" * 60)
print("TradingView OCR Test")
print("=" * 60)

with open(TV_IMAGE, "rb") as f:
    ocr_data = parse_screenshot(f.read())

print("\n--- OCR Extracted Fields ---")
fields = ["platform", "price", "ma5", "ma10", "ma20", "ema20", "rsi", "macd_bullish", "volume", "change_pct", "timeframe"]
for k in fields:
    print(f"  {k}: {ocr_data.get(k)}")

print("\n--- Full Analysis JSON (forecasts + volume) ---")
result = analyze(ocr_data)
print(f"  MA5 (indicators): {result['indicators']['MA5']}")
print(f"  MA10 (indicators): {result['indicators']['MA10']}")
print(f"  MA20 (indicators): {result['indicators']['MA20']}")
print(json.dumps({
    "platform": result["platform"],
    "signal": result["signal"],
    "confidence": result["confidence"],
    "volume": result["indicators"]["volume"],
    "short_term_forecast": result["short_term_forecast"],
    "medium_term_forecast": result["medium_term_forecast"],
    "long_term_forecast": result["long_term_forecast"],
    "monthly_forecast": result["monthly_forecast"],
}, indent=2))

# Validation
assert result["platform"] == "TradingView", f"Expected TradingView, got {result['platform']}"
assert result["indicators"]["volume"] != "Normal volume" or "High" in result["indicators"]["volume"] or "Very High" in result["indicators"]["volume"]
assert "medium_term_forecast" in result
assert "monthly_forecast" in result
ma5, ma10, ma20 = result["indicators"]["MA5"], result["indicators"]["MA10"], result["indicators"]["MA20"]
assert ma5 < 2.0, f"MA5 too large: {ma5}"
assert ma10 < 2.0, f"MA10 too large: {ma10}"
assert 0.4 < ma20 < 0.7, f"MA20 out of range: {ma20}"
print("\n[PASS] TradingView OCR test PASSED")
