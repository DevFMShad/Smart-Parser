"""
Storage service  --  local stand-in for Amazon S3.

Responsibilities:
  * save an uploaded file to disk under a unique name
  * delete a file
  * purge files older than the retention window (30 days)

Everything that touches the filesystem lives here, so swapping to real S3
later means changing only this one file (e.g. boto3 put_object / delete_object).
"""

import os
import uuid
from datetime import datetime, timedelta

from config import STORAGE_DIR, RETENTION_DAYS
from database import get_connection


def _ensure_dir():
    os.makedirs(STORAGE_DIR, exist_ok=True)


def save(file_storage, original_name):
    """
    Save a Werkzeug FileStorage to disk. Returns (stored_path, purge_after).

    The stored filename is a random UUID + original extension, which avoids
    collisions and stops a user from overwriting another user's file by
    choosing a clever name (a small security win worth mentioning in defense).
    """
    _ensure_dir()
    ext = os.path.splitext(original_name)[1].lower()
    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(STORAGE_DIR, stored_name)
    file_storage.save(stored_path)

    purge_after = (datetime.now() + timedelta(days=RETENTION_DAYS)).isoformat(timespec="seconds")
    return stored_path, purge_after


def delete(stored_path):
    """Remove a single stored file if it still exists."""
    try:
        if stored_path and os.path.exists(stored_path):
            os.remove(stored_path)
            return True
    except OSError as exc:  # pragma: no cover
        print(f"[storage] could not delete {stored_path}: {exc}")
    return False


def purge_expired():
    """
    Delete original files whose retention window has passed (30 days), and
    blank out their stored_path in the DB. The receipt's extracted DATA is
    kept; only the original image/PDF is purged, exactly as the spec requires.

    Returns the number of files purged. Called once on every app start.
    """
    now_iso = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, stored_path FROM receipts "
        "WHERE stored_path != '' AND purge_after < ?",
        (now_iso,),
    ).fetchall()

    purged = 0
    for row in rows:
        if delete(row["stored_path"]):
            purged += 1
        conn.execute("UPDATE receipts SET stored_path = '' WHERE id = ?", (row["id"],))

    conn.commit()
    conn.close()
    return purged
