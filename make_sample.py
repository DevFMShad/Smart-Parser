"""
Helper: generate a realistic-looking sample receipt image you can use to test
or demo the parser. Run:  python make_sample.py   -> creates sample_receipt.png
"""
from PIL import Image, ImageDraw, ImageFont

LINES = [
    "FRESH MART SUPERMARKET",
    "123 Main Street, Springfield",
    "Tel: 555-0142",
    "Date: 12/05/2024  14:32",
    "------------------------------",
    "Milk 2L              2.50",
    "Whole Bread          1.20",
    "Free Range Eggs      3.49",
    "Bananas 1kg          0.99",
    "Cheddar Cheese       4.25",
    "------------------------------",
    "Subtotal            12.43",
    "Tax                  1.24",
    "TOTAL               13.67",
    "VISA                13.67",
    "------------------------------",
    "Thank you for shopping!",
]


def main():
    width, line_h, pad = 460, 34, 30
    height = pad * 2 + line_h * len(LINES)
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("cour.ttf", 22)        # Courier = monospace
    except OSError:
        font = ImageFont.load_default()

    y = pad
    for line in LINES:
        draw.text((pad, y), line, fill="black", font=font)
        y += line_h

    img.save("sample_receipt.png")
    print("Wrote sample_receipt.png")


if __name__ == "__main__":
    main()
