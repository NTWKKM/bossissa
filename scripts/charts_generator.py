"""
charts_generator.py
-------------------
Generates Plotly chart specs (as JSON) and additional statistics:
  - DSM-5 criteria fulfilment heatmap (SIP vs Non-SIP)
  - Clinical symptom grouped bar chart
  - Primary substance pie/donut chart
  - Age distribution violin+box plot
  - UDS result stacked bar
  - Discharge status grouped bar
  - Logistic regression forest plot (OR + 95% CI)
  - DSM-5 criteria waterfall (% met per criterion)

All charts output as Plotly JSON specs — rendered client-side via Plotly.js (no server needed).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from data_loader import STRATIFY_COL, STRATIFY_LABELS

# ──────────────────────────────────────────────
# Plotly dark theme tokens (match CSS design system)
# ──────────────────────────────────────────────
COLORS = {
    "sip":     "#63b3ed",   # accent blue — SIP group
    "non_sip": "#9f7aea",   # accent purple — Non-SIP group
    "green":   "#68d391",
    "orange":  "#f6ad55",
    "red":     "#fc8181",
    "bg":      "#111520",
    "bg_paper":"#0a0d14",
    "grid":    "rgba(255,255,255,0.06)",
    "text":    "#8b97b0",
    "title":   "#e8edf5",
}

BASE_LAYOUT = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor":  "rgba(0,0,0,0)",
    "font":          {"family": "Inter, system-ui, sans-serif", "color": COLORS["text"], "size": 13},
    "title_font":    {"family": "Inter, system-ui, sans-serif", "color": COLORS["title"], "size": 16},
    "xaxis": {"gridcolor": COLORS["grid"], "zerolinecolor": COLORS["grid"]},
    "yaxis": {"gridcolor": COLORS["grid"], "zerolinecolor": COLORS["grid"]},
    "legend": {"bgcolor": "rgba(0,0,0,0)", "bordercolor": COLORS["grid"]},
    "margin": {"l": 50, "r": 20, "t": 50, "b": 50},
    "hoverlabel": {
        "bgcolor": "#1a2035", 
        "bordercolor": COLORS["grid"], 
        "font": {"color": "#ffffff", "size": 13, "family": "Inter, system-ui, sans-serif"}
    },
}


def _layout(**overrides) -> dict:
    import copy
    lay = copy.deepcopy(BASE_LAYOUT)
    lay.update(overrides)
    return lay


def group_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (sip_df, non_sip_df)."""
    sip = df[df[STRATIFY_COL] == 1]
    non = df[df[STRATIFY_COL] == 0]
    return sip, non


# ──────────────────────────────────────────────
# Chart 1: SIP vs Non-SIP group donut
# ──────────────────────────────────────────────
def chart_group_donut(df: pd.DataFrame) -> dict:
    counts = df[STRATIFY_COL].value_counts().sort_index()
    labels = [STRATIFY_LABELS.get(int(k), str(k)) for k in counts.index]
    values = counts.tolist()
    return {
        "id": "group_donut",
        "title": "SIP vs Non-SIP Distribution",
        "description": "Proportion of patients meeting DSM-5 SIP diagnostic criteria",
        "type": "pie",
        "data": [{
            "type": "pie",
            "labels": labels,
            "values": values,
            "hole": 0.55,
            "marker": {"colors": [COLORS["sip"], COLORS["non_sip"]], "line": {"color": COLORS["bg_paper"], "width": 3}},
            "textinfo": "label+percent",
            "textfont": {"color": COLORS["title"], "size": 13},
            "hovertemplate": "<b>%{label}</b><br>n = %{value}<br>%{percent}<extra></extra>",
        }],
        "layout": _layout(
            title="SIP vs Non-SIP Distribution",
            showlegend=True,
            legend={"orientation": "h", "y": -0.1},
        ),
    }


# ──────────────────────────────────────────────
# Chart 2: Clinical symptoms grouped bar
# ──────────────────────────────────────────────
SYMPTOM_COLS = {
    "sx_hallucination_auditory": "Auditory Hallucination",
    "sx_hallucination_visual":   "Visual Hallucination",
    "sx_delusion":               "Delusion",
    "sx_aggression":             "Aggression",
    "sx_disorganized_speech":    "Disorganized Speech",
    "sx_confusion":              "Confusion",
}


def chart_symptoms(df: pd.DataFrame) -> dict:
    sip, non = group_split(df)
    labels, sip_pcts, non_pcts, pvals = [], [], [], []

    for col, label in SYMPTOM_COLS.items():
        if col not in df.columns:
            continue
        labels.append(label)
        sip_pcts.append(_pct_positive(sip[col]) if col in sip.columns else 0)
        non_pcts.append(_pct_positive(non[col]) if col in non.columns else 0)
        # Chi-square
        try:
            ct = pd.crosstab(df[col], df[STRATIFY_COL])
            _, p, _, _ = stats.chi2_contingency(ct)
            pvals.append(round(float(p), 4))
        except Exception:
            pvals.append(None)

    return {
        "id": "symptoms_bar",
        "title": "Clinical Symptoms by SIP Diagnosis",
        "description": "Percentage of patients presenting each symptom, stratified by SIP diagnostic group",
        "type": "bar",
        "data": [
            {
                "type": "bar",
                "name": "SIP",
                "x": labels,
                "y": sip_pcts,
                "marker": {"color": COLORS["sip"], "opacity": 0.9},
                "hovertemplate": "<b>%{x}</b><br>SIP: %{y:.1f}%<extra></extra>",
            },
            {
                "type": "bar",
                "name": "Non-SIP",
                "x": labels,
                "y": non_pcts,
                "marker": {"color": COLORS["non_sip"], "opacity": 0.9},
                "hovertemplate": "<b>%{x}</b><br>Non-SIP: %{y:.1f}%<extra></extra>",
            },
        ],
        "layout": _layout(
            title="Clinical Symptoms by SIP Diagnosis",
            barmode="group",
            yaxis={"title": "Prevalence (%)", "gridcolor": COLORS["grid"], "range": [0, 105]},
            xaxis={"gridcolor": COLORS["grid"]},
            bargap=0.25,
        ),
        "pvalues": dict(zip(labels, pvals)),
    }


# ──────────────────────────────────────────────
# Chart 3: Primary substance distribution
# ──────────────────────────────────────────────
def chart_substance(df: pd.DataFrame) -> dict:
    col = "primary_substance"
    if col not in df.columns:
        return {}
    sip, non = group_split(df)

    def top_counts(sub_df: pd.DataFrame, top_n: int = 8) -> pd.Series:
        counts = sub_df[col].value_counts(sort=False).head(top_n)
        return counts

    sip_c = top_counts(sip)
    non_c = top_counts(non)
    raw_labels = list(dict.fromkeys(list(sip_c.index) + list(non_c.index)))
    
    # Sort by the dictionary index order
    order = ["Meth", "Cannabis", "Ket", "Opioid", "Alc", "Benzo", "Kratom", "อื่นๆ"]
    all_labels = sorted(raw_labels, key=lambda x: order.index(x) if x in order else 999)

    return {
        "id": "substance_bar",
        "title": "Primary Substance Used",
        "description": "Distribution of primary substance reported by patients in each diagnostic group",
        "type": "bar",
        "data": [
            {
                "type": "bar",
                "name": "SIP",
                "x": all_labels,
                "y": [int(sip_c.get(s, 0)) for s in all_labels],
                "marker": {"color": COLORS["sip"]},
                "hovertemplate": "<b>%{x}</b><br>SIP: %{y} patients<extra></extra>",
            },
            {
                "type": "bar",
                "name": "Non-SIP",
                "x": all_labels,
                "y": [int(non_c.get(s, 0)) for s in all_labels],
                "marker": {"color": COLORS["non_sip"]},
                "hovertemplate": "<b>%{x}</b><br>Non-SIP: %{y} patients<extra></extra>",
            },
        ],
        "layout": _layout(
            title="Primary Substance Used",
            barmode="group",
            yaxis={"title": "Number of Patients", "gridcolor": COLORS["grid"]},
            xaxis={"gridcolor": COLORS["grid"]},
        ),
    }


# ──────────────────────────────────────────────
# Chart 4: Age distribution violin + box
# ──────────────────────────────────────────────
def chart_age(df: pd.DataFrame) -> dict:
    col = "age"
    if col not in df.columns:
        return {}
    sip, non = group_split(df)
    sip_age = sip[col].dropna().tolist()
    non_age = non[col].dropna().tolist()

    return {
        "id": "age_violin",
        "title": "Age Distribution by SIP Diagnosis",
        "description": "Age distribution of patients stratified by SIP diagnostic outcome",
        "type": "violin",
        "data": [
            {
                "type": "violin",
                "name": "SIP",
                "y": sip_age,
                "box": {"visible": True},
                "meanline": {"visible": True},
                "fillcolor": COLORS["sip"],
                "opacity": 0.7,
                "line": {"color": COLORS["sip"]},
                "hovertemplate": "SIP<br>Age: %{y}<extra></extra>",
            },
            {
                "type": "violin",
                "name": "Non-SIP",
                "y": non_age,
                "box": {"visible": True},
                "meanline": {"visible": True},
                "fillcolor": COLORS["non_sip"],
                "opacity": 0.7,
                "line": {"color": COLORS["non_sip"]},
                "hovertemplate": "Non-SIP<br>Age: %{y}<extra></extra>",
            },
        ],
        "layout": _layout(
            title="Age Distribution by SIP Diagnosis",
            yaxis={"title": "Age (years)", "gridcolor": COLORS["grid"]},
        ),
    }


# ──────────────────────────────────────────────
# Chart 5: DSM-5 criteria waterfall (% met)
# ──────────────────────────────────────────────
DSM_COLS = {
    "dsm_hallucination_delusion":    "Hallucination / Delusion",
    "dsm_within_1mo_or_withdrawal":  "Within 1 mo / Withdrawal",
    "dsm_substance_related":         "Substance-Related Sx",
    "dsm_not_primary":               "Not Primary Psychosis",
    "dsm_no_delirium":               "No Delirium",
    "dsm_functional_impairment":     "Functional Impairment",
}


def chart_dsm_criteria(df: pd.DataFrame) -> dict:
    labels, sip_pcts, non_pcts = [], [], []
    sip, non = group_split(df)

    for col, label in DSM_COLS.items():
        if col not in df.columns:
            continue
        labels.append(label)
        sip_pcts.append(_pct_positive(sip[col]) if col in sip.columns else 0)
        non_pcts.append(_pct_positive(non[col]) if col in non.columns else 0)

    return {
        "id": "dsm_criteria",
        "title": "DSM-5 Criteria Fulfilment Rate",
        "description": "Percentage of patients meeting each DSM-5 SIP criterion, by diagnostic group",
        "type": "bar",
        "data": [
            {
                "type": "bar",
                "name": "SIP",
                "x": sip_pcts,
                "y": labels,
                "orientation": "h",
                "marker": {"color": COLORS["sip"], "opacity": 0.9},
                "hovertemplate": "<b>%{y}</b><br>SIP: %{x:.1f}%<extra></extra>",
            },
            {
                "type": "bar",
                "name": "Non-SIP",
                "x": non_pcts,
                "y": labels,
                "orientation": "h",
                "marker": {"color": COLORS["non_sip"], "opacity": 0.9},
                "hovertemplate": "<b>%{y}</b><br>Non-SIP: %{x:.1f}%<extra></extra>",
            },
        ],
        "layout": _layout(
            title="DSM-5 Criteria Fulfilment Rate",
            barmode="group",
            xaxis={"title": "Fulfilment Rate (%)", "gridcolor": COLORS["grid"], "range": [0, 105]},
            yaxis={"gridcolor": COLORS["grid"], "automargin": True},
            margin={"l": 200, "r": 30, "t": 60, "b": 60},
        ),
    }


# ──────────────────────────────────────────────
# Chart 6: UDS stacked bar
# ──────────────────────────────────────────────
UDS_COLS = {
    "uds_meth":    "Methamphetamine",
    "uds_cannabis":"Cannabis",
    "uds_opioid":  "Opioid",
}
UDS_COLORS = [COLORS["sip"], COLORS["green"], COLORS["orange"]]


def chart_uds(df: pd.DataFrame) -> dict:
    sip, non = group_split(df)
    traces = []
    for (col, label), color in zip(UDS_COLS.items(), UDS_COLORS):
        if col not in df.columns:
            continue
        traces.append({
            "type": "bar",
            "name": label,
            "x": ["SIP", "Non-SIP"],
            "y": [_pct_positive(sip[col]), _pct_positive(non[col])],
            "marker": {"color": color},
            "hovertemplate": f"<b>{label}</b><br>%{{x}}: %{{y:.1f}}%<extra></extra>",
        })
    return {
        "id": "uds_bar",
        "title": "Urine Drug Screen Positivity by Group",
        "description": "Percentage of positive UDS results for each substance, by diagnostic group",
        "type": "bar",
        "data": traces,
        "layout": _layout(
            title="Urine Drug Screen Positivity",
            barmode="group",
            yaxis={"title": "Positive Rate (%)", "gridcolor": COLORS["grid"], "range": [0, 105]},
            xaxis={"gridcolor": COLORS["grid"]},
        ),
    }


# ──────────────────────────────────────────────
# Chart 7: Discharge status
# ──────────────────────────────────────────────
def chart_discharge(df: pd.DataFrame) -> dict:
    col = "discharge_status"
    if col not in df.columns:
        return {}
    sip, non = group_split(df)

    raw_cats = df[col].dropna().unique().tolist()
    order = ["Admitจิตเวช", "Admitอื่น", "Refer", "กลับบ้าน"]
    all_cats = sorted(raw_cats, key=lambda x: order.index(x) if x in order else 999)
    total_sip = max(len(sip), 1)
    total_non = max(len(non), 1)

    return {
        "id": "discharge_bar",
        "title": "Discharge Status",
        "description": "Discharge disposition of patients by SIP diagnostic group",
        "type": "bar",
        "data": [
            {
                "type": "bar",
                "name": "SIP",
                "x": all_cats,
                "y": [round(100 * int((sip[col] == c).sum()) / total_sip, 1) for c in all_cats],
                "marker": {"color": COLORS["sip"]},
                "hovertemplate": "<b>%{x}</b><br>SIP: %{y:.1f}%<extra></extra>",
            },
            {
                "type": "bar",
                "name": "Non-SIP",
                "x": all_cats,
                "y": [round(100 * int((non[col] == c).sum()) / total_non, 1) for c in all_cats],
                "marker": {"color": COLORS["non_sip"]},
                "hovertemplate": "<b>%{x}</b><br>Non-SIP: %{y:.1f}%<extra></extra>",
            },
        ],
        "layout": _layout(
            title="Discharge Status by Group",
            barmode="group",
            yaxis={"title": "Percentage (%)", "gridcolor": COLORS["grid"]},
            xaxis={"gridcolor": COLORS["grid"]},
        ),
    }


# ──────────────────────────────────────────────
# Chart 8: Logistic regression OR forest plot
# ──────────────────────────────────────────────
OR_VARS = {
    "age":                       "Age",
    "sx_hallucination_auditory": "Auditory Hallucination",
    "sx_hallucination_visual":   "Visual Hallucination",
    "sx_delusion":               "Delusion",
    "sx_aggression":             "Aggression",
    "sx_confusion":              "Confusion",
    "hx_psychiatric":            "Prior Psychiatric Hx",
    "hx_substance_use":          "Substance Use Hx",
    "uds_meth":                  "UDS Meth+",
    "uds_cannabis":              "UDS Cannabis+",
}


def chart_forest_plot(df: pd.DataFrame) -> dict:
    """Simple univariate logistic regression OR forest plot."""
    from scipy.special import expit

    labels, ors, ci_los, ci_his, pvals = [], [], [], [], []

    for col, label in OR_VARS.items():
        if col not in df.columns:
            continue
        try:
            sub = df[[col, STRATIFY_COL]].dropna()
            if len(sub) < 10 or sub[STRATIFY_COL].nunique() < 2:
                continue
            if pd.api.types.is_numeric_dtype(sub[col]):
                x = (sub[col] == 1).astype(float)
            else:
                x = sub[col].str.lower().str.fullmatch(r"yes|ใช่|positive|\+|มี", na=False).astype(float)
            y = sub[STRATIFY_COL].astype(float).values
            x = x.values

            # Simple logistic via scipy
            from scipy.optimize import minimize
            def nll(p):
                lp = np.clip(expit(p[0] + p[1] * x), 1e-9, 1 - 1e-9)
                return -np.sum(y * np.log(lp) + (1 - y) * np.log(1 - lp))
            res = minimize(nll, [0.0, 0.0], method="BFGS")
            if not res.success:
                continue
            b1 = res.x[1]
            or_val = float(np.exp(min(b1, 700.0)))
            # Validate Hessian inverse before computing SE
            if res.hess_inv is None or np.any(np.isnan(res.hess_inv)) or np.any(np.isinf(res.hess_inv)):
                continue
            se = float(np.sqrt(max(abs(res.hess_inv[1, 1]), 1e-10)))
            
            # Prevent overflow in np.exp
            val_lo = min(b1 - 1.96 * se, 700.0)
            val_hi = min(b1 + 1.96 * se, 700.0)
            ci_lo = float(np.exp(val_lo))
            ci_hi = float(np.exp(val_hi))
            # Wald p-value
            z = b1 / se if se > 0 else 0
            p = float(2 * (1 - stats.norm.cdf(abs(z))))

            labels.append(label)
            ors.append(round(or_val, 3))
            ci_los.append(round(ci_lo, 3))
            ci_his.append(round(ci_hi, 3))
            pvals.append(round(p, 4))
        except Exception:
            continue

    if not labels:
        return {}

    # Sort by OR
    order = sorted(range(len(ors)), key=lambda i: ors[i])
    labels  = [labels[i]  for i in order]
    ors     = [ors[i]     for i in order]
    ci_los  = [ci_los[i]  for i in order]
    ci_his  = [ci_his[i]  for i in order]
    pvals   = [pvals[i]   for i in order]

    colors = [COLORS["green"] if p < 0.05 else COLORS["text"] for p in pvals]
    err_minus = [round(o - lo, 3) for o, lo in zip(ors, ci_los)]
    err_plus  = [round(hi - o, 3) for o, hi in zip(ors, ci_his)]

    return {
        "id": "forest_plot",
        "title": "Odds Ratio Forest Plot (Univariate)",
        "description": "Univariate logistic regression OR with 95% CI for SIP diagnosis outcome. Green = p<0.05.",
        "type": "scatter",
        "data": [
            {
                "type": "scatter",
                "mode": "markers",
                "name": "OR (95% CI)",
                "x": ors,
                "y": labels,
                "error_x": {
                    "type": "data",
                    "symmetric": False,
                    "array": err_plus,
                    "arrayminus": err_minus,
                    "color": COLORS["text"],
                    "thickness": 2,
                    "width": 6,
                },
                "marker": {"size": 12, "color": colors, "symbol": "diamond"},
                "hovertemplate": "<b>%{y}</b><br>OR: %{x:.3f}<extra></extra>",
            },
            # Reference line at OR=1
            {
                "type": "scatter",
                "mode": "lines",
                "name": "OR = 1 (no effect)",
                "x": [1, 1],
                "y": [labels[0], labels[-1]],
                "line": {"color": COLORS["orange"], "dash": "dash", "width": 1.5},
                "hoverinfo": "skip",
            },
        ],
        "layout": _layout(
            title="Univariate OR Forest Plot",
            xaxis={"title": "Odds Ratio (log scale)", "type": "log", "gridcolor": COLORS["grid"]},
            yaxis={"gridcolor": COLORS["grid"], "automargin": True},
            margin={"l": 180, "r": 30, "t": 60, "b": 60},
            showlegend=True,
        ),
    }


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def _pct_positive(s: pd.Series) -> float:
    """Return % of non-null values that are truthy / 'Yes' / 1 / positive."""
    s = s.dropna()
    if len(s) == 0:
        return 0.0
    # Detect positive: numeric 1, or string "Yes"/"ใช่"/"Positive"/"+"/"มี" (exact match, not substring)
    if pd.api.types.is_numeric_dtype(s):
        pos = (s == 1).sum()
    else:
        # Exact match on positive labels — avoid matching "ไม่มี" (contains "มี")
        pos = s.str.lower().str.fullmatch(r"yes|ใช่|positive|\+|มี", na=False).sum()
    return round(100.0 * int(pos) / len(s), 1)


# ──────────────────────────────────────────────
# Main entry
# ──────────────────────────────────────────────
def generate_all_charts(df: pd.DataFrame) -> list[dict]:
    generators = [
        chart_group_donut,
        chart_symptoms,
        chart_substance,
        chart_age,
        chart_dsm_criteria,
        chart_uds,
        chart_discharge,
        chart_forest_plot,
    ]
    charts = []
    for fn in generators:
        try:
            result = fn(df)
            if result:
                charts.append(result)
        except Exception as e:
            print(f"  Warning: {fn.__name__} failed: {e}")
    return charts
