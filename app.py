"""
Receipt Parser  --  main Flask application.

Run with:  python app.py
Then open: http://127.0.0.1:5000

This file wires together the services. Each upload flows through the pipeline:

    upload -> storage_service (save)
           -> ocr_service     (Tesseract -> raw text, with quota + retries)
           -> extraction_service (raw text -> merchant/date/items/total)
           -> category_service   (classify items + receipt)
           -> database           (persist)
           -> audit_service      (record what happened)
"""

import os
import time
from datetime import datetime, timedelta

from flask import (
    Flask, render_template, request, redirect, url_for, flash, session, abort
)

import config
from database import init_db, get_connection
import auth
from services import storage_service as storage
from services import ocr_service as ocr
from services import extraction_service as extraction
from services import category_service as category
from services import audit_service as audit


app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
# Flask rejects bodies larger than this BEFORE reading them -> enforces 10 MB.
app.config["MAX_CONTENT_LENGTH"] = config.MAX_FILE_BYTES


# --- One-time startup tasks ------------------------------------------------
init_db()
_purged = storage.purge_expired()          # 30-day retention enforcement
if _purged:
    audit.log("purge", f"purged {_purged} expired original file(s)")
    print(f"[startup] purged {_purged} expired file(s)")


# --- Helpers ---------------------------------------------------------------
def _allowed(filename):
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    return ext in config.ALLOWED_EXTENSIONS


@app.context_processor
def inject_user():
    """Make the current user (and admin flag) available to every template."""
    uid, uname = auth.current_user()
    return {"current_username": uname, "current_uid": uid,
            "current_is_admin": auth.is_admin()}


# --- Auth routes -----------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register_view():
    if request.method == "POST":
        try:
            auth.register(request.form.get("username"), request.form.get("password"))
            flash("Account created. Please log in.", "success")
            return redirect(url_for("login_view"))
        except auth.AuthError as exc:
            flash(str(exc), "error")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login_view():
    if request.method == "POST":
        try:
            auth.login(request.form.get("username"), request.form.get("password"))
            return redirect(url_for("dashboard"))
        except auth.AuthError as exc:
            flash(str(exc), "error")
    return render_template("login.html")


@app.route("/logout")
def logout_view():
    auth.logout()
    flash("Logged out.", "success")
    return redirect(url_for("login_view"))


# --- Main pages ------------------------------------------------------------
@app.route("/")
@auth.login_required
def dashboard():
    uid, _ = auth.current_user()
    conn = get_connection()
    receipts = conn.execute(
        "SELECT * FROM receipts WHERE user_id = ? ORDER BY id DESC", (uid,)
    ).fetchall()

    # Summary stats for the dashboard cards.
    total_spent = sum(r["total"] or 0 for r in receipts)
    by_category = {}
    for r in receipts:
        cat = r["category"] or "Other"
        by_category[cat] = by_category.get(cat, 0) + (r["total"] or 0)
    conn.close()

    return render_template(
        "dashboard.html",
        receipts=receipts,
        total_spent=total_spent,
        by_category=sorted(by_category.items(), key=lambda kv: kv[1], reverse=True),
        ocr_used=ocr.pages_used_today(),
        ocr_limit=config.OCR_DAILY_PAGE_LIMIT,
    )


@app.route("/upload", methods=["POST"])
@auth.login_required
def upload():
    uid, uname = auth.current_user()
    file = request.files.get("receipt")

    if not file or file.filename == "":
        flash("Please choose a file to upload.", "error")
        return redirect(url_for("dashboard"))
    if not _allowed(file.filename):
        flash("Unsupported file type. Use an image (PNG/JPG/TIFF) or PDF.", "error")
        return redirect(url_for("dashboard"))

    started = time.time()
    stored_path, purge_after = storage.save(file, file.filename)

    try:
        raw_text, pages = ocr.extract_text(stored_path)
        data = extraction.extract(raw_text)

        # Categorize each item by keyword, then the receipt as a whole.
        for item in data["items"]:
            item["category"] = category.categorize_text(item["description"])
        receipt_category = category.categorize_receipt(data["merchant"], data["items"])
        # Fall back to the receipt's category for any item a keyword didn't catch
        # (e.g. an unrecognised item on a cafe receipt is still "Dining").
        for item in data["items"]:
            if item["category"] == category.DEFAULT_CATEGORY:
                item["category"] = receipt_category

        elapsed_ms = int((time.time() - started) * 1000)
        if elapsed_ms > config.PROCESS_BUDGET_SECONDS * 1000:
            print(f"[warn] processing took {elapsed_ms} ms (budget "
                  f"{config.PROCESS_BUDGET_SECONDS}s)")

        # Persist receipt + items.
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO receipts
               (user_id, original_name, stored_path, merchant, purchase_date,
                total, category, raw_text, status, process_ms, uploaded_at, purge_after)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (uid, file.filename, stored_path, data["merchant"], data["purchase_date"],
             data["total"], receipt_category, raw_text, "processed", elapsed_ms,
             datetime.now().isoformat(timespec="seconds"), purge_after),
        )
        receipt_id = cur.lastrowid
        for item in data["items"]:
            cur.execute(
                "INSERT INTO receipt_items (receipt_id, description, price, category) "
                "VALUES (?,?,?,?)",
                (receipt_id, item["description"], item["price"], item["category"]),
            )
        conn.commit()
        conn.close()

        audit.log("upload", f"receipt #{receipt_id} '{file.filename}' "
                            f"({pages} page(s), {elapsed_ms} ms)",
                  user_id=uid, username=uname)
        flash(f"Receipt processed in {elapsed_ms/1000:.1f}s "
              f"({len(data['items'])} items found).", "success")
        return redirect(url_for("receipt_detail", receipt_id=receipt_id))

    except ocr.OcrQuotaExceeded as exc:
        storage.delete(stored_path)
        audit.log("ocr_quota", str(exc), user_id=uid, username=uname)
        flash(str(exc), "error")
    except (ocr.OcrError, Exception) as exc:        # noqa: BLE001
        # Record the failure so it is visible in the audit log.
        conn = get_connection()
        conn.execute(
            """INSERT INTO receipts
               (user_id, original_name, stored_path, status, uploaded_at, purge_after)
               VALUES (?,?,?,?,?,?)""",
            (uid, file.filename, stored_path, "failed",
             datetime.now().isoformat(timespec="seconds"), purge_after),
        )
        conn.commit()
        conn.close()
        audit.log("upload_failed", f"'{file.filename}': {exc}", user_id=uid, username=uname)
        flash(f"Could not process that receipt: {exc}", "error")

    return redirect(url_for("dashboard"))


@app.route("/receipt/<int:receipt_id>")
@auth.login_required
def receipt_detail(receipt_id):
    uid, _ = auth.current_user()
    conn = get_connection()
    receipt = conn.execute(
        "SELECT * FROM receipts WHERE id = ? AND user_id = ?", (receipt_id, uid)
    ).fetchone()
    if receipt is None:
        conn.close()
        abort(404)
    items = conn.execute(
        "SELECT * FROM receipt_items WHERE receipt_id = ?", (receipt_id,)
    ).fetchall()
    conn.close()
    return render_template("receipt_detail.html", receipt=receipt, items=items)


@app.route("/receipt/<int:receipt_id>/delete", methods=["POST"])
@auth.login_required
def receipt_delete(receipt_id):
    uid, uname = auth.current_user()
    conn = get_connection()
    receipt = conn.execute(
        "SELECT * FROM receipts WHERE id = ? AND user_id = ?", (receipt_id, uid)
    ).fetchone()
    if receipt is None:
        conn.close()
        abort(404)
    storage.delete(receipt["stored_path"])
    conn.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))   # items cascade
    conn.commit()
    conn.close()
    audit.log("delete", f"receipt #{receipt_id}", user_id=uid, username=uname)
    flash("Receipt deleted.", "success")
    return redirect(url_for("dashboard"))


@app.route("/audit")
@auth.admin_required
def audit_view():
    """
    Audit trail page -- ADMIN ONLY.
    The @admin_required decorator enforces authorization: a normal logged-in
    user is redirected away, so they cannot see other users' activity.
    """
    return render_template("audit.html", entries=audit.recent(200))


# --- Error handler for the 10 MB limit -------------------------------------
@app.errorhandler(413)
def too_large(_e):
    flash(f"File too large. Maximum size is "
          f"{config.MAX_FILE_BYTES // (1024*1024)} MB.", "error")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    print("Receipt Parser running at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
