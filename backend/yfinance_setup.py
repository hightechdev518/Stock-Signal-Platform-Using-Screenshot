"""Configure yfinance cache for Windows desktop installs (avoids Errno 22 on invalid paths)."""

from __future__ import annotations

import os
import sys
import tempfile
from typing import Optional

import pandas as pd

_cache_dir: Optional[str] = None
_configured = False


def get_yfinance_cache_dir() -> str:
    """Writable cache folder under AppData (or temp) for client PCs."""
    global _cache_dir
    if _cache_dir:
        return _cache_dir

    base = os.environ.get("APPDATA") or tempfile.gettempdir()
    _cache_dir = os.path.join(base, "stock-signal-dashboard", "yfinance-cache")
    os.makedirs(_cache_dir, exist_ok=True)
    return _cache_dir


def configure_yfinance_cache() -> str:
    """Point yfinance SQLite caches at AppData. Call before any Ticker/history use."""
    global _configured
    cache_dir = get_yfinance_cache_dir()

    if _configured:
        return cache_dir

    try:
        import yfinance as yf

        yf.set_tz_cache_location(cache_dir)
    except Exception as exc:
        print(f"yfinance cache setup warning: {exc}", file=sys.stderr)

    _configured = True
    print(f"yfinance cache dir: {cache_dir}")
    return cache_dir


def safe_ticker_history(
    ticker: str,
    *,
    period: str = "5d",
    interval: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """Fetch OHLCV history with cache path fixed and errors swallowed."""
    configure_yfinance_cache()
    import yfinance as yf

    symbol = (ticker or "SPY").strip().upper() or "SPY"
    try:
        stock = yf.Ticker(symbol)
        if interval:
            hist = stock.history(period=period, interval=interval)
        else:
            hist = stock.history(period=period)
    except Exception as exc:
        print(f"yfinance error ({symbol}, period={period}, interval={interval}): {exc}")
        return None

    if hist is None or hist.empty:
        return None
    return hist
