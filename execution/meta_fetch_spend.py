"""
meta_fetch_spend.py
===================
Layer 3 — Execution Script
"""

import os
import sys
import json
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8')

GRAPH_API_VERSION = "v19.0"
GRAPH_API_BASE    = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

def fetch_yesterday_spend() -> dict:
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
    access_token = os.getenv("FACEBOOK_ACCESS_TOKEN", "").strip()
    account_id   = os.getenv("FACEBOOK_AD_ACCOUNT_ID", "").strip()

    if not access_token or not account_id:
        raise ValueError("FACEBOOK_ACCESS_TOKEN and FACEBOOK_AD_ACCOUNT_ID must be set in .env")

    if not account_id.startswith("act_"):
        account_id = f"act_{account_id}"

    aest_now = datetime.now(timezone.utc) + timedelta(hours=10)
    yesterday_date = (aest_now - timedelta(days=1)).strftime("%Y-%m-%d")
    
    print(f"[Meta Ads] Fetching spend for {yesterday_date} (AEST)")

    url = f"{GRAPH_API_BASE}/{account_id}/insights"
    params = {
        "access_token": access_token,
        "time_range":   json.dumps({"since": yesterday_date, "until": yesterday_date}),
        "level":        "account",
        "fields":       "spend,account_currency",
        "time_increment": 1,
    }

    response = requests.get(url, params=params, timeout=30)
    if response.status_code != 200:
        error_data = response.json().get("error", {})
        raise RuntimeError(f"Meta API error {response.status_code}: {error_data.get('message', response.text)}")

    data = response.json().get("data", [])
    if not data:
        return {"date": yesterday_date, "ad_spend": 0.0, "currency": "AUD"}

    total_spend = sum(float(row.get("spend", 0)) for row in data)
    currency    = data[0].get("account_currency", "AUD")

    result = {"date": yesterday_date, "ad_spend": round(total_spend, 2), "currency": currency}
    print(f"[Meta Ads] ✓ Ad Spend: {currency} ${result['ad_spend']:.2f}")
    return result

if __name__ == "__main__":
    try:
        data = fetch_yesterday_spend()
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"[Meta Ads] ✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
