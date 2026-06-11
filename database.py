"""
SQLite database layer.

SQLite is a single file (receipts.db) so there is nothing to install or
configure. The SQL here is standard, so in production one could point the
same queries at PostgreSQL.

Tables
------
users         - registered accounts (hashed passwords)
receipts      - one row per uploaded receipt (merchant, date, total, category)
receipt_items - the individual line items extracted from each receipt
audit_log     - an append-only record of every important action
ocr_usage     - pages processed per day, to enforce the 500/day OCR quota
"""

import sqlite3
from config import DB_PATH


def get_connection():
    """Open a connection. row_factory lets us read columns by name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enforce foreign keys (off by default in SQLite).
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they do not exist yet. Safe to call on every start."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin      INTEGER NOT NULL DEFAULT 0,   -- 1 = can see the audit log
            created_at    TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS receipts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            original_name TEXT NOT NULL,
            stored_path   TEXT NOT NULL,
            merchant      TEXT,
            purchase_date TEXT,
            total         REAL,
            category      TEXT,
            raw_text      TEXT,
            status        TEXT NOT NULL,          -- processed / failed
            process_ms    INTEGER,                -- how long OCR+parse took
            uploaded_at   TEXT NOT NULL,
            purge_after   TEXT NOT NULL,          -- uploaded_at + 30 days
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS receipt_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_id  INTEGER NOT NULL,
            description TEXT NOT NULL,
            price       REAL,
            category    TEXT,
            FOREIGN KEY (receipt_id) REFERENCES receipts(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            username   TEXT,
            action     TEXT NOT NULL,
            detail     TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ocr_usage (
            day   TEXT PRIMARY KEY,    -- YYYY-MM-DD
            pages INTEGER NOT NULL
        )
    """)

    # --- Migration: add is_admin to older databases that predate it -------
    columns = [row["name"] for row in cur.execute("PRAGMA table_info(users)")]
    if "is_admin" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")

    # Make sure at least one admin exists: if none, promote the first user.
    has_admin = cur.execute("SELECT COUNT(*) AS c FROM users WHERE is_admin = 1").fetchone()["c"]
    if has_admin == 0:
        first = cur.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
        if first:
            cur.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (first["id"],))

    conn.commit()
    conn.close()
