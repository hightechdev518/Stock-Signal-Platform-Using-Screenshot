"""
FastAPI backend for Stock Signal Analysis Tool.
"""

import io
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backtest import run_backtest
from ocr_parser import parse_screenshot
from signal_engine import analyze

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "model.pkl"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure model exists; train on first run if missing
    if not MODEL_PATH.exists():
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
        model_loaded=MODEL_PATH.exists(),
        version="1.0.0",
    )


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

        ocr_data = parse_screenshot(contents)
        result = analyze(ocr_data)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(
            422,
            f"Could not analyze screenshot. Ensure chart is readable. Detail: {str(e)}",
        )


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

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
