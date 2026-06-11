"""
Unit tests for the two pure-logic services (extraction + categorization).

These are the parts with real algorithms, so they are the parts worth testing.
Run from the project root with:   python -m pytest -v
(or simply:  python tests/test_extraction.py)

Having tests is a good thing to show in a defense: it proves the parsing logic
works without needing to upload an image every time.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import extraction_service as extraction
from services import category_service as category


SAMPLE_RECEIPT = """\
FRESH MART SUPERMARKET
123 Main Street
Date: 12/05/2024

Milk 2L            2.50
Whole Bread        1.20
Free Range Eggs    3.49
Bananas            0.99
Subtotal           8.18
Tax                0.82
TOTAL              9.00
VISA               9.00
Thank you!
"""


def test_merchant_detected():
    data = extraction.extract(SAMPLE_RECEIPT)
    assert data["merchant"] == "FRESH MART SUPERMARKET"


def test_date_detected():
    data = extraction.extract(SAMPLE_RECEIPT)
    assert data["purchase_date"] == "12/05/2024"


def test_total_prefers_total_line_not_subtotal():
    data = extraction.extract(SAMPLE_RECEIPT)
    assert data["total"] == 9.00


def test_line_items_exclude_tax_and_payment():
    data = extraction.extract(SAMPLE_RECEIPT)
    descriptions = [i["description"].lower() for i in data["items"]]
    assert any("milk" in d for d in descriptions)
    assert any("bread" in d for d in descriptions)
    # tax / subtotal / visa must NOT be treated as products
    assert not any("tax" in d for d in descriptions)
    assert not any("visa" in d for d in descriptions)


def test_european_number_format():
    # 1.299,00 (european) should parse as 1299.00
    assert extraction._to_float("1.299,00") == 1299.00
    # 12,99 should parse as 12.99
    assert extraction._to_float("12,99") == 12.99


def test_categorization():
    assert category.categorize_text("Whole Bread") == "Groceries"
    assert category.categorize_text("Uber trip to airport") == "Transport"
    assert category.categorize_text("Starbucks Latte") == "Dining"
    assert category.categorize_text("Mystery widget xyz") == "Other"


def test_categorization_expanded_keywords():
    # Common menu/grocery item names should now be recognised.
    assert category.categorize_text("Cappuccino") == "Dining"
    assert category.categorize_text("Croissant") == "Dining"
    assert category.categorize_text("Cheddar Cheese") == "Groceries"
    assert category.categorize_text("Bananas 1kg") == "Groceries"


def test_receipt_category_from_merchant():
    cat = category.categorize_receipt("Fresh Mart Supermarket", [])
    assert cat == "Groceries"


if __name__ == "__main__":
    # Allow running without pytest installed.
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS  {name}")
            passed += 1
    print(f"\n{passed} tests passed.")
