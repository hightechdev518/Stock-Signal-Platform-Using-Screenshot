"""Generate a sample Webull-style chart screenshot for testing."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

out = Path(__file__).resolve().parent.parent / "data" / "sample_screenshots" / "webull_sample.png"
out.parent.mkdir(parents=True, exist_ok=True)

img = Image.new("RGB", (800, 500), color=(10, 14, 23))
draw = ImageDraw.Draw(img)
try:
    font_lg = ImageFont.truetype("arial.ttf", 28)
    font_sm = ImageFont.truetype("arial.ttf", 16)
except OSError:
    font_lg = ImageFont.load_default()
    font_sm = font_lg

draw.text((20, 20), "Webull", fill=(16, 185, 129), font=font_lg)
draw.text((20, 60), "Price: 0.5861", fill=(255, 255, 255), font=font_sm)
draw.text((20, 90), "MA5: 0.5789", fill=(200, 200, 200), font=font_sm)
draw.text((20, 120), "MA10: 0.5540", fill=(200, 200, 200), font=font_sm)
draw.text((20, 150), "MA20: 0.5295", fill=(200, 200, 200), font=font_sm)
draw.text((20, 180), "+21.18%", fill=(16, 185, 129), font=font_sm)
draw.text((20, 210), "1 min", fill=(150, 150, 150), font=font_sm)
draw.text((20, 240), "19:15 - 20:10", fill=(150, 150, 150), font=font_sm)
draw.rectangle([100, 300, 700, 450], outline=(16, 185, 129), width=2)

img.save(out)
print(f"Saved {out}")
