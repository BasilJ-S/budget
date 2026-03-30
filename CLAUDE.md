# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
poetry install

# Run the transaction categorization CLI
python src/budget/clean.py

# Launch the interactive dashboard (http://127.0.0.1:8050/)
python src/budget/plot.py

# Manage budgets (create/edit/read/evaluate)
python src/budget/budget_manager.py

# Run tests
pytest
```

## Architecture

This is a personal finance analytics tool with three independent entry points:

**`clean.py`** — Interactive CLI that ingests raw bank CSVs (`chequing.csv`, `visa.csv`, `savings.csv`), applies regex pattern rules from `rulesets/rules.yaml`, and lets the user manually categorize remaining transactions while optionally generating new rules. Outputs `data/transactions.csv`.

**`plot.py`** — Dash web dashboard that reads `transactions.csv` and renders 6 reactive visualizations (monthly bar chart, category breakdown, line chart, cumulative net flow, budget vs. actual, transaction table). All views update through a single callback driven by three dropdowns: month, timeframe, and category filter.

**`budget_manager.py`** — CLI for creating and editing monthly budgets stored as YAML in `budgets/`. Budget data is loaded by `plot.py` to power the budget vs. actual chart.

## Key Data Flow

```
Bank CSVs → clean.py (rule matching + manual categorization) → transactions.csv
                                                                        ↓
budgets/*.yaml ─────────────────────────────────────────────→ plot.py dashboard
```

## Rule System

Rules are dataclasses serialized to `rulesets/rules.yaml`. Each rule matches a substring pattern in the transaction description and assigns a category. `apply_rules()` in `clean.py` runs `str.contains()` over all transactions. Every save creates a timestamped backup in `rulesets/`.

## Data Files (gitignored)

All files under `src/budget/data/`, `src/budget/rulesets/`, and `src/budget/budgets/` are gitignored — these contain personal financial data. Place source CSVs in `src/budget/data/` before running `clean.py`.
