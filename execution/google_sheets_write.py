"""
google_sheets_write.py
======================
Layer 3 — Execution Script

Appends one row of daily profit data to the Google Sheet.
Checks for duplicates (same date) before writing — safe to re-run.

Usage (standalone test):
    python execution/google_sheets_write.py

Importable via: write_daily_row(data: dict) -> None

Env vars required:
    GOOGLE_CREDENTIALS_PATH
    GOOGLE_TOKEN_PATH
    SPREADSHEET_ID
"""

import os
import sys
import io
import sys
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8')
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
TOKEN_PATH       = os.getenv("GOOGLE_TOKEN_PATH",       "token.json")
SPREADSHEET_ID   = os.getenv("SPREADSHEET_ID",          "")

PROJECT_ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(PROJECT_ROOT, CREDENTIALS_PATH)
TOKEN_PATH       = os.path.join(PROJECT_ROOT, TOKEN_PATH)

TAB_NAME         = "Daily Log"


def get_google_client():
    """Authenticate and return a gspread client using OAuth2."""
    try:
        import gspread
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
    except ImportError:
        print("Missing dependencies. Run: pip install -r requirements.txt")
        sys.exit(1)

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
    ]

    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # In CI (GitHub Actions), this branch should never be reached
            # because token.json is written from a Secret
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDENTIALS_PATH}. "
                    "Run google_sheets_setup.py locally first."
                )
            flow  = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as tf:
            tf.write(creds.to_json())

    import gspread
    return gspread.authorize(creds)


def write_daily_row(data: dict) -> None:
    """
    Appends one row to the Daily Log sheet.

    Expected keys in `data`:
        date, orders, gross_revenue, tax_total, refunds, net_revenue,
        email_revenue, total_revenue, cogs_cost, shipping_cost,
        payment_fees, ad_spend, profit, margin_pct,
        cogs_per_order, shipping_per_order, payment_fee_pct
    """
    if not SPREADSHEET_ID:
        raise ValueError("SPREADSHEET_ID must be set in .env (run google_sheets_setup.py first)")

    client      = get_google_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    worksheet   = spreadsheet.worksheet(TAB_NAME)

    # Duplicate check: scan date column (col A) for today's date
    date_str   = data.get("date", "")
    date_col   = worksheet.col_values(1)  # Returns list of values in column A
    if date_str in date_col:
        print(f"[Google Sheets] ⚠ Row for {date_str} already exists — skipping to avoid duplicate.")
        return

    row = [
        data.get("date",              ""),
        data.get("orders",            0),
        data.get("gross_revenue",     0.0),
        data.get("tax_total",         0.0),
        data.get("refunds",           0.0),
        data.get("net_revenue",       0.0),
        data.get("email_revenue",     0.0),
        data.get("total_revenue",     0.0),
        data.get("cogs_cost",         0.0),
        data.get("shipping_cost",     0.0),
        data.get("payment_fees",      0.0),
        data.get("ad_spend",          0.0),
        data.get("profit",            0.0),
        data.get("margin_pct",        0.0),
        data.get("cogs_per_order",    0.0),
        data.get("shipping_per_order",0.0),
        data.get("payment_fee_pct",   0.0),
    ]

    worksheet.append_row(row, value_input_option="USER_ENTERED")
    print(f"[Google Sheets] ✓ Row written for {date_str}")


if __name__ == "__main__":
    # Standalone test using dummy data
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    test_data = {
        "date":             yesterday,
        "orders":           1,
        "gross_revenue":    100.00,
        "tax_total":        9.09,
        "refunds":          0.00,
        "net_revenue":      90.91,
        "email_revenue":    10.00,
        "total_revenue":    100.91,
        "cogs_cost":        42.00,
        "shipping_cost":    9.50,
        "payment_fees":     1.59 + 0.30,
        "ad_spend":         20.00,
        "profit":           27.52,
        "margin_pct":       27.3,
        "cogs_per_order":   42.00,
        "shipping_per_order": 9.50,
        "payment_fee_pct":  1.75,
    }
    try:
        write_daily_row(test_data)
    except Exception as e:
        print(f"[Google Sheets] ✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
