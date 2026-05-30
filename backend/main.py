"""
FastAPI backend for Stock Signal Analysis Tool.
"""

import asyncio
import gc
import math
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backtest import run_backtest
from debug_logging import setup_debug_logging
from ocr_parser import parse_screenshot
from scanner import get_scanner_list
from yfinance_setup import configure_yfinance_cache

setup_debug_logging()
configure_yfinance_cache()

from paths import model_path
from signal_engine import analyze, analyze_live
from market_hours import get_market_status


def sanitize_nans(obj):
    """Recursively replace NaN/Inf floats with None."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: sanitize_nans(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_nans(v) for v in obj]
    return obj


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure model exists; train on first run if missing
    if not model_path().exists():
        try:
            from train_model import train_and_save

            train_and_save()
        except Exception as e:
            print(f"Auto-train skipped: {e}")
    yield


app = FastAPI(
    title="Stock Signal Analysis API",
    description="OCR + ML powered trading signal analysis",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OCR_TIMEOUT_SEC = 30
_ocr_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if not isinstance(detail, str):
        detail = str(detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "detail": str(exc)},
    )


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    version: str


class RetrainResponse(BaseModel):
    status: str
    message: str
    backtest: dict | None = None


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ok",
        model_loaded=model_path().exists(),
        version="1.0.0",
    )


@app.get("/market-status")
async def market_status():
    """US market session status using PC local time for display."""
    return get_market_status()


@app.get("/live/{ticker}")
async def live_signal(ticker: str):
    """
    Fetch real-time price and recalculate BUY/SELL/HOLD from latest 1-minute bars.
    Intended for polling every few seconds in Live Mode.
    """
    print(f"Live data fetched for {ticker} at {datetime.now()}")
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, analyze_live, ticker)
        if result is None:
            raise HTTPException(status_code=404, detail="Ticker not found")
        return sanitize_nans(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Live data unavailable for {ticker.upper()}. Detail: {str(e)}",
        )


@app.get("/scanner")
async def scanner(category: str = "gainers"):
    """
    Fetch top gainers, losers, or most active stocks
    with quick signal for each.
    category: gainers | losers | active | all
    """
    try:
        from scanner import get_scanner_list

        loop = asyncio.get_running_loop()
        all_stocks = await loop.run_in_executor(
            None, get_scanner_list, category
        )
        
        def sort_change(s, reverse=True):
            try:
                return float(s.get("change_pct") or 0)
            except:
                return 0.0
        
        def sort_vol(s):
            try:
                return float(s.get("vol_ratio") or 0)
            except:
                return 0.0
        
        if category == "gainers":
            stocks = sorted(all_stocks, 
                key=lambda x: sort_change(x), reverse=True)[:10]
        elif category == "losers":
            stocks = sorted(all_stocks,
                key=lambda x: sort_change(x), reverse=False)[:10]
        elif category == "active":
            stocks = sorted(all_stocks,
                key=lambda x: sort_vol(x), reverse=True)[:10]
        else:
            stocks = all_stocks
            
        return sanitize_nans({"category": category, "stocks": stocks})
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/scanner/all")
async def scanner_all():
    try:
        from scanner import get_scanner_list

        loop = asyncio.get_running_loop()
        all_stocks = await loop.run_in_executor(
            None, get_scanner_list, "all"
        )
        
        def sort_change(s, reverse=True):
            try:
                return float(s.get("change_pct") or 0)
            except:
                return 0.0
        
        def sort_vol(s):
            try:
                return float(s.get("vol_ratio") or 0)
            except:
                return 0.0
        
        gainers = sorted(all_stocks,
            key=lambda x: sort_change(x), reverse=True)[:10]
        losers = sorted(all_stocks,
            key=lambda x: sort_change(x), reverse=False)[:10]
        active = sorted(all_stocks,
            key=lambda x: sort_vol(x), reverse=True)[:10]
        
        return sanitize_nans({
            "gainers": gainers,
            "losers": losers,
            "active": active,
            "all": all_stocks
        })
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/scanner/status")
def scanner_status():
    from scanner import (
        _scanner_cache,
        _scanner_cache_lock,
        ALL_TICKERS,
        _scan_complete
    )
    with _scanner_cache_lock:
        cached = len(_scanner_cache)
    return {
        "cached": cached,
        "total": len(ALL_TICKERS),
        "scanning": not _scan_complete
    }


@app.post("/analyze")
async def analyze_screenshot(file: UploadFile = File(...)):
    """
    Upload chart screenshot (PNG/JPG/JPEG) and receive full signal JSON.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        ext = (file.filename or "").lower()
        if not any(ext.endswith(e) for e in (".png", ".jpg", ".jpeg")):
            raise HTTPException(400, "File must be PNG, JPG, or JPEG image")

    try:
        contents = await file.read()
        if len(contents) < 100:
            raise HTTPException(400, "Image file too small or empty")

        loop = asyncio.get_running_loop()
        try:
            ocr_data = await asyncio.wait_for(
                loop.run_in_executor(_ocr_executor, parse_screenshot, contents),
                timeout=OCR_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                504,
                f"OCR timed out after {OCR_TIMEOUT_SEC} seconds. Try a smaller or clearer image.",
            )

        result = analyze(ocr_data)
        return sanitize_nans(result)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            422,
            f"Could not analyze screenshot. Ensure chart is readable. Detail: {str(e)}",
        )
    finally:
        gc.collect()


@app.post("/retrain", response_model=RetrainResponse)
async def retrain():
    """Retrain ML model with latest yfinance data."""
    try:
        from train_model import train_and_save

        train_and_save()
        bt = run_backtest()
        return RetrainResponse(
            status="ok",
            message="Model retrained successfully",
            backtest=bt,
        )
    except Exception as e:
        raise HTTPException(500, f"Retrain failed: {str(e)}")


@app.get("/backtest")
async def backtest_endpoint():
    """Run backtest and return accuracy report."""
    return run_backtest()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
