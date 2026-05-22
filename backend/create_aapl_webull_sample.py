"""Generate desktop Webull AAPL-style header screenshot for OCR testing."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

out = Path(__file__).resolve().parent.parent / "data" / "sample_screenshots" / "webull_aapl_sample.png"
out.parent.mkdir(parents=True, exist_ok=True)

w, h = 900, 400
img = Image.new("RGB", (w, h), color=(18, 22, 30))
draw = ImageDraw.Draw(img)
try:
    font_lg = ImageFont.truetype("arial.ttf", 22)
    font_md = ImageFont.truetype("arial.ttf", 16)
except OSError:
    font_lg = font_md = ImageFont.load_default()

draw.text((16, 12), "AAPL  Apple Inc  1 minute  Adjusted", fill=(200, 200, 200), font=font_md)
draw.text((16, 44), "O 298.00  H 299.50  L 297.00  C 297.91", fill=(255, 255, 255), font=font_lg)
draw.text((16, 78), "MA MA5 297.81  MA10 296.50  MA20 295.20", fill=(200, 200, 200), font=font_md)
draw.text((16, 110), "Webull", fill=(16, 185, 129), font=font_md)

img.save(out)
print(f"Saved {out}")
