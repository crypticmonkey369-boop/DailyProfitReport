"""
google_sheets_setup.py
======================
Layer 3 - Execution Script (RUN ONCE LOCALLY)

Creates a new Google Sheet named "Daily Profit Report" with the correct
column headers for the daily profit log. Prints the Spreadsheet ID for
you to paste into your .env file as SPREADSHEET_ID.

Run this script once from your local machine:
    python execution/google_sheets_setup.py

Env vars required:
    GOOGLE_CREDENTIALS_PATH    Path to credentials.json (default: credentials.json)
    GOOGLE_TOKEN_PATH          Path to token.json (default: token.json)
"""

import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
TOKEN_PATH       = os.getenv("GOOGLE_TOKEN_PATH",       "token.json")

# Resolve paths relative to project root
PROJECT_ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(PROJECT_ROOT, CREDENTIALS_PATH)
TOKEN_PATH       = os.path.join(PROJECT_ROOT, TOKEN_PATH)

SHEET_NAME = "Daily Profit Report"
TAB_NAME   = "Daily Log"

# Column headers in order - matches google_sheets_write.py exactly
HEADERS = [
    "Date",
    "Orders",
    "Gross Revenue (AUD)",
    "Tax (AUD)",
    "Refunds (AUD)",
    "Net Revenue ex Tax (AUD)",
    "Klaviyo Email Revenue (AUD)",
    "Total Revenue (AUD)",
    "COGS Cost (AUD)",
    "Shipping Cost (AUD)",
    "Payment Fees (AUD)",
    "Meta Ad Spend (AUD)",
    "Estimated Profit (AUD)",
    "Profit Margin %",
    "COGS/Order Used",
    "Shipping/Order Used",
    "Payment Fee % Used",
]


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
        "https://www.googleapis.com/auth/gmail.send",
    ]

    creds = None

    # Load existing token
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # Refresh or perform new OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                print(f"\n[X] credentials.json not found at: {CREDENTIALS_PATH}")
                sys.exit(1)
            flow  = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save token for future runs
        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())
        print(f"[Google] Token saved to {TOKEN_PATH}")

    return gspread.authorize(creds)


def create_profit_sheet() -> str:
    """
    Creates the Google Sheet with headers.
    Returns the Spreadsheet ID.
    """
    client = get_google_client()

    print(f"[Google Sheets] Creating spreadsheet: '{SHEET_NAME}'")
    spreadsheet = client.create(SHEET_NAME)

    # Rename the default 'Sheet1' tab to 'Daily Log'
    worksheet = spreadsheet.sheet1
    worksheet.update_title(TAB_NAME)

    # Write header row (row 1)
    worksheet.append_row(HEADERS, value_input_option="USER_ENTERED")

    # Bold + freeze the header row via batch update
    spreadsheet.batch_update({
        "requests": [
            # Bold header row with dark background + white text
            {
                "repeatCell": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
                            "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2},
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            },
            # Freeze header row
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": worksheet.id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            # Auto-resize columns
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": worksheet.id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": len(HEADERS),
                    }
                }
            },
        ]
    })

    spreadsheet_id  = spreadsheet.id
    spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

    print(f"\n{'='*60}")
    print(f"[OK] Google Sheet created successfully!")
    print(f"  Name:  {SHEET_NAME}")
    print(f"  URL:   {spreadsheet_url}")
    print(f"\n{'='*60}")
    print(f"IMPORTANT: Copy this ID into your .env file:")
    print(f"\n  SPREADSHEET_ID={spreadsheet_id}\n")
    print(f"{'='*60}\n")

    return spreadsheet_id


if __name__ == "__main__":
    try:
        sheet_id = create_profit_sheet()
    except Exception as e:
        print(f"[Google Sheets Setup] Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
