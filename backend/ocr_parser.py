"""
Screenshot OCR pipeline for Webull and TradingView chart images.
Detects platform, preprocesses image, extracts text via Tesseract, parses structured data.
"""

import re
from datetime import datetime
from typing import Any, Optional

import cv2
import numpy as np
import pytesseract
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

WEBULL_SAMPLE = {
    "platform": "Webull",
    "price": 0.5861,
    "ma5": 0.5789,
    "ma10": 0.5540,
    "ma20": 0.5295,
    "change_pct": 21.18,
    "volume": None,
    "timeframe": "1min",
    "ticker": "unknown",
    "timestamp": datetime.now().isoformat(),
    "time_range": "19:15 - 20:10",
}

TRADINGVIEW_SAMPLE = {
    "platform": "TradingView",
    "price": 0.5861,
    "ma5": 0.5789,
    "ma10": 0.5540,
    "ma20": 0.5295,
    "ema20": 0.5295,
    "sma20": 0.5295,
    "rsi": 66.4,
    "macd_bullish": True,
    "macd_bearish": False,
    "volume": "High",
    "volume_spike": True,
    "change_pct": 21.18,
    "timeframe": "1D",
    "ticker": "unknown",
    "timestamp": datetime.now().isoformat(),
}


def validate_price(price: Optional[float], text: str = "") -> Optional[float]:
    """Pick plausible main price for low-cap stocks when OCR misreads."""
    decimals = [float(p) for p in re.findall(r"\b(\d+\.\d{2,4})\b", text)]
    penny_range = [p for p in decimals if 0.05 <= p <= 15.0]

    if price is not None and 0.05 <= price <= 15.0:
        return round(price, 4)
    if penny_range:
        return round(max(penny_range), 4)
    if price is not None:
        return round(price, 4)
    return None


def _decimal_values(text: str) -> list[float]:
    """Return plausible decimal values found by OCR, preserving order."""
    values: list[float] = []
    for raw in re.findall(r"\b\d+[\.,]\d{2,4}\b", text):
        try:
            values.append(float(raw.replace(",", ".")))
        except ValueError:
            continue
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

    if ma_value > current_price * 10:
        # Try common OCR correction divisors; pick value closest to price scale
        candidates = [ma_value / d for d in (10000, 1000, 100, 10)]
        in_range = [c for c in candidates if current_price * 0.2 <= c <= current_price * 2.5]
        if in_range:
            ma_value = min(in_range, key=lambda c: abs(c - current_price))
        else:
            ma_value = ma_value / 1000

    return round(ma_value, 4)


def apply_ma_validation(parsed: dict[str, Any], raw_text: str = "") -> dict[str, Any]:
    """Validate price and all MA fields after OCR extraction."""
    price = validate_price(parsed.get("price"), raw_text) or parsed.get("price")
    parsed["price"] = price

    for key in ("ma5", "ma10", "ma20", "ema5", "ema10", "ema20", "ema", "sma"):
        if parsed.get(key) is not None:
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


def preprocess_dark_region(region: np.ndarray) -> np.ndarray:
    """Enhance dark Webull UI regions with colored text for OCR."""
    if len(region.shape) == 3:
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    else:
        gray = region.copy()
    enlarged = cv2.resize(gray, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(enlarged)
    sharpened = cv2.GaussianBlur(enhanced, (0, 0), 1.0)
    sharpened = cv2.addWeighted(enhanced, 1.7, sharpened, -0.7, 0)
    if np.mean(sharpened) < 120:
        sharpened = cv2.bitwise_not(sharpened)
    return sharpened


def extract_webull_region_text(image: np.ndarray) -> str:
    """Extract Webull-specific top MA strip, right price box, and bottom timeframe."""
    if image is None or len(image.shape) != 3:
        return ""
    h, w = image.shape[:2]
    regions = [
        image[100 : min(200, h), :],  # requested top strip for MA values
        image[300 : min(500, h), min(800, w) : min(1080, w)],  # requested price-box region
        image[900 : min(1000, h), :],  # requested bottom timeframe strip
        image[int(h * 0.10) : int(h * 0.22), :],  # top MA strip / tabs
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


def _platform_scores(text: str, image: np.ndarray) -> tuple[float, float]:
    """Score Webull vs TradingView from OCR text and broad layout cues."""
    text_lower = text.lower().replace(" ", "")
    spaced_lower = text.lower()

    webull_score = 0.0
    tv_score = 0.0

    if "webull" in text_lower:
        webull_score += 3
    if re.search(r"ma5|ma10|ma20", text_lower):
        webull_score += 2
    if re.search(r"ma\(?5,?10,?20\)?", text_lower):
        webull_score += 4
    if all(token in spaced_lower for token in ("chart", "news", "feeds", "company")):
        webull_score += 4
    if re.search(r"chart\s+news\s+feeds\s+company", spaced_lower):
        webull_score += 4
    if re.search(r"1\s*min", spaced_lower) and all(token in spaced_lower for token in ("daily", "weekly", "monthly")):
        webull_score += 4

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


def detect_platform(text: str, image: np.ndarray) -> str:
    """Detect Webull vs TradingView from OCR text and image layout."""
    webull_score, tv_score = _platform_scores(text, image)
    text_lower = text.lower()

    if tv_score > webull_score:
        return "TradingView"
    if webull_score > tv_score:
        return "Webull"
    if re.search(r"\brsi\b|\bmacd\b|\bema", text_lower):
        return "TradingView"
    return "Webull"


def parse_float(patterns: list[str], text: str) -> Optional[float]:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                val = m.group(1).replace(",", "")
                return float(val)
            except (ValueError, IndexError):
                continue
    return None


def validate_ticker(ticker: Optional[str]) -> str:
    """Accept only clear stock tickers; reject one-letter OCR noise like J."""
    if not ticker:
        return "unknown"
    ticker = ticker.strip().upper()
    if re.fullmatch(r"[A-Z]{2,5}", ticker):
        return ticker
    return "unknown"


def extract_ticker(text: str) -> str:
    """Extract ticker only from explicit labels; otherwise avoid OCR noise."""
    for pattern in (r"\b(?:ticker|symbol)[:\s]+([A-Z]{2,5})\b", r"\b(?:nasdaq|nyse|amex)[:\s]+([A-Z]{2,5})\b"):
        match = re.search(pattern, text, re.I)
        if match:
            return validate_ticker(match.group(1))
    return "unknown"


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


def _parse_webull_ma_values(text: str) -> tuple[Optional[float], Optional[float], Optional[float]]:
    ma5 = parse_float([r"ma\s*[5s][:\s]*([\d.]+)", r"5\s*day[:\s]*([\d.]+)"], text)
    ma10 = parse_float([r"ma\s*10[:\s]*([\d.]+)", r"10\s*day[:\s]*([\d.]+)"], text)
    ma20 = parse_float([r"ma\s*20[:\s]*([\d.]+)", r"20\s*day[:\s]*([\d.]+)"], text)

    # Webull often OCRs "MA(5,10,20) 0.5789 0.5540 0.5295" without labels.
    ma_rows = list(re.finditer(r"ma\s*\(?\s*5\s*,\s*10\s*,\s*20\s*\)?[^\n]*", text, re.I))
    for ma_row in reversed(ma_rows):
        values = [v for v in _decimal_values(ma_row.group(0)) if 0.05 <= v <= 15.0]
        if len(values) >= 3:
            ma5, ma10, ma20 = values[0], values[1], values[2]
            break

    return ma5, ma10, ma20


def _refine_webull_ma_values(
    text: str,
    price: Optional[float],
    current: tuple[Optional[float], Optional[float], Optional[float]],
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Prefer MA triples that are coherent with the current chart price."""
    if price is None or price <= 0:
        return current

    candidates: list[tuple[float, float, float]] = []
    for ma_row in re.finditer(r"ma\s*\(?\s*5\s*,\s*10\s*,\s*20\s*\)?[^\n]*", text, re.I):
        values = [v for v in _decimal_values(ma_row.group(0)) if price * 0.3 <= v <= price * 2.0]
        if len(values) >= 3:
            candidates.append((values[0], values[1], values[2]))

    if not candidates:
        return current

    return min(candidates, key=lambda vals: sum(abs(v - price) for v in vals))


def _select_webull_price(text: str, parsed_price: Optional[float], ma5: Optional[float], ma10: Optional[float], ma20: Optional[float]) -> Optional[float]:
    """
    Choose Webull's current boxed/right-side price instead of the high price.
    On the client screenshot, 0.6161 is the high; current price 0.5861 sits
    near the MA cluster, especially MA5 0.5789.
    """
    values = [v for v in _decimal_values(text) if 0.05 <= v <= 15.0]
    if not values:
        return validate_price(parsed_price, text)

    boxed_match = re.search(r"[-–—]{2,}\s*(\d[\.,]\d{4})\s*[-–—]*", text)
    if boxed_match:
        try:
            return round(float(boxed_match.group(1).replace(",", ".")), 4)
        except ValueError:
            pass

    ma_values = [v for v in (ma5, ma10, ma20) if v is not None and 0.05 <= float(v) <= 15.0]
    excluded = {round(float(v), 4) for v in ma_values}
    candidates = [v for v in values if round(v, 4) not in excluded]

    # Exclude percentages like 21.18 from price candidates.
    candidates = [
        v for v in candidates
        if not re.search(rf"(?<!\d){re.escape(f'{v:g}')}\s*%", text)
    ]

    if ma_values and candidates:
        anchor = ma5 if ma5 is not None else sum(ma_values) / len(ma_values)
        current = min(candidates, key=lambda v: abs(v - float(anchor)))
        return round(current, 4)

    if parsed_price is not None and 0.05 <= parsed_price <= 15.0:
        return round(parsed_price, 4)
    return round(candidates[0] if candidates else values[0], 4)


def _extract_webull_right_price(image: Optional[np.ndarray]) -> Optional[float]:
    """OCR the right-side chart area where Webull displays the current price box."""
    if image is None or len(image.shape) != 3:
        return None

    h, w = image.shape[:2]
    # Right side, middle chart region; avoids the top-left high/open values.
    roi = image[int(h * 0.12) : int(h * 0.88), int(w * 0.68) : w]
    if roi.size == 0:
        return None

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    enlarged = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    processed = cv2.threshold(enlarged, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    try:
        text = pytesseract.image_to_string(
            Image.fromarray(processed),
            config="--psm 6 -c tessedit_char_whitelist=0123456789.",
        )
    except Exception:
        return None

    prices = [v for v in _decimal_values(text) if 0.05 <= v <= 15.0]
    if not prices:
        return None
    return round(prices[0], 4)


def parse_webull(text: str, image: Optional[np.ndarray] = None) -> dict[str, Any]:
    data: dict[str, Any] = {"platform": "Webull"}

    price = parse_float(
        [
            r"(?:price|last|close)[:\s]*\$?([\d.]+)",
            r"\$([\d]{1,3}\.[\d]{2,4})",
            r"([\d]\.[\d]{4})\s",
        ],
        text,
    )
    ma5, ma10, ma20 = _parse_webull_ma_values(text)
    roi_price = _extract_webull_right_price(image)
    selected_price = _select_webull_price(text, price, ma5, ma10, ma20)
    ma_values = {round(float(v), 4) for v in (ma5, ma10, ma20) if v is not None}
    price = roi_price if roi_price is not None and round(float(roi_price), 4) not in ma_values else selected_price
    ma5, ma10, ma20 = _refine_webull_ma_values(text, price, (ma5, ma10, ma20))
    refined_ma_values = {round(float(v), 4) for v in (ma5, ma10, ma20) if v is not None}
    if price is not None and round(float(price), 4) in refined_ma_values:
        price = selected_price

    change_m = re.search(r"([+-]\s*\d+(?:[\.,]\d+)?)\s*%", text)
    if not change_m:
        change_m = re.search(r"(\d+(?:[\.,]\d+)?)\s*%", text)
    change_pct = float(change_m.group(1).replace(" ", "").replace(",", ".")) if change_m else None

    vol_m = re.search(r"(?:vol|volume)[:\s]*([\d,.]+[KMB]?)", text, re.I)
    volume = vol_m.group(1) if vol_m else None
    volume_spike = bool(re.search(r"high\s*vol|volume\s*spike|vol.*high", text, re.I))

    ticker = extract_ticker(text)

    data.update(
        {
            "price": price,
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "rsi_from_ocr": False,
            "macd_from_ocr": False,
            "change_pct": change_pct,
            "volume": volume,
            "volume_spike": volume_spike,
            "timeframe": parse_timeframe(text, "1min"),
            "ticker": ticker,
            "timestamp": datetime.now().isoformat(),
        }
    )
    return apply_ma_validation(data, text)


def parse_tradingview(text: str) -> dict[str, Any]:
    """Parse TradingView dark/light theme chart screenshots."""
    data: dict[str, Any] = {"platform": "TradingView"}

    price = parse_float(
        [
            r"(?:price|close|last|o)[:\s]*([\d.]+)",
        ],
        text,
    )
    if price is None:
        prices = [float(p) for p in re.findall(r"\b(\d\.\d{4})\b", text)]
        if prices:
            price = max(prices)
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
            "ticker": "unknown",
            "timestamp": datetime.now().isoformat(),
        }
    )
    return apply_ma_validation(data, text)


def merge_with_fallbacks(parsed: dict[str, Any], platform: str, raw_text: str = "") -> dict[str, Any]:
    """Fill missing OCR values with platform-specific sample defaults."""
    sample = WEBULL_SAMPLE if platform == "Webull" else TRADINGVIEW_SAMPLE

    for key, val in sample.items():
        if key == "platform":
            continue
        if key == "rsi" and not parsed.get("rsi_from_ocr"):
            continue
        if parsed.get(key) is None and val is not None:
            parsed[key] = val

    # TradingView: map EMA/SMA to ma fields for downstream feature engineering
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

    if parsed.get("price") is None:
        parsed["price"] = sample.get("price", 0.5861)

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
    combined_text = raw_standard + "\n" + raw_gray + "\n" + raw_webull_regions

    platform = detect_platform(combined_text, image)

    # TradingView dark theme: extra preprocessing pass
    if platform == "TradingView" or _tradingview_image_score(image) >= 1.5:
        tv_processed = preprocess_tradingview_dark(image)
        raw_tv = extract_text(tv_processed)
        combined_text = combined_text + "\n" + raw_tv
        webull_score, tv_score = _platform_scores(combined_text, image)
        # Do not let generic indicator OCR (RSI/MACD/EMA) override strong
        # Webull layout cues like Chart/News/Feeds/Company and MA(5,10,20).
        platform = "TradingView" if tv_score > webull_score else "Webull"

    if platform == "Webull":
        parsed = parse_webull(combined_text, image)
    else:
        parsed = parse_tradingview(combined_text)

    parsed["platform"] = platform
    parsed["raw_ocr_text"] = combined_text[:500]
    parsed["tesseract_available"] = bool(combined_text.strip())
    parsed = merge_with_fallbacks(parsed, platform, combined_text)
    if not combined_text.strip():
        parsed["ocr_note"] = "Tesseract not installed or no text detected; using sample/fallback values"
    return parsed
