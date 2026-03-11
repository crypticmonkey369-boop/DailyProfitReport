"""
klaviyo_fetch_revenue.py
========================
Layer 3 - Execution Script
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8')

KLAVIYO_API_BASE    = "https://a.klaviyo.com/api"
KLAVIYO_API_VERSION = "2024-02-15"

METRIC_IDS = {
    "Placed Order":  "TmZUsU",
    "Sent Email":    None,
    "Opened Email":  "UsMuZn",
    "Clicked Email": "ThnE7w",
    "Received Email": "WfdnvR",
}

def get_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Klaviyo-API-Key {api_key}",
        "revision":      KLAVIYO_API_VERSION,
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }

def get_yesterday_iso_aest():
    aest_now = datetime.now(timezone.utc) + timedelta(hours=10)
    yesterday_aest_start = (aest_now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_aest_end   = yesterday_aest_start + timedelta(hours=23, minutes=59, seconds=59)
    utc_start = yesterday_aest_start - timedelta(hours=10)
    utc_end   = yesterday_aest_end   - timedelta(hours=10)
    return utc_start.isoformat(), utc_end.isoformat()

def get_metric_id_from_api(metric_name: str, api_key: str) -> str | None:
    url      = f"{KLAVIYO_API_BASE}/metrics/"
    headers  = get_headers(api_key)
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

def fetch_metric_aggregate(metric_id: str, start_iso: str, end_iso: str, api_key: str) -> dict:
    url     = f"{KLAVIYO_API_BASE}/metric-aggregates/"
    headers = get_headers(api_key)
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
        return {"revenue": 0.0, "count": 0}
    response.raise_for_status()
    body = response.json()
    data_attrs  = body.get("data", {}).get("attributes", {})
    measurements = data_attrs.get("measurements", {})
    sum_values = measurements.get("sum_value", []) or []
    counts     = measurements.get("count", []) or []
    return {"revenue": round(sum(float(v or 0) for v in sum_values), 2), "count": sum(int(v or 0) for v in counts)}

def fetch_email_sends_and_rates(start_iso: str, end_iso: str, api_key: str) -> dict:
    sent_id    = get_metric_id_from_api("Sent Email", api_key) or get_metric_id_from_api("Received Email", api_key)
    opened_id  = METRIC_IDS["Opened Email"]
    clicked_id = METRIC_IDS["Clicked Email"]
    sent = 0
    opened = 0
    clicked = 0
    if sent_id:
        sent = fetch_metric_aggregate(sent_id, start_iso, end_iso, api_key).get("count", 0)
    if opened_id:
        opened = fetch_metric_aggregate(opened_id, start_iso, end_iso, api_key).get("count", 0)
    if clicked_id:
        clicked = fetch_metric_aggregate(clicked_id, start_iso, end_iso, api_key).get("count", 0)
    return {
        "emails_sent": sent,
        "open_rate":   round((opened / sent * 100), 1) if sent > 0 else 0.0,
        "click_rate":  round((clicked / sent * 100), 1) if sent > 0 else 0.0,
    }

def fetch_yesterday_revenue() -> dict:
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
    api_key = os.getenv("KLAVIYO_API_KEY", "").strip()
    if not api_key:
        raise ValueError("KLAVIYO_API_KEY must be set in .env")
    
    aest_now = datetime.now(timezone.utc) + timedelta(hours=10)
    yesterday_date = (aest_now - timedelta(days=1)).strftime("%Y-%m-%d")
    start_iso, end_iso = get_yesterday_iso_aest()
    print(f"[Klaviyo] Fetching email revenue for {yesterday_date} (AEST)")
    
    placed_order_id = METRIC_IDS["Placed Order"]
    email_revenue = 0.0
    if placed_order_id:
        email_revenue = fetch_metric_aggregate(placed_order_id, start_iso, end_iso, api_key).get("revenue", 0.0)
    send_data = fetch_email_sends_and_rates(start_iso, end_iso, api_key)
    result = {"date": yesterday_date, "email_revenue": email_revenue, **send_data}
    print(f"[Klaviyo] ✓ Email Revenue: ${result['email_revenue']:.2f}")
    return result

if __name__ == "__main__":
    try:
        data = fetch_yesterday_revenue()
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"[Klaviyo] Error: {e}", file=sys.stderr)
        sys.exit(1)
