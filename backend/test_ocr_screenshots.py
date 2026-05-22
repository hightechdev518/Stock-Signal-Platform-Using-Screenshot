"""
Real screenshot OCR gate — all 6 must pass before release.
Run: python test_ocr_screenshots.py
"""

from pathlib import Path

from ocr_parser import parse_screenshot

SHOTS = Path(__file__).resolve().parent.parent / "data" / "sample_screenshots"

# name -> (file, expected dict)
TESTS = {
    "AAPL": (
        "Appl_may5.jpg",
        {"ticker": "AAPL", "price": 297.91, "ma5": 297.81},
    ),
    "DIA": (
        "Dia_may5.jpg",
        {"ticker": "DIA", "price": 493.98, "ma5": 493.68},
    ),
    "SAIC": (
        "SAIC_may5.jpg",
        {"ticker": "SAIC", "price": 95.32, "ma5": 95.41},
    ),
    "SLXN": (
        "SLXN_Ma20.jpg",
        {"ticker": "SLXN", "price": 0.4683, "ma5": 0.4649},
    ),
    "Client mobile": (
        "WhatsApp Image 2026-05-16 at 4.51.44 AM.jpeg",
        {"price": 0.5861, "ma5": 0.5789},
    ),
    "OCGN": (
        "Ocgn_may5.jpg",
        {"ticker": "OCGN", "price": 1.300, "ma5": 1.300},
    ),
    "PAPL": (
        "PAPL_Ma20.jpg",
        {"ticker": "PAPL", "ma5": 1.089},
    ),
    "GRAN": (
        "GRAN_May20.jpg",
        {"ticker": "GRAN", "ma5": 1.037},
    ),
}

TOLERANCE = 0.02
NOISE_TICKERS = frozenset({"TPO", "VS", "BB", "MC", "TF", "MA", "RSI", "NAT"})


def _close(actual: float | None, expected: float, label: str) -> None:
    assert actual is not None, f"{label}: expected {expected}, got None"
    assert abs(float(actual) - expected) <= TOLERANCE, (
        f"{label}: expected {expected}, got {actual}"
    )


def main() -> None:
    print("Real screenshot OCR gate (6 required)\n")
    failed = []
    for name, (filename, expected) in TESTS.items():
        path = SHOTS / filename
        if not path.is_file():
            failed.append(f"{name}: missing file {filename}")
            print(f"  [FAIL] {name}: missing {filename}")
            continue
        parsed = parse_screenshot(path.read_bytes())
        ticker = parsed.get("ticker", "unknown")
        price = parsed.get("price")
        ma5 = parsed.get("ma5")
        platform = parsed.get("platform")

        try:
            if "ticker" in expected:
                assert ticker == expected["ticker"], (
                    f"ticker expected {expected['ticker']}, got {ticker}"
                )
                assert ticker not in NOISE_TICKERS, f"chart noise ticker {ticker}"
            if "price" in expected:
                _close(price, expected["price"], "price")
            _close(ma5, expected["ma5"], "ma5")
            if platform != "Webull" and name != "Client mobile":
                raise AssertionError(f"platform expected Webull, got {platform}")
            if parsed.get("price_from_ocr_c_close") and price:
                pass
            print(
                f"  [PASS] {name}: ticker={ticker} price={price} ma5={ma5} "
                f"platform={platform}"
            )
        except AssertionError as exc:
            failed.append(f"{name}: {exc}")
            print(
                f"  [FAIL] {name}: {exc} (ticker={ticker} price={price} ma5={ma5})"
            )

    print()
    if failed:
        print(f"FAILED {len(failed)}/{len(TESTS)}:")
        for item in failed:
            print(f"  - {item}")
        raise SystemExit(1)
    print("All 6 screenshot tests passed.")


if __name__ == "__main__":
    main()
