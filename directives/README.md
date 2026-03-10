# Directives — Standard Operating Procedures

This folder contains Markdown SOPs (Standard Operating Procedures) — **Layer 1** of the 3-layer architecture.

## What belongs here

Each directive is a Markdown file that defines:
- **Objective** — What the task accomplishes
- **Inputs** — What data or context is needed
- **Scripts to use** — Which `execution/` scripts to call
- **Outputs** — What the deliverable is and where it lives
- **Edge cases** — Known issues, rate limits, timing constraints

## Naming Convention

```
<domain>_<action>.md
```

Examples:
- `shopify_fetch_orders.md`
- `facebook_pull_insights.md`
- `google_sheets_export.md`
- `klaviyo_get_revenue.md`

## Index

| File | Description | Status |
|------|-------------|--------|
| `daily_profit_report.md` | Full SOP for the automated daily profit report pipeline (Shopify + Meta + Klaviyo → Sheets + Gmail) | ✅ Active |

> Directives are **living documents**. Update them whenever you discover new API constraints, better approaches, or common errors — do not discard knowledge.
