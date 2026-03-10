# Execution Scripts

This folder contains deterministic Python scripts — **Layer 3** of the 3-layer architecture.

## What belongs here

Each script should:
- Do **one thing** reliably
- Accept inputs via arguments or environment variables (`.env`)
- Be **independently testable**
- Be well-commented
- Handle errors gracefully and print useful output

## Naming Convention

```
<domain>_<action>.py
```

Examples:
- `shopify_fetch_orders.py`
- `facebook_fetch_insights.py`
- `google_sheets_write.py`
- `klaviyo_get_revenue.py`
- `makecom_trigger_scenario.py`

## Running Scripts

All scripts assume:
1. A `.env` file exists in the project root (see `.env.example`)
2. Dependencies are installed: `pip install -r requirements.txt`

```bash
cd Automation
python execution/your_script.py
```

## Index

| Script | Description | Dependencies |
|--------|-------------|--------------|
| `shopify_fetch_orders.py` | Fetch yesterday's orders, net revenue ex tax, refunds | `requests`, `python-dotenv` |
| `meta_fetch_spend.py` | Fetch yesterday's Meta Ads daily spend | `requests`, `python-dotenv` |
| `klaviyo_fetch_revenue.py` | Fetch yesterday's Klaviyo attributed email revenue + stats | `requests`, `python-dotenv` |
| `google_sheets_setup.py` | **Run once.** Create the Google Sheet with headers, returns Spreadsheet ID | `gspread`, `google-auth-oauthlib` |
| `google_sheets_write.py` | Append one daily row to the Google Sheet (duplicate-safe) | `gspread`, `google-auth` |
| `send_email_report.py` | Compose and send the Gmail profit summary | `smtplib` (stdlib) |
| `run_daily_report.py` | **Orchestrator.** Calls all scripts, calculates profit, runs the pipeline | All of the above |

## Shared Dependencies

Install all at once:
```bash
pip install -r requirements.txt
```

## Self-Correction

If a script fails:
1. Read the error and stack trace
2. Fix the script
3. Test it again
4. Update the corresponding `directives/` file with what was learned
