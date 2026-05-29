"""
Stock scanner — fetches top gainers, losers, most active
with quick BUY/SELL/HOLD signal for each ticker.
"""

import pandas as pd
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

from yfinance_setup import configure_yfinance_cache, safe_ticker_history

import threading
import time as _time

_scanner_cache: list[dict] = []
_scanner_cache_lock = threading.Lock()
_scanner_cache_ready = threading.Event()
_scanner_last_updated: float = 0.0

# Predefined ticker lists
LARGE_CAPS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "JNJ", "WMT",
    "XOM", "V", "UNH", "PG", "MA",
]
MID_CAPS = [
    "SAIC", "PLTR", "COIN", "INTC",
    "MSTR", "GME", "AMC", "SNAP", "UBER",
]
PENNY_STOCKS = [
    "OCGN", "SNDL", "CENN", "SLXN",
    "GRAN", "XSLL", "WKHS",
]
ALL_TICKERS = list(dict.fromkeys([
'AAPL','MSFT','GOOGL','AMZN','TSLA','NVDA','META','JPM','JNJ','WMT',
'XOM','V','UNH','PG','MA','HD','CVX','MRK','ABBV','PEP','KO','AVGO','COST',
'MCD','TMO','ACN','ABT','DHR','NKE','LLY','TXN','NEE','PM','RTX','HON','UNP',
'MS','GS','SCHW','BLK','SPGI','AXP','ISRG','SYK','GILD','AMGN','BMY','REGN',
'VRTX','ZTS','ELV','CI','HUM','CVS','MCK','CAT','DE','MMM','GE','ETN','EMR',
'ITW','PH','ROK','CMI','GWW','FAST','ODFL','UPS','FDX','CSX','NSC','UAL',
'DAL','LUV','AAL','MAR','HLT','EXPE','BKNG','ABNB','UBER','DASH','COIN',
'MSTR','PLTR','SAIC','INTC','AMD','MU','QCOM','AMAT','LRCX','KLAC','NFLX',
'DIS','CMCSA','T','VZ','TMUS','SNAP','PINS','RBLX','HOOD','SOFI','AFRM',
'UPST','PYPL','FIS','FISV','GPN','BAC','WFC','C','USB','TFC','PNC','KEY',
'RF','HBAN','CFG','MTB','ZION','FITB','GME','AMC','WKHS','SNDL','MARA',
'RIOT','HUT','CLSK','CIFR','BTBT','OCGN','CENN','SLXN','GRAN','SPCE',
'LCID','RIVN','NIO','XPEV','LI','BLNK','CHPT','EVGO','SKLZ','PENN',
'DKNG','OPEN','CHWY','CLOV','BARK','PAYO','ATER','IMPP','MTCH','BMBL',
'VRSK','CDNS','SNPS','ADBE','CRM','NOW','WDAY','VEEV','ZM','DOCU',
'OKTA','CRWD','PANW','FTNT','ZS','NET','DDOG','MDB','SNOW','U',
'LMND','ROOT','OPAD','GREE','TPVG','OXLC','PSEC','GAIN','MAIN',
'ARCC','GBDC','HTGC','SLRC','TRIN','NMFC','GSBD','PFLT','FDUS'
]))


def _safe_float(value, default: float = 0.0) -> float:
    try:
        num = float(value)
        if pd.isna(num):
            return default
        return num
    except (TypeError, ValueError):
        return default


def _fetch_yfinance_extras(ticker: str) -> dict:
    """Fetch quote fields and sparkline from yfinance."""
    try:
        configure_yfinance_cache()
        import yfinance as yf

        stock = yf.Ticker(ticker)
        try:
            info = stock.info or {}
        except Exception:
            info = {}

        prev_close = _safe_float(
            info.get("previousClose") or info.get("regularMarketPreviousClose")
        )
        price = _safe_float(
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        change = price - prev_close if prev_close else 0.0
        change_pct = (change / prev_close * 100) if prev_close else 0.0

        sparkline: list[float] = []
        hist = safe_ticker_history(ticker, period="5d", interval="1h")
        if hist is not None and not hist.empty:
            close_col = "Close" if "Close" in hist.columns else "close"
            closes = hist[close_col].dropna().tail(10)
            sparkline = [round(_safe_float(v), 4) for v in closes.tolist()]

        hist_daily = safe_ticker_history(ticker, period="3mo", interval="1d")

        if hist_daily is not None and not hist_daily.empty:
            closes = hist_daily["Close"].dropna()
            current = closes.iloc[-1] if len(closes) > 0 else None

            def pct_change_ago(days):
                if current is None or len(closes) < days:
                    return None
                past = closes.iloc[-days]
                return round((current - past) / past * 100, 2)

            change_3d = pct_change_ago(3)
            change_1w = pct_change_ago(5)   # 5 trading days
            change_15d = pct_change_ago(10)  # 10 trading days
            change_1m = pct_change_ago(21)  # 21 trading days
            change_3m = pct_change_ago(60)  # 60 trading days
        else:
            change_3d = change_1w = change_15d = change_1m = change_3m = None

        volume = _safe_float(info.get("volume") or info.get("regularMarketVolume"))
        market_cap = _safe_float(info.get("marketCap"))

        return {
            "price": round(price, 4),
            "change": round(change, 4),
            "change_pct": round(change_pct, 2),
            "prev_close": round(prev_close, 4),
            "open": round(_safe_float(info.get("open") or info.get("regularMarketOpen")), 4),
            "high": round(
                _safe_float(info.get("dayHigh") or info.get("regularMarketDayHigh")), 4
            ),
            "low": round(
                _safe_float(info.get("dayLow") or info.get("regularMarketDayLow")), 4
            ),
            "volume": int(volume) if volume else 0,
            "market_cap": int(market_cap) if market_cap else 0,
            "roe": round(_safe_float(info.get("returnOnEquity")) * 100, 2)
            if info.get("returnOnEquity")
            else None,
            "sparkline": sparkline,
            "change_3d": change_3d,
            "change_1w": change_1w,
            "change_15d": change_15d,
            "change_1m": change_1m,
            "change_3m": change_3m,
            "name": info.get("longName") or info.get("shortName") or ticker,
        }
    except Exception as e:
        print(f"[scanner] extras failed for {ticker}: {e}")
        return {
            "name": ticker,
            "price": None,
            "change": None,
            "change_pct": None,
            "prev_close": None,
            "open": None,
            "high": None,
            "low": None,
            "volume": None,
            "market_cap": None,
            "roe": None,
            "sparkline": [],
            "change_3d": None,
            "change_1w": None,
            "change_15d": None,
            "change_1m": None,
            "change_3m": None,
        }


def _bulk_fetch_signals(tickers: list[str]) -> dict:
    """Fetch 1-min bars for all tickers in one call,
    run ML on each slice. Returns dict of
    ticker -> signal data."""
    from feature_engineer import compute_indicators
    from ml_model import predict_signal

    results = {}

    try:
        ticker_str = " ".join(tickers)
        print(f"[scanner] bulk fetching {len(tickers)} tickers...")

        import time
        start = time.time()
        data = yf.download(
            ticker_str,
            period="5d",
            interval="1m",
            group_by="ticker",
            progress=False,
            threads=True,
        )
        elapsed = time.time() - start
        print(f"[scanner] bulk fetch done in {elapsed:.1f}s")

        if data is None or data.empty:
            return {}

        # Handle single ticker case
        if len(tickers) == 1:
            df = data.copy()
            df.columns = [c.lower() for c in df.columns]
            df = df.dropna()
            if not df.empty:
                try:
                    df = compute_indicators(df)
                    latest = df.iloc[-1]
                    price = float(latest["close"])
                    features = _extract_features_from_row(latest, price)
                    from feature_engineer import features_to_ml_array
                    ml_result = predict_signal(features_to_ml_array(features))
                    signal = ml_result["signal"]
                    confidence = ml_result["confidence"]
                    results[tickers[0]] = {
                        "signal": signal,
                        "confidence": confidence,
                        "price": price,
                        "df": df,
                    }
                except Exception as e:
                    print(f"[scanner] signal failed for {tickers[0]}: {e}")
            return results

        # Multi-ticker case
        from feature_engineer import features_to_ml_array
        from concurrent.futures import ThreadPoolExecutor as _TPE

        available = data.columns.get_level_values(0).unique().tolist()

        # Pre-load ML model before threading to avoid race condition
        try:
            predict_signal(features_to_ml_array(
                _extract_features_from_row(
                    __import__('pandas').Series({
                        'close': 100.0, 'rsi': 50.0, 'macd': 0.0,
                        'macd_signal': 0.0, 'macd_hist': 0.0,
                        'ema_5': 100.0, 'ema_10': 100.0, 'ema_20': 100.0,
                        'atr': 1.0, 'vol_ratio': 1.0, 'volume': 1000.0,
                        'bb_upper': 105.0, 'bb_lower': 95.0,
                        'bb_position': 0.5, 'bb_score': 0.5,
                        'roc_5': 0.0, 'roc_20': 0.0,
                    }), 100.0)
            ))
        except Exception:
            pass

        def _process(ticker):
            if ticker not in available:
                return None
            try:
                df = data[ticker].copy()
                df.columns = [c.lower() for c in df.columns]
                df = df.dropna()
                if df.empty or len(df) < 10:
                    return None
                df = compute_indicators(df)
                latest = df.iloc[-1]
                price = float(latest["close"])
                features = _extract_features_from_row(latest, price)
                ml_result = predict_signal(features_to_ml_array(features))
                return ticker, {
                    "signal": ml_result["signal"],
                    "confidence": ml_result["confidence"],
                    "price": price,
                    "df": df
                }
            except Exception as e:
                print(f"[scanner] signal failed for {ticker}: {e}")
                return None

        with _TPE(max_workers=8) as ex:
            for outcome in ex.map(_process, tickers):
                if outcome:
                    ticker, payload = outcome
                    results[ticker] = payload

    except Exception as e:
        print(f"[scanner] bulk fetch failed: {e}")

    return results


def _extract_features_from_row(latest, price: float) -> dict:
    """Extract ML feature dict from a computed indicators row."""
    from feature_engineer import classify_volume
    import math

    def safe(key, default=0.0):
        try:
            val = latest.get(key, default)
            if val is None:
                return default
            f = float(val)
            return default if math.isnan(f) or math.isinf(f) else f
        except:
            return default

    vol_ratio = safe("vol_ratio", 1.0)
    rsi = safe("rsi", 50.0)
    macd = safe("macd", 0.0)
    macd_signal = safe("macd_signal", 0.0)
    ma5 = safe("ema_5", price)
    ma10 = safe("ema_10", price)
    ma20 = safe("ema_20", price)

    # ma_signal
    if price > ma5 and price > ma10 and price > ma20:
        ma_signal = "bullish"
    elif price < ma5 and price < ma10 and price < ma20:
        ma_signal = "bearish"
    else:
        ma_signal = "neutral"

    # long_trend
    if ma5 > ma20:
        long_trend = "uptrend"
    else:
        long_trend = "downtrend"

    # macd_for_ml
    if macd > macd_signal:
        macd_for_ml = "bullish"
    elif macd < macd_signal:
        macd_for_ml = "bearish"
    else:
        macd_for_ml = "neutral"

    # rsi_for_ml
    if rsi >= 70:
        rsi_for_ml = 1.0
    elif rsi <= 30:
        rsi_for_ml = 0.0
    else:
        rsi_for_ml = (rsi - 30) / 40

    # roc_5 and roc_20 from close history
    roc_5 = safe("roc_5", 0.0)
    roc_20 = safe("roc_20", 0.0)

    return {
        "price": price,
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "rsi": rsi,
        "rsi_for_ml": rsi_for_ml,
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_hist": safe("macd_hist", 0.0),
        "macd_for_ml": macd_for_ml,
        "atr": safe("atr", 0.0),
        "bb_upper": safe("bb_upper", price),
        "bb_lower": safe("bb_lower", price),
        "bb_position": safe("bb_position", 0.5),
        "bb_score": safe("bb_score", 0.5),
        "volume": safe("volume", 0.0),
        "vol_ratio": vol_ratio,
        "volume_label": classify_volume(vol_ratio),
        "ma_signal": ma_signal,
        "long_trend": long_trend,
        "roc_5": roc_5,
        "roc_20": roc_20,
        "vwap": safe("vwap", price),
        "adx": safe("adx", 20.0),
        "adx_signal": "bullish" if safe("adx", 20.0) > 25 else "neutral",
        "trend_strength": "strong" if safe("adx", 20.0) > 25 else "weak",
        "cci": safe("cci", 0.0),
        "resistance": safe("resistance", price * 1.05),
        "support": safe("support", price * 0.95),
        "change_pct": safe("change_pct", 0.0),
        "pivot_score": safe("pivot_score", 0.5),
    }


def _quick_signal(ticker: str) -> dict:
    """Get real ML signal for a single ticker using analyze_live()."""
    try:
        from signal_engine import analyze_live
        result = analyze_live(ticker)
        if not result:
            extras = _fetch_yfinance_extras(ticker)
            return {
                "ticker": ticker,
                "signal": "HOLD",
                "signal_color": "neutral",
                "confidence": 0,
                "rsi": 50,
                "vol_ratio": 1,
                "ma_trend": "bearish",
                "conclusion": "",
                **extras,
            }

        price = _safe_float(result.get("price"), 0)
        change_pct = _safe_float(result.get("change_pct"), 0)
        signal = result.get("signal", "HOLD")
        confidence = _safe_float(result.get("confidence"), 0)
        indicators = result.get("indicators", {})
        rsi = _safe_float(indicators.get("RSI"), 50)
        vol_ratio = _safe_float(indicators.get("vol_ratio"), 1)
        ma_trend = str(indicators.get("MA_trend", "") or "")
        ma_bias = (
            "bullish" if "bullish" in ma_trend.lower() or "above" in ma_trend.lower()
            else "bearish"
        )

        signal_color = (
            "bullish" if signal == "BUY"
            else "bearish" if signal == "SELL"
            else "neutral"
        )

        extras = _fetch_yfinance_extras(ticker)
        if not extras.get("price") and price:
            extras["price"] = round(price, 4)
            extras["change_pct"] = round(change_pct, 2)
            if extras.get("prev_close"):
                extras["change"] = round(extras["price"] - extras["prev_close"], 4)

        if not extras.get("price"):
            return {
                "ticker": ticker,
                "signal": signal,
                "signal_color": signal_color,
                "confidence": round(confidence, 1),
                "rsi": round(rsi, 1),
                "vol_ratio": round(vol_ratio, 2),
                "ma_trend": ma_bias,
                "conclusion": result.get("conclusion", ""),
                **extras,
            }

        return {
            "ticker": ticker,
            "signal": signal,
            "signal_color": signal_color,
            "confidence": round(confidence, 1),
            "rsi": round(rsi, 1),
            "vol_ratio": round(vol_ratio, 2),
            "ma_trend": ma_bias,
            "conclusion": result.get("conclusion", ""),
            **extras,
        }
    except Exception as e:
        print(f"[scanner] signal failed for {ticker}: {e}")
        return {
            "ticker": ticker,
            "signal": "HOLD",
            "confidence": 0,
            "name": ticker,
        }


def _run_background_scan():
    """Runs full scan using _quick_signal() (analyze_live + extras).
    Stores result in _scanner_cache. Repeats every 10 minutes."""
    global _scanner_cache, _scanner_last_updated
    while True:
        try:
            print(f"[scanner] background scan starting — {len(ALL_TICKERS)} tickers...")
            start = _time.time()
            results = []
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(_quick_signal, ticker): ticker
                    for ticker in ALL_TICKERS
                }
                for future in as_completed(futures):
                    ticker = futures[future]
                    try:
                        data = future.result(timeout=30)
                    except Exception as e:
                        print(f"[scanner] {ticker} failed: {e}")
                        data = None
                    if data:
                        results.append(data)
            with _scanner_cache_lock:
                _scanner_cache = results
                _scanner_last_updated = _time.time()
            _scanner_cache_ready.set()
            elapsed = _time.time() - start
            print(f"[scanner] background scan done in {elapsed:.1f}s — "
                  f"{len(results)} tickers cached")
        except Exception as e:
            print(f"[scanner] background scan error: {e}")
        _time.sleep(600)  # repeat every 10 minutes


# Start background scan on import
_bg_thread = threading.Thread(target=_run_background_scan, daemon=True)
_bg_thread.start()


def _sort_change_pct(stock: dict, *, reverse: bool = True) -> tuple:
    pct = stock.get("change_pct")
    if pct is None:
        return (1, 0)
    return (0, -pct if reverse else pct)


def _sort_vol_ratio(stock: dict) -> tuple:
    vol = stock.get("vol_ratio")
    if vol is None:
        return (1, 0)
    return (0, -vol)


def get_scanner_list(category: str = "all") -> list[dict]:
    """Serve from cache instantly. Cache built by background thread."""
    # Wait for first scan to complete (only blocks on very first call)
    if not _scanner_cache_ready.is_set():
        print("[scanner] waiting for background scan to complete...")
        _scanner_cache_ready.wait()
    
    with _scanner_cache_lock:
        stocks = list(_scanner_cache)
    
    return stocks
