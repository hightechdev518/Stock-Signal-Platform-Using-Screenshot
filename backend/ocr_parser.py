"""
Screenshot OCR pipeline for Webull and TradingView chart images.
Detects platform, preprocesses image, extracts text via Tesseract, parses structured data.
"""

import os
import re
import sys
from datetime import datetime
from typing import Any, Optional

import cv2
import numpy as np
import pytesseract
from PIL import Image

from debug_logging import pipeline_log


def _set_tessdata_prefix(tesseract_root: str) -> None:
    """Point Tesseract at tessdata/ (UB Mannheim layout)."""
    tessdata = os.path.join(tesseract_root, "tessdata")
    if os.path.isdir(tessdata):
        os.environ["TESSDATA_PREFIX"] = tessdata + os.sep
    else:
        os.environ["TESSDATA_PREFIX"] = tesseract_root + os.sep


def _configure_tesseract() -> Optional[str]:
    """Use bundled Tesseract in PyInstaller build, else dev machine install."""
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    bundled_dir = os.path.join(base_path, "tesseract")
    bundled_exe = os.path.join(bundled_dir, "tesseract.exe")
    if os.path.isfile(bundled_exe):
        pytesseract.pytesseract.tesseract_cmd = bundled_exe
        _set_tessdata_prefix(bundled_dir)
        os.environ["PATH"] = bundled_dir + os.pathsep + os.environ.get("PATH", "")
        return bundled_exe

    for fallback in (
        os.path.join(base_path, "tesseract", "tesseract.exe"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if os.path.isfile(fallback):
            pytesseract.pytesseract.tesseract_cmd = fallback
            _set_tessdata_prefix(os.path.dirname(fallback))
            return fallback
    return None


_TESSERACT_EXE = _configure_tesseract()
if _TESSERACT_EXE:
    pipeline_log(f"[OCR] Tesseract: {_TESSERACT_EXE}")
else:
    pipeline_log("[OCR] WARNING: Tesseract not found — OCR will be empty")

MIN_STOCK_PRICE = 0.01
MAX_STOCK_PRICE = 100_000.0

# --- Permanent OCR rules (layout/ticker/price/MA5) — never ticker-specific hardcoding ---
_TICKER_BLACKLIST = frozenset({
    "MA", "TF", "VS", "TPO", "MC", "BB", "RSI", "ATR", "EMA", "SMA", "VOL", "BOLL",
    "MACD", "NEWS", "ALL", "ADJ", "VWAP", "OHLC", "EXT", "TA", "NAT", "ORDER", "ENTRY",
    "CHART", "FREE", "LIVE", "MIN", "DAY", "WEEK", "MONTH", "AUTO", "NIGHT", "INTERVAL",
    "RANGE", "ADJUSTED", "MA5", "MA10", "MA20", "OPEN", "HIGH", "LOW", "CLOSE", "FEEDS",
    "DAILY", "WEEKLY", "MONTHLY", "MAX", "VOLUME", "NYSE", "AMEX", "NASDAQ", "USD",
    "ETF", "INC", "IPO", "BUY", "SELL", "FEED", "COMPANY", "APPLE", "VIEW", "TRADE",
    "STOCK", "SCRIPT", "EDITOR", "SIGNAL", "TECHNICAL", "INDICATORS", "STATE", "SPDR",
    "HB", "FF", "AP", "SF", "BW", "AY", "EE", "FS", "CNFC", "OS", "SAIL",
})
_TICKER_SKIP = _TICKER_BLACKLIST  # alias

HEADER_TICKER_FRAC = 0.08  # ticker OCR: top header (8% min; title row to 12% on desktop)
HEADER_TICKER_OCR_END = 0.12

_RE_C_CLOSE = re.compile(
    r"\bC\s*[:,]?\s*(\d+(?:[.,]\d+)?)\b"
    r"|\bC(\d+(?:[.,]\d+)?)\b",
    re.I,
)
_RE_OHLC_COMPACT = re.compile(
    r"(?:\bO\s*)?(\d+(?:[.,]\d+)?)\s*H\s*(\d+(?:[.,]\d+)?)\s*L\s*(\d+(?:[.,]\d+)?)\s*C\s*[:,]?(\d+(?:[.,]\d+)?)",
    re.I,
)
_RE_OHLC_BAR = re.compile(
    r"\bO\s+[\d.,]+\s+H\s+[\d.,]+\s+L\s+[\d.,]+\s+C\s+[\d.,]+\b",
    re.I,
)
_RE_MA_MA5_LABEL = re.compile(r"\bma\s+ma\s*5\b|\bma\s+ma5\b|\bma\s+mas\b", re.I)
# MA5 label→value patterns (order matters). Avoid ma\s*ma\s*s\s*(\d+) — it captures
# the "5" in "MAS5" as the value (e.g. PAPL "MA MAS5-1.089" → 5 instead of 1.089).
_MA5_VALUE_PATTERNS: tuple[str, ...] = (
    r"(?:ma\s*[.\s]*)?(?:mas5|ma5s?|mass)\s*[-–—:,+]?\s*(\d+[.,]\d+)",
    r"(?:ma\s*[.\s]*)?ma\s+mas5\s*[-–—:,+]?\s*(\d+[.,]\d+)",
    r"(?:ma\s*[.\s]*)?ma5\s*[-–—:,+]?\s*(\d+[.,]\d+)",
    r"ma\s+ma\s*5\s+(\d+[.,]\d+)",
    r"ma\s+mas\s+(\d+[.,]\d+)",
    r"ma\s+ma\s*5\s+(\d+(?:[.,]\d+)?)",
    r"ma\s+mas\s+(\d+(?:[.,]\d+)?)",
    r"mamas(\d+(?:[.,]\d+)?)",
    r"mamas\s*[-–—:,+]?\s*(\d+(?:[.,]\d+)?)",
)


def _is_plausible_price(value: float, reference: Optional[float] = None) -> bool:
    if not (MIN_STOCK_PRICE <= value <= MAX_STOCK_PRICE):
        return False
    if reference is not None and reference > 0:
        return reference * 0.2 <= value <= reference * 5.0
    return True


def validate_price(
    price: Optional[float],
    text: str = "",
    *,
    lock_parsed: bool = False,
) -> Optional[float]:
    """Return OCR price only if it is a plausible stock price (no sample fallback)."""
    if price is not None:
        try:
            parsed = float(price)
        except (TypeError, ValueError):
            parsed = None
        if parsed is not None and _is_plausible_price(parsed):
            return round(parsed, 4)

    if lock_parsed:
        return None

    for value in _decimal_values(text):
        if _is_plausible_price(value):
            return round(value, 4)
    return None


def _is_percent_value(text: str, raw: str, value: float) -> bool:
    """True when a numeric OCR token is part of a percentage (e.g. +21.18%)."""
    token = re.escape(raw.replace(",", "."))
    return bool(re.search(rf"{token}\s*%", text)) or bool(re.search(rf"{token}\s*%", text.replace(",", ".")))


# Treat OCR values within this band of a parsed MA as the MA line, not current price.
MA_PRICE_EPSILON = 0.06


def _ma_values_list(
    ma5: Optional[float],
    ma10: Optional[float],
    ma20: Optional[float],
) -> list[float]:
    return [float(v) for v in (ma5, ma10, ma20) if v is not None]


def _near_any_ma(value: float, ma_values: list[float], epsilon: float = MA_PRICE_EPSILON) -> bool:
    """True when OCR price is effectively the same number as an MA label."""
    return any(abs(value - float(ma)) <= epsilon for ma in ma_values)


def _value_in_ma_label_context(value: float, text: str) -> bool:
    """True when a number appears immediately after an MA period label in OCR text."""
    raw = f"{value:g}".replace(".", r"[.,]")
    patterns = (
        rf"(?:ma\s*)?(?:ma\s*)?(?:mas|ma\s*5|ma5|mamas)\s*[:：]?\s*{raw}\b",
        rf"(?:ma\s*)?(?:ma\s*)?10\s*[:：]?\s*{raw}\b",
        rf"(?:ma\s*)?(?:ma\s*)?20\s*[:：]?\s*{raw}\b",
        rf"ma\s*\(\s*5\s*,\s*10\s*,\s*20\s*\)[^\d]*{raw}\b",
    )
    return any(re.search(pat, text, re.I) for pat in patterns)


def _decimal_values(text: str, exclude_percents: bool = True) -> list[float]:
    """Return plausible decimal values found by OCR, preserving order."""
    values: list[float] = []
    for raw in re.findall(r"\b\d+[\.,]\d{1,4}\b", text):
        try:
            value = float(raw.replace(",", "."))
        except ValueError:
            continue
        if exclude_percents and _is_percent_value(text, raw, value):
            continue
        values.append(value)
    return values


def validate_ma_value(ma_value: Optional[float], current_price: Optional[float]) -> Optional[float]:
    """
    Correct OCR misreads where decimal points are lost on low-priced stocks.
    E.g. 578.9 or 740.36 should become ~0.57 when price is ~0.58.
    """
    if ma_value is None:
        return None
    if current_price is None or current_price <= 0:
        return round(float(ma_value), 4)

    ma_value = float(ma_value)
    current_price = float(current_price)

    # Large-cap OCR: reject MA far below price (e.g. 7.34 vs price 298)
    if current_price > 50 and ma_value < current_price * 0.25:
        return None

    # Penny-stock OCR only: lost decimal (e.g. 578.9 vs price 0.58)
    if current_price < 10 and ma_value > current_price * 10:
        candidates = [ma_value / d for d in (10000, 1000, 100, 10)]
        in_range = [c for c in candidates if current_price * 0.2 <= c <= current_price * 2.5]
        if in_range:
            ma_value = min(in_range, key=lambda c: abs(c - current_price))
        else:
            ma_value = ma_value / 1000

    if not _is_plausible_price(ma_value, current_price):
        return None
    return round(ma_value, 4)


def apply_ma_validation(parsed: dict[str, Any], raw_text: str = "") -> dict[str, Any]:
    """Validate price and all MA fields after OCR extraction."""
    lock_price = bool(
        parsed.get("price_from_ocr_header")
        or parsed.get("price_from_ocr_c_close")
        or parsed.get("price_from_mobile_box")
        or parsed.get("price_from_right_box")
        or parsed.get("price_from_axis_highlight")
    )
    parsed["price"] = validate_price(parsed.get("price"), raw_text, lock_parsed=lock_price)
    price = parsed.get("price")

    for key in ("ma5", "ma10", "ma20", "ema5", "ema10", "ema20", "ema", "sma"):
        if parsed.get(key) is None:
            continue
        lock_ma = bool(parsed.get(f"{key}_from_ocr"))
        if lock_ma:
            try:
                parsed[key] = round(float(parsed[key]), 4)
            except (TypeError, ValueError):
                parsed.pop(key, None)
            continue
        validated = validate_ma_value(parsed[key], price)
        if validated is not None:
            parsed[key] = validated
        else:
            parsed.pop(key, None)
    return parsed


def preprocess_image(image: np.ndarray) -> np.ndarray:
    """Grayscale, denoise, adaptive threshold for better OCR."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    sharpened = cv2.filter2D(denoised, -1, kernel)
    thresh = cv2.adaptiveThreshold(
        sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    return thresh


def preprocess_tradingview_dark(image: np.ndarray) -> np.ndarray:
    """Brighten TradingView dark-theme screenshots for improved OCR."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    # CLAHE contrast enhancement for dark UI
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    # Invert if predominantly dark background
    if np.mean(enhanced) < 100:
        enhanced = cv2.bitwise_not(enhanced)
    return preprocess_image(cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR))


def extract_text(image: np.ndarray) -> str:
    """Run Tesseract OCR on preprocessed image."""
    pil_img = Image.fromarray(image)
    config = "--psm 6 -c tessedit_char_whitelist=0123456789.+-%,ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:/ "
    try:
        text = pytesseract.image_to_string(pil_img, config=config)
    except pytesseract.TesseractNotFoundError:
        return ""
    except Exception:
        try:
            text = pytesseract.image_to_string(pil_img)
        except Exception:
            return ""
    return text


def extract_text_with_config(image: np.ndarray, config: str = "--psm 6 --oem 3") -> str:
    """Run Tesseract with caller-provided config for targeted OCR regions."""
    try:
        return pytesseract.image_to_string(Image.fromarray(image), config=config)
    except Exception:
        return ""


def preprocess_dark_region(region: np.ndarray, scale: float = 2.5) -> np.ndarray:
    """Enhance dark Webull UI regions with colored text for OCR."""
    if len(region.shape) == 3:
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    else:
        gray = region.copy()
    enlarged = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(enlarged)
    sharpened = cv2.GaussianBlur(enhanced, (0, 0), 1.0)
    sharpened = cv2.addWeighted(enhanced, 1.7, sharpened, -0.7, 0)
    if np.mean(sharpened) < 120:
        sharpened = cv2.bitwise_not(sharpened)
    return sharpened


def preprocess_ma_colored_strip(region: np.ndarray) -> np.ndarray:
    """Isolate pink/magenta MA label text (MA MA5 297.81) on dark Webull charts."""
    if len(region.shape) == 3:
        b, g, r = cv2.split(region)
        # Magenta/pink UI text: strong red, weaker green/blue
        pink = cv2.subtract(r, g)
        pink = cv2.max(pink, cv2.subtract(r, b))
        _, mask = cv2.threshold(pink, 35, 255, cv2.THRESH_BINARY)
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        boosted = cv2.add(gray, (mask // 3))
    else:
        boosted = region.copy()
    enlarged = cv2.resize(boosted, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(enlarged)
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if np.mean(binary) < 127:
        binary = cv2.bitwise_not(binary)
    return binary


def _debug_log_ocr(combined: str, header: str, regions: str) -> None:
    """Print OCR output for troubleshooting misreads."""
    print("\n===== OCR DEBUG: combined text =====")
    print(combined or "(empty)")
    print("\n===== OCR DEBUG: Webull header (top-left) =====")
    print(header or "(empty)")
    print("\n===== OCR DEBUG: Webull regions =====")
    print(regions or "(empty)")
    print("===== END OCR DEBUG =====\n")


def _ocr_region(
    image: np.ndarray,
    y0: float,
    y1: float,
    x0: float = 0.0,
    x1: float = 1.0,
    *,
    preprocess: str = "dark",
) -> str:
    """OCR a relative crop of the screenshot (fractions of height/width)."""
    if image is None or len(image.shape) != 3:
        return ""
    h, w = image.shape[:2]
    y_start, y_end = int(h * y0), int(h * y1)
    x_start, x_end = int(w * x0), int(w * x1)
    region = image[y_start:y_end, x_start:x_end]
    if region.size == 0:
        return ""
    if preprocess == "ma_colored":
        processed = preprocess_ma_colored_strip(region)
    else:
        processed = preprocess_dark_region(region)
    return extract_text_with_config(processed, "--psm 6 --oem 3").strip()


def extract_webull_ma_strip_text(image: np.ndarray) -> str:
    """OCR the top MA indicator row (MA MA5 297.81) with upscale + colored-text prep."""
    if image is None or len(image.shape) != 3:
        return ""
    h, w = image.shape[:2]
    parts = [
        _ocr_region(image, 0.05, 0.20, 0.0, 1.0, preprocess="ma_colored"),
        _ocr_region(image, 0.06, 0.18, 0.0, 1.0, preprocess="dark"),
        _ocr_region(image, 0.08, 0.22, 0.0, 1.0, preprocess="ma_colored"),
        _ocr_region(image, 0.10, 0.24, 0.0, 1.0, preprocess="dark"),
    ]
    # Upscale full-width top band (helps phone screenshots)
    top = image[0 : max(int(h * 0.22), 40), :]
    if top.size > 0:
        scaled = cv2.resize(top, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        for prep in (preprocess_ma_colored_strip, preprocess_dark_region):
            parts.append(extract_text_with_config(prep(scaled), "--psm 6 --oem 3").strip())
    return "\n".join(t for t in parts if t.strip())


def extract_webull_ticker_header_text(image: np.ndarray) -> str:
    """OCR top header only (8–12% height, left 75%) — ticker row, never chart body."""
    if image is None or len(image.shape) != 3:
        return ""
    parts = [
        _ocr_region(image, 0.0, HEADER_TICKER_FRAC, 0.0, 0.75, preprocess="dark"),
        _ocr_region(image, HEADER_TICKER_FRAC, HEADER_TICKER_OCR_END, 0.0, 0.75, preprocess="dark"),
        _ocr_region(image, 0.0, HEADER_TICKER_OCR_END, 0.0, 0.75, preprocess="ma_colored"),
    ]
    h, w = image.shape[:2]
    top = image[0 : max(int(h * HEADER_TICKER_OCR_END), 40), 0 : max(int(w * 0.75), 40)]
    if top.size > 0:
        scaled = cv2.resize(top, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
        for prep in (preprocess_dark_region, preprocess_ma_colored_strip):
            processed = prep(scaled)
            parts.append(
                extract_text_with_config(
                    processed,
                    "--psm 7 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ. ",
                ).strip()
            )
    return "\n".join(t for t in parts if t.strip())


def extract_webull_header_text(image: np.ndarray) -> str:
    """OCR top bar for OHLC / price (ticker uses extract_webull_ticker_header_text only)."""
    if image is None or len(image.shape) != 3:
        return ""
    parts = [
        _ocr_region(image, 0.0, 0.28, 0.0, 0.55),
        _ocr_region(image, 0.0, 0.22, 0.0, 1.0),
        _ocr_region(image, 0.08, 0.22, 0.0, 1.0, preprocess="ma_colored"),
    ]
    return "\n".join(t for t in parts if t)


def is_mobile_webull_layout(text: str, image: Optional[np.ndarray] = None) -> bool:
    """Detect Webull mobile app layout (tabs, MA(5,10,20), bottom timeframe row)."""
    spaced = text.lower()
    has_tabs = bool(
        re.search(r"chart\s+news\s+feeds", spaced)
        or re.search(r"chart[\s+]*news[\s+]*feeds", spaced)
        or re.search(r"chart.*?news.*?feeds", spaced)
    )
    has_ma_row = bool(re.search(r"ma\s*[\(\[]?\s*5\s*,\s*10\s*,\s*20", spaced, re.I))
    has_ma_colon = bool(re.search(r"ma\s*5\s*[:：]\s*\d", spaced, re.I))
    has_bottom_tf = bool(
        re.search(r"(?:1\s*min|amine|4mine|imine|lmin|imin)", spaced, re.I)
        and re.search(r"daily", spaced, re.I)
        and re.search(r"weekly", spaced, re.I)
    ) or bool(
        re.search(r"daily", spaced, re.I)
        and re.search(r"weekly", spaced, re.I)
        and re.search(r"month", spaced, re.I)
    )
    mobile_core = (has_tabs or has_ma_row) and (has_ma_colon or has_ma_row)
    return mobile_core and (has_bottom_tf or (has_ma_colon and has_tabs))


def extract_mobile_webull_region_text(image: np.ndarray) -> str:
    """OCR regions specific to Webull mobile: top MA row, right price box, bottom timeframe."""
    if image is None or len(image.shape) != 3:
        return ""
    parts = [
        _ocr_region(image, 0.04, 0.18, 0.0, 1.0),  # Chart / News / Feeds + MA(5,10,20) row
        _ocr_region(image, 0.22, 0.78, 0.68, 0.98),  # right-side current price box
        _ocr_region(image, 0.86, 1.0, 0.0, 1.0),  # 1 min Daily Weekly Monthly
    ]
    return "\n".join(t for t in parts if t)


def extract_webull_region_text(image: np.ndarray) -> str:
    """Extract Webull-specific top MA strip, right price box, and bottom timeframe."""
    if image is None or len(image.shape) != 3:
        return ""
    h, w = image.shape[:2]
    regions = [
        image[int(h * 0.05) : int(h * 0.20), :],  # top MA strip (all resolutions)
        image[int(h * 0.10) : int(h * 0.22), :],  # MA strip / tabs
        image[int(h * 0.30) : int(h * 0.52), int(w * 0.72) : w],  # right price box
        image[int(h * 0.88) : h, :],  # bottom timeframe buttons
    ]
    texts = []
    for region in regions:
        if region.size == 0:
            continue
        processed = preprocess_dark_region(region)
        texts.append(extract_text_with_config(processed, "--psm 6 --oem 3"))
    return "\n".join(t for t in texts if t.strip())


def _tradingview_image_score(image: np.ndarray) -> float:
    """Heuristic score for TradingView dark/light layout."""
    if len(image.shape) != 3:
        return 0.0
    h, w = image.shape[:2]
    score = 0.0
    # Right sidebar (indicators panel) common on TV
    right = image[:, int(w * 0.75) :]
    if np.mean(right) < 80:
        score += 1.5  # dark sidebar
    # Top bar often dark blue-gray on TV
    top = image[0 : h // 10, :]
    mean_b, mean_g, mean_r = np.mean(top[:, :, 0]), np.mean(top[:, :, 1]), np.mean(top[:, :, 2])
    if mean_b > mean_r and mean_b > mean_g:
        score += 1.0
    return score


def has_webull_adjusted_header(text: str) -> bool:
    """'Adjusted' in header = Webull (layout rule; allows minuteAdjusted)."""
    return bool(re.search(r"adjusted", text, re.I))


def has_webull_ohlc_bar(text: str) -> bool:
    """O H L C bar present = Webull (layout rule; spaced or compact)."""
    return bool(_RE_OHLC_BAR.search(text) or _RE_OHLC_COMPACT.search(text))


def has_webull_ma_ma5_label(text: str) -> bool:
    """MA MA5 label present = Webull (layout rule; tolerates MAMAS OCR)."""
    return bool(
        _RE_MA_MA5_LABEL.search(text)
        or re.search(r"\bmamas\d", text, re.I)
        or re.search(r"\bma\s+mas\s+\d", text, re.I)
    )


def is_webull_layout_text(text: str) -> bool:
    """Webull layout from header cues only — never ticker/company name."""
    return (
        has_webull_adjusted_header(text)
        or has_webull_ohlc_bar(text)
        or has_webull_ma_ma5_label(text)
        or is_mobile_webull_layout(text)
    )


def _platform_scores(text: str, image: np.ndarray) -> tuple[float, float]:
    """Score Webull vs TradingView from layout and UI text (not ticker names)."""
    text_lower = text.lower().replace(" ", "")
    spaced_lower = text.lower()

    webull_score = 0.0
    tv_score = 0.0

    if "webull" in text_lower:
        webull_score += 3
    if re.search(r"\badjusted\b", spaced_lower):
        webull_score += 5
    if re.search(
        r"\bO\s+[\d.,]+\s+H\s+[\d.,]+\s+L\s+[\d.,]+\s+C\s+[\d.,]+",
        text,
        re.I,
    ):
        webull_score += 6
    if re.search(r"\bma\s*ma\s*5\b|\bma\s*ma5\b", spaced_lower, re.I):
        webull_score += 4
    if re.search(r"\b1\s*min(?:ute)?\b", spaced_lower, re.I):
        webull_score += 3
    if re.search(r"ma\s*\(\s*5\s*,\s*10\s*,\s*20\s*\)", spaced_lower, re.I):
        webull_score += 4
    if re.search(r"ma5|ma10|ma20", text_lower):
        webull_score += 2
    if re.search(r"ma\(?5,?10,?20\)?", text_lower):
        webull_score += 3
    if all(token in spaced_lower for token in ("chart", "news", "feeds")):
        webull_score += 3
    if re.search(r"1\s*min", spaced_lower) and all(
        token in spaced_lower for token in ("daily", "weekly", "monthly")
    ):
        webull_score += 4
    if is_mobile_webull_layout(text):
        webull_score += 6
    if is_webull_layout_text(text):
        webull_score += 5

    if "tradingview" in text_lower or "tradingview" in text.lower():
        tv_score += 3
    if re.search(r"\brsi\b", text.lower()):
        tv_score += 2
    if re.search(r"\bmacd\b", text.lower()):
        tv_score += 2
    if re.search(r"\bema\d+", text_lower) or re.search(r"ema\s*20", text.lower()):
        tv_score += 2
    if re.search(r"\b1d\b|\b4h\b|\b1w\b", text.lower()):
        tv_score += 1

    tv_score += _tradingview_image_score(image)

    if len(image.shape) == 3:
        top = image[0 : image.shape[0] // 8, :]
        if np.mean(top[:, :, 1]) > np.mean(top[:, :, 0]) + 10:
            webull_score += 1.5

    return webull_score, tv_score


def detect_platform(text: str, image: Optional[np.ndarray] = None) -> str:
    """
    Platform from layout only (never ticker name). No overrides.
    Adjusted | OHLC bar | MA MA5 => Webull always.
    """
    _ = image  # layout-only; image heuristics intentionally disabled
    if is_webull_layout_text(text):
        return "Webull"
    return "TradingView"


def parse_float(
    patterns: list[str],
    text: str,
    *,
    case_sensitive: bool = False,
) -> Optional[float]:
    flags = 0 if case_sensitive else re.IGNORECASE
    for pat in patterns:
        m = re.search(pat, text, flags)
        if m:
            try:
                val = m.group(1).replace(",", "")
                value = float(val)
            except (ValueError, IndexError):
                continue
            if _is_percent_value(text, m.group(1), value):
                continue
            return value
    return None


def validate_ticker(ticker: Optional[str]) -> str:
    """2–5 uppercase letters; reject chart UI blacklist."""
    if not ticker:
        return "unknown"
    ticker = ticker.strip().upper()
    if ticker in _TICKER_BLACKLIST:
        return "unknown"
    if ticker.startswith("MA") and len(ticker) <= 4:
        return "unknown"
    if re.fullmatch(r"[A-Z]{2,5}", ticker):
        return ticker
    return "unknown"


def _ticker_noise_token(token: str) -> bool:
    """True when OCR token is chart UI garbage (e.g. FVS, HB from toolbar)."""
    if token in _TICKER_BLACKLIST:
        return True
    for frag in ("VS", "TPO", "BB", "MACD", "BOLL", "VWAP", "OHLC"):
        if len(token) > len(frag) and frag in token:
            return True
    if token.endswith("VS") and len(token) > 2:
        return True
    return False


def _line_title_score(line: str) -> int:
    """Higher = more likely Webull title row (TICKER Company 1 minute Adjusted)."""
    score = 0
    low = line.lower()
    if "adjusted" in low:
        score += 5
    if re.search(r"\d\s*min|minute", low):
        score += 4
    if re.search(r"corp|inc|llc|etf|trust|therapeutics|street|average", low):
        score += 3
    if re.search(r"science|apple|silexion|ocugen|spdr|dow", low):
        score += 2
    return score


def extract_ticker(header_text: str, _body_text: str = "") -> str:
    """
    Ticker from top-header OCR only. Prefer title row (minute/Adjusted/company).
    Webull: TICKER Company Name 1 minute Adjusted.
    """
    header = (header_text or "").strip()
    if not header:
        return "unknown"

    qm = re.search(r"Q\.?\s*([A-Z]{2,5})\b", header, re.I)
    if qm:
        ticker = validate_ticker(qm.group(1))
        if ticker != "unknown":
            return ticker

    lines = [ln.strip() for ln in header.splitlines() if ln.strip()]
    ranked = sorted(lines, key=_line_title_score, reverse=True)
    for line in ranked:
        if _line_title_score(line) < 2:
            continue
        for match in re.finditer(r"\b([A-Z]{2,5})\b", line):
            token = match.group(1)
            if _ticker_noise_token(token):
                continue
            ticker = validate_ticker(token)
            if ticker != "unknown":
                return ticker

    for line in ranked:
        for match in re.finditer(r"\b([A-Z]{2,5})([A-Z][a-z]{2,}|[a-z]{3,})", line):
            token = match.group(1)
            if not _ticker_noise_token(token):
                ticker = validate_ticker(token)
                if ticker != "unknown":
                    return ticker
        for match in re.finditer(r"\b([A-Z]{2,5})\s+[A-Za-z]{2,}", line):
            token = match.group(1)
            if not _ticker_noise_token(token):
                ticker = validate_ticker(token)
                if ticker != "unknown":
                    return ticker

    for match in re.finditer(r"\b([A-Z]{2,5})\b", header):
        token = match.group(1)
        if _ticker_noise_token(token):
            continue
        ticker = validate_ticker(token)
        if ticker != "unknown":
            return ticker

    return "unknown"


def extract_locked_c_close(text: str) -> tuple[Optional[float], bool]:
    """Price from OHLC C value. Locks when found."""
    compact = _RE_OHLC_COMPACT.search(text)
    if compact:
        try:
            close = float(compact.group(4).replace(",", "."))
            if _is_plausible_price(close):
                return round(close, 4), True
        except (TypeError, ValueError):
            pass

    best: Optional[float] = None
    for match in _RE_C_CLOSE.finditer(text):
        try:
            raw = match.group(1) or match.group(2)
            if not raw:
                continue
            price = float(str(raw).replace(",", "."))
        except (TypeError, ValueError, IndexError):
            continue
        snippet = text[max(0, match.start() - 50) : match.end() + 50]
        if _RE_MA_MA5_LABEL.search(snippet) or re.search(r"mamas\d", snippet, re.I):
            continue
        if _is_ma_period_price_false_positive(snippet, price):
            continue
        if _is_timeframe_unit_false_positive(snippet, price):
            continue
        if not _is_plausible_price(price):
            continue
        if re.search(r"[\d.,]+H[\d.,]+L[\d.,]+", snippet, re.I) or re.search(
            r"\b[OH]\s*[\d.,]", snippet, re.I
        ):
            return round(price, 4), True
        if price < 50 and (best is None or price > best):
            best = price
    if best is not None:
        return round(best, 4), True
    return None, False


def _price_near_locked_ma5(text: str, ma5: float) -> Optional[float]:
    """When OHLC C is missing, pick header decimal closest to OCR MA5 (e.g. PAPL MAS5-1.089)."""
    anchor = float(ma5)
    candidates: list[float] = []
    for raw in re.findall(r"\b\d+[\.,]\d{2,4}\b", text[:2500]):
        try:
            value = float(raw.replace(",", "."))
        except ValueError:
            continue
        if _is_plausible_price(value, anchor) and abs(value - anchor) / anchor <= 0.08:
            candidates.append(value)
    if not candidates:
        return None
    return round(min(candidates, key=lambda v: abs(v - anchor)), 4)


def _ma5_period_label_false_positive(raw: str, value: float) -> bool:
    """Reject MA period integers (5/10/20) when OCR meant MAS5 label, not MA5 value."""
    raw_s = str(raw).strip()
    if value in {5.0, 10.0, 20.0} and "." not in raw_s and "," not in raw_s:
        return True
    return False


def _parse_ma5_match(raw: str) -> Optional[float]:
    try:
        value = float(str(raw).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if _ma5_period_label_false_positive(raw, value):
        return None
    if _is_plausible_price(value):
        return round(value, 4)
    return None


def extract_locked_ma5(text: str) -> tuple[Optional[float], bool]:
    """MA5 from labeled MA / MAS5 / MAS row. Locks when found."""
    for pattern in _MA5_VALUE_PATTERNS:
        for match in re.finditer(pattern, text, re.I):
            value = _parse_ma5_match(match.group(1))
            if value is not None:
                return value, True

    for line in text.splitlines():
        if not re.search(r"mas5|ma5s?|mass|mamas|ma\s+mas\b", line, re.I):
            continue
        for pattern in _MA5_VALUE_PATTERNS[:5]:
            match = re.search(pattern, line, re.I)
            if not match:
                continue
            value = _parse_ma5_match(match.group(1))
            if value is not None:
                return value, True
    return None, False


def parse_timeframe(text: str, default: str = "1min") -> str:
    """Parse chart timeframe from OCR text."""
    # Webull mobile shows this bottom row; selected button can OCR as "1 min".
    if re.search(r"1\s*min", text, re.I) and re.search(r"daily", text, re.I):
        return "1min"
    if re.search(r"\b(?:amine|4mine|imine|lmin|imin)\b", text, re.I) and re.search(r"daily|weekly|monthly", text, re.I):
        return "1min"
    if all(re.search(word, text, re.I) for word in ("daily", "weekly", "month")):
        return "1min"

    patterns = [
        (r"\b1\s*min\b|\b1m\b(?!\w)", "1min"),
        (r"\b5\s*min\b|\b5m\b", "5min"),
        (r"\b15\s*min\b|\b15m\b", "15min"),
        (r"\b1\s*h\b|\b1h\b|\b60\b", "1h"),
        (r"\b4\s*h\b|\b4h\b", "4h"),
        (r"\b1\s*d\b|\b1d\b|\bdaily\b", "1D"),
        (r"\b1\s*w\b|\b1w\b|\bweekly\b", "1W"),
        (r"\bmonthly\b", "1M"),
    ]
    for pat, label in patterns:
        if re.search(pat, text, re.I):
            return label
    return default


def _parse_webull_desktop_ma(period: int, text: str) -> tuple[Optional[float], bool]:
    """Desktop Webull strip: MA MA5 297.81 (exact label before value)."""
    patterns = [
        rf"ma\s+ma\s*{period}\s+(\d+(?:[.,]\d+)?)",
        rf"ma\s+ma{period}\s+(\d+(?:[.,]\d+)?)",
        rf"ma\s*ma\s*{period}\s*[:：]?\s*(\d+(?:[.,]\d+)?)",
    ]
    if period == 5:
        locked_ma5, ok = extract_locked_ma5(text)
        if ok and locked_ma5 is not None:
            return locked_ma5, True
        patterns.extend(
            [
                r"ma\s+mas\s+(\d+(?:[.,]\d+)?)",
                r"ma\s*mas\s+(\d+(?:[.,]\d+)?)",
                r"mamas\s+(\d+(?:[.,]\d+)?)",
            ]
        )
    if period == 10:
        patterns.append(r"ma\s*10\s+(\d+(?:[.,]\d+)?)")
    if period == 20:
        patterns.append(r"ma\s*20\s+(\d+(?:[.,]\d+)?)")

    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        try:
            value = float(match.group(1).replace(",", "."))
        except ValueError:
            continue
        if _is_plausible_price(value):
            return round(value, 4), True
    return None, False


def _parse_webull_ma_line_triple(text: str) -> tuple[Optional[float], Optional[float], Optional[float], bool]:
    """
    Parse one indicator row: MA MA5 297.81 MA10 296.50 MA20 295.20
    Tolerates OCR like MAMAS / MAS for MA5.
    """
    row_match = re.search(
        r"(?:ma\s*)?(?:ma\s*)?(?:mas|ma\s*5|ma5|mamas)\s*(\d{1,5}(?:[.,]\d+)?)"
        r".{0,40}?(?:ma\s*)?(?:ma\s*)?10\s*(\d{1,5}(?:[.,]\d+)?)"
        r".{0,40}?(?:ma\s*)?(?:ma\s*)?20\s*(\d{1,5}(?:[.,]\d+)?)",
        text,
        re.I | re.DOTALL,
    )
    if not row_match:
        return None, None, None, False

    values: list[float] = []
    for raw in row_match.groups():
        try:
            val = float(str(raw).replace(",", "."))
        except ValueError:
            return None, None, None, False
        if not _is_plausible_price(val):
            return None, None, None, False
        values.append(round(val, 4))

    if len(values) == 3:
        return values[0], values[1], values[2], True
    return None, None, None, False


def _parse_webull_ma_colon_values(text: str) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Parse mobile Webull MA row: MA(5,10,20) MA5:0.5789 MA10:0.5540 MA20:0.5295."""

    def _grab(period: str) -> Optional[float]:
        match = re.search(rf"ma\s*{period}\s*[:：]\s*(\d+(?:[.,]\d+)?)", text, re.I)
        if not match:
            return None
        try:
            value = float(match.group(1).replace(",", "."))
        except ValueError:
            return None
        return round(value, 4) if _is_plausible_price(value) else None

    return _grab("5"), _grab("10"), _grab("20")


def _parse_labeled_ma_ma5(text: str, *, mobile: bool = False) -> tuple[Optional[float], bool]:
    """MA MA5 labeled value — highest priority MA5 source."""
    value, locked = extract_locked_ma5(text)
    if locked:
        return value, True
    if mobile:
        colon = re.search(r"\bma\s*5\s*[:：]\s*(\d+(?:[.,]\d+)?)\b", text, re.I)
        if colon:
            try:
                v = float(colon.group(1).replace(",", "."))
                if _is_plausible_price(v):
                    return round(v, 4), True
            except (TypeError, ValueError):
                pass
    return None, False


def _parse_webull_ma_values(
    text: str,
) -> tuple[Optional[float], Optional[float], Optional[float], dict[str, bool]]:
    ma_from_ocr = {"ma5_from_ocr": False, "ma10_from_ocr": False, "ma20_from_ocr": False}

    labeled_ma5, labeled_locked = _parse_labeled_ma_ma5(text, mobile=is_mobile_webull_layout(text))
    if labeled_locked and labeled_ma5 is not None:
        ma_from_ocr["ma5_from_ocr"] = True
        ma10, ma10_locked = _parse_webull_desktop_ma(10, text)
        ma20, ma20_locked = _parse_webull_desktop_ma(20, text)
        ma_from_ocr["ma10_from_ocr"] = ma10_locked
        ma_from_ocr["ma20_from_ocr"] = ma20_locked
        return labeled_ma5, ma10, ma20, ma_from_ocr

    line5, line10, line20, line_locked = _parse_webull_ma_line_triple(text)
    if line_locked:
        ma_from_ocr["ma5_from_ocr"] = True
        ma_from_ocr["ma10_from_ocr"] = True
        ma_from_ocr["ma20_from_ocr"] = True
        return line5, line10, line20, ma_from_ocr

    ma5, ma5_locked = _parse_webull_desktop_ma(5, text)
    ma10, ma10_locked = _parse_webull_desktop_ma(10, text)
    ma20, ma20_locked = _parse_webull_desktop_ma(20, text)
    ma_from_ocr["ma5_from_ocr"] = ma5_locked
    ma_from_ocr["ma10_from_ocr"] = ma10_locked
    ma_from_ocr["ma20_from_ocr"] = ma20_locked

    colon5, colon10, colon20 = _parse_webull_ma_colon_values(text)
    if ma5 is None:
        ma5 = colon5
    if ma10 is None:
        ma10 = colon10
    if ma20 is None:
        ma20 = colon20
    if ma5 is not None and ma10 is not None and ma20 is not None and all(ma_from_ocr.values()):
        return ma5, ma10, ma20, ma_from_ocr

    if ma5 is not None and ma10 is not None and ma20 is not None and not any(ma_from_ocr.values()):
        return ma5, ma10, ma20, ma_from_ocr

    if ma5 is None:
        ma5 = parse_float(
            [
                r"ma\s*ma\s*5[:\s]+([\d.,]+)",
                r"ma\s*ma5[:\s]+([\d.,]+)",
                r"ma\s*5[:\s]+([\d.,]+)",
                r"5\s*day[:\s]*([\d.,]+)",
            ],
            text,
        )
    if ma10 is None:
        ma10 = parse_float(
            [r"ma\s*ma\s*10[:\s]+([\d.,]+)", r"ma\s*10[:\s]+([\d.,]+)", r"10\s*day[:\s]*([\d.,]+)"],
            text,
        )
    if ma20 is None:
        ma20 = parse_float(
            [r"ma\s*ma\s*20[:\s]+([\d.,]+)", r"ma\s*20[:\s]+([\d.,]+)", r"20\s*day[:\s]*([\d.,]+)"],
            text,
        )

    # Webull often OCRs "MA(5,10,20) 297.81 296.50 295.20" or "MA MA5 297.81".
    ma_rows = list(
        re.finditer(
            r"ma\s*(?:\(?\s*5\s*,\s*10\s*,\s*20\s*\)?|ma\s*5)[^\n]*",
            text,
            re.I,
        )
    )
    for ma_row in reversed(ma_rows):
        row = ma_row.group(0)
        if re.search(r"ma\s*5\s*[:：]", row, re.I):
            values = [
                v
                for v in _decimal_values(row)
                if _is_plausible_price(v) and round(v, 4) not in {5.0, 10.0, 20.0, 5.1, 10.2, 20.3}
            ]
        else:
            values = [v for v in _decimal_values(row) if _is_plausible_price(v)]
        if len(values) >= 3:
            ma5, ma10, ma20 = values[0], values[1], values[2]
            break
        if len(values) == 1 and ma5 is None:
            ma5 = values[0]

    return ma5, ma10, ma20, ma_from_ocr


def _refine_webull_ma_values(
    text: str,
    price: Optional[float],
    current: tuple[Optional[float], Optional[float], Optional[float]],
    ma_from_ocr: Optional[dict[str, bool]] = None,
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Prefer MA triples that are coherent with the current chart price."""
    if ma_from_ocr and any(ma_from_ocr.get(k) for k in ("ma5_from_ocr", "ma10_from_ocr", "ma20_from_ocr")):
        return current
    if price is None or price <= 0:
        return current

    candidates: list[tuple[float, float, float]] = []
    for ma_row in re.finditer(r"ma\s*\(?\s*5\s*,\s*10\s*,\s*20\s*\)?[^\n]*", text, re.I):
        values = [v for v in _decimal_values(ma_row.group(0)) if _is_plausible_price(v, price)]
        if len(values) >= 3:
            candidates.append((values[0], values[1], values[2]))

    if not candidates:
        return current

    return min(candidates, key=lambda vals: sum(abs(v - price) for v in vals))


def _is_ma_period_price_false_positive(context: str, price: float) -> bool:
    """Reject MA(5,10,20) period numbers misread as close price (e.g. 5.1 from '5,10')."""
    ctx = context.lower()
    if re.search(r"ma\s*[\(\[]?\s*5\s*,\s*10", ctx, re.I):
        return True
    if price in {5.0, 5.1, 10.0, 10.2, 20.0, 20.3} and re.search(r"\bma\b|\bvy\b", ctx, re.I):
        return True
    return False


def _is_timeframe_unit_false_positive(context: str, price: float) -> bool:
    """Reject '1 minute' / '1 min' OCR noise misread as price (e.g. 1.0 or 1.5)."""
    if price not in {1.0, 1.5}:
        return False
    return bool(re.search(r"\b1\s*min(?:ute)?\b", context, re.I))


def _extract_webull_c_close(text: str) -> Optional[float]:
    """Primary Webull price: C <value> from OHLC bar."""
    price, _locked = extract_locked_c_close(text)
    return price


def _extract_webull_ohlc_close(text: str) -> Optional[float]:
    """Parse close from desktop OHLC bar: O 298 H 299 L 297 C 297.91."""
    match = re.search(
        r"\bO\s*(\d{1,5}(?:[.,]\d{1,4})?)\s+"
        r"H\s*(\d{1,5}(?:[.,]\d{1,4})?)\s+"
        r"L\s*(\d{1,5}(?:[.,]\d{1,4})?)\s+"
        r"C\s*(\d{1,5}(?:[.,]\d{1,4})?)\b",
        text,
        re.I,
    )
    if not match:
        return None
    try:
        close = float(match.group(4).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return round(close, 4) if _is_plausible_price(close) else None


def _extract_webull_close_price(text: str, header_text: str = "") -> Optional[float]:
    """Parse Webull top-bar close/current price — always prefer C <value>."""
    for source in (header_text, text, f"{header_text}\n{text}"):
        if not source.strip():
            continue
        c_close = _extract_webull_c_close(source)
        if c_close is not None:
            return c_close
        ohlc_close = _extract_webull_ohlc_close(source)
        if ohlc_close is not None:
            return ohlc_close
        for match in re.finditer(r"\bC\s+(\d+(?:\.\d+)?)\b", source, re.I):
            try:
                price = float(match.group(1).replace(",", "."))
            except (TypeError, ValueError):
                continue
            snippet = source[max(0, match.start() - 30) : match.end() + 30]
            if _is_ma_period_price_false_positive(snippet, price):
                continue
            if _is_plausible_price(price):
                return round(price, 4)
    combined = f"{header_text}\n{text}"
    patterns = [
        (r"\bClose\s*(\d{1,5}(?:[.,]\d{1,4})?)\b", False),
        (r"\$\s*(\d{1,5}(?:[.,]\d{1,4})?)\b", False),
        (r"(?:price|last)[:\s]*\$?(\d{1,5}(?:[.,]\d{1,4})?)\b", False),
    ]
    for pattern, case_sensitive in patterns:
        flags = 0 if case_sensitive else re.IGNORECASE
        for match in re.finditer(pattern, combined, flags):
            raw = match.group(1)
            try:
                price = float(str(raw).replace(",", "."))
            except (TypeError, ValueError):
                continue
            snippet = combined[max(0, match.start() - 30) : match.end() + 30]
            if _is_ma_period_price_false_positive(snippet, price):
                continue
            if _is_plausible_price(price):
                return round(price, 4)
    return None


def _confirm_ocr_readings(
    data: dict[str, Any],
    merged_text: str,
    header_text: str = "",
    image: Optional[np.ndarray] = None,
) -> dict[str, Any]:
    """Log exact OCR price/MA5 and re-read header if they diverge by >20%."""
    price = data.get("price")
    ma5 = data.get("ma5")
    print("\n===== OCR CONFIRM: exact values read =====")
    print(f"  price: {price}")
    print(f"  ma5:   {ma5}")
    print(f"  price_from_header: {data.get('price_from_ocr_header')}")
    print(f"  ma5_from_ocr: {data.get('ma5_from_ocr')}")
    print("===== END OCR CONFIRM =====\n")

    if price is None or ma5 is None or float(price) <= 0:
        return data

    diff_pct = abs(float(price) - float(ma5)) / float(price)
    if diff_pct <= 0.20:
        return data

    print("===== OCR RE-READ: price vs MA5 differ by >20%, re-parsing header =====")
    retry_header = header_text
    if image is not None:
        retry_header = extract_webull_header_text(image) or header_text

    retry_close = _extract_webull_close_price(merged_text, retry_header)
    retry_ma5, retry_locked = _parse_webull_desktop_ma(5, f"{retry_header}\n{merged_text}")
    if retry_close is not None:
        data["price"] = retry_close
        data["price_from_ocr_header"] = True
    if retry_ma5 is not None and retry_locked:
        data["ma5"] = retry_ma5
        data["ma5_from_ocr"] = True
    print(f"  after re-read price: {data.get('price')} ma5: {data.get('ma5')}")
    print("===== END OCR RE-READ =====\n")
    return data


def _select_webull_price(text: str, parsed_price: Optional[float], ma5: Optional[float], ma10: Optional[float], ma20: Optional[float]) -> Optional[float]:
    """Choose Webull's current price near the MA cluster / price box (not sample defaults)."""
    c_close = _extract_webull_c_close(text)
    if c_close is not None:
        return c_close

    anchor = None
    ma_values = [float(v) for v in (ma5, ma10, ma20) if v is not None]
    if ma_values:
        anchor = ma5 if ma5 is not None else sum(ma_values) / len(ma_values)

    values = [v for v in _decimal_values(text) if _is_plausible_price(v, anchor)]
    if anchor and anchor >= 10:
        large_cap = [v for v in values if v >= max(10.0, anchor * 0.4)]
        if large_cap:
            values = large_cap
    if not values:
        return validate_price(parsed_price, text)

    boxed_match = re.search(r"[-–—]{2,}\s*(\d[\.,]\d{1,4})\s*[-–—]*", text)
    if boxed_match:
        try:
            boxed = round(float(boxed_match.group(1).replace(",", ".")), 4)
            if _is_plausible_price(boxed, anchor):
                return boxed
        except ValueError:
            pass

    candidates = [
        v
        for v in values
        if not _near_any_ma(v, ma_values)
        and not _value_in_ma_label_context(v, text)
        and not re.search(rf"(?<!\d){re.escape(f'{v:g}')}\s*%", text)
    ]

    if candidates:
        return round(candidates[0], 4)

    if parsed_price is not None and _is_plausible_price(float(parsed_price), anchor):
        return round(float(parsed_price), 4)
    if candidates:
        return round(candidates[0], 4)
    return validate_price(parsed_price, text)


def _left_chart_edge_prices(image: np.ndarray) -> set[float]:
    """High/low labels on the left of the chart (not the current price on mobile)."""
    left_text = _ocr_region(image, 0.12, 0.88, 0.0, 0.42)
    return {round(v, 4) for v in _decimal_values(left_text) if _is_plausible_price(v)}


def _extract_webull_mobile_price_box(
    image: np.ndarray,
    ma5: Optional[float],
    ma10: Optional[float],
    ma20: Optional[float],
) -> Optional[float]:
    """Current price from the boxed value on the right (mobile Webull layout)."""
    ma_values = _ma_values_list(ma5, ma10, ma20)
    anchor = ma5 if ma5 is not None else (sum(ma_values) / len(ma_values) if ma_values else None)
    left_prices = _left_chart_edge_prices(image)

    # Tightest crops first — current price box, not the MA strip above it.
    for y0, y1, x0, x1 in (
        (0.32, 0.62, 0.72, 0.98),
        (0.20, 0.78, 0.68, 0.98),
        (0.25, 0.72, 0.72, 0.96),
        (0.30, 0.65, 0.70, 0.95),
    ):
        region_text = _ocr_region(image, y0, y1, x0, x1)
        for value in _decimal_values(region_text):
            if not _is_plausible_price(value, anchor):
                continue
            rounded = round(value, 4)
            if _near_any_ma(rounded, ma_values):
                continue
            if rounded in left_prices:
                continue
            if rounded in {5.0, 10.0, 20.0}:
                continue
            if anchor and anchor < 10 and (
                rounded > max(ma_values) * 1.2 or rounded < min(ma_values) * 0.75
            ):
                continue
            return rounded
    return None


def _ocr_price_box_digits(
    image: np.ndarray,
    y0: float,
    y1: float,
    x0: float,
    x1: float,
) -> list[float]:
    """Digits-only OCR on a relative crop (current price box on the right)."""
    if image is None or len(image.shape) != 3:
        return []
    h, w = image.shape[:2]
    roi = image[int(h * y0) : int(h * y1), int(w * x0) : int(w * x1)]
    if roi.size == 0:
        return []

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    enlarged = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    processed = cv2.threshold(enlarged, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    try:
        text = pytesseract.image_to_string(
            Image.fromarray(processed),
            config="--psm 6 -c tessedit_char_whitelist=0123456789.",
        )
    except Exception:
        return []
    return [v for v in _decimal_values(text) if _is_plausible_price(v)]


def _ocr_highlight_roi_digits(roi: np.ndarray) -> list[float]:
    """OCR a small colored highlight patch (Y-axis current price label)."""
    if roi.size == 0:
        return []
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    enlarged = cv2.resize(gray, None, fx=4.0, fy=4.0, interpolation=cv2.INTER_CUBIC)
    processed = cv2.threshold(enlarged, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    try:
        text = pytesseract.image_to_string(
            Image.fromarray(processed),
            config="--psm 7 -c tessedit_char_whitelist=0123456789.",
        )
    except Exception:
        return []
    return [v for v in _decimal_values(text) if _is_plausible_price(v)]


def _extract_webull_yaxis_highlight_price(
    image: np.ndarray,
    ma_values: list[float],
) -> Optional[float]:
    """
    Read current price from the colored label on the right Y-axis (Webull desktop).
    The live price is shown in a red highlight box, separate from MA values in the top strip.
    """
    if image is None or len(image.shape) != 3:
        return None

    h, w = image.shape[:2]
    right = image[:, int(w * 0.82) :]
    if right.size == 0:
        return None

    b, g, r = cv2.split(right)
    red_mask = (
        (r > 120) & (g < 90) & (b < 90) & (r.astype(np.int16) - g.astype(np.int16) > 25)
    ).astype(np.uint8) * 255

    contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[tuple[float, int]] = []

    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        if bw * bh < 200 or bh < 8 or bw < 15:
            continue
        for value in _ocr_highlight_roi_digits(right[y : y + bh, x : x + bw]):
            rounded = round(value, 4)
            if ma_values and _near_any_ma(rounded, ma_values):
                continue
            candidates.append((rounded, bw * bh))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[1], reverse=True)
    return candidates[0][0]


def _extract_webull_right_price(
    image: Optional[np.ndarray],
    *,
    exclude_ma: Optional[list[float]] = None,
    anchor: Optional[float] = None,
) -> Optional[float]:
    """
    OCR the right-side current price box (desktop/mobile).
    Never returns a value that matches an MA line — MA strip is above this region.
    """
    if image is None or len(image.shape) != 3:
        return None

    ma_values = list(exclude_ma or [])
    ref = anchor if anchor is not None else (sum(ma_values) / len(ma_values) if ma_values else None)

    # Tight crops on the right price box first, then broader fallbacks.
    for y0, y1, x0, x1 in (
        (0.32, 0.58, 0.75, 0.98),
        (0.28, 0.62, 0.72, 0.98),
        (0.30, 0.52, 0.72, 1.0),
        (0.12, 0.88, 0.68, 1.0),
    ):
        for value in _ocr_price_box_digits(image, y0, y1, x0, x1):
            rounded = round(value, 4)
            if ma_values and _near_any_ma(rounded, ma_values):
                continue
            if ref is not None and not _is_plausible_price(rounded, ref):
                continue
            return rounded
    return None


def parse_webull(
    text: str,
    image: Optional[np.ndarray] = None,
    header_text: str = "",
    ticker_header_text: str = "",
) -> dict[str, Any]:
    data: dict[str, Any] = {"platform": "Webull"}
    merged_text = f"{header_text}\n{text}".strip()
    mobile_layout = is_mobile_webull_layout(merged_text)

    price, price_from_c_close = extract_locked_c_close(merged_text)
    price_from_header = price_from_c_close
    price_from_mobile_box = False
    price_from_right_box = False
    price_from_axis_highlight = False

    ma5, ma5_from_ocr = extract_locked_ma5(merged_text)
    if not ma5_from_ocr and mobile_layout:
        ma5, ma5_from_ocr = _parse_labeled_ma_ma5(merged_text, mobile=True)

    ma_flags = {
        "ma5_from_ocr": ma5_from_ocr,
        "ma10_from_ocr": False,
        "ma20_from_ocr": False,
    }
    ma10, ma20 = None, None
    if not ma5_from_ocr:
        ma5, ma10, ma20, ma_flags = _parse_webull_ma_values(merged_text)
        if ma5 is None and image is not None:
            ma_strip_text = extract_webull_ma_strip_text(image)
            if ma_strip_text.strip():
                merged_text = f"{merged_text}\n{ma_strip_text}"
                ma5, ma10, ma20, ma_flags = _parse_webull_ma_values(merged_text)

    pipeline_log(f"[OCR] MA5 read from screenshot: {ma5}")
    pipeline_log(f"[OCR] ma5_from_ocr flag: {ma_flags.get('ma5_from_ocr')}")

    ma_list = _ma_values_list(ma5, ma10, ma20)

    if not price_from_c_close:
        if mobile_layout and image is not None:
            mobile_price = _extract_webull_mobile_price_box(image, ma5, ma10, ma20)
            if mobile_price is not None:
                price = mobile_price
                price_from_mobile_box = True
            else:
                price = _extract_webull_right_price(image, exclude_ma=ma_list, anchor=ma5)
                if price is not None:
                    price_from_right_box = True
        elif image is not None:
            axis_price = _extract_webull_yaxis_highlight_price(image, ma_list)
            if axis_price is not None:
                price = axis_price
                price_from_axis_highlight = True
        if price is None:
            price = _select_webull_price(merged_text, None, ma5, ma10, ma20)

    if (
        not price_from_c_close
        and ma5_from_ocr
        and ma5 is not None
        and price is not None
        and (
            float(price) <= 1.01
            or abs(float(price) - float(ma5)) / max(float(ma5), 0.01) > 0.25
        )
    ):
        near_ma5 = _price_near_locked_ma5(merged_text, float(ma5))
        if near_ma5 is not None:
            price = near_ma5
            price_from_header = True

    if not ma5_from_ocr:
        ma5, ma10, ma20 = _refine_webull_ma_values(merged_text, price, (ma5, ma10, ma20), ma_flags)

    change_m = re.search(r"([+-]\s*\d+(?:[\.,]\d+)?)\s*%", text)
    if not change_m:
        change_m = re.search(r"(\d+(?:[\.,]\d+)?)\s*%", text)
    change_pct = float(change_m.group(1).replace(" ", "").replace(",", ".")) if change_m else None

    vol_m = re.search(r"(?:vol|volume)[:\s]*([\d,.]+[KMB]?)", text, re.I)
    volume = vol_m.group(1) if vol_m else None
    volume_spike = bool(re.search(r"high\s*vol|volume\s*spike|vol.*high", text, re.I))

    ticker = extract_ticker((ticker_header_text or "").strip())

    data.update(
        {
            "price": price,
            "price_from_ocr_header": price_from_header,
            "price_from_ocr_c_close": price_from_c_close,
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "rsi_from_ocr": False,
            "macd_from_ocr": False,
            "change_pct": change_pct,
            "volume": volume,
            "volume_spike": volume_spike,
            "timeframe": parse_timeframe(merged_text if mobile_layout else text, "1min"),
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
            "mobile_layout": mobile_layout,
            "price_from_mobile_box": price_from_mobile_box,
            "price_from_right_box": price_from_right_box,
            "price_from_axis_highlight": price_from_axis_highlight,
            **ma_flags,
        }
    )
    data = _confirm_ocr_readings(data, merged_text, header_text, image)
    data = apply_ma_validation(data, merged_text)
    pipeline_log(f"[OCR] MA5 after parse_webull validation: {data.get('ma5')}")
    return data


def parse_tradingview(text: str, header_text: str = "") -> dict[str, Any]:
    """Parse TradingView dark/light theme chart screenshots."""
    merged = f"{header_text}\n{text}".strip()
    if has_webull_adjusted_header(merged) or is_webull_layout_text(merged):
        return parse_webull(text, None, header_text, header_text)

    data: dict[str, Any] = {"platform": "TradingView"}

    c_close = _extract_webull_c_close(merged)
    price = c_close
    if price is None:
        price = parse_float(
            [
                r"(?:price|close|last|open)\b[:\s]*([\d.,]+)",
                r"\bO\s+([\d.,]+)\b",
                r"\bH\s+([\d.,]+)\b",
                r"\bL\s+([\d.,]+)\b",
                r"\bC\s+([\d.,]+)\b",
            ],
            text,
            case_sensitive=True,
        )
    if price is None:
        ocr_prices = [v for v in _decimal_values(text) if _is_plausible_price(v)]
        if ocr_prices:
            # Prefer the dominant price cluster (avoids spurious OCR like 40 from "1O40").
            under_10 = [v for v in ocr_prices if v < 10]
            over_50 = [v for v in ocr_prices if v >= 50]
            if len(under_10) >= 2:
                price = max(under_10)
            elif len(over_50) >= 2:
                price = max(over_50)
            else:
                price = max(ocr_prices)
    price = validate_price(price, text)

    rsi = parse_float(
        [
            r"rsi[:\s(]*([\d.]+)",
            r"rsi\s*14[:\s]*([\d.]+)",
            r"rsi\s*\d+\s*([\d.]+)",
        ],
        text,
    )
    if rsi is None and re.search(r"rsi", text, re.I):
        rsi_candidates = [
            float(raw)
            for raw in re.findall(r"\b(\d{2}\.\d)\b", text)
            if not re.search(rf"{re.escape(raw)}\s*%", text)
        ]
        plausible = [value for value in rsi_candidates if 20 <= value <= 90]
        if plausible:
            rsi = plausible[0]

    ma5 = parse_float(
        [
            r"ema\s*5[:\s]*([\d.]+)",
            r"ma\s*5[:\s]*([\d.]+)",
            r"ema5[:\s]*([\d.]+)",
        ],
        text,
    )
    ma10 = parse_float(
        [
            r"ema\s*10[:\s]*([\d.]+)",
            r"ma\s*10[:\s]*([\d.]+)",
            r"ema10[:\s]*([\d.]+)",
        ],
        text,
    )
    ema20 = parse_float(
        [
            r"ema\s*20[:\s]*([\d.]+)",
            r"ema20[:\s]*([\d.]+)",
        ],
        text,
    )
    ema = parse_float([r"ema[:\s]*([\d.]+)", r"ema\s*\d+[:\s]*([\d.]+)"], text) or ema20
    sma = parse_float([r"sma[:\s]*([\d.]+)", r"sma\s*\d+[:\s]*([\d.]+)"], text)
    ma20 = parse_float([r"ma\s*20[:\s]*([\d.]+)", r"ma20[:\s]*([\d.]+)"], text) or ema20 or ema

    change_m = re.search(r"([+-]?[\d.]+)\s*%", text)
    change_pct = float(change_m.group(1)) if change_m else None

    macd_visible = bool(re.search(r"\bmacd\b", text, re.I))
    macd_bullish = bool(re.search(r"macd.*bull|bullish.*macd|macd\s*bull", text, re.I))
    macd_bearish = bool(re.search(r"macd.*bear|bearish.*macd|macd\s*bear", text, re.I))
    if re.search(r"\bmacd\b", text, re.I) and not macd_bearish and rsi and rsi > 50:
        macd_bullish = True

    vol_m = re.search(r"(?:vol|volume)[:\s]*([\d,.]+[KMB]?|high|low)", text, re.I)
    volume = vol_m.group(1) if vol_m else None
    volume_spike = bool(
        re.search(r"high\s*vol|volume.*high|vol.*spike|volume:\s*high", text, re.I)
        or (volume and str(volume).lower() == "high")
    )

    data.update(
        {
            "price": price,
            "ma5": ma5,
            "ma10": ma10,
            "rsi": rsi,
            "rsi_from_ocr": rsi is not None and bool(re.search(r"rsi", text, re.I)),
            "ema": ema,
            "ema20": ema20 or ema,
            "sma": sma,
            "ma20": ma20,
            "change_pct": change_pct,
            "macd_bullish": macd_bullish,
            "macd_bearish": macd_bearish,
            "macd_from_ocr": macd_visible and (macd_bullish or macd_bearish),
            "volume": volume,
            "volume_spike": volume_spike,
            "timeframe": parse_timeframe(text, "1D"),
            "ticker": extract_ticker(header_text),
            "timestamp": datetime.now().isoformat(),
        }
    )
    return apply_ma_validation(data, text)


def finalize_parsed(parsed: dict[str, Any], platform: str, raw_text: str = "") -> dict[str, Any]:
    """Validate OCR fields only — never inject hardcoded sample chart values."""
    if has_webull_adjusted_header(raw_text):
        platform = "Webull"
        parsed["platform"] = "Webull"
    if platform == "TradingView":
        if parsed.get("ma20") is None and parsed.get("ema20"):
            parsed["ma20"] = parsed["ema20"]
        if parsed.get("ma5") is None and parsed.get("ema5"):
            parsed["ma5"] = parsed["ema5"]
        if parsed.get("ma10") is None and parsed.get("ema10"):
            parsed["ma10"] = parsed["ema10"]
        if parsed.get("macd_bullish"):
            parsed["macd_cross"] = "bullish"
        elif parsed.get("macd_bearish"):
            parsed["macd_cross"] = "bearish"

    parsed.setdefault("platform", platform)
    parsed.setdefault("timestamp", datetime.now().isoformat())
    parsed = apply_ma_validation(parsed, raw_text)
    parsed["ocr_confidence"] = _ocr_confidence(parsed)
    return parsed


def _ocr_confidence(parsed: dict[str, Any]) -> float:
    platform = parsed.get("platform", "Webull")
    if platform == "TradingView":
        required = ["price", "rsi", "ma20"]
    else:
        required = ["price", "ma5", "ma10", "ma20"]
    found = sum(1 for k in required if parsed.get(k) is not None)
    return round(found / len(required) * 100, 1)


def parse_screenshot(image_bytes: bytes | np.ndarray) -> dict[str, Any]:
    """Main entry: load image, preprocess, OCR, detect platform, parse fields."""
    if isinstance(image_bytes, np.ndarray):
        image = image_bytes.copy()
    else:
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image. Use PNG, JPG, or JPEG.")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    raw_standard = extract_text(preprocess_image(image))
    raw_gray = extract_text(gray)
    raw_webull_regions = extract_webull_region_text(image)
    raw_webull_header = extract_webull_header_text(image)
    raw_ticker_header = extract_webull_ticker_header_text(image)
    raw_webull_ma_strip = extract_webull_ma_strip_text(image)
    raw_mobile_regions = extract_mobile_webull_region_text(image)
    combined_text = "\n".join(
        t
        for t in (
            raw_standard,
            raw_gray,
            raw_webull_header,
            raw_webull_ma_strip,
            raw_webull_regions,
            raw_mobile_regions,
        )
        if t.strip()
    )

    platform = detect_platform(combined_text, image)

    _debug_log_ocr(combined_text, raw_webull_header, raw_webull_regions)

    ticker_header = raw_ticker_header
    if platform == "Webull":
        parsed = parse_webull(
            combined_text,
            image,
            raw_webull_header,
            ticker_header,
        )
    else:
        parsed = parse_tradingview(combined_text, raw_webull_header)
        parsed["ticker"] = extract_ticker(ticker_header) or parsed.get("ticker", "unknown")

    parsed["platform"] = detect_platform(combined_text, image)
    platform = parsed["platform"]
    parsed["raw_ocr_text"] = combined_text[:2000]
    parsed["tesseract_available"] = bool(combined_text.strip())
    parsed = finalize_parsed(parsed, platform, combined_text)
    pipeline_log(f"[OCR] MA5 leaving parse_screenshot: {parsed.get('ma5')}")
    if not combined_text.strip():
        parsed["ocr_note"] = "Tesseract not installed or no text detected; OCR fields may be empty"
    return parsed
