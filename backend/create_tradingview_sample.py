"""Generate a simulated TradingView dark-theme chart screenshot for testing."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

out = Path(__file__).resolve().parent.parent / "data" / "sample_screenshots" / "tradingview_sample.png"
out.parent.mkdir(parents=True, exist_ok=True)

# TradingView dark theme colors
bg = (14, 17, 23)
sidebar = (22, 26, 35)
accent = (41, 98, 255)
text_white = (255, 255, 255)
text_gray = (180, 185, 195)
green = (38, 166, 91)

img = Image.new("RGB", (900, 550), color=bg)
draw = ImageDraw.Draw(img)
draw.rectangle([650, 0, 900, 550], fill=sidebar)

try:
    font_lg = ImageFont.truetype("arial.ttf", 26)
    font_sm = ImageFont.truetype("arial.ttf", 15)
except OSError:
    font_lg = ImageFont.load_default()
    font_sm = font_lg

draw.text((20, 15), "TradingView", fill=accent, font=font_lg)
draw.text((20, 55), "0.5861", fill=text_white, font=font_lg)
draw.text((20, 95), "+21.18%", fill=green, font=font_sm)
draw.text((120, 95), "1D", fill=text_gray, font=font_sm)

draw.rectangle([80, 130, 620, 480], outline=(40, 45, 55), width=1)

# Right sidebar indicators (TradingView style)
draw.text((670, 30), "RSI 14", fill=text_gray, font=font_sm)
draw.text((670, 50), "66.4", fill=text_white, font=font_sm)
draw.text((670, 90), "MACD", fill=text_gray, font=font_sm)
draw.text((670, 110), "Bullish", fill=green, font=font_sm)
draw.text((670, 150), "EMA 5", fill=text_gray, font=font_sm)
draw.text((670, 170), "0.5789", fill=text_white, font=font_sm)
draw.text((670, 200), "EMA 10", fill=text_gray, font=font_sm)
draw.text((670, 220), "0.5540", fill=text_white, font=font_sm)
draw.text((670, 250), "EMA 20", fill=text_gray, font=font_sm)
draw.text((670, 270), "0.5295", fill=text_white, font=font_sm)
draw.text((670, 310), "Volume", fill=text_gray, font=font_sm)
draw.text((670, 330), "High", fill=green, font=font_sm)

img.save(out)
print(f"Saved {out}")
