# Automation Workspace

This workspace follows a **3-Layer Architecture** to separate concerns and maximize reliability.

## Architecture Overview

```
Automation/
├── directives/        # Layer 1 — Markdown SOPs (what to do)
├── execution/         # Layer 3 — Deterministic Python scripts (doing it)
├── .tmp/              # Intermediate files (never committed)
├── .env               # API keys and environment variables
├── credentials.json   # Google OAuth credentials (gitignored)
├── token.json         # Google OAuth token (gitignored)
├── instructions.md    # Agent operating instructions
└── README.md          # This file
```

## The 3 Layers

| Layer | Name | Location | Description |
|-------|------|----------|-------------|
| 1 | **Directive** | `directives/` | Markdown SOPs — define the *what* |
| 2 | **Orchestration** | AI Agent | Reads directives, calls scripts, handles errors |
| 3 | **Execution** | `execution/` | Python scripts — do the actual work deterministically |

## How It Works

1. A **directive** defines an objective, its inputs, which scripts to use, and expected outputs.
2. The **agent** reads the directive, decides the order of operations, and invokes the relevant scripts.
3. The **scripts** handle all API calls, file I/O, and data processing deterministically.

## Key Principles

- **Deliverables** live in cloud (Google Sheets, Slides, etc.)
- **Intermediates** live in `.tmp/` and are always regenerable
- **Environment variables** and API tokens live in `.env`
- **Directives are living documents** — updated as the system learns

## Getting Started

1. Copy `.env.example` to `.env` and fill in your credentials.
2. Check `directives/` for available SOPs.
3. Check `execution/` for available scripts.
