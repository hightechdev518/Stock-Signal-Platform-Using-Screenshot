"""Conclusion bias from bullish vs warning counts (not ML signal)."""

from signal_engine import build_analysis_signals, build_conclusion


def _signals_for(indicators: dict, risk: str) -> list[dict[str, str]]:
    return build_analysis_signals(indicators, risk)


def test_saic_bearish_one_bullish_four_warnings():
    """SAIC: 1 bullish, 4 warnings → BEARISH."""
    indicators = {
        "MA_trend": "Mixed MA alignment - Neutral",
        "volume": "Normal volume (1.0x avg)",
        "RSI": 72,
        "MACD": "Bearish crossover",
    }
    risk = "Low volatility - stable conditions"
    signals = _signals_for(indicators, risk)
    bullish = sum(1 for s in signals if s["type"] == "bullish")
    warnings = sum(1 for s in signals if s["type"] == "warning")
    assert bullish == 1, f"expected 1 bullish, got {bullish}: {signals}"
    assert warnings == 4, f"expected 4 warnings, got {warnings}: {signals}"
    conclusion = build_conclusion(signals)
    assert "BEARISH" in conclusion
    assert "Avoid new entries" in conclusion


def test_sndl_bullish_five_two():
    """SNDL-style: 5 bullish, 2 warnings → BULLISH."""
    indicators = {
        "MA_trend": "Price above all MAs - Bullish",
        "volume": "Very high volume (3.5x avg)",
        "RSI": 58,
        "MACD": "Bullish crossover",
        "momentum": "Weak",
        "bollinger": "Lower half of bands",
    }
    risk = "Low volatility - stable conditions"
    signals = _signals_for(indicators, risk)
    bullish = sum(1 for s in signals if s["type"] == "bullish")
    warnings = sum(1 for s in signals if s["type"] == "warning")
    assert bullish == 5, f"expected 5 bullish, got {bullish}: {signals}"
    assert warnings == 2, f"expected 2 warnings, got {warnings}: {signals}"
    assert "BULLISH" in build_conclusion(signals)


def test_pltr_bullish_five_two():
    """PLTR-style: same as SNDL pattern."""
    test_sndl_bullish_five_two()


def test_amzn_bullish_four_three():
    """AMZN: 4 bullish, 3 warnings → BULLISH (was NEUTRAL under ML-based bias)."""
    signals = [{"type": "bullish"}] * 4 + [{"type": "warning"}] * 3
    conclusion = build_conclusion(signals)
    assert "BULLISH" in conclusion
    assert "Consider entering" in conclusion


def test_spy_bullish_four_three():
    """SPY: 4 bullish, 3 warnings → BULLISH."""
    test_amzn_bullish_four_three()


def test_neutral_tie():
    signals = [{"type": "bullish"}, {"type": "warning"}]
    conclusion = build_conclusion(signals)
    assert "NEUTRAL" in conclusion


if __name__ == "__main__":
    test_saic_bearish_one_bullish_four_warnings()
    test_sndl_bullish_five_two()
    test_pltr_bullish_five_two()
    test_amzn_bullish_four_three()
    test_spy_bullish_four_three()
    test_neutral_tie()
    print("All conclusion tests passed.")
