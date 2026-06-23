"""
data_loader.py
--------------
Loads data from the public Google Sheet CSV export,
cleans column names, and prepares the DataFrame for analysis.
"""

import requests
import pandas as pd
import io

SHEET_ID = "1JG5cGNaqo_2DB4Z7N-3w8Yz8eHkQhAhDLoUxMoymlAY"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# ---------------------------------------------------------------------------
# Column rename map: Thai names → short snake_case keys
# ---------------------------------------------------------------------------
COLUMN_RENAME = {
    "ID": "patient_id",
    "Arrival_Date": "er_date",
    "Age": "age",
    "Inclusion_Criteria": "inclusion_criteria",
    "Exclusion_Criteria": "exclusion_criteria",
    "Sex": "sex",
    "Health_Coverage": "insurance_type",
    "Residence": "domicile",
    "ICD10_ER": "icd10_er",
    "Symp_Auditory": "sx_hallucination_auditory",
    "Symp_Visual": "sx_hallucination_visual",
    "Symp_Delusion": "sx_delusion",
    "Symp_Aggressive": "sx_aggression",
    "Symp_Disorganized": "sx_disorganized_speech",
    "Symp_Confusion": "sx_confusion",
    "Symp_Other": "sx_other",
    "Symp_Duration": "symptom_duration",
    "Hx_Primary_Psych": "hx_psychiatric",
    "Hx_Psych_Detail": "hx_psychiatric_detail",
    "Hx_Subst_Use": "hx_substance_use",
    "Hx_Meth": "hx_meth",
    "Hx_Cannabis": "hx_cannabis",
    "Hx_Ketamine": "hx_ketamine",
    "Hx_Opioid": "hx_opioid",
    "Hx_Alcohol": "hx_alcohol",
    "Hx_Benzo": "hx_benzo",
    "Hx_Kratom": "hx_kratom",
    "Hx_Subst_Other": "hx_substance_other",
    "Primary_Subst_Type": "primary_substance",
    "Primary_Route": "primary_substance_route",
    "Primary_Duration_Val": "substance_duration_value",
    "Primary_Duration_Unit": "substance_duration_unit",
    "Last_Use_Time": "last_substance_use",
    "UDS_Done": "uds_status",
    "UDS_Meth": "uds_meth",
    "UDS_Cannabis": "uds_cannabis",
    "UDS_Opioid": "uds_opioid",
    "DSM5_A": "dsm_hallucination_delusion",
    "DSM5_B-1": "dsm_within_1mo_or_withdrawal",
    "DSM5_B-2": "dsm_substance_related",
    "DSM5_C": "dsm_not_primary",
    "DSM5_D": "dsm_no_delirium",
    "DSM5_E": "dsm_functional_impairment",
    "SIP_Diagnosis": "sip_diagnosis",
    "Med_Antipsychotic": "med_antipsychotic",
    "Med_Benzo": "med_benzo",
    "Med_Sedation": "med_sedation",
    "Med_Other": "medications_other",
    "Disposition": "discharge_status",
}

# ---------------------------------------------------------------------------
# Variable metadata for TableOne
# (label, type_hint — None = auto-detect)
# ---------------------------------------------------------------------------
VARIABLE_META = {
    "age":                        {"label": "Age (years)",                    "type_hint": None},
    "sex":                        {"label": "Sex",                            "type_hint": "categorical"},
    "insurance_type":             {"label": "Insurance Type",                 "type_hint": "categorical"},
    "domicile":                   {"label": "Domicile",                       "type_hint": "categorical"},
    "icd10_er":                   {"label": "ICD-10 Diagnosis (ER)",          "type_hint": "categorical"},
    "sx_hallucination_auditory":  {"label": "Auditory Hallucination",         "type_hint": "categorical"},
    "sx_hallucination_visual":    {"label": "Visual Hallucination",           "type_hint": "categorical"},
    "sx_delusion":                {"label": "Delusion",                       "type_hint": "categorical"},
    "sx_aggression":              {"label": "Aggression",                     "type_hint": "categorical"},
    "sx_disorganized_speech":     {"label": "Disorganized Speech",            "type_hint": "categorical"},
    "sx_confusion":               {"label": "Confusion",                      "type_hint": "categorical"},
    "symptom_duration":           {"label": "Symptom Duration",               "type_hint": "categorical"},
    "hx_psychiatric":             {"label": "Prior Psychiatric History",      "type_hint": "categorical"},
    "hx_substance_use":           {"label": "Substance Use History",          "type_hint": "categorical"},
    "primary_substance":          {"label": "Primary Substance",              "type_hint": "categorical"},
    "primary_substance_route":    {"label": "Route of Administration",        "type_hint": "categorical"},
    "last_substance_use":         {"label": "Last Substance Use",             "type_hint": "categorical"},
    "uds_status":                 {"label": "UDS Status",                     "type_hint": "categorical"},
    "uds_meth":                   {"label": "UDS: Methamphetamine",           "type_hint": "categorical"},
    "uds_cannabis":               {"label": "UDS: Cannabis",                  "type_hint": "categorical"},
    "uds_opioid":                 {"label": "UDS: Opioid",                    "type_hint": "categorical"},
    "dsm_hallucination_delusion": {"label": "DSM-5: Hallucination or Delusion","type_hint": "categorical"},
    "dsm_within_1mo_or_withdrawal":{"label": "DSM-5: Within 1 mo / Withdrawal","type_hint": "categorical"},
    "dsm_substance_related":      {"label": "DSM-5: Substance-Related Sx",   "type_hint": "categorical"},
    "dsm_not_primary":            {"label": "DSM-5: Not Primary Psychosis",   "type_hint": "categorical"},
    "dsm_no_delirium":            {"label": "DSM-5: No Delirium",             "type_hint": "categorical"},
    "dsm_functional_impairment":  {"label": "DSM-5: Functional Impairment",  "type_hint": "categorical"},
    "medications":                {"label": "Medications Received",           "type_hint": "categorical"},
    "discharge_status":           {"label": "Discharge Status",               "type_hint": "categorical"},
}

STRATIFY_COL = "sip_diagnosis"
STRATIFY_LABELS = {0: "Not SIP", 1: "SIP", 99: None}  # None → exclude from analysis
INCLUSION_LABELS = {0: "Not Met", 1: "Met"}
HX_PSYCH_LABELS = {0: "No", 1: "Yes"}
SIP_ALL_LABELS = {0: "Not SIP", 1: "SIP", 99: "Incomplete Data"}


PRIMARY_SUBSTANCE_MAP = {
    1: "Meth",
    2: "Cannabis",
    3: "Ket",
    4: "Opioid",
    5: "Alc",
    6: "Benzo",
    7: "Kratom",
    8: "อื่นๆ"
}

DISCHARGE_STATUS_MAP = {
    1: "Admitจิตเวช",
    2: "Admitอื่น",
    3: "Refer",
    4: "กลับบ้าน"
}


def load_data(exclude_sip_99: bool = True) -> pd.DataFrame:
    """Fetch CSV from Google Sheet public URL and return cleaned DataFrame."""
    print(f"Fetching data from Google Sheet ({SHEET_ID})...")
    try:
        response = requests.get(CSV_URL, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch Google Sheet: {e}") from e

    df = pd.read_csv(io.StringIO(response.text), skiprows=[1])
    print(f"  Raw rows: {len(df)}, columns: {len(df.columns)}")

    # Rename columns (only rename those present in the map)
    rename_map = {k: v for k, v in COLUMN_RENAME.items() if k in df.columns}
    df = df.rename(columns=rename_map)

    # Map categorical values to labels
    if "primary_substance" in df.columns:
        df["primary_substance"] = pd.to_numeric(df["primary_substance"], errors="coerce").map(PRIMARY_SUBSTANCE_MAP).fillna(df["primary_substance"])
        
    if "discharge_status" in df.columns:
        df["discharge_status"] = pd.to_numeric(df["discharge_status"], errors="coerce").map(DISCHARGE_STATUS_MAP).fillna(df["discharge_status"])

    # Convert sip_diagnosis to numeric, coerce errors to NaN
    if STRATIFY_COL in df.columns:
        df[STRATIFY_COL] = pd.to_numeric(df[STRATIFY_COL], errors="coerce")

    if exclude_sip_99:
        # Exclude rows where sip_diagnosis == 99 (incomplete data)
        df = df[df[STRATIFY_COL] != 99].copy()
        print(f"  After exclusion (99 removed): {len(df)} rows")
    else:
        print(f"  Retaining 99 (incomplete data) as requested: {len(df)} rows")

    return df

