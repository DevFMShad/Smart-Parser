# 🧾 Receipt Parser

A web application that lets users upload a **receipt image or PDF**, runs **OCR**
to read the text, **extracts** the structured data (merchant, date, line items,
total), and **categorizes** the expense automatically.

Built with **Python + Flask**, **Tesseract OCR**, and **SQLite**.

---

## 1. How to run it

> Tesseract OCR and all Python packages are already installed on this machine.
> If you move the project to another computer, see "Setup from scratch" below.

```powershell
cd C:\Users\fuade\Downloads\Smart_Parser_Main_File
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

1. Click **Sign up**, create an account (username 3+ chars, password 6+).
   > The **first** account you create automatically becomes the **admin** — the
   > only role allowed to view the audit log. Create a second account to
   > demonstrate a normal (non-admin) user.
2. Log in.
3. On the dashboard, click **Choose receipt**, pick an image or PDF, and
   **Upload & parse**.
4. You'll see the extracted merchant, date, line items, category, and total.

There is a ready-made test image: **`sample_receipt.png`**
(regenerate it any time with `python make_sample.py`).

---

## 2. What to demo in your defense (5-minute script)

1. **Sign up + log in** — show passwords are hashed (open `receipts.db`, the
   `users` table stores `password_hash`, never the plain password).
2. **Upload `sample_receipt.png`** — show it gets parsed in well under a second.
3. **Open the receipt detail page** — show the extracted line items, the
   per-item categories, the total, and scroll down to **"Raw OCR text"** to prove
   the text really came from the image (not hard-coded).
4. **Back on the dashboard** — show the **Spending by category** bars and the
   **OCR pages today / 500** counter.
5. **Audit log page (admin only)** — log in as the **first** account you created
   (the admin) and show every action was recorded. Then log in as a second,
   normal account and show the **Audit log link is gone** and visiting
   `/audit` directly is **refused** — this is role-based authorization.
6. **Try a too-big file or a `.txt`** — show it is rejected with a friendly error.

---

## 3. Architecture — how this maps to the original cloud design

The assignment describes a cloud system. This project implements the **same
design locally**, so it runs on one laptop with no accounts or costs. Each cloud
component has a direct local equivalent behind a clean service interface — so
"upgrading" to the cloud means changing one file, not rewriting the app.

| Cloud design (the spec)        | This project (local)                     | File |
|--------------------------------|------------------------------------------|------|
| Object storage (S3)            | A local `storage/` folder                | `services/storage_service.py` |
| External OCR (Textract/Vision) | **Tesseract** OCR engine                 | `services/ocr_service.py` |
| Serverless extraction pipeline | A pure parsing function                  | `services/extraction_service.py` |
| Database                       | **SQLite** (`receipts.db`)               | `database.py` |
| Category service               | Keyword rules engine                     | `services/category_service.py` |
| Auth + audit                   | Session login + audit-log table          | `auth.py`, `services/audit_service.py` |

**The upload pipeline:**

```
Upload → storage_service (save original)
       → ocr_service       (Tesseract → raw text; daily quota + retries)
       → extraction_service (raw text → merchant / date / items / total)
       → category_service   (classify each item + the whole receipt)
       → database           (save receipt + items)
       → audit_service      (log what happened)
```

---

## 4. How each requirement from the spec is met

| Requirement                         | Where it lives |
|-------------------------------------|----------------|
| Max **2,000 users**                 | `auth.register()` checks the user count |
| Max file **10 MB**                  | `MAX_CONTENT_LENGTH` in `app.py` (rejected before reading) |
| Process **< 60s / receipt**         | Each upload is timed; `process_ms` is stored and shown |
| OCR limit **500 pages / day**       | `ocr_usage` table + check in `ocr_service.extract_text()` |
| Store originals **30 days, then purge** | `purge_after` column + `storage_service.purge_expired()` runs on startup |
| **Retries for failures**            | Retry loop with backoff in `ocr_service.extract_text()` |
| Upload **image or PDF**             | PDFs are rendered to images with PyMuPDF, then OCR'd page by page |

---

## 5. Project structure

```
Smart_Parser_Main_File/
├── app.py                 # Flask routes — ties everything together
├── config.py              # All limits & settings in one place
├── auth.py                # Register / login / sessions (hashed passwords)
├── database.py            # SQLite schema + connection helper
├── services/
│   ├── storage_service.py   # save / delete / purge files  (S3 analog)
│   ├── ocr_service.py       # Tesseract OCR + quota + retries (Textract analog)
│   ├── extraction_service.py# raw text → structured data
│   ├── category_service.py  # expense categorization
│   └── audit_service.py     # append-only action log
├── templates/             # HTML pages (Jinja2)
├── static/
│   ├── style.css          # the "analog receipt" design system
│   ├── fonts.css          # @font-face rules (self-hosted)
│   └── fonts/             # woff2 fonts bundled so the UI works OFFLINE
├── tests/test_extraction.py # unit tests for the parsing logic
├── make_sample.py         # generates sample_receipt.png for testing
├── seed_demo.py           # creates a demo admin + 2 receipts to preview the UI
├── smoke_test.py          # end-to-end test of the whole web flow
├── test_authz.py          # proves the audit log is admin-only
└── requirements.txt
```

---

## Design

The interface uses an **"analog receipt / editorial ledger"** theme — cream
paper slips on a warm desk, an editorial serif (**Fraunces**) for headings, a
grotesk (**Hanken Grotesk**) for body text, and a monospace (**IBM Plex Mono**)
for every figure, just like a real till printer. Signature details: torn
perforated paper edges, a rotated rubber-stamp status badge, and dotted leader
lines for amounts.

- The fonts are **self-hosted** in `static/fonts/`, so the design renders fully
  **offline** — no internet needed during your defense.
- Accessibility is built in (from the Vercel Web Interface Guidelines): visible
  keyboard focus rings, `prefers-reduced-motion` support, a skip link,
  `aria-live` status messages, labelled inputs with `autocomplete`, and
  `tabular-nums` for aligned figures.
- Want demo data to show it off? Run **`python seed_demo.py`** (creates
  `demo` / `demo123` as admin with two sample receipts), then log in.

This was built with the help of two published Claude skills: Anthropic's
**frontend-design** skill (for the bold, non-generic visual direction) and
Vercel's **web-design-guidelines** skill (for the accessibility audit).

## 6. Testing

```powershell
# Unit tests (parsing + categorization logic)
python tests\test_extraction.py

# End-to-end test (register → login → upload → parse → audit)
python smoke_test.py
```

---

## 7. Likely questions & honest answers

- **"Why Tesseract instead of AWS Textract?"**
  Same role (turn an image into text), but free, offline, and no account needed.
  The OCR is hidden behind `ocr_service`, so switching to Textract would only
  change that one file.

- **"Why SQLite instead of a 'real' database?"**
  It's a single file, zero setup, and uses standard SQL — so the exact same
  queries would run on PostgreSQL in production.

- **"How accurate is the parsing?"**
  OCR is never perfect on photos. The extractor uses regular expressions and
  sensible rules (e.g. prefer the line that says "TOTAL", ignore "subtotal"/
  "tax"/"visa"). The **Raw OCR text** panel shows exactly what the engine read,
  so you can always see why a value came out the way it did.

- **"How are passwords stored?"**
  Hashed with Werkzeug's PBKDF2 — the plain password is never saved.

- **"What stops one user seeing another's receipts?"**
  Every query is filtered by the logged-in `user_id`, and stored files use random
  UUID names.

- **"Who can see the audit log, and why?"**
  Only an **admin** (the first registered account). The audit log is a system-wide
  security record, so regular users must not see other people's activity. This is
  **authorization** (`@admin_required` in `auth.py`), separate from authentication —
  a non-admin who visits `/audit` is redirected, and that attempt is itself logged
  as `access_denied`. (Avoiding this kind of "broken access control" is #1 on the
  OWASP Top 10.)

- **"How would this scale to the cloud?"**
  Each service is independent, so storage → S3, OCR → Textract, DB → RDS, and the
  extraction function → a Lambda — without touching the rest of the app.

- **"Tell me about the interface design."**
  I chose a deliberate "analog receipt" theme so the UI matches the product
  instead of looking like a generic template — paper slips, a till-printer
  monospace for figures, torn edges and a rubber-stamp status. The fonts are
  self-hosted so it works offline, and it follows accessibility guidelines
  (keyboard focus, reduced-motion, labelled inputs, high-contrast colours).

---

## Setup from scratch (only needed on a new computer)

1. Install **Python 3.10+**.
2. Install **Tesseract OCR**. On Windows: `winget install UB-Mannheim.TesseractOCR`
   (it installs to `C:\Program Files\Tesseract-OCR\`; if your path differs, update
   `TESSERACT_PATH` in `config.py`).
3. Install Python packages: `pip install -r requirements.txt`
4. Run: `python app.py`


## Switching to cloud — exactly 4 files to change

The project was deliberately designed so each cloud component maps to exactly one file. You'd touch nothing else.

What you're replacing, File to change	and What to do
1. Tesseract → AWS Textract or Google Vision	services/ocr_service.py	Replace the pytesseract.image_to_string() call with an API call to Textract/Vision. The function still returns a text string — nothing else changes.
2. SQLite → PostgreSQL / MySQL / any real DB	database.py	Change sqlite3.connect("receipts.db") to a proper connection string like psycopg2.connect("postgresql://user:pass@host/db"). The SQL queries themselves don't need to change.
3. Local storage/ folder → AWS S3	services/storage_service.py	Replace the open()/os file calls with boto3 S3 calls (s3.upload_fileobj(), s3.delete_object() etc.)
4. config.py;	config.py	Move secrets (DB password, AWS keys) out of the file and into environment variables
app.py, auth.py, extraction_service.py, all the templates — none of that would need to change at all. That's the whole point of the service layer design.

"# Smart-Parser" 
