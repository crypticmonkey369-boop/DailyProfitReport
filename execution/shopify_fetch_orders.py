"""
shopify_fetch_orders.py
=======================
Layer 3 — Execution Script

Fetches yesterday's orders from the Shopify Admin REST API.
Returns order count, gross revenue, tax total, refunds, and net revenue (ex tax).
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8')

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


def fetch_all_orders(created_at_min: str, created_at_max: str, store_url: str, access_token: str) -> list:
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }
    base_url = f"{store_url}/admin/api/2024-01/orders.json"
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
            page_params = {"limit": 250, "page_info": page_info}
            response = requests.get(base_url, headers=headers, params=page_params, timeout=30)
        else:
            response = requests.get(base_url, headers=headers, params=params, timeout=30)

        response.raise_for_status()
        orders = response.json().get("orders", [])
        all_orders.extend(orders)

        link_header = response.headers.get("Link", "")
        if 'rel="next"' in link_header:
            for part in link_header.split(","):
                if 'rel="next"' in part:
                    url_part = part.split(";")[0].strip().strip("<>")
                    page_info = url_part.split("page_info=")[-1].split("&")[0]
                    break
        else:
            break

    return all_orders


def calculate_refunds(orders: list) -> float:
    total_refunded = 0.0
    for order in orders:
        for refund in order.get("refunds", []):
            for transaction in refund.get("transactions", []):
                if transaction.get("kind") == "refund" and transaction.get("status") == "success":
                    total_refunded += float(transaction.get("amount", 0))
    return round(total_refunded, 2)


def fetch_yesterday_orders() -> dict:
    # Load env here to be absolutely sure
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
    store_url    = os.getenv("SHOPIFY_STORE_URL", "").rstrip("/")
    access_token = os.getenv("SHOPIFY_ACCESS_TOKEN", "").strip()

    if not store_url or not access_token:
        raise ValueError("SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN missing from .env")

    start, end = get_yesterday_window_utc()
    aest_now = datetime.now(timezone.utc) + timedelta(hours=10)
    yesterday_date = (aest_now - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"[Shopify] Fetching orders for {yesterday_date} (AEST)")
    orders = fetch_all_orders(start, end, store_url, access_token)

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

    print(f"[Shopify] ✓ Orders: {result['orders']} | Net: ${result['net_revenue']:.2f}")
    return result


if __name__ == "__main__":
    try:
        data = fetch_yesterday_orders()
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"[Shopify] ✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
