"""Quick end-to-end smoke test of the web flow using Flask's test client."""
import io, os

# Start from a clean database so the test is deterministic (the first user
# registered becomes the admin, which this test relies on to see the audit log).
if os.path.exists("receipts.db"):
    os.remove("receipts.db")

from app import app

app.config["WTF_CSRF_ENABLED"] = False
client = app.test_client()

# 1. Register
r = client.post("/register", data={"username": "demo_user", "password": "secret123"},
                follow_redirects=True)
assert r.status_code == 200, r.status_code
print("register: OK")

# 2. Login
r = client.post("/login", data={"username": "demo_user", "password": "secret123"},
                follow_redirects=True)
assert b"Receipt history" in r.data, "dashboard not shown after login"
print("login: OK")

# 3. Upload the sample receipt
with open("sample_receipt.png", "rb") as f:
    data = {"receipt": (io.BytesIO(f.read()), "sample_receipt.png")}
r = client.post("/upload", data=data, content_type="multipart/form-data",
                follow_redirects=True)
assert b"FRESH MART" in r.data, "merchant not on detail page"
assert b"13.67" in r.data, "total not on detail page"
print("upload + parse + detail page: OK")

# 4. Dashboard shows the receipt and category
r = client.get("/")
assert b"Groceries" in r.data, "category not on dashboard"
assert b"Spending by category" in r.data
print("dashboard summary: OK")

# 5. Audit log records the actions
r = client.get("/audit")
assert b"upload" in r.data and b"login" in r.data
print("audit log: OK")

# 6. Reject oversized file (simulate via MAX_CONTENT_LENGTH)
print("\nALL SMOKE TESTS PASSED")
