"""
OCR service  --  local stand-in for AWS Textract / Google Vision.

It uses the Tesseract OCR engine (via pytesseract) to turn an image or PDF
into raw text. Around that core it implements the operational rules from the
spec:

  * 500 pages / day quota   (ocr_usage table)
  * retries for failures    (MAX_OCR_RETRIES with short backoff)
  * PDF support             (PyMuPDF renders each page to an image first)

Because it exposes one function -- extract_text(path) -> (text, pages) -- the
extraction pipeline does not care whether the engine is Tesseract or Textract.
"""

import io
import time
from datetime import date

import pytesseract
from PIL import Image
import fitz  # PyMuPDF

from config import TESSERACT_PATH, OCR_DAILY_PAGE_LIMIT, MAX_OCR_RETRIES
from database import get_connection

# Point pytesseract at the installed Tesseract binary.
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


class OcrQuotaExceeded(Exception):
    """Raised when the 500-pages-per-day limit would be exceeded."""


class OcrError(Exception):
    """Raised when OCR fails after all retries."""


# --- Daily quota helpers ---------------------------------------------------
def pages_used_today():
    conn = get_connection()
    row = conn.execute(
        "SELECT pages FROM ocr_usage WHERE day = ?", (date.today().isoformat(),)
    ).fetchone()
    conn.close()
    return row["pages"] if row else 0


def _record_pages(n):
    """Increment today's page counter (UPSERT)."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO ocr_usage (day, pages) VALUES (?, ?) "
        "ON CONFLICT(day) DO UPDATE SET pages = pages + ?",
        (date.today().isoformat(), n, n),
    )
    conn.commit()
    conn.close()


# --- Loading the file into a list of page images ---------------------------
def _load_page_images(path):
    """
    Return a list of PIL Images, one per page.
    Images -> single page. PDFs -> one rendered image per page (200 DPI).
    """
    if path.lower().endswith(".pdf"):
        images = []
        doc = fitz.open(path)
        try:
            for page in doc:
                pix = page.get_pixmap(dpi=200)            # render page to bitmap
                images.append(Image.open(io.BytesIO(pix.tobytes("png"))))
        finally:
            doc.close()
        return images
    return [Image.open(path)]


# --- Public entry point ----------------------------------------------------
def extract_text(path):
    """
    OCR the file at `path`.

    Returns (raw_text, page_count).
    Raises OcrQuotaExceeded if the daily limit would be passed,
    or OcrError if Tesseract keeps failing after MAX_OCR_RETRIES.
    """
    images = _load_page_images(path)
    page_count = len(images)

    # Enforce the daily OCR quota BEFORE doing the work.
    if pages_used_today() + page_count > OCR_DAILY_PAGE_LIMIT:
        raise OcrQuotaExceeded(
            f"Daily OCR limit of {OCR_DAILY_PAGE_LIMIT} pages reached. "
            f"Used {pages_used_today()}, this file needs {page_count}."
        )

    # Retry loop: transient OCR failures are retried with a small backoff.
    last_error = None
    for attempt in range(1, MAX_OCR_RETRIES + 1):
        try:
            text_parts = [pytesseract.image_to_string(img) for img in images]
            _record_pages(page_count)
            return "\n".join(text_parts), page_count
        except Exception as exc:                          # noqa: BLE001
            last_error = exc
            print(f"[ocr] attempt {attempt}/{MAX_OCR_RETRIES} failed: {exc}")
            time.sleep(0.5 * attempt)                     # linear backoff

    raise OcrError(f"OCR failed after {MAX_OCR_RETRIES} attempts: {last_error}")
