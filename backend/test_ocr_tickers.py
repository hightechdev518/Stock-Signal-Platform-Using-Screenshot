"""Universal ticker OCR tests — header-only, no chart noise."""

from pathlib import Path

from ocr_parser import (
    _extract_webull_c_close,
    detect_platform,
    extract_ticker,
    is_webull_layout_text,
    parse_screenshot,
    parse_webull,
)

CHART_NOISE = (
    "\nTPO VS BB MC RSI ATR EMA SMA VOL BOLL MACD VWAP OHLC EXT TF TA\n"
    "MA MA5 297.81 MA10 296.50 Bollinger Bands\n"
)

CASES = {
    "SLXN": {
        "header": (
            "SLXN Silexion Therapeutics Corp 1 minute Adjusted\n"
            "O 0.4675 H 0.4685 L 0.4647 C 0.4683\n"
            "MA MA5 0.4649 MA10 0.4600 MA20 0.4550"
        ),
        "price": 0.4683,
        "ma5": 0.4649,
        "platform": "Webull",
    },
    "AAPL": {
        "header": (
            "AAPL Apple Inc\n"
            "1 minute Adjusted\n"
            "O 297.50 H 299.10 L 296.80 C 298.970\n"
            "MA MA5 297.810 MA10 296.500 MA20 295.200"
        ),
        "price": 298.97,
        "ma5": 297.81,
        "platform": "Webull",
    },
    "DIA": {
        "header": (
            "DIA SPDR Dow Jones\n"
            "1 minute Adjusted\n"
            "O 420.10 H 422.00 L 419.50 C 421.750\n"
            "MA MA5 421.200 MA10 420.800 MA20 419.900"
        ),
        "price": 421.75,
        "ma5": 421.2,
        "platform": "Webull",
    },
    "SAIC": {
        "header": (
            "SAIC Science Applications International 1 minute Adjusted\n"
            "O 94.10 H 95.20 L 93.80 C 94.850\n"
            "MA MA5 94.200 MA10 93.900 MA20 93.500"
        ),
        "price": 94.85,
        "ma5": 94.2,
        "platform": "Webull",
    },
    "OCGN": {
        "header": (
            "OCGN Ocugen Inc\n"
            "1 minute Adjusted\n"
            "O 0.52 H 0.55 L 0.50 C 0.5380\n"
            "MA MA5 0.5295 MA10 0.5200 MA20 0.5100"
        ),
        "price": 0.538,
        "ma5": 0.5295,
        "platform": "Webull",
    },
}

SCREENSHOT_TICKERS = {
    "Appl_may5.jpg": "AAPL",
    "Dia_may5.jpg": "DIA",
    "SLXN_Ma20.jpg": "SLXN",
    "SAIC_may5.jpg": "SAIC",
}


def _assert_close(actual: float | None, expected: float, label: str) -> None:
    assert actual is not None, f"{label}: expected {expected}, got None"
    assert abs(float(actual) - expected) < 0.02, f"{label}: expected ~{expected}, got {actual}"


def test_synthetic() -> None:
    print("Synthetic OCR ticker tests\n")
    for name, case in CASES.items():
        header = case["header"]
        assert is_webull_layout_text(header), f"{name}: layout should be Webull"
        assert detect_platform(header, None) == "Webull", f"{name}: platform"

        ticker = extract_ticker(header)
        assert ticker == name, f"{name}: ticker expected {name}, got {ticker}"

        # Chart noise in body must not override header ticker
        noise_ticker = extract_ticker(header)
        assert noise_ticker == name, f"{name}: noise leaked ticker {noise_ticker}"
        parsed_noise = parse_webull(header + CHART_NOISE, None, header, header)
        assert parsed_noise["ticker"] == name, (
            f"{name}: chart noise changed ticker to {parsed_noise['ticker']}"
        )

        c_price = _extract_webull_c_close(header)
        _assert_close(c_price, case["price"], f"{name} C close")

        parsed = parse_webull(header, None, header, header)
        assert parsed["platform"] == case["platform"], f"{name}: parsed platform"
        assert parsed["ticker"] == name, f"{name}: parsed ticker"
        _assert_close(parsed.get("price"), case["price"], f"{name} price")
        _assert_close(parsed.get("ma5"), case["ma5"], f"{name} ma5")
        if name == "SLXN":
            assert parsed.get("ma5_from_ocr") is True, f"{name}: ma5_from_ocr"
            assert parsed.get("price_from_ocr_c_close") is True, f"{name}: price_from_ocr_c_close"
        print(f"  [PASS] {name}: ticker={ticker} price={parsed.get('price')} ma5={parsed.get('ma5')}")


def test_real_screenshots() -> None:
    shots_dir = Path(__file__).resolve().parent.parent / "data" / "sample_screenshots"
    print("\nReal screenshot ticker tests\n")
    for filename, expected in SCREENSHOT_TICKERS.items():
        path = shots_dir / filename
        if not path.is_file():
            print(f"  [SKIP] {filename}: file not found")
            continue
        data = path.read_bytes()
        parsed = parse_screenshot(data)
        ticker = parsed.get("ticker", "unknown")
        assert ticker == expected, f"{filename}: expected {expected}, got {ticker}"
        assert ticker not in {"TPO", "VS", "BB", "MC", "TF", "MA", "RSI"}, (
            f"{filename}: chart noise ticker {ticker}"
        )
        print(f"  [PASS] {filename}: ticker={ticker}")


def main() -> None:
    test_synthetic()
    test_real_screenshots()
    print("\nAll ticker OCR tests passed.")


if __name__ == "__main__":
    main()
