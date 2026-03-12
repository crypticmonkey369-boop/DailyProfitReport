"""
run_daily_report.py
===================
Layer 2 — Orchestrator Script

This is the main entry point for the daily profit report pipeline.
It calls all execution scripts in order, calculates profit, writes to
Google Sheets, and sends the email. Exits with code 1 on any failure.

Usage:
    python execution/run_daily_report.py

This script is what GitHub Actions calls every day at 8:00 AM UTC (6 PM AEST).
All output prints to stdout — visible in the GitHub Actions log.

Env vars required:
    All vars from .env.example must be set (see .env.example for reference).
    COGS_PER_ORDER, SHIPPING_PER_ORDER, PAYMENT_FEE_PCT, PAYMENT_FEE_FIXED
    are used directly here for the profit formula.
"""

import os
import sys
import io
import sys
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8')
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── Profit Formula Constants ──────────────────────────────────────────────────
COGS_PER_ORDER      = float(os.getenv("COGS_PER_ORDER",     "42.00"))
SHIPPING_PER_ORDER  = float(os.getenv("SHIPPING_PER_ORDER", "9.50"))
PAYMENT_FEE_PCT     = float(os.getenv("PAYMENT_FEE_PCT",    "0.0175"))  # 1.75%
PAYMENT_FEE_FIXED   = float(os.getenv("PAYMENT_FEE_FIXED",  "0.30"))    # per order


def calculate_profit(shopify: dict, meta: dict, klaviyo: dict) -> dict:
    """
    Applies the profit formula to the raw API data.

    Formula:
        Total Revenue   = net_revenue (ex tax, ex refunds) + email_revenue
        COGS cost       = COGS_PER_ORDER × orders
        Shipping cost   = SHIPPING_PER_ORDER × orders
        Payment fees    = (PAYMENT_FEE_PCT × net_revenue) + (PAYMENT_FEE_FIXED × orders)
        Profit          = Total Revenue − COGS − Shipping − Payment Fees − Ad Spend
        Margin %        = Profit / Total Revenue × 100
    """
    orders          = shopify.get("orders", 0)
    net_revenue     = shopify.get("net_revenue", 0.0)
    email_revenue   = klaviyo.get("email_revenue", 0.0)
    ad_spend        = meta.get("ad_spend", 0.0)

    total_revenue   = round(net_revenue + email_revenue, 2)
    cogs_cost       = round(COGS_PER_ORDER * orders, 2)
    shipping_cost   = round(SHIPPING_PER_ORDER * orders, 2)
    payment_fees    = round((PAYMENT_FEE_PCT * net_revenue) + (PAYMENT_FEE_FIXED * orders), 2)

    profit          = round(total_revenue - cogs_cost - shipping_cost - payment_fees - ad_spend, 2)
    margin_pct      = round((profit / total_revenue * 100), 1) if total_revenue > 0 else 0.0

    return {
        "total_revenue":    total_revenue,
        "cogs_cost":        cogs_cost,
        "shipping_cost":    shipping_cost,
        "payment_fees":     payment_fees,
        "profit":           profit,
        "margin_pct":       margin_pct,
        "cogs_per_order":   COGS_PER_ORDER,
        "shipping_per_order": SHIPPING_PER_ORDER,
        "payment_fee_pct":  PAYMENT_FEE_PCT,
    }


def print_summary(data: dict) -> None:
    """Print a nicely formatted summary to stdout (shows in GitHub Actions log)."""
    sep = "─" * 52
    print(f"\n{'═'*52}")
    print(f"  DAILY PROFIT REPORT — {data.get('date', '')}")
    print(f"{'═'*52}")
    print(f"  Orders:            {data.get('orders', 0):>8}")
    print(f"  Gross Revenue:     ${data.get('gross_revenue', 0):>12,.2f}")
    print(f"  Net Revenue:       ${data.get('net_revenue', 0):>12,.2f}")
    print(f"  Email Revenue:     ${data.get('email_revenue', 0):>12,.2f}")
    print(f"  Total Revenue:     ${data.get('total_revenue', 0):>12,.2f}")
    print(sep)
    print(f"  COGS Cost:         ${data.get('cogs_cost', 0):>12,.2f}")
    print(f"  Shipping Cost:     ${data.get('shipping_cost', 0):>12,.2f}")
    print(f"  Payment Fees:      ${data.get('payment_fees', 0):>12,.2f}")
    print(f"  Meta Ad Spend:     ${data.get('ad_spend', 0):>12,.2f}")
    print(sep)
    print(f"  PROFIT:            ${data.get('profit', 0):>12,.2f}")
    print(f"  MARGIN:            {data.get('margin_pct', 0):>11.1f}%")
    print(f"{'═'*52}\n")


def run():
    """Main pipeline. Exits with code 1 on failure."""

    print("\n" + "="*52)
    print("  DAILY PROFIT REPORT — STARTING PIPELINE")
    print("="*52)
    AEST = timezone(timedelta(hours=10))
    yesterday = (datetime.now(AEST) - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"  Reporting date: {yesterday} (AEST)\n")

    # ── Step 1: Fetch Shopify orders ────────────────────────────────────────
    print("[1/5] Fetching Shopify orders...")
    try:
        from shopify_fetch_orders import fetch_yesterday_orders
        shopify_data = fetch_yesterday_orders()
    except Exception as e:
        msg = str(e)
        print(f"[X] Shopify fetch failed: {msg}", file=sys.stderr)
        from send_email_report import send_error_alert
        send_error_alert(msg, step="Shopify order fetch")
        sys.exit(1)

    # ── Step 2: Fetch Meta Ads spend ────────────────────────────────────────
    print("\n[2/5] Fetching Meta Ads spend...")
    try:
        from meta_fetch_spend import fetch_yesterday_spend
        meta_data = fetch_yesterday_spend()
    except Exception as e:
        msg = str(e)
        print(f"[X] Meta Ads fetch failed: {msg}", file=sys.stderr)
        from send_email_report import send_error_alert
        send_error_alert(msg, step="Meta Ads spend fetch")
        sys.exit(1)

    # ── Step 3: Fetch Klaviyo revenue ───────────────────────────────────────
    print("\n[3/5] Fetching Klaviyo email revenue...")
    try:
        from klaviyo_fetch_revenue import fetch_yesterday_revenue
        klaviyo_data = fetch_yesterday_revenue()
    except Exception as e:
        msg = str(e)
        print(f"[X] Klaviyo fetch failed: {msg}", file=sys.stderr)
        from send_email_report import send_error_alert
        send_error_alert(msg, step="Klaviyo revenue fetch")
        sys.exit(1)

    # ── Step 4: Calculate profit ────────────────────────────────────────────
    print("\n[4/5] Calculating profit...")
    profit_data = calculate_profit(shopify_data, meta_data, klaviyo_data)

    # Merge all data into one complete record
    full_record = {
        **shopify_data,
        "ad_spend":      meta_data.get("ad_spend", 0.0),
        "email_revenue": klaviyo_data.get("email_revenue", 0.0),
        "emails_sent":   klaviyo_data.get("emails_sent", 0),
        "open_rate":     klaviyo_data.get("open_rate", 0.0),
        "click_rate":    klaviyo_data.get("click_rate", 0.0),
        **profit_data,
    }

    print_summary(full_record)

    # ── Step 5a: Write to Google Sheets ─────────────────────────────────────
    print("[5a/5] Writing to Google Sheets...")
    try:
        from google_sheets_write import write_daily_row
        write_daily_row(full_record)
    except Exception as e:
        # Non-fatal: log the error but continue to send email
        print(f"⚠ Google Sheets write failed: {e}", file=sys.stderr)

    # ── Step 5b: Send email report ───────────────────────────────────────────
    print("\n[5b/5] Sending email report...")
    try:
        from send_email_report import send_profit_email
        send_profit_email(full_record)
    except Exception as e:
        msg = str(e)
        print(f"[X] Email send failed: {msg}", file=sys.stderr)
        from send_email_report import send_error_alert
        send_error_alert(msg, step="Email delivery")
        sys.exit(1)

    print("\n✓ Daily profit report pipeline completed successfully.\n")


if __name__ == "__main__":
    # Ensure execution/ directory is on the Python path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    run()
