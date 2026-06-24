"""
multivariate_analysis.py
------------------------
LASSO feature selection → Firth + Standard logistic regression side-by-side.
Outputs docs/data/multivariate.json for the dashboard.
"""

from __future__ import annotations

import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).parent))

from data_loader import STRATIFY_COL, VARIABLE_META, load_data

OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "data"

# ──────────────────────────────────────────────
# Feature preparation
# ──────────────────────────────────────────────

def prepare_features(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, list[str], pd.Series]:
    """
    One-hot encode categoricals, standardize continuous, return (X, y, feature_names, y_series).
    """
    y_raw = df[STRATIFY_COL].to_numpy(dtype=float)
    feature_dfs = []
    feature_names: list[str] = []

    for var, meta in VARIABLE_META.items():
        if var not in df.columns or var == STRATIFY_COL:
            continue

        series = df[var].copy()

        # Detect if categorical (already mapped to Thai labels by data_loader)
        if meta.get("type_hint") == "categorical" or not pd.api.types.is_numeric_dtype(series):
            # One-hot encode, drop first category as reference
            dummies = pd.get_dummies(series, prefix=var, drop_first=True, dtype=float)
            # Drop columns that are all-zero (no patients in that category)
            dummies = dummies.loc[:, dummies.sum() > 0]
            feature_dfs.append(dummies)
            feature_names.extend(dummies.columns.tolist())
        else:
            # Continuous — standardize
            scaler = StandardScaler()
            vals = series.dropna().values.reshape(-1, 1)
            scaled = scaler.fit_transform(vals)
            col_name = f"{var}_scaled"
            feature_dfs.append(pd.DataFrame(scaled, columns=[col_name], index=series.dropna().index))
            feature_names.append(col_name)

    X_df = pd.concat(feature_dfs, axis=1)
    mask = np.isfinite(y_raw)
    X_df = X_df.loc[mask]
    y = y_raw[mask].astype(int)

    # Fill any remaining NaN in X with 0 (median for scaled, 0 for dummies = reference category)
    X_df = X_df.fillna(0)
    
    X_raw = X_df.values.astype(float)
    y_raw_int = y.astype(int)

    # Remove perfectly collinear features via QR decomposition
    import scipy.linalg
    X_with_intercept = np.column_stack([np.ones(X_raw.shape[0]), X_raw])
    Q, R, P = scipy.linalg.qr(X_with_intercept, mode='economic', pivoting=True)
    rank = np.sum(np.abs(np.diag(R)) > 1e-10)
    indep_indices = P[:rank]
    
    # Original features correspond to indices 1 to N in the augmented matrix
    selected_orig_idx = [i - 1 for i in indep_indices if i > 0]
    selected_orig_idx.sort()
    
    if len(selected_orig_idx) < len(feature_names):
        dropped = [feature_names[i] for i in range(len(feature_names)) if i not in selected_orig_idx]
        print(f"  Dropped {len(dropped)} collinear features: {', '.join(dropped)}")
    
    X_clean = X_raw[:, selected_orig_idx]
    names_clean = [feature_names[i] for i in selected_orig_idx]

    return X_clean, y_raw_int, names_clean, pd.Series(y)


# ──────────────────────────────────────────────
# LASSO selection
# ──────────────────────────────────────────────

def lasso_select(X: np.ndarray, y: np.ndarray, feature_names: list[str], C: float = 0.1) -> list[str]:
    """
    L1-regularized logistic regression for feature selection.
    Lower C = stronger regularization = fewer features.
    Returns list of selected feature names.
    """
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = LogisticRegression(
            penalty="l1",
            solver="saga",
            C=C,
            max_iter=5000,
            random_state=42,
        )
        model.fit(X, y)

    selected_idx = np.where(model.coef_[0] != 0)[0]
    selected = [feature_names[i] for i in selected_idx]

    print(f"  LASSO (C={C}): selected {len(selected)}/{len(feature_names)} features")
    for name, coef in zip(selected, model.coef_[0][selected_idx]):
        print(f"    {name}: {coef:.4f}")

    return selected


# ──────────────────────────────────────────────
# Firth logistic regression
# ──────────────────────────────────────────────

def run_firth(X: np.ndarray, y: np.ndarray, feature_names: list[str]) -> dict[str, Any]:
    """Fit FirthLogisticRegression (firthmodels) and return results dict."""
    from firthmodels import FirthLogisticRegression

    fl = FirthLogisticRegression(max_iter=200, gtol=1e-6, xtol=1e-6)
    fl.fit(X, y)

    coefs = fl.coef_.tolist()
    ses = fl.bse_.tolist()
    pvals = fl.pvalues_.tolist()

    # Profile likelihood CIs (may be slow — skip if too many features)
    try:
        cis = fl.confint_  # profile likelihood
    except AttributeError:
        # Fallback: Wald CIs
        from scipy import stats as sp_stats
        z = sp_stats.norm.ppf(0.975)
        cis = [(c - z * s, c + z * s) for c, s in zip(coefs, ses)]

    variables = []
    for i, name in enumerate(feature_names):
        or_val = round(float(np.exp(coefs[i])), 3)
        ci_lo = round(float(np.exp(cis[i][0])), 3)
        ci_hi = round(float(np.exp(cis[i][1])), 3)
        variables.append({
            "name": name,
            "coef": round(coefs[i], 4),
            "se": round(ses[i], 4),
            "or": or_val,
            "ci_lo": ci_lo,
            "ci_hi": ci_hi,
            "p_value": round(pvals[i], 4),
            "significant": pvals[i] < 0.05,
        })

    return {
        "method": "Firth (Penalized Likelihood — firthmodels)",
        "n_iterations": int(getattr(fl, "n_iter_", 0)),
        "variables": variables,
    }


# ──────────────────────────────────────────────
# Standard logistic regression (statsmodels)
# ──────────────────────────────────────────────

def run_standard(X: np.ndarray, y: np.ndarray, feature_names: list[str]) -> dict[str, Any]:
    """Fit statsmodels.Logit and return results dict."""
    import statsmodels.api as sm

    from statsmodels.tools.sm_exceptions import PerfectSeparationError

    # Add intercept
    X_sm = sm.add_constant(X)
    all_names = ["Intercept"] + feature_names

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = sm.Logit(y, X_sm)
        try:
            result = model.fit(disp=False, maxiter=200)
        except PerfectSeparationError:
            return {
                "method": "Standard MLE (statsmodels)",
                "error": "Perfect separation detected — model cannot be estimated",
                "variables": []
            }
        except Exception as e:
            return {
                "method": "Standard MLE (statsmodels)",
                "error": str(e),
                "variables": []
            }

    variables = []
    for i, name in enumerate(all_names):
        coef = float(result.params[i])
        se = float(result.bse[i])
        ci_lo = float(result.conf_int()[i, 0])
        ci_hi = float(result.conf_int()[i, 1])
        pval = float(result.pvalues[i])

        or_val = round(float(np.exp(coef)), 3)
        ci_lo_or = round(float(np.exp(ci_lo)), 3)
        ci_hi_or = round(float(np.exp(ci_hi)), 3)

        variables.append({
            "name": name,
            "coef": round(coef, 4),
            "se": round(se, 4),
            "or": or_val,
            "ci_lo": ci_lo_or,
            "ci_hi": ci_hi_or,
            "p_value": round(pval, 4),
            "significant": pval < 0.05,
        })

    return {
        "method": "Standard MLE (statsmodels)",
        "log_likelihood": round(float(result.llf), 2),
        "pseudo_r2": round(float(result.prsquared), 4),
        "n_iterations": int(getattr(result, "iterations", result.mle_retvals.get("iterations", 0))),
        "variables": variables,
    }


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main(df: pd.DataFrame = None) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if df is None:
        print("Loading data...")
        df = load_data()

    print("Preparing features...")
    X, y, feature_names, _ = prepare_features(df)
    print(f"  Feature matrix: {X.shape[0]} rows × {X.shape[1]} columns")

    # LASSO selection — try multiple C values, pick best by AIC
    print("\nLASSO feature selection (trying C=0.1, 0.5, 1.0)...")
    best_selected = None
    best_aic = float("inf")
    best_C = None

    for C_val in [0.1, 0.5, 1.0]:
        selected = lasso_select(X, y, feature_names, C=C_val)
        if len(selected) == 0:
            continue
        # Quick AIC via FirthLogisticRegression on selected features
        sel_idx = [feature_names.index(s) for s in selected]
        X_tmp = X[:, sel_idx]
        from firthmodels import FirthLogisticRegression
        fl_tmp = FirthLogisticRegression(max_iter=200, gtol=1e-6, xtol=1e-6)
        
        try:
            fl_tmp.fit(X_tmp, y)
            # AIC = 2k - 2 * log(L)
            k = len(selected) + 1  # +1 for intercept
            aic = 2 * k - 2 * fl_tmp.loglik_
        except Exception as e:
            print(f"  C={C_val}: {len(selected)} features, AIC calculation failed ({e})")
            continue
                
        print(f"  C={C_val}: {len(selected)} features, AIC={aic:.1f}")
        if aic < best_aic:
            best_aic = aic
            best_selected = selected
            best_C = C_val

    selected = best_selected or feature_names
    print(f"  → Selected C={best_C}: {len(selected)} features, AIC={best_aic:.1f}")

    # Subset X to selected features
    selected_idx = [feature_names.index(s) for s in selected]
    X_sel = X[:, selected_idx]

    # Run both models
    print("\nFirth logistic regression...")
    try:
        firth_result = run_firth(X_sel, y, selected)
    except Exception as e:
        print(f"  Firth regression failed: {e}")
        firth_result = {"method": "Firth", "error": str(e), "variables": []}

    print("\nStandard logistic regression...")
    try:
        standard_result = run_standard(X_sel, y, selected)
    except Exception as e:
        print(f"  Standard MLE failed: {e}")
        standard_result = {"method": "Standard MLE (statsmodels)", "error": str(e), "variables": []}

    # Build output
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_n": len(y),
        "n_features_total": len(feature_names),
        "n_features_selected": len(selected),
        "lasso_C": best_C,
        "selected_features": selected,
        "firth": firth_result,
        "standard": standard_result,
    }

    out_path = OUTPUT_DIR / "multivariate.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ Multivariate analysis → {out_path}")

    # Quick summary
    print(f"\n--- Significant predictors (Firth, p<0.05) ---")
    sig = [v for v in firth_result["variables"] if v["significant"]]
    if sig:
        for v in sorted(sig, key=lambda x: x["p_value"]):
            print(f"  {v['name']}: OR={v['or']} [{v['ci_lo']}–{v['ci_hi']}], p={v['p_value']}")
    else:
        print("  None")

    print(f"\n--- Significant predictors (Standard, p<0.05) ---")
    sig_std = [v for v in standard_result["variables"] if v["significant"] and v["name"] != "Intercept"]
    if sig_std:
        for v in sorted(sig_std, key=lambda x: x["p_value"]):
            print(f"  {v['name']}: OR={v['or']} [{v['ci_lo']}–{v['ci_hi']}], p={v['p_value']}")
    else:
        print("  None")


if __name__ == "__main__":
    main()
