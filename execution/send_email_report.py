"""
send_email_report.py
====================
Layer 3 - Execution Script

Sends the daily profit report email using the Gmail API via OAuth2.
No SMTP password or App Password required - uses the same Google OAuth
token as the Google Sheets integration (token.json).

Usage:
    python execution/send_email_report.py

Importable via: send_profit_email(data: dict) -> None

Env vars required:
    GOOGLE_CREDENTIALS_PATH   Path to credentials.json
    GOOGLE_TOKEN_PATH         Path to token.json
    REPORT_EMAIL              Recipient email address
"""

import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
TOKEN_PATH       = os.getenv("GOOGLE_TOKEN_PATH",       "token.json")
REPORT_EMAIL     = os.getenv("REPORT_EMAIL",            "")
ALERT_EMAIL      = os.getenv("ALERT_EMAIL",             "liam@makdivision.com.au")

PROJECT_ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(PROJECT_ROOT, CREDENTIALS_PATH)
TOKEN_PATH       = os.path.join(PROJECT_ROOT, TOKEN_PATH)

# Gmail OAuth scopes - must match what was authorised in token.json
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_gmail_service():
    """Build and return an authenticated Gmail API service."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow  = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as tf:
            tf.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def format_aud(value: float) -> str:
    sign = "-" if value < 0 else " "
    return f"{sign}${abs(value):,.2f}"


def format_pct(value: float) -> str:
    return f"{value:.1f}%"


def build_email_body(data: dict) -> tuple:
    """Return (subject, plain_text_body) for the daily profit report."""
    date_str = data.get("date", "")
    try:
        date_obj  = datetime.strptime(date_str, "%Y-%m-%d")
        date_nice = date_obj.strftime("%A, %d %b %Y")
    except ValueError:
        date_nice = date_str

    subject = f"Daily Profit Report - {date_nice}"

    profit    = data.get("profit", 0.0)
    margin    = data.get("margin_pct", 0.0)
    indicator = "PROFITABLE" if profit >= 0 else "LOSS DAY"

    body = f"""
====================================================
  DAILY PROFIT REPORT
  {date_nice}
====================================================

REVENUE
----------------------------------------------------
  Orders Placed:          {data.get('orders', 0):>8}
  Gross Revenue:          {format_aud(data.get('gross_revenue', 0)):>12}
  Tax Collected:        - {format_aud(data.get('tax_total', 0)):>12}
  Refunds:              - {format_aud(data.get('refunds', 0)):>12}
  --------------------------------------------------
  Net Revenue (ex tax):   {format_aud(data.get('net_revenue', 0)):>12}
  Klaviyo Email Rev:    + {format_aud(data.get('email_revenue', 0)):>12}
  --------------------------------------------------
  Total Revenue:          {format_aud(data.get('total_revenue', 0)):>12}

COSTS
----------------------------------------------------
  COGS ({data.get('orders',0)} x ${data.get('cogs_per_order',0):.2f}):     - {format_aud(data.get('cogs_cost', 0)):>12}
  Shipping ({data.get('orders',0)} x ${data.get('shipping_per_order',0):.2f}): - {format_aud(data.get('shipping_cost', 0)):>12}
  Payment Fees:         - {format_aud(data.get('payment_fees', 0)):>12}
  Meta Ad Spend:        - {format_aud(data.get('ad_spend', 0)):>12}

====================================================
  ESTIMATED PROFIT:       {format_aud(profit):>12}
  PROFIT MARGIN:          {format_pct(margin):>12}

  >> {indicator}
====================================================

KLAVIYO EMAIL STATS (informational)
----------------------------------------------------
  Emails Sent:            {data.get('emails_sent', 0):>8}
  Open Rate:              {format_pct(data.get('open_rate', 0)):>12}
  Click Rate:             {format_pct(data.get('click_rate', 0)):>12}

----------------------------------------------------
Note: Estimated operational profit only.
COGS/order: ${data.get('cogs_per_order',0):.2f} | Shipping/order: ${data.get('shipping_per_order',0):.2f}
Payment fee: {data.get('payment_fee_pct',0)*100:.2f}% + $0.30/order
----------------------------------------------------
Automated report - do not reply to this email.
    """.strip()

    return subject, body


def send_profit_email(data: dict) -> None:
    """
    Sends the daily profit report email via Gmail API (OAuth2).

    Args:
        data: The enriched profit data dict from run_daily_report.py
    """
    if not REPORT_EMAIL:
        raise ValueError("REPORT_EMAIL must be set in .env")

    subject, body = build_email_body(data)
    service       = get_gmail_service()

    # Support multiple recipients (comma-separated in REPORT_EMAIL)
    recipients = [r.strip() for r in REPORT_EMAIL.split(",") if r.strip()]

    # Debug: Log actual scopes and account from creds
    print(f"[Debug] Active scopes: {service._http.credentials.scopes}")
    try:
        profile = service.users().getProfile(userId="me").execute()
        print(f"[Debug] Authenticated as: {profile.get('emailAddress')}")
    except Exception as e:
        print(f"[Debug] Could not fetch profile: {e}")
    
    for recipient in recipients:
        msg            = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = "me"
        msg["To"]      = recipient
        msg.attach(MIMEText(body, "plain"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        print(f"[Email] Sending report to {recipient}...")
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        print(f"[Email] Report sent to {recipient}")


def send_error_alert(error_message: str, step: str = "Unknown") -> None:
    """
    Sends an error alert email to ALERT_EMAIL when the pipeline fails.
    Uses the same Gmail API OAuth token.

    Args:
        error_message: The error string to include in the alert
        step: Which pipeline step failed (e.g. 'Shopify fetch')
    """
    if not ALERT_EMAIL:
        print("[Alert] No ALERT_EMAIL set — skipping error alert.")
        return

    try:
        service = get_gmail_service()
        now_aest = datetime.now(timezone(timedelta(hours=10))).strftime("%Y-%m-%d %H:%M AEST")

        subject = f"[ALERT] Daily Profit Report Failed — {now_aest}"
        body = f"""DAILY PROFIT REPORT — PIPELINE ERROR
============================================================

Time:  {now_aest}
Step:  {step}

Error:
{error_message}

------------------------------------------------------------
The daily profit report did NOT complete successfully.
Please check the GitHub Actions log for full details:
https://github.com/crypticmonkey369-boop/DailyProfitReport/actions

This is an automated alert.
        """.strip()

        msg            = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = "me"
        msg["To"]      = ALERT_EMAIL
        msg.attach(MIMEText(body, "plain"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        print(f"[Alert] Sending error alert to {ALERT_EMAIL}...")
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        print(f"[Alert] Error alert sent to {ALERT_EMAIL}")
    except Exception as alert_err:
        print(f"[Alert] Failed to send error alert: {alert_err}", file=sys.stderr)


if __name__ == "__main__":
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    test_data = {
        "date":               yesterday,
        "orders":             38,
        "gross_revenue":      4180.00,
        "tax_total":          380.00,
        "refunds":            95.00,
        "net_revenue":        3705.00,
        "email_revenue":      412.00,
        "total_revenue":      4117.00,
        "cogs_cost":          1596.00,
        "shipping_cost":      361.00,
        "payment_fees":       64.87,
        "ad_spend":           420.00,
        "profit":             1675.13,
        "margin_pct":         40.7,
        "emails_sent":        1240,
        "open_rate":          28.4,
        "click_rate":         3.1,
        "cogs_per_order":     42.00,
        "shipping_per_order": 9.50,
        "payment_fee_pct":    0.0175,
    }
    try:
        send_profit_email(test_data)
    except Exception as e:
        print(f"[Email] Error: {e}", file=sys.stderr)
        sys.exit(1)
