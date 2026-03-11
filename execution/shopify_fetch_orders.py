"""
shopify_fetch_orders.py
=======================
Layer 3 — Execution Script

Fetches yesterday's orders from the Shopify Admin REST API.
Returns order count, gross revenue, tax total, refunds, and net revenue (ex tax).

Usage:
    python execution/shopify_fetch_orders.py

Output:
    Prints a JSON summary to stdout. Importable as a module via fetch_yesterday_orders().

Env vars required:
    SHOPIFY_STORE_URL      e.g. https://your-store.myshopify.com
    SHOPIFY_ACCESS_TOKEN   Admin API access token
"""

import os
import sys
import io
import json
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8')

# Load environment variables from .env file in project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

SHOPIFY_STORE_URL   = os.getenv("SHOPIFY_STORE_URL", "").rstrip("/")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN", "")


def get_yesterday_window_utc():
    """Return (start, end) ISO 8601 strings in UTC, covering yesterday in AEST (UTC+10)."""
    # 1. Get current time in AEST
    aest_now = datetime.now(timezone.utc) + timedelta(hours=10)
    
    # 2. Get start/end of yesterday in AEST
    yesterday_aest_start = (aest_now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_aest_end   = yesterday_aest_start + timedelta(hours=23, minutes=59, seconds=59)
    
    # 3. Convert AEST bounds back to UTC equivalents
    # AEST is UTC+10, so UTC = AEST - 10 hours
    utc_start = yesterday_aest_start - timedelta(hours=10)
    utc_end   = yesterday_aest_end   - timedelta(hours=10)
    
    return utc_start.strftime("%Y-%m-%dT%H:%M:%SZ"), utc_end.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_all_orders(created_at_min: str, created_at_max: str) -> list:
    """
    Fetch all orders from Shopify for the given UTC window.
    Handles pagination automatically (limit 250 per page).
    Includes any order status (paid, refunded, cancelled).
    """
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json",
    }
    base_url = f"{SHOPIFY_STORE_URL}/admin/api/2024-01/orders.json"
    params = {
        "status": "any",
        "created_at_min": created_at_min,
        "created_at_max": created_at_max,
        "limit": 250,
        "fields": "id,total_price,subtotal_price,total_tax,financial_status,refunds",
    }

    all_orders = []
    page_info  = None

    while True:
        if page_info:
            # Use cursor-based pagination for subsequent pages
            page_params = {"limit": 250, "page_info": page_info}
            response = requests.get(base_url, headers=headers, params=page_params, timeout=30)
        else:
            response = requests.get(base_url, headers=headers, params=params, timeout=30)

        response.raise_for_status()
        orders = response.json().get("orders", [])
        all_orders.extend(orders)

        # Check for next page via Link header
        link_header = response.headers.get("Link", "")
        if 'rel="next"' in link_header:
            # Extract page_info from link header: <url?page_info=xxx>; rel="next"
            for part in link_header.split(","):
                if 'rel="next"' in part:
                    url_part = part.split(";")[0].strip().strip("<>")
                    page_info = url_part.split("page_info=")[-1].split("&")[0]
                    break
        else:
            break  # No more pages

    return all_orders


def calculate_refunds(orders: list) -> float:
    """Sum all refund amounts across all orders."""
    total_refunded = 0.0
    for order in orders:
        for refund in order.get("refunds", []):
            for transaction in refund.get("transactions", []):
                # Only count successful refund transactions
                if transaction.get("kind") == "refund" and transaction.get("status") == "success":
                    total_refunded += float(transaction.get("amount", 0))
    return round(total_refunded, 2)


def fetch_yesterday_orders() -> dict:
    """
    Main function. Fetches yesterday's sales data from Shopify.
    """
    if not SHOPIFY_STORE_URL or not SHOPIFY_ACCESS_TOKEN:
        raise ValueError("SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN must be set in .env")

    start, end = get_yesterday_window_utc()
    aest_now = datetime.now(timezone.utc) + timedelta(hours=10)
    yesterday_date = (aest_now - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"[Shopify] Fetching orders from {start} → {end} (UTC window for AEST day)")
    orders = fetch_all_orders(start, end)

    # Only count financially processed orders (not pending/voided)
    countable_statuses = {"paid", "partially_paid", "partially_refunded", "refunded"}
    counted_orders = [o for o in orders if o.get("financial_status") in countable_statuses]

    gross_revenue = sum(float(o.get("total_price", 0)) for o in counted_orders)
    tax_total     = sum(float(o.get("total_tax", 0))   for o in counted_orders)
    refunds       = calculate_refunds(counted_orders)
    net_revenue   = round(gross_revenue - tax_total - refunds, 2)

    result = {
        "date":          yesterday_date,
        "orders":        len(counted_orders),
        "gross_revenue": round(gross_revenue, 2),
        "tax_total":     round(tax_total, 2),
        "refunds":       round(refunds, 2),
        "net_revenue":   round(net_revenue, 2),
    }

    print(f"[Shopify] ✓ Orders: {result['orders']} | Gross: ${result['gross_revenue']:.2f} | "
          f"Net: ${result['net_revenue']:.2f}")
    return result


if __name__ == "__main__":
    try:
        data = fetch_yesterday_orders()
        print("\n--- Shopify Output ---")
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"[Shopify] ✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
