"""
Central configuration for the Receipt Parser.

Every limit from the project spec lives here in one place"""

import os

# --- Paths -----------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")        # local stand-in for S3
DB_PATH = os.path.join(BASE_DIR, "receipts.db")

# --- Tesseract OCR engine --------------------------------------------------
# On Windows the UB-Mannheim build installs here. pytesseract needs the path
# to the .exe because Tesseract is not added to PATH by default.
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# --- Business rules / limits (straight from the spec) ----------------------
MAX_USERS = 2000                       # max 2,000 users
MAX_FILE_BYTES = 10 * 1024 * 1024      # max file size 10 MB
PROCESS_BUDGET_SECONDS = 60            # process < 60s / receipt (we measure & warn)
OCR_DAILY_PAGE_LIMIT = 500             # OCR limit 500 pages / day
RETENTION_DAYS = 30                    # store originals 30 days then purge
MAX_OCR_RETRIES = 3                    # retries for failures

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "bmp", "tiff", "pdf"}

# --- Flask -----------------------------------------------------------------
# In a real deployment this would come from an environment variable / secrets
# manager, never be committed. Hard-coded here only to keep the demo runnable.
SECRET_KEY =  "receipt-parser-demo"
