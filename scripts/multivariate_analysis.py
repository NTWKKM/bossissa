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
            # Continuous — raw values
            col_name = var
            feature_dfs.append(pd.DataFrame(series.values, columns=[col_name], index=series.index))
            feature_names.append(col_name)

    X_df = pd.concat(feature_dfs, axis=1)
    mask = np.isfinite(y_raw)
    X_df = X_df.loc[mask]
    y = y_raw[mask].astype(int)

    # Impute missing values: 0 for binary dummies, median for continuous
    for col in X_df.columns:
        if set(X_df[col].dropna().unique()).issubset({0.0, 1.0}):
            X_df[col] = X_df[col].fillna(0.0)
        else:
            X_df[col] = X_df[col].fillna(X_df[col].median())
    
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

def run_lasso_cv(X: np.ndarray, y: np.ndarray, feature_names: list[str]) -> dict[str, Any]:
    """
    10-fold Cross-Validated LASSO (L1-regularized logistic regression).
    Calculates AUC, Brier Score, and Calibration Curve.
    Returns a dictionary with selected features, coefficients, and metrics.
    """
    import warnings
    from sklearn.linear_model import LogisticRegressionCV, LogisticRegression
    from sklearn.metrics import roc_auc_score, brier_score_loss
    from sklearn.calibration import calibration_curve
    from sklearn.model_selection import cross_val_predict

    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # 1. Scale X and find best C using 10-fold CV
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        model = LogisticRegressionCV(
            Cs=10,
            cv=10,
            penalty="l1",
            solver="saga",
            max_iter=5000,
            random_state=42,
            scoring='neg_log_loss'
        )
        model.fit(X_scaled, y)

    best_C = float(model.C_[0])
    
    # Get coefficients
    coefs = model.coef_[0]
    selected_idx = np.where(coefs != 0)[0]
    
    variables = []
    
    for idx in selected_idx:
        variables.append({
            "name": feature_names[idx],
            "coef": round(float(coefs[idx]), 4),
            "or": round(float(np.exp(coefs[idx])), 3)
        })
        
    # To get cross-validated metrics, we use a Pipeline within cross_val_predict
    # to perfectly isolate the scaling step and prevent data leakage
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("lasso", LogisticRegression(penalty="l1", solver="saga", C=best_C, max_iter=5000, random_state=42))
        ])
        y_prob_cv = cross_val_predict(pipeline, X, y, cv=10, method='predict_proba')[:, 1]
        
    # Calculate metrics
    auc_cv = roc_auc_score(y, y_prob_cv)
    brier_cv = brier_score_loss(y, y_prob_cv)
    
    # Calibration curve
    prob_true, prob_pred = calibration_curve(y, y_prob_cv, n_bins=10, strategy='quantile')
    
    print(f"  LASSO 10-fold CV: Best C={best_C:.4f}, Selected {len(selected_idx)}/{len(feature_names)} features")
    print(f"    Cross-Validated AUC: {auc_cv:.4f}, Brier Score: {brier_cv:.4f}")

    return {
        "method": "LASSO (10-fold CV)",
        "best_C": round(best_C, 4),
        "auc_cv": round(auc_cv, 4),
        "brier_score_cv": round(brier_cv, 4),
        "calibration": {
            "prob_true": [round(float(p), 4) for p in prob_true],
            "prob_pred": [round(float(p), 4) for p in prob_pred]
        },
        "variables": variables,
        "n_features_selected": len(selected_idx)
    }


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
    import scipy.stats as stats
    from sklearn.metrics import roc_auc_score
    import pandas as pd

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

    n = len(y)
    llf = float(result.llf)
    llnull = float(result.llnull)
    
    # Nagelkerke R2
    cox_snell = 1 - np.exp(2 * (llnull - llf) / n)
    r2_max = 1 - np.exp(2 * llnull / n)
    nagelkerke_r2 = cox_snell / r2_max if r2_max > 0 else 0

    # Predictions for AUC & HL
    y_pred = result.predict(X_sm)
    
    # AUC
    try:
        auc = roc_auc_score(y, y_pred)
    except:
        auc = None
        
    # Hosmer-Lemeshow test (g=10)
    hl_chi2 = None
    hl_p = None
    try:
        df_hl = pd.DataFrame({'y': y, 'p': y_pred})
        # Use qcut to get deciles, drop duplicates if there are many ties
        df_hl['g'] = pd.qcut(df_hl['p'], 10, duplicates='drop')
        observed = df_hl.groupby('g', observed=True)['y'].sum()
        expected = df_hl.groupby('g', observed=True)['p'].sum()
        total = df_hl.groupby('g', observed=True)['y'].count()
        
        # Calculate Pearson chi2 for deciles
        chi2_val = np.sum((observed - expected)**2 / (expected * (1 - expected / total)))
        df_groups = len(df_hl['g'].unique())
        if df_groups > 2:
            hl_chi2 = float(chi2_val)
            hl_p = float(1 - stats.chi2.cdf(hl_chi2, df_groups - 2))
        else:
            hl_chi2 = None
            hl_p = None
    except Exception as e:
        pass

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
        
        # Univariate crude OR
        crude_or = None
        crude_ci_lo = None
        crude_ci_hi = None
        crude_pval = None
        
        if i > 0: # Not intercept
            try:
                X_univ = sm.add_constant(X[:, i-1])
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    res_univ = sm.Logit(y, X_univ).fit(disp=False, maxiter=50)
                crude_or = round(float(np.exp(res_univ.params[1])), 3)
                crude_ci_lo = round(float(np.exp(res_univ.conf_int()[1, 0])), 3)
                crude_ci_hi = round(float(np.exp(res_univ.conf_int()[1, 1])), 3)
                crude_pval = round(float(res_univ.pvalues[1]), 4)
            except:
                pass

        var_dict = {
            "name": name,
            "coef": round(coef, 4),
            "se": round(se, 4),
            "or": or_val,
            "ci_lo": ci_lo_or,
            "ci_hi": ci_hi_or,
            "p_value": round(pval, 4),
            "significant": pval < 0.05,
        }
        
        if crude_or is not None:
            var_dict.update({
                "crude_or": crude_or,
                "crude_ci_lo": crude_ci_lo,
                "crude_ci_hi": crude_ci_hi,
                "crude_p_value": crude_pval
            })
            
        variables.append(var_dict)

    return {
        "method": "Standard MLE (statsmodels)",
        "log_likelihood": round(llf, 2),
        "pseudo_r2": round(float(result.prsquared), 4),
        "nagelkerke_r2": round(nagelkerke_r2, 4) if nagelkerke_r2 else None,
        "auc": round(auc, 4) if auc else None,
        "hl_chi2": round(hl_chi2, 4) if hl_chi2 else None,
        "hl_p_value": round(hl_p, 4) if hl_p else None,
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

    # LASSO prediction model
    print("\nLASSO feature selection and predictive evaluation (10-fold CV)...")
    try:
        lasso_result = run_lasso_cv(X, y, feature_names)
        selected = [v["name"] for v in lasso_result["variables"]]
        best_C = lasso_result["best_C"]
    except Exception as e:
        print(f"  LASSO failed: {e}")
        lasso_result = {"method": "LASSO (10-fold CV)", "error": str(e), "variables": []}
        selected = feature_names
        best_C = None

    # Run explanatory models on ALL pre-specified features
    print("\nFirth logistic regression (Explanatory)...")
    try:
        firth_result = run_firth(X, y, feature_names)
    except Exception as e:
        print(f"  Firth regression failed: {e}")
        firth_result = {"method": "Firth", "error": str(e), "variables": []}

    print("\nStandard logistic regression (Explanatory)...")
    try:
        standard_result = run_standard(X, y, feature_names)
    except Exception as e:
        print(f"  Standard MLE failed: {e}")
        standard_result = {"method": "Standard MLE (statsmodels)", "error": str(e), "variables": []}

    # Build output
    n_events = int(y.sum())
    minority_events = min(n_events, len(y) - n_events)
    epv = minority_events / len(feature_names) if len(feature_names) > 0 else 0

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_n": len(y),
        "n_events": n_events,
        "epv": round(epv, 2),
        "n_features_total": len(feature_names),
        "lasso": lasso_result,
        "firth": firth_result,
        "standard": standard_result,
    }

    out_path = OUTPUT_DIR / "multivariate.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ Multivariate analysis → {out_path}")

    # Quick summary
    print(f"\n--- Significant predictors (Firth, p<0.05) ---")
    if "error" not in firth_result:
        sig = [v for v in firth_result["variables"] if v["significant"]]
        if sig:
            for v in sorted(sig, key=lambda x: x["p_value"]):
                print(f"  {v['name']}: OR={v['or']} [{v['ci_lo']}–{v['ci_hi']}], p={v['p_value']}")
        else:
            print("  None")

    print(f"\n--- Significant predictors (Standard, p<0.05) ---")
    if "error" not in standard_result:
        sig_std = [v for v in standard_result["variables"] if v["significant"] and v["name"] != "Intercept"]
        if sig_std:
            for v in sorted(sig_std, key=lambda x: x["p_value"]):
                print(f"  {v['name']}: OR={v['or']} [{v['ci_lo']}–{v['ci_hi']}], p={v['p_value']}")
        else:
            print("  None")

if __name__ == "__main__":
    main()
