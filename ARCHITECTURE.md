# Architecture (ARCHITECTURE.md)

This document describes the core architecture of the Bossissa SIP Statistical Analysis pipeline.

## Core Components
* **`data_loader.py`** — Fetches data from external sources (Google Sheets) — Deps: pandas, requests
* **`tableone_generator.py`** — Generates statistical baseline characteristics (Table 1) using normal/non-normal inference — Deps: pandas, tableone, scipy
* **`charts_generator.py`** — Generates JSON payloads for Plotly infographics — Deps: pandas, plotly
* **`Frontend UI (docs/)`** — Serves static interactive visualization dashboards — Deps: Plotly.js, Vanilla JS/CSS

## Data Flow
* **`Source`** → `Google Sheets` → `data_loader.py` → `Raw CSV` (sync on GH Actions)
* **`Table Data`** → `Raw CSV` → `tableone_generator.py` → `docs/data/tableone.json` (static/offline payload)
* **`Charts Data`** → `Raw CSV` → `charts_generator.py` → `docs/data/charts.json` (static/offline payload)

## Offline Decisions
* **`Analysis Payload`**: Conflict-resolution: GH Actions overwrites state. Sync-strategy: Static files deployed to Pages. Read-only on client.
* **`User Theme Preference`**: Conflict-resolution: Client overrides default. Sync-strategy: Stored in `localStorage` locally.
* **`Filter & Search State`**: Conflict-resolution: Last-writer wins locally. Sync-strategy: Ephemeral DOM state, no persistent sync.

## Clinical/System Warnings
* **Statistical Power**: P-values presented might lack power if subgroup N is critically low. Interpret with caution.
* **Automated Normality Tests**: Skewness and kurtosis metrics trigger parametric/non-parametric tests automatically; however, clinical researchers should visually verify distributions.
* **PHI Sanitization**: The GitHub Actions pipeline must ensure that no Patient Health Information (PHI) or Personally Identifiable Information (PII) is included in the final `docs/data/*.json` payloads.
