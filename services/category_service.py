"""
Category service.

Classifies an item (and the whole receipt) into an expense category using a
keyword rules engine. It is deliberately simple and transparent: each category
owns a list of keywords, and the first match wins. In production this could be
replaced by a trained ML classifier behind the same interface.
"""

# Order matters a little: more specific categories can be listed first.
CATEGORY_KEYWORDS = {
    "Groceries":      ["market", "grocery", "supermarket", "milk", "bread", "egg",
                        "vegetable", "fruit", "produce", "aldi", "tesco", "walmart",
                        "kroger", "lidl", "rice", "meat", "chicken", "banana",
                        "tomato", "potato", "onion", "cheese",
                        "cheddar", "yogurt", "yoghurt", "butter", "cereal", "flour",
                        "sugar", "pasta", "snack", "fish", "beef"],
    "Dining":         ["restaurant", "cafe", "coffee", "pizza", "burger", "bar",
                        "grill", "diner", "starbucks", "mcdonald", "kfc", "sushi",
                        "lunch", "dinner", "bakery", "cappuccino", "latte",
                        "espresso", "mocha", "americano", "croissant", "muffin",
                        "bagel", "toast", "sandwich", "wrap", "salad", "soup",
                        "noodle", "fries", "taco", "smoothie", "tea", "cake",
                        "dessert", "brownie"],
    "Transport":      ["fuel", "petrol", "gas", "diesel", "uber", "taxi", "lyft",
                        "parking", "metro", "bus", "train", "shell", "toll"],
    "Utilities":      ["electric", "water", "internet", "phone", "mobile", "bill",
                        "gas bill", "broadband", "utility"],
    "Healthcare":     ["pharmacy", "chemist", "clinic", "hospital", "medical",
                        "dental", "doctor", "drug", "medicine"],
    "Shopping":       ["clothing", "shoes", "apparel", "electronics", "store",
                        "mall", "amazon", "shirt", "book", "stationery"],
    "Entertainment":  ["cinema", "movie", "netflix", "spotify", "game", "concert",
                        "ticket", "theatre"],
}

DEFAULT_CATEGORY = "Other"


def categorize_text(text):
    """Return the best category for a piece of text (item desc or merchant)."""
    if not text:
        return DEFAULT_CATEGORY
    low = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return category
    return DEFAULT_CATEGORY


def categorize_receipt(merchant, items):
    """
    Decide the overall receipt category.

    1. If the merchant name matches a category, trust that.
    2. Otherwise pick the most common category among the line items.
    3. Otherwise 'Other'.
    """
    merchant_cat = categorize_text(merchant)
    if merchant_cat != DEFAULT_CATEGORY:
        return merchant_cat

    counts = {}
    for item in items:
        cat = item.get("category") or categorize_text(item.get("description"))
        if cat != DEFAULT_CATEGORY:
            counts[cat] = counts.get(cat, 0) + 1

    if counts:
        return max(counts, key=counts.get)
    return DEFAULT_CATEGORY
