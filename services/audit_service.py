"""
Audit service.

Append-only log of important actions (login, upload, delete, purge, failures).
In production this might be a separate, write-once audit store; here it is a
table. Keeping it in its own module means the rest of the code just calls
audit.log(...) and does not care how it is stored.
"""

from datetime import datetime
from database import get_connection


def log(action, detail="", user_id=None, username=None):
    """Record one audit entry. Never raises - auditing must not break the app."""
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO audit_log (user_id, username, action, detail, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, username, action, detail, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        conn.close()
    except Exception as exc:  # pragma: no cover - defensive only
        print(f"[audit] failed to log '{action}': {exc}")


def recent(limit=100):
    """Return the most recent audit entries (used by the admin audit page)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows
