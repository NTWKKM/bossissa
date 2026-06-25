"""
run_analysis.py
---------------
Entry point for GitHub Actions.
Loads data → generates TableOne → writes results to docs/data/.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).parent))

from charts_generator import generate_all_charts
from data_loader import STRATIFY_COL, STRATIFY_LABELS, VARIABLE_META, load_data
from multivariate_analysis import main as generate_multivariate
from stat_generator import main as generate_stat_freq
from tableone_generator import TableOneFormatter, TableOneGenerator

OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "data"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load & clean data
    df_all = load_data(exclude_sip_99=False)
    df = df_all[df_all[STRATIFY_COL] != 99].copy()

    # Map sip_diagnosis values to human-readable labels
    group_labels: dict[str, str] = {
        str(k): v for k, v in STRATIFY_LABELS.items() if v is not None
    }

    # 2. Generate TableOne
    selected_vars = list(VARIABLE_META.keys())
    generator = TableOneGenerator(df, VARIABLE_META)
    results, _ = generator.generate(
        selected_vars=selected_vars,
        stratify_by=STRATIFY_COL,
        or_style="all_levels",
    )

    # Override auto group_labels with human-readable ones
    for va in results:
        new_groups: dict[str, str] = {}
        for k, v in va.stats_groups.items():
            label = STRATIFY_LABELS.get(int(float(k))) or k
            new_groups[label] = v
        va.stats_groups = new_groups

    # 3. Build output group_labels for formatter
    # Since sip_diagnosis is already mapped in df, the keys in stats_groups are the labels
    display_labels = {v: v for k, v in STRATIFY_LABELS.items() if v is not None}

    # 4. Render to HTML
    formatter = TableOneFormatter()
    df_table = TableOneFormatter.to_dataframe(results, display_labels)

    # Rename group columns to human-readable
    df_table = df_table.rename(columns=display_labels)
    html_table = TableOneFormatter.to_html(df_table)

    # 5. Build JSON payload for frontend
    json_results = TableOneFormatter.to_dict(results, display_labels)

    # Compute group counts
    group_counts: dict[str, int] = {}
    for k, label in STRATIFY_LABELS.items():
        if label is not None:
            group_counts[label] = int((df[STRATIFY_COL] == k).sum())

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sheet_id": "1JG5cGNaqo_2DB4Z7N-3w8Yz8eHkQhAhDLoUxMoymlAY",
        "total_n": len(df),
        "group_counts": group_counts,
        "stratify_col": STRATIFY_COL,
        "group_labels": display_labels,
        "n_variables": len(results),
        "n_significant": sum(1 for r in results if r.p_value is not None and r.p_value < 0.05),
    }

    # 6. Generate multivariate analysis (LASSO → Firth + Standard)
    print("Generating multivariate analysis...")
    generate_multivariate(df)

    # 7. Generate charts
    print("Generating Plotly chart specs...")
    charts = generate_all_charts(df)
    metadata["n_charts"] = len(charts)

    # 8. Generate stat_freq (inclusion/hx_psych/sip_all)
    print("Generating frequency stats...")
    generate_stat_freq(df_all)

    # 9. Write outputs
    (OUTPUT_DIR / "tableone.json").write_text(
        json.dumps(json_results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUTPUT_DIR / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUTPUT_DIR / "tableone.html").write_text(html_table, encoding="utf-8")
    (OUTPUT_DIR / "charts.json").write_text(
        json.dumps(charts, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    latex_raw = TableOneFormatter.to_latex(results, display_labels, correction="none")
    latex_bonf = TableOneFormatter.to_latex(results, display_labels, correction="bonferroni",
                                            caption="Baseline Characteristics (Bonferroni-corrected)",
                                            label="tab:tableone_bonf")
    (OUTPUT_DIR / "tableone.tex").write_text(latex_raw, encoding="utf-8")
    (OUTPUT_DIR / "tableone_bonf.tex").write_text(latex_bonf, encoding="utf-8")
    print("  LaTeX tables → docs/data/tableone.tex + tableone_bonf.tex")
    print(f"  Generated {len(charts)} chart specs → docs/data/charts.json")

    print("\n✅ Analysis complete.")
    print(f"   Total N: {metadata['total_n']}")
    for label, count in group_counts.items():
        print(f"   {label}: {count}")
    print(f"   Significant variables (p<0.05): {metadata['n_significant']}/{metadata['n_variables']}")
    print(f"   Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
