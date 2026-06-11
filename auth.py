"""
Authentication.

Simple session-based auth:
  * passwords are hashed with Werkzeug's PBKDF2 (never stored in plain text)
  * the logged-in user id is kept in the Flask session cookie (signed)
  * a 2,000-user cap is enforced, matching the spec
  * a @login_required decorator protects private pages
"""

from functools import wraps
from datetime import datetime

from flask import session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_connection
from config import MAX_USERS
from services import audit_service as audit


class AuthError(Exception):
    """Raised for register/login problems with a user-friendly message."""


def user_count():
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    conn.close()
    return n


def register(username, password):
    """Create a new account. Raises AuthError on any problem."""
    username = (username or "").strip()
    if len(username) < 3:
        raise AuthError("Username must be at least 3 characters.")
    if len(password or "") < 6:
        raise AuthError("Password must be at least 6 characters.")
    if user_count() >= MAX_USERS:
        raise AuthError(f"User limit reached ({MAX_USERS} max).")

    # The very first account to register becomes the admin (the one allowed to
    # view the system-wide audit log). Everyone after that is a normal user.
    is_admin = 1 if user_count() == 0 else 0

    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if existing:
        conn.close()
        raise AuthError("That username is already taken.")

    conn.execute(
        "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?)",
        (username, generate_password_hash(password), is_admin,
         datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()
    role = "admin" if is_admin else "user"
    audit.log("register", f"new {role} '{username}'", username=username)


def login(username, password):
    """Validate credentials and start a session. Raises AuthError if invalid."""
    username = (username or "").strip()
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()

    if row is None or not check_password_hash(row["password_hash"], password):
        audit.log("login_failed", f"username '{username}'", username=username)
        raise AuthError("Invalid username or password.")

    session["user_id"] = row["id"]
    session["username"] = row["username"]
    session["is_admin"] = bool(row["is_admin"])
    audit.log("login", "successful", user_id=row["id"], username=row["username"])


def logout():
    audit.log("logout", "", user_id=session.get("user_id"), username=session.get("username"))
    session.clear()


def current_user():
    """Return (user_id, username) or (None, None)."""
    return session.get("user_id"), session.get("username")


def is_admin():
    """True if the logged-in user is an admin."""
    return bool(session.get("is_admin"))


def login_required(view):
    """Decorator that redirects anonymous users to the login page."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login_view"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    """
    Decorator for admin-only pages. This is the authorization check the audit
    log was missing: a logged-in non-admin user is refused access.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login_view"))
        if not session.get("is_admin"):
            audit.log("access_denied", "tried to open the audit log",
                      user_id=session.get("user_id"), username=session.get("username"))
            flash("You don't have permission to view that page (admins only).", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped
