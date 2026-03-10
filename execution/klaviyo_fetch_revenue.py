"""
klaviyo_fetch_revenue.py
========================
Layer 3 - Execution Script

Fetches yesterday's email-attributed revenue from Klaviyo using the
Klaviyo REST API (2024-02-15). Also retrieves email stats:
emails sent, open rate, click rate for the daily log.

Env vars required:
    KLAVIYO_API_KEY              Private API key from Klaviyo account settings
    KLAVIYO_ATTRIBUTION_DAYS     Attribution window in days (default: 5)
"""

import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import json
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

KLAVIYO_API_KEY          = os.getenv("KLAVIYO_API_KEY", "")
KLAVIYO_ATTRIBUTION_DAYS = int(os.getenv("KLAVIYO_ATTRIBUTION_DAYS", "5"))

KLAVIYO_API_BASE    = "https://a.klaviyo.com/api"
KLAVIYO_API_VERSION = "2024-02-15"

# Metric IDs discovered from the account (avoids the broken page[size] lookup)
METRIC_IDS = {
    "Placed Order":  "TmZUsU",
    "Sent Email":    None,   # Will fetch from /metrics/ without page params
    "Opened Email":  "UsMuZn",
    "Clicked Email": "ThnE7w",
    "Received Email": "WfdnvR",
}


def get_headers() -> dict:
    return {
        "Authorization": f"Klaviyo-API-Key {KLAVIYO_API_KEY}",
        "revision":      KLAVIYO_API_VERSION,
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }


def get_yesterday_iso() -> tuple:
    """Return (start, end) as ISO 8601 strings for yesterday in UTC."""
    today_utc       = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_utc - timedelta(days=1)
    yesterday_end   = today_utc
    return yesterday_start.isoformat(), yesterday_end.isoformat()


def get_metric_id_from_api(metric_name: str) -> str | None:
    """Look up a metric ID by name without page[size] param (which causes 400)."""
    url      = f"{KLAVIYO_API_BASE}/metrics/"
    headers  = get_headers()
    next_url = url

    while next_url:
        response = requests.get(next_url, headers=headers, timeout=30)
        response.raise_for_status()
        body = response.json()

        for metric in body.get("data", []):
            if metric.get("attributes", {}).get("name") == metric_name:
                return metric["id"]

        next_url = body.get("links", {}).get("next")

    return None


def fetch_metric_aggregate(metric_id: str, start_iso: str, end_iso: str) -> dict:
    """
    Query Klaviyo metric aggregates for a given metric + date range.
    Returns summed revenue and count.
    """
    url     = f"{KLAVIYO_API_BASE}/metric-aggregates/"
    headers = get_headers()

    payload = {
        "data": {
            "type": "metric-aggregate",
            "attributes": {
                "metric_id":    metric_id,
                "interval":     "day",
                "measurements": ["sum_value", "count"],
                "filter": [
                    f"greater-or-equal(datetime,{start_iso})",
                    f"less-than(datetime,{end_iso})",
                ],
                "timezone": "UTC",
            }
        }
    }

    response = requests.post(url, headers=headers, json=payload, timeout=30)

    if response.status_code == 422:
        # Metric exists but no data for this period — not an error
        return {"revenue": 0.0, "count": 0}

    response.raise_for_status()
    body = response.json()

    data_attrs  = body.get("data", {}).get("attributes", {})
    # API returns parallel arrays: dates[] and measurements{}
    dates        = data_attrs.get("dates", [])
    measurements = data_attrs.get("measurements", {})

    sum_values = measurements.get("sum_value", []) or []
    counts     = measurements.get("count", []) or []

    total_rev   = sum(float(v or 0) for v in sum_values)
    total_count = sum(int(v or 0) for v in counts)

    return {"revenue": round(total_rev, 2), "count": total_count}


def fetch_email_sends_and_rates(start_iso: str, end_iso: str) -> dict:
    """Fetch email sends, opens, and clicks for informational purposes."""
    # Use known metric IDs directly — avoid extra API calls
    sent_id    = get_metric_id_from_api("Sent Email") or get_metric_id_from_api("Received Email")
    opened_id  = METRIC_IDS["Opened Email"]
    clicked_id = METRIC_IDS["Clicked Email"]

    sent    = 0
    opened  = 0
    clicked = 0

    if sent_id:
        sent = fetch_metric_aggregate(sent_id, start_iso, end_iso).get("count", 0)
    if opened_id:
        opened = fetch_metric_aggregate(opened_id, start_iso, end_iso).get("count", 0)
    if clicked_id:
        clicked = fetch_metric_aggregate(clicked_id, start_iso, end_iso).get("count", 0)

    open_rate  = round((opened  / sent * 100), 1) if sent > 0 else 0.0
    click_rate = round((clicked / sent * 100), 1) if sent > 0 else 0.0

    return {
        "emails_sent": sent,
        "open_rate":   open_rate,
        "click_rate":  click_rate,
    }


def fetch_yesterday_revenue() -> dict:
    """
    Main function. Fetches Klaviyo attributed revenue for yesterday.

    Returns dict with keys:
        date          - Yesterday's date YYYY-MM-DD
        email_revenue - Klaviyo Placed Order revenue (float)
        emails_sent   - Emails sent count (int)
        open_rate     - Open rate % (float)
        click_rate    - Click rate % (float)
    """
    if not KLAVIYO_API_KEY:
        raise ValueError("KLAVIYO_API_KEY must be set in .env")

    yesterday_date     = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    start_iso, end_iso = get_yesterday_iso()

    print(f"[Klaviyo] Fetching email revenue for {yesterday_date}")

    # Placed Order revenue — use hardcoded ID for speed and reliability
    placed_order_id = METRIC_IDS["Placed Order"]
    email_revenue   = 0.0

    if placed_order_id:
        agg = fetch_metric_aggregate(placed_order_id, start_iso, end_iso)
        email_revenue = agg.get("revenue", 0.0)
    else:
        print("[Klaviyo] Could not find Placed Order metric. Revenue = $0.00")

    # Email engagement stats
    send_data = fetch_email_sends_and_rates(start_iso, end_iso)

    result = {
        "date":          yesterday_date,
        "email_revenue": email_revenue,
        **send_data,
    }

    print(f"[Klaviyo] Email Revenue: ${result['email_revenue']:.2f} | "
          f"Sent: {result['emails_sent']} | "
          f"Open: {result['open_rate']}% | Click: {result['click_rate']}%")
    return result


if __name__ == "__main__":
    try:
        data = fetch_yesterday_revenue()
        print("\n--- Klaviyo Output ---")
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"[Klaviyo] Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
