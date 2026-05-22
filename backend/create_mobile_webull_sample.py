"""Generate a mobile Webull-style chart screenshot for OCR testing."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

out = Path(__file__).resolve().parent.parent / "data" / "sample_screenshots" / "webull_mobile_sample.png"
out.parent.mkdir(parents=True, exist_ok=True)

w, h = 390, 844
img = Image.new("RGB", (w, h), color=(18, 22, 30))
draw = ImageDraw.Draw(img)
try:
    font_xs = ImageFont.truetype("arial.ttf", 12)
    font_sm = ImageFont.truetype("arial.ttf", 14)
    font_md = ImageFont.truetype("arial.ttf", 16)
    font_lg = ImageFont.truetype("arial.ttf", 22)
    font_xl = ImageFont.truetype("arial.ttf", 28)
except OSError:
    font_xs = font_sm = font_md = font_lg = font_xl = ImageFont.load_default()

draw.text((12, 8), "Chart  News  Feeds  Company", fill=(180, 180, 180), font=font_sm)
draw.text(
    (12, 32),
    "MA(5,10,20)  MA5:0.5789  MA10:0.5540  MA20:0.5295",
    fill=(200, 200, 200),
    font=font_xs,
)
draw.text((24, 120), "0.6161", fill=(150, 150, 150), font=font_md)
draw.text((24, h - 220), "0.4876", fill=(150, 150, 150), font=font_md)

box = (int(w * 0.72), 280, w - 8, 380)
draw.rectangle(box, outline=(16, 185, 129), width=2)
draw.text((box[0] + 12, box[1] + 28), "0.5861", fill=(255, 255, 255), font=font_xl)

draw.rectangle([0, h - 56, w, h], fill=(28, 32, 42))
draw.text((16, h - 40), "1 min", fill=(16, 185, 129), font=font_sm)
draw.text((70, h - 40), "Daily", fill=(140, 140, 140), font=font_sm)
draw.text((130, h - 40), "Weekly", fill=(140, 140, 140), font=font_sm)
draw.text((200, h - 40), "Monthly", fill=(140, 140, 140), font=font_sm)

img.save(out)
print(f"Saved {out}")
