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
The pipeline evaluates pre-specified clinical covariates across three model configurations based on Events Per Variable (EPV) and clinical objectives:

1. **Standard MLE Logistic Regression** (`statsmodels.Logit`) — Explanatory model. Evaluates all pre-specified covariates. Reports Crude/Adjusted OR, 95% Wald CI, p-value, Hosmer-Lemeshow goodness-of-fit, Nagelkerke R², and AUC. Recommended when EPV ≥ 10.
2. **Firth's Penalized Likelihood** (`firthmodels`) — Explanatory model. Evaluates all pre-specified covariates. Reports Adjusted OR, 95% profile likelihood CI, and p-value. Recommended when EPV < 10 or perfect separation is detected.
3. **LASSO Logistic Regression (10-fold CV)** (`sklearn.linear_model.LogisticRegressionCV`) — Predictive model. Automatically selects the optimal regularization parameter ($C$) via cross-validation. Reports cross-validated AUC, Brier Score, and Calibration Curve to rigorously assess predictive performance without overfitting.

## Offline Decisions

| State | Conflict Resolution | Sync Strategy |
|-------|-------------------|---------------|
| Analysis Payload | GH Actions overwrites | Static files deployed to Pages, read-only on client |
| User Theme | Client overrides default | `localStorage` (key: `bossissa-theme`) |
| Filter/Search | Last-writer wins | Ephemeral DOM state, no persistence |

## Warnings

- **Statistical Power**: P-values may lack power if subgroup N is critically low. Interpret with caution.
- **Automated Normality Tests**: Shapiro-Wilk (N<5000) or Jarque-Bera (N≥5000) with skew/kurtosis criteria. Clinical researchers should visually verify distributions.
- **EPV and Multivariate Stability**: The UI enforces strict interpretative recommendations based on Events Per Variable (EPV). If EPV < 10 or perfect separation occurs, Firth's Penalized Likelihood is the recommended explanatory model. Standard MLE is safely interpretable only when EPV ≥ 10. For predictive workflows, LASSO is the recommended first step.
- **LASSO Predictive Validation**: The LASSO model utilizes 10-fold Cross-Validation with `neg_log_loss` scoring to rigorously estimate the out-of-sample AUC, Brier Score, and Calibration. This prevents over-optimistic performance reporting typical in non-cross-validated pipelines.
- **PHI Sanitization**: Pipeline must ensure no PHI/PII in `docs/data/*.json` payloads. Google Sheet must be public ("Anyone with link can view") with PHI removed beforehand.
