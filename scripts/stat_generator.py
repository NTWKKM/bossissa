"""
stat_generator.py
-----------------
Generates frequency distribution tables stratified by:
1. Inclusion Criteria
2. Psychiatric History
3. SIP Diagnosis (including 99)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).parent))

from data_loader import (
    VARIABLE_META, load_data,
    INCLUSION_LABELS, HX_PSYCH_LABELS, SIP_ALL_LABELS
)
from tableone_generator import TableOneFormatter, TableOneGenerator

OUTPUT_DIR = Path(__file__).parent.parent / "docs" / "data"

def process_group(generator: TableOneGenerator, df: pd.DataFrame, selected_vars: list[str], stratify_col: str, labels: dict) -> dict:
    # Only convert to numeric if the column still has numeric values (e.g. sip_diagnosis)
    # For columns already mapped to categorical strings (inclusion_criteria, hx_psychiatric), skip
    if stratify_col in df.columns:
        sample_vals = df[stratify_col].dropna().head(5).tolist()
        if sample_vals and all(isinstance(v, (int, float)) or (isinstance(v, str) and v.replace('.','',1).replace('-','',1).isdigit()) for v in sample_vals):
            df[stratify_col] = pd.to_numeric(df[stratify_col], errors="coerce")

    # Generate results
    results, _ = generator.generate(
        selected_vars=selected_vars,
        stratify_by=stratify_col,
        or_style="none",
    )

    # Override auto group_labels with human-readable ones
    for va in results:
        new_groups = {}
        for k, v in va.stats_groups.items():
            # Try numeric key first, then string key
            try:
                numeric_k = int(float(k))
                label = labels.get(numeric_k) or k
            except (ValueError, TypeError):
                # String key — look up directly in labels dict
                label = labels.get(k) or k
            new_groups[label] = v
        va.stats_groups = new_groups

    # String keys for JSON output display labels
    display_labels = {str(k): v for k, v in labels.items() if v is not None}
    
    # We can use the existing to_dict, but it needs display_labels string map
    json_results = TableOneFormatter.to_dict(results, display_labels)

    # Compute group counts
    group_counts = {}
    for k, label in labels.items():
        if label is not None:
            group_counts[label] = int((df[stratify_col] == k).sum())

    return {
        "group_counts": group_counts,
        "results": json_results,
        "stratify_col": stratify_col,
        "group_labels": display_labels
    }

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load data, but do NOT drop sip_diagnosis == 99
    df = load_data(exclude_sip_99=False)
    selected_vars = list(VARIABLE_META.keys())
    
    generator = TableOneGenerator(df, VARIABLE_META)

    print("Generating stats for Inclusion Criteria...")
    inclusion_data = process_group(generator, df, selected_vars, "inclusion_criteria", INCLUSION_LABELS)

    print("Generating stats for Psychiatric History...")
    hx_psych_data = process_group(generator, df, selected_vars, "hx_psychiatric", HX_PSYCH_LABELS)

    print("Generating stats for SIP Diagnosis (All)...")
    sip_all_data = process_group(generator, df, selected_vars, "sip_diagnosis", SIP_ALL_LABELS)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_n": len(df),
        "inclusion": inclusion_data,
        "hx_psych": hx_psych_data,
        "sip_all": sip_all_data
    }

    # 2. Write outputs
    (OUTPUT_DIR / "stat_freq.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("✅ Stat frequency generation complete -> docs/data/stat_freq.json")


if __name__ == "__main__":
    main()
