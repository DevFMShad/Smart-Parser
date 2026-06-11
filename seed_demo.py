"""Seed a demo admin user + two parsed receipts, for previewing the UI."""
import io, os
from PIL import Image, ImageDraw, ImageFont

# --- make a second, different sample (a cafe) for category variety ----------
CAFE = [
    "THE CORNER CAFE", "45 Oak Avenue", "Date: 11/05/2024  09:15",
    "------------------------------",
    "Cappuccino           3.20", "Croissant            2.10",
    "Avocado Toast        6.50", "Orange Juice         2.80",
    "------------------------------",
    "Subtotal            14.60", "Tax                  1.46",
    "TOTAL               16.06", "VISA                16.06",
    "Thank you!",
]
def render(lines, path):
    w, lh, pad = 460, 34, 30
    img = Image.new("RGB", (w, pad*2 + lh*len(lines)), "white")
    d = ImageDraw.Draw(img)
    try: font = ImageFont.truetype("cour.ttf", 22)
    except OSError: font = ImageFont.load_default()
    y = pad
    for ln in lines:
        d.text((pad, y), ln, fill="black", font=font); y += lh
    img.save(path)

render(CAFE, "sample_cafe.png")

from app import app
c = app.test_client()
c.post("/register", data={"username": "demo", "password": "demo123"})  # first -> admin
c.post("/login", data={"username": "demo", "password": "demo123"})
for fname in ("sample_receipt.png", "sample_cafe.png"):
    with open(fname, "rb") as f:
        c.post("/upload", data={"receipt": (io.BytesIO(f.read()), fname)},
               content_type="multipart/form-data", follow_redirects=True)
print("Seeded demo/demo123 with 2 receipts.")
