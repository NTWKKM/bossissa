# Architecture (ARCHITECTURE.md)

This document describes the core architecture of the Bossissa SIP Statistical Analysis pipeline.

## Core Components

| Component | Purpose | Dependencies |
|-----------|---------|-------------|
| **`data_loader.py`** | Fetch Google Sheets CSV, clean columns, map Thai→English labels | pandas, requests |
| **`tableone_generator.py`** | OOP Table One engine: classify variables, run statistical tests, format output | pandas, numpy, scipy |
| **`charts_generator.py`** | Generate Plotly JSON specs for 8 infographic charts | pandas, numpy, scipy |
| **`stat_generator.py`** | Frequency distribution tables stratified by inclusion/hx_psych/SIP-all | pandas, tableone_generator |
| **`multivariate_analysis.py`** | LASSO feature selection → Firth + Standard logistic regression side-by-side | scikit-learn, statsmodels, firthmodels |
| **`run_analysis.py`** | Pipeline entry point — orchestrates all generators | all above |
| **`Frontend UI (docs/`)** | Static interactive dashboard: Table One, Infographics, Frequency Stats, Multivariate | Plotly.js, Vanilla JS/CSS |

## Data Flow

1. **Source** → Google Sheets (public CSV export) → `data_loader.py` → cleaned DataFrame
2. **Table One** → DataFrame → `tableone_generator.py` → `docs/data/tableone.json` + `docs/data/metadata.json`
3. **Charts** → DataFrame → `charts_generator.py` → `docs/data/charts.json` (8 Plotly specs)
4. **Frequency Stats** → DataFrame (N=1000, incl. incomplete) → `stat_generator.py` → `docs/data/stat_freq.json`
5. **Multivariate** → DataFrame (N=678, excl. incomplete) → `multivariate_analysis.py` → `docs/data/multivariate.json`
6. **Deploy** → `docs/data/*` pushed to `main` → GitHub Pages auto-deploys `docs/`

All generators are called sequentially from `run_analysis.py`. Each fetches live data independently (no shared DataFrame across generators — ensures freshness).

## Pipeline Trigger

- **GitHub Actions** (`workflow_dispatch`) → `analyze.yml` → `uv run python scripts/run_analysis.py` → commit & push results → `deploy.yml` auto-deploys to Pages

## Frontend Tabs

| Tab | Data Source | Load Strategy |
|-----|------------|---------------|
| 📊 Table One | `metadata.json` + `tableone.json` | Eager (on page load) |
| 📈 Infographics | `charts.json` | Lazy (on first tab click) |
| 📋 Frequency Stats | `stat_freq.json` | Lazy (on first tab click) |
| 🧬 Multivariate | `multivariate.json` | Lazy (on first tab click) |

## Statistical Methods

### Univariate (Table One)
| Variable Type | Test | Reported As |
|---|---|---|
| Continuous Normal | Welch t-test | Mean ± SD |
| Continuous Non-Normal | Mann-Whitney U | Median [Q1, Q3] |
| Categorical | Chi-square / Fisher's Exact | n (%) |

Effect sizes: SMD (pooled SD), OR with 95% CI (Haldane-Anscombe for categorical, logistic regression for continuous).

### Multivariate
1. **LASSO** (L1-regularized logistic regression, C=0.1/0.5/1.0) — feature selection by AIC
2. **Firth Logistic Regression** (`firthmodels`) — penalized likelihood, profile likelihood CIs, handles separation
3. **Standard MLE** (`statsmodels.Logit`) — Wald CIs, pseudo R²

Both models run on LASSO-selected features. Results presented side-by-side for comparison.

## Offline Decisions

| State | Conflict Resolution | Sync Strategy |
|-------|-------------------|---------------|
| Analysis Payload | GH Actions overwrites | Static files deployed to Pages, read-only on client |
| User Theme | Client overrides default | `localStorage` (key: `bossissa-theme`) |
| Filter/Search | Last-writer wins | Ephemeral DOM state, no persistence |

## Warnings

- **Statistical Power**: P-values may lack power if subgroup N is critically low. Interpret with caution.
- **Automated Normality Tests**: Shapiro-Wilk (N<5000) or Jarque-Bera (N≥5000) with skew/kurtosis criteria. Clinical researchers should visually verify distributions.
- **Multivariate Pseudo R²**: Current model explains limited variance (R²≈0.015). SIP determination is multifactorial; unmeasured confounders (substance dose, duration, genetics) dominate.
- **LASSO Sparsity**: C=0.1 selects only 3 features. This is intentional — the model prioritizes independent predictors over redundant ones. Less aggressive C values (0.5, 1.0) select 33–42 features but increase AIC.
- **PHI Sanitization**: Pipeline must ensure no PHI/PII in `docs/data/*.json` payloads. Google Sheet must be public ("Anyone with link can view") with PHI removed beforehand.
- **Firth vs Standard**: Both methods agree on significant predictors. Firth provides more conservative CIs (profile likelihood) — preferred reference. Standard MLE provides pseudo R² for model fit assessment.
