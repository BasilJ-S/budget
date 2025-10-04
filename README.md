# Budget Tracker

A Python-based personal finance tool for categorizing bank transactions and visualizing spending patterns through an interactive dashboard.

## Overview

This project processes bank transaction data from checking and credit card accounts, categorizes transactions using user-defined rules, and provides an interactive Dash web application for analyzing spending patterns over time.

## Features

- **Transaction Cleaning & Categorization** (`clean.py`)
  - Loads debit/credit CSV files from bank exports
  - Interactive CLI for categorizing uncategorized transactions
  - Rule-based auto-categorization with pattern matching
  - Shorthand system for quick category assignment
  - Automatic rule backup with timestamps

- **Interactive Dashboard** (`plot.py`)
  - Monthly income vs. expenses bar charts
  - Category breakdown visualization
  - Time-series line charts with customizable date ranges
  - Filterable transaction tables
  - Average spending trend lines

- **Budget Planning** (`budget.py` - in budget branch)
  - Create and edit monthly budgets
  - Assign budget amounts to categories
  - Track budgeted vs. actual spending

## Setup

```bash
# Install dependencies
poetry install

# Place your bank CSVs in src/budget/data/
# - checking.csv (debit transactions)
# - visa.csv (credit transactions)
```

## Usage

### 1. Categorize Transactions
```bash
python src/budget/clean.py
```
Interactively categorize transactions, create rules, and generate `transactions.csv`.

### 2. Launch Dashboard
```bash
python src/budget/plot.py
```
Opens interactive visualization at `http://127.0.0.1:8050/`

## Technical Details

- **Data Flow**: CSV → cleaning/categorization → transactions.csv → dashboard
- **Rule System**: YAML-based pattern matching for automatic categorization
- **Visualization**: Plotly/Dash for interactive charts and tables
