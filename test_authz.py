"""Authorization test: only admins may view the audit log."""
import os
if os.path.exists("receipts.db"):
    os.remove("receipts.db")

from app import app
c = app.test_client()

# First user registered -> becomes admin. Second -> normal user.
c.post("/register", data={"username": "adminuser", "password": "secret123"})
c.post("/register", data={"username": "normaluser", "password": "secret123"})

# --- Normal user must NOT access the audit log ---
c.post("/login", data={"username": "normaluser", "password": "secret123"})
r = c.get("/audit", follow_redirects=False)
assert r.status_code == 302, f"expected redirect, got {r.status_code}"
print("normal user blocked from /audit (redirected):", r.headers.get("Location"))

home = c.get("/").data
assert b">Audit" not in home, "audit link should be hidden for normal user"
print("audit link hidden for normal user: OK")
c.get("/logout")

# --- Admin user CAN access the audit log ---
c.post("/login", data={"username": "adminuser", "password": "secret123"})
r = c.get("/audit")
assert r.status_code == 200 and b"Audit log" in r.data, "admin should see audit log"
print("admin can view /audit: OK")
assert b"Audit" in c.get("/").data, "admin should see audit nav link"
print("audit link visible for admin: OK")
assert b"access_denied" in r.data, "denied attempt should be recorded"
print("denied attempt was audited: OK")

print("\nAUTHORIZATION TESTS PASSED")
