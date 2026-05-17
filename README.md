# Stock Signal Analysis Tool

AI-powered full-stack application that analyzes Webull and TradingView chart screenshots using OCR, technical indicators, and an XGBoost + LightGBM ensemble ML model.

## Features

- **Screenshot OCR**: Upload PNG/JPG chart screenshots; auto-detect Webull vs TradingView
- **Technical Analysis**: RSI, MACD, Bollinger Bands, EMA/SMA, ATR, volume spikes, MA crossovers (computed in-house)
- **ML Signals**: BUY / SELL / HOLD with confidence score (0–100%)
- **Trading Levels**: Entry price, take profit, stop loss, risk/reward ratio
- **Forecasts**: Short-term and long-term price direction panels
- **Backtesting**: Historical accuracy report on 1000+ samples

## Requirements

- **Python 3.10+**
- **Node.js 18+**
- **Tesseract OCR** ([install guide](https://github.com/tesseract-ocr/tesseract))

### Install Tesseract

- **Windows**: Download from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and add to PATH
- **macOS**: `brew install tesseract`
- **Linux**: `sudo apt install tesseract-ocr`

## Project Structure

```
stock-signal-tool/
├── backend/           # FastAPI + OCR + ML
├── frontend/          # React + Tailwind dashboard
├── models/            # Trained model.pkl
├── data/              # Sample screenshots
└── README.md
```

## Installation

### Backend

```bash
cd stock-signal-tool/backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Frontend

```bash
cd stock-signal-tool/frontend
npm install
```

## Train the ML Model

Run once before first use (also auto-runs on server start if model is missing):

```bash
cd stock-signal-tool/backend
python train_model.py
```

This downloads historical data via yfinance, trains XGBoost + LightGBM, saves `models/model.pkl`, and prints backtest accuracy.

### Retrain with Latest Data

```bash
# Via script
python train_model.py

# Via API (server must be running)
curl -X POST http://localhost:8000/retrain
```

## Run the Application

### Start Backend

```bash
cd stock-signal-tool/backend
uvicorn main:app --reload
```

API docs: http://localhost:8000/docs

### Start Frontend

```bash
cd stock-signal-tool/frontend
npm start
```

Dashboard: http://localhost:3000

## Test with a Screenshot

1. Open http://localhost:3000
2. Drag & drop a Webull or TradingView chart screenshot
3. View the full signal dashboard (BUY/SELL/HOLD, confidence, TP/SL, indicators)

### API Test (curl)

```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@data/sample_screenshots/chart.png"
```

### Sample Webull Values (fallback when OCR is partial)

| Field    | Value   |
|----------|---------|
| Price    | 0.5861  |
| MA5      | 0.5789  |
| MA10     | 0.5540  |
| MA20     | 0.5295  |
| Change   | +21.18% |
| Timeframe| 1 min   |

## API Endpoints

| Method | Endpoint   | Description                    |
|--------|------------|--------------------------------|
| GET    | /health    | API status + model loaded      |
| POST   | /analyze   | Upload screenshot → signal JSON|
| POST   | /retrain   | Retrain ML model               |
| GET    | /backtest  | Backtest accuracy report       |

## Backtest

```bash
cd stock-signal-tool/backend
python backtest.py
```

Target: **75–80% directional accuracy** on historical samples.

## Demo Tips (Zoom)

1. Start backend and frontend in separate terminals
2. Use a clear Webull 1-min chart screenshot for best OCR results
3. Show platform auto-detection, signal badge, and indicator grid
4. Run `GET /backtest` to show accuracy metrics

## License

MIT
