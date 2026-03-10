"""
meta_fetch_spend.py
===================
Layer 3 — Execution Script

Fetches yesterday's total ad spend from the Meta (Facebook) Marketing API.
Uses account-level insights with the 'yesterday' date preset so it captures
all campaigns, ad sets, and ads in a single API call.

Usage:
    python execution/meta_fetch_spend.py

Output:
    Prints a JSON summary to stdout. Importable as a module via fetch_yesterday_spend().

Env vars required:
    FACEBOOK_ACCESS_TOKEN    Long-lived user access token or system user token
    FACEBOOK_AD_ACCOUNT_ID   Format: act_XXXXXXXXXX (include the 'act_' prefix)
"""

import os
import sys
import io
import sys
if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8')
import json
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

FACEBOOK_ACCESS_TOKEN  = os.getenv("FACEBOOK_ACCESS_TOKEN", "")
FACEBOOK_AD_ACCOUNT_ID = os.getenv("FACEBOOK_AD_ACCOUNT_ID", "")

GRAPH_API_VERSION = "v19.0"
GRAPH_API_BASE    = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def fetch_yesterday_spend() -> dict:
    """
    Fetches yesterday's total ad spend from Meta Ads at the account level.

    Returns:
        dict with keys:
            date      (str)   — Yesterday's date YYYY-MM-DD
            ad_spend  (float) — Total spend in account currency
            currency  (str)   — Currency code e.g. AUD
    """
    if not FACEBOOK_ACCESS_TOKEN or not FACEBOOK_AD_ACCOUNT_ID:
        raise ValueError("FACEBOOK_ACCESS_TOKEN and FACEBOOK_AD_ACCOUNT_ID must be set in .env")

    # Ensure account ID has the act_ prefix
    account_id = FACEBOOK_AD_ACCOUNT_ID
    if not account_id.startswith("act_"):
        account_id = f"act_{account_id}"

    yesterday_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"[Meta Ads] Fetching spend for {yesterday_date} on account {account_id}")

    url = f"{GRAPH_API_BASE}/{account_id}/insights"
    params = {
        "access_token": FACEBOOK_ACCESS_TOKEN,
        "date_preset":  "yesterday",
        "level":        "account",
        "fields":       "spend,account_currency",
        "time_increment": 1,
    }

    response = requests.get(url, params=params, timeout=30)

    # Handle API errors explicitly
    if response.status_code != 200:
        error_data = response.json().get("error", {})
        raise RuntimeError(
            f"Meta API error {response.status_code}: "
            f"{error_data.get('message', response.text)}"
        )

    data = response.json().get("data", [])

    if not data:
        # No active campaigns yesterday — zero spend, not an error
        print(f"[Meta Ads] ℹ No active campaigns yesterday. Spend = $0.00")
        return {
            "date":     yesterday_date,
            "ad_spend": 0.0,
            "currency": "AUD",
        }

    # Sum spend across all entries (should be a single row at account level)
    total_spend = sum(float(row.get("spend", 0)) for row in data)
    currency    = data[0].get("account_currency", "AUD")

    result = {
        "date":     yesterday_date,
        "ad_spend": round(total_spend, 2),
        "currency": currency,
    }

    print(f"[Meta Ads] ✓ Ad Spend: {currency} ${result['ad_spend']:.2f}")
    return result


if __name__ == "__main__":
    try:
        data = fetch_yesterday_spend()
        print("\n--- Meta Ads Output ---")
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"[Meta Ads] ✗ Error: {e}", file=sys.stderr)
        sys.exit(1)
