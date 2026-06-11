"""
Extraction service  --  the "serverless extraction pipeline" box.

It takes the raw OCR text and turns it into structured data:
    merchant, purchase date, line items (description + price), and total.

It is written as a pure function (no database, no files), so it is easy to
unit-test and could be deployed as a single AWS Lambda. The logic is plain
regular expressions and heuristics -- nothing magic --.
"""

import re

# A money amount like 12.99, 1,299.00, 3.5  -> we normalise later.
MONEY_RE = re.compile(r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})|\d+[.,]\d{2})")

# Common date formats: 12/05/2024, 2024-05-12, 12.05.24, 5 May 2024
DATE_RE = re.compile(
    r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
    r"|\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2}"
    r"|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})"
)

# Lines that are totals/taxes/payments, not products.
TOTAL_KEYWORDS = ("total", "amount due", "balance", "grand total")
SKIP_KEYWORDS = (
    "subtotal", "sub total", "tax", "vat", "gst", "change", "cash", "card",
    "visa", "mastercard", "tip", "tender", "payment", "discount", "auth",
)


def _to_float(raw):
    """Turn '1,299.00' or '1.299,00' or '12,99' into a float."""
    s = raw.strip()
    # If both separators present, the last one is the decimal separator.
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):       # european style 1.299,00
            s = s.replace(".", "").replace(",", ".")
        else:                                  # us style 1,299.00
            s = s.replace(",", "")
    elif "," in s:
        # treat a single comma with 2 trailing digits as decimal: 12,99
        s = s.replace(",", ".") if re.search(r",\d{2}$", s) else s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _find_merchant(lines):
    """Heuristic: the first line that looks like a name (letters, not a number)."""
    for line in lines:
        stripped = line.strip()
        if len(stripped) >= 3 and re.search(r"[A-Za-z]", stripped) \
                and not MONEY_RE.fullmatch(stripped):
            return stripped[:80]
    return None


def _find_date(text):
    match = DATE_RE.search(text)
    return match.group(1) if match else None


def _find_total(lines, all_amounts):
    """
    Prefer a line that says 'total' (but not 'subtotal') and has an amount.
    Fall back to the largest amount on the receipt.
    """
    for line in lines:
        low = line.lower()
        if any(k in low for k in TOTAL_KEYWORDS) and "subtotal" not in low:
            amounts = [_to_float(m) for m in MONEY_RE.findall(line)]
            amounts = [a for a in amounts if a is not None]
            if amounts:
                return max(amounts)
    return max(all_amounts) if all_amounts else None


def _find_items(lines):
    """
    A line item is a line that ends in a price and is not a total/tax/payment
    line. We take the text before the price as the description.
    """
    items = []
    for line in lines:
        low = line.lower()
        if any(k in low for k in SKIP_KEYWORDS) or any(k in low for k in TOTAL_KEYWORDS):
            continue
        money = MONEY_RE.findall(line)
        if not money:
            continue
        price = _to_float(money[-1])                # price is usually last
        # description = everything before the final price token
        desc = line[: line.rfind(money[-1])].strip(" .-:\t")
        if desc and price is not None and len(desc) >= 2:
            items.append({"description": desc[:80], "price": price})
    return items


def extract(raw_text):
    """
    Main entry point. Returns a dict:
        { merchant, purchase_date, total, items: [ {description, price}, ... ] }
    """
    lines = [ln for ln in raw_text.splitlines() if ln.strip()]
    all_amounts = [a for a in (_to_float(m) for m in MONEY_RE.findall(raw_text)) if a is not None]

    return {
        "merchant": _find_merchant(lines),
        "purchase_date": _find_date(raw_text),
        "total": _find_total(lines, all_amounts),
        "items": _find_items(lines),
    }
