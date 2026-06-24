"""
tableone_generator.py
---------------------
Advanced OOP Table One generator with 5 components:
  1. VariableAnalysis   — dataclass for per-variable results
  2. VariableClassifier — auto-detects variable type
  3. StatisticalEngine  — all statistical calculations
  4. TableOneFormatter  — renders results to HTML / dict
  5. TableOneGenerator  — orchestrator

Design follows the shiny-stat architecture pattern.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy import stats


# ===========================================================================
# 1. VariableAnalysis — Result dataclass for a single table row
# ===========================================================================

VarType = Literal["categorical", "continuous_normal", "continuous_non_normal", "unknown"]


@dataclass
class VariableAnalysis:
    name: str
    label: str
    var_type: VarType
    stats_overall: str = ""
    stats_groups: dict[str, str] = field(default_factory=dict)
    p_value: float | None = None
    test_name: str = ""
    or_test_name: str = ""
    extra_stats: dict[str, Any] = field(default_factory=dict)  # SMD, OR, CI


# ===========================================================================
# 2. VariableClassifier — intelligent variable type inference
# ===========================================================================

class VariableClassifier:
    @staticmethod
    def classify(series: pd.Series, type_hint: str | None = None) -> VarType:
        """Classify a pandas Series into a variable type."""
        s = series.dropna()
        n = len(s)

        if n == 0:
            return "unknown"

        if type_hint == "categorical":
            return "categorical"
        if type_hint in ("continuous_normal", "continuous_non_normal"):
            return type_hint  # type: ignore[return-value]

        # Non-numeric or low-cardinality → categorical
        if not pd.api.types.is_numeric_dtype(s):
            return "categorical"
        if s.nunique() <= 10:
            return "categorical"

        # Numeric with enough unique values → normality test
        return VariableClassifier._test_normality(s, n)

    @staticmethod
    def _test_normality(s: pd.Series, n: int) -> VarType:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if n < 5000:
                _, p_norm = stats.shapiro(s.sample(min(n, 5000), random_state=42))
            else:
                _, p_norm = stats.jarque_bera(s)

        is_normal_test = p_norm > 0.05

        # Descriptive criteria for n > 50
        if n > 50:
            skew = abs(float(s.skew()))
            kurt = abs(float(s.kurtosis()))
            is_normal_desc = skew < 1.0 and kurt < 2.0
            is_normal = is_normal_test and is_normal_desc
        else:
            is_normal = is_normal_test

        return "continuous_normal" if is_normal else "continuous_non_normal"


# ===========================================================================
# 3. StatisticalEngine — all statistical calculations
# ===========================================================================

class StatisticalEngine:

    # --- Descriptive statistics ---

    @staticmethod
    def describe_continuous_normal(s: pd.Series) -> str:
        s = s.dropna()
        return f"{s.mean():.1f} ± {s.std():.1f}"

    @staticmethod
    def describe_continuous_non_normal(s: pd.Series) -> str:
        s = s.dropna()
        q1, med, q3 = s.quantile([0.25, 0.50, 0.75])
        return f"{med:.1f} [{q1:.1f}, {q3:.1f}]"

    @staticmethod
    def describe_categorical(s: pd.Series, total: int) -> dict[str, str]:
        """Returns {category_value: 'count (pct%)'} for each level."""
        counts = s.value_counts(dropna=True).sort_index()
        result: dict[str, str] = {}
        for val, cnt in counts.items():
            pct = 100.0 * cnt / total if total > 0 else 0
            result[str(val)] = f"{cnt} ({pct:.1f}%)"
        return result

    # --- P-value calculations ---

    @staticmethod
    def pvalue_continuous(groups: list[pd.Series], var_type: VarType) -> tuple[float | None, str]:
        """Returns (p_value, test_name)."""
        clean = [g.dropna() for g in groups]
        if any(len(g) < 2 for g in clean):
            return None, "N/A (insufficient data)"

        if var_type == "continuous_normal":
            if len(clean) == 2:
                _, p = stats.ttest_ind(*clean, equal_var=False)
                return float(p), "Welch t-test"
            else:
                _, p = stats.f_oneway(*clean)
                return float(p), "One-way ANOVA"
        else:
            if len(clean) == 2:
                _, p = stats.mannwhitneyu(*clean, alternative="two-sided")
                return float(p), "Mann-Whitney U"
            else:
                _, p = stats.kruskal(*clean)
                return float(p), "Kruskal-Wallis"

    @staticmethod
    def pvalue_categorical(contingency: pd.DataFrame) -> tuple[float | None, str]:
        """Chi-square, fallback to Fisher's exact for 2×2 with low expected freq."""
        if contingency.shape == (2, 2):
            chi2, p_chi, _, expected = stats.chi2_contingency(contingency)
            if expected.min() < 5:
                _, p = stats.fisher_exact(contingency)
                return float(p), "Fisher's Exact"
            return float(p_chi), "Chi-square"
        if contingency.shape[0] < 2 or contingency.shape[1] < 2:
            return None, "N/A (insufficient categories)"
        _, p, _, _ = stats.chi2_contingency(contingency)
        return float(p), "Chi-square"

    # --- Extra stats: SMD and OR ---

    @staticmethod
    def smd_continuous(g1: pd.Series, g2: pd.Series) -> float | None:
        """Standardized Mean Difference (pooled SD)."""
        a, b = g1.dropna(), g2.dropna()
        if len(a) < 2 or len(b) < 2:
            return None
        pooled_sd = math.sqrt(
            ((len(a) - 1) * a.var() + (len(b) - 1) * b.var()) / (len(a) + len(b) - 2)
        )
        if pooled_sd == 0:
            return None
        return float((a.mean() - b.mean()) / pooled_sd)

    @staticmethod
    def smd_categorical(s: pd.Series, group_col: pd.Series, g0_val: Any, g1_val: Any) -> float | None:
        """SMD for binary categorical using proportions."""
        p1 = s[group_col == g1_val].value_counts(normalize=True)
        p0 = s[group_col == g0_val].value_counts(normalize=True)
        cats = list(s.dropna().unique())
        if hasattr(s, "cat"):
            cat_list = list(s.cat.categories)
            cats = sorted(cats, key=lambda x: cat_list.index(x) if x in cat_list else 0)
            
        if len(cats) != 2:
            return None
        cat = cats[-1]  # Use the 'event' or 'positive' category
        p1v = float(p1.get(cat, 0))
        p0v = float(p0.get(cat, 0))
        denom = math.sqrt((p1v * (1 - p1v) + p0v * (1 - p0v)) / 2)
        return float((p1v - p0v) / denom) if denom > 0 else None

    @staticmethod
    def odds_ratio_categorical(contingency: pd.DataFrame) -> dict[str, Any]:
        """OR with Haldane-Anscombe correction for 2×2 tables."""
        if contingency.shape != (2, 2):
            return {}
        a, b, c, d = (
            contingency.iloc[0, 0], contingency.iloc[0, 1],
            contingency.iloc[1, 0], contingency.iloc[1, 1],
        )
        # Haldane-Anscombe: add 0.5 if any cell is 0
        if min(a, b, c, d) == 0:
            a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
        or_val = (a * d) / (b * c) if (b * c) != 0 else None
        if or_val is None:
            return {}
        log_or = math.log(or_val)
        se_log_or = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
        ci_lo = math.exp(log_or - 1.96 * se_log_or)
        ci_hi = math.exp(log_or + 1.96 * se_log_or)
        return {"or": round(or_val, 3), "ci_lo": round(ci_lo, 3), "ci_hi": round(ci_hi, 3)}

    @staticmethod
    def odds_ratio_continuous(s: pd.Series, group_col: pd.Series) -> dict[str, Any]:
        """Univariate logistic regression OR for continuous variable."""
        try:
            from scipy.special import expit
            combined = pd.DataFrame({"x": s, "y": group_col}).dropna()
            if len(combined) < 10 or combined["y"].nunique() < 2:
                return {}
            # Simple logistic via scipy minimize
            from scipy.optimize import minimize

            def neg_log_likelihood(params):
                b0, b1 = params
                y_hat = expit(b0 + b1 * combined["x"])
                y_hat = np.clip(y_hat, 1e-10, 1 - 1e-10)
                return -np.sum(combined["y"] * np.log(y_hat) + (1 - combined["y"]) * np.log(1 - y_hat))

            res = minimize(neg_log_likelihood, [0.0, 0.0], method="BFGS")
            if not res.success:
                return {}
            b1 = res.x[1]
            or_val = math.exp(b1)
            # Approximate SE from Hessian
            if res.hess_inv is not None:
                se = math.sqrt(abs(res.hess_inv[1, 1]))
                ci_lo = math.exp(b1 - 1.96 * se)
                ci_hi = math.exp(b1 + 1.96 * se)
            else:
                ci_lo, ci_hi = None, None
            return {
                "or": round(or_val, 3),
                "ci_lo": round(ci_lo, 3) if ci_lo else None,
                "ci_hi": round(ci_hi, 3) if ci_hi else None,
            }
        except Exception:
            return {}


# ===========================================================================
# 4. TableOneFormatter — renders VariableAnalysis results to HTML / dict
# ===========================================================================

class TableOneFormatter:

    @staticmethod
    def format_pvalue(p: float | None) -> str:
        if p is None:
            return "—"
        if p < 0.001:
            return "<0.001"
        return f"{p:.3f}"

    @staticmethod
    def to_dataframe(results: list[VariableAnalysis], group_labels: dict) -> pd.DataFrame:
        """Convert list of VariableAnalysis to a flat pandas DataFrame."""
        rows = []
        for va in results:
            if va.var_type == "categorical":
                # One row per category level
                # Collect all level keys across groups + overall, maintaining order
                level_keys = list(va.stats_overall.keys()) if isinstance(va.stats_overall, dict) else []
                for gd in va.stats_groups.values():
                    if isinstance(gd, dict):
                        for k in gd.keys():
                            if k not in level_keys:
                                level_keys.append(k)

                for i, level in enumerate(level_keys):
                    row: dict[str, Any] = {
                        "Variable": va.label if i == 0 else "",
                        "Level": level,
                        "Type": va.var_type if i == 0 else "",
                        "Overall": va.stats_overall.get(level, "0 (0.0%)") if isinstance(va.stats_overall, dict) else "",
                    }
                    for g_val, g_label in group_labels.items():
                        gd = va.stats_groups.get(str(g_val), {})
                        row[g_label] = gd.get(level, "0 (0.0%)") if isinstance(gd, dict) else ""
                    row["p-value"] = TableOneFormatter.format_pvalue(va.p_value) if i == 0 else ""
                    row["Test"] = va.test_name if i == 0 else ""
                    row["SMD"] = f"{va.extra_stats.get('smd', ''):.3f}" if i == 0 and va.extra_stats.get("smd") is not None else ("" if i != 0 else "—")
                    if i == 0 and va.extra_stats.get("or"):
                        or_d = va.extra_stats["or"]
                        row["OR (95% CI)"] = f"{or_d['or']} ({or_d.get('ci_lo','?')}–{or_d.get('ci_hi','?')})"
                    else:
                        row["OR (95% CI)"] = "" if i != 0 else "—"
                    rows.append(row)
            else:
                row = {
                    "Variable": va.label,
                    "Level": "",
                    "Type": va.var_type,
                    "Overall": va.stats_overall if isinstance(va.stats_overall, str) else "",
                }
                for g_val, g_label in group_labels.items():
                    row[g_label] = va.stats_groups.get(str(g_val), "—")
                row["p-value"] = TableOneFormatter.format_pvalue(va.p_value)
                row["Test"] = va.test_name
                smd = va.extra_stats.get("smd")
                row["SMD"] = f"{smd:.3f}" if smd is not None else "—"
                or_d = va.extra_stats.get("or", {})
                if or_d:
                    row["OR (95% CI)"] = f"{or_d['or']} ({or_d.get('ci_lo','?')}–{or_d.get('ci_hi','?')})"
                else:
                    row["OR (95% CI)"] = "—"
                rows.append(row)
        return pd.DataFrame(rows)

    @staticmethod
    def to_html(df: pd.DataFrame) -> str:
        """Render DataFrame to styled HTML table."""
        def highlight_pvalue(val: str) -> str:
            if val in ("<0.001", "") or val == "—":
                return val
            try:
                p = float(val)
                if p < 0.05:
                    return f'<span class="sig">{val}</span>'
            except ValueError:
                pass
            return val

        df_copy = df.copy()
        if "p-value" in df_copy.columns:
            df_copy["p-value"] = df_copy["p-value"].apply(highlight_pvalue)

        html = df_copy.to_html(
            index=False,
            border=0,
            classes="tableone",
            escape=False,
            na_rep="—",
        )
        return html

    @staticmethod
    def to_dict(results: list[VariableAnalysis], group_labels: dict) -> list[dict]:
        """Convert results to JSON-serializable list for the frontend."""
        output = []
        for va in results:
            entry: dict[str, Any] = {
                "name": va.name,
                "label": va.label,
                "var_type": va.var_type,
                "stats_overall": va.stats_overall,
                "stats_groups": va.stats_groups,
                "p_value": va.p_value,
                "p_value_fmt": TableOneFormatter.format_pvalue(va.p_value),
                "test_name": va.test_name,
                "significant": va.p_value is not None and va.p_value < 0.05,
                "extra_stats": {
                    k: (round(v, 4) if isinstance(v, float) else v)
                    for k, v in va.extra_stats.items()
                },
            }
            output.append(entry)
        return output


# ===========================================================================
# 5. TableOneGenerator — orchestrator
# ===========================================================================

class TableOneGenerator:
    def __init__(self, df: pd.DataFrame, variable_meta: dict[str, dict] | None = None):
        self.df = df
        self.variable_meta = variable_meta or {}

    def generate(
        self,
        selected_vars: list[str],
        stratify_by: str | None = None,
        or_style: Literal["all_levels", "binary_only", "none"] = "all_levels",
    ) -> tuple[list[VariableAnalysis], dict]:
        """
        Orchestrates classification, statistics, and formatting.

        Returns:
            (results, group_labels)  where group_labels = {group_val: group_label}
        """
        group_labels: dict[str, str] = {}
        group_values: list[Any] = []

        if stratify_by and stratify_by in self.df.columns:
            group_values = sorted(self.df[stratify_by].dropna().unique())
            group_labels = {str(gv): str(gv) for gv in group_values}

        results: list[VariableAnalysis] = []

        for var in selected_vars:
            if var not in self.df.columns:
                continue

            series = self.df[var]
            meta = self.variable_meta.get(var, {})
            label = meta.get("label", var)
            type_hint = meta.get("type_hint")

            var_type = VariableClassifier.classify(series, type_hint)
            va = VariableAnalysis(name=var, label=label, var_type=var_type)

            # --- Descriptive stats overall ---
            if var_type == "categorical":
                va.stats_overall = StatisticalEngine.describe_categorical(series, len(series.dropna()))
            elif var_type == "continuous_normal":
                va.stats_overall = StatisticalEngine.describe_continuous_normal(series)
            elif var_type == "continuous_non_normal":
                va.stats_overall = StatisticalEngine.describe_continuous_non_normal(series)

            # --- Per-group stats + p-value ---
            if stratify_by and group_values:
                group_series = [
                    self.df.loc[self.df[stratify_by] == gv, var]
                    for gv in group_values
                ]

                for gv, gs in zip(group_values, group_series):
                    key = str(gv)
                    if var_type == "categorical":
                        va.stats_groups[key] = StatisticalEngine.describe_categorical(gs, len(gs.dropna()))
                    elif var_type == "continuous_normal":
                        va.stats_groups[key] = StatisticalEngine.describe_continuous_normal(gs)
                    elif var_type == "continuous_non_normal":
                        va.stats_groups[key] = StatisticalEngine.describe_continuous_non_normal(gs)

                # P-value
                if var_type in ("continuous_normal", "continuous_non_normal"):
                    p, tname = StatisticalEngine.pvalue_continuous(group_series, var_type)
                    va.p_value, va.test_name = p, tname
                elif var_type == "categorical":
                    contingency = pd.crosstab(series, self.df[stratify_by])
                    p, tname = StatisticalEngine.pvalue_categorical(contingency)
                    va.p_value, va.test_name = p, tname

                # SMD (2-group only)
                if len(group_values) == 2:
                    gv0, gv1 = group_values[0], group_values[1]
                    s0 = self.df.loc[self.df[stratify_by] == gv0, var]
                    s1 = self.df.loc[self.df[stratify_by] == gv1, var]

                    if var_type in ("continuous_normal", "continuous_non_normal"):
                        smd = StatisticalEngine.smd_continuous(s0, s1)
                    else:
                        smd = StatisticalEngine.smd_categorical(series, self.df[stratify_by], gv0, gv1)
                    va.extra_stats["smd"] = smd

                    # OR
                    if or_style != "none":
                        if var_type == "categorical" and or_style in ("all_levels", "binary_only"):
                            contingency2 = pd.crosstab(series, self.df[stratify_by])
                            if contingency2.shape == (2, 2):
                                or_d = StatisticalEngine.odds_ratio_categorical(contingency2)
                                va.extra_stats["or"] = or_d
                                va.or_test_name = "Haldane-Anscombe OR"
                        elif var_type in ("continuous_normal", "continuous_non_normal"):
                            or_d = StatisticalEngine.odds_ratio_continuous(series, self.df[stratify_by])
                            va.extra_stats["or"] = or_d
                            va.or_test_name = "Logistic Regression OR"

            results.append(va)

        return results, group_labels
