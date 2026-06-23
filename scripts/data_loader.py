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
    "Timestamp": "timestamp",
    "Untitled Question": "untitled",
    "ID (ลำดับที่)": "patient_id",
    "วันที่มา ER": "er_date",
    "อายุ (ปี)": "age",
    "เข้าเกณฑ์คัดเข้า": "inclusion_criteria",
    "เกณฑ์คัดออก": "exclusion_criteria",
    "เพศ": "sex",
    "สิทธิการรักษา": "insurance_type",
    "ภูมิลำเนา": "domicile",
    "การวินิจฉัย (ICD10_ER)": "icd10_er",
    "อาการทางคลินิก [หูแว่ว]": "sx_hallucination_auditory",
    "อาการทางคลินิก [เห็นภาพหลอน]": "sx_hallucination_visual",
    "อาการทางคลินิก [หลงผิด]": "sx_delusion",
    "อาการทางคลินิก [ก้าวร้าว]": "sx_aggression",
    "อาการทางคลินิก [พูดไม่รู้เรื่อง]": "sx_disorganized_speech",
    "อาการทางคลินิก [สับสน]": "sx_confusion",
    "อาการอื่นๆ (ระบุ)": "sx_other",
    "ระยะเวลาอาการ": "symptom_duration",
    "ประวัติโรคจิตเดิม": "hx_psychiatric",
    "ระบุโรคจิตเดิม (ถ้ามี)": "hx_psychiatric_detail",
    "ประวัติการใช้สารเสพติด": "hx_substance_use",
    "ประเภทสารที่เคยใช้": "substance_types_used",
    "สารเสพติดหลัก": "primary_substance",
    "รูปแบบการใช้สารหลัก": "primary_substance_route",
    "ระยะเวลาใช้สารหลัก (ตัวเลข)": "substance_duration_value",
    "หน่วยเวลา": "substance_duration_unit",
    "การใช้งานครั้งสุดท้าย": "last_substance_use",
    "สถานะการตรวจ UDS": "uds_status",
    "ผลการตรวจ UDS [UDS: Meth]": "uds_meth",
    "ผลการตรวจ UDS [UDS: Cannabis]": "uds_cannabis",
    "ผลการตรวจ UDS [UDS: Opioid]": "uds_opioid",
    "DSM-5 Criteria Assessment [อาการ Hallucination or Delusion]": "dsm_hallucination_delusion",
    "DSM-5 Criteria Assessment [เกิดขึ้นภายใน 1 เดือน หรือ มี withdrawal]": "dsm_within_1mo_or_withdrawal",
    "DSM-5 Criteria Assessment [อาการสัมพันธ์กับสาร]": "dsm_substance_related",
    "DSM-5 Criteria Assessment [ไม่ใช่โรคจิตปฐมภูมิ]": "dsm_not_primary",
    "DSM-5 Criteria Assessment [ไม่มีภาวะ Delirium]": "dsm_no_delirium",
    "DSM-5 Criteria Assessment [กระทบการทำงาน]": "dsm_functional_impairment",
    "สรุป: เข้าเกณฑ์ SIP": "sip_diagnosis",
    "ยาที่ได้รับ": "medications",
    "ยาอื่นๆ (ระบุ)": "medications_other",
    "การจำหน่าย": "discharge_status",
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


def load_data() -> pd.DataFrame:
    """Fetch CSV from Google Sheet public URL and return cleaned DataFrame."""
    print(f"Fetching data from Google Sheet ({SHEET_ID})...")
    try:
        response = requests.get(CSV_URL, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch Google Sheet: {e}") from e

    df = pd.read_csv(io.StringIO(response.text))
    print(f"  Raw rows: {len(df)}, columns: {len(df.columns)}")

    # Rename columns (only rename those present in the map)
    rename_map = {k: v for k, v in COLUMN_RENAME.items() if k in df.columns}
    df = df.rename(columns=rename_map)

    # Convert sip_diagnosis to numeric, coerce errors to NaN
    if STRATIFY_COL in df.columns:
        df[STRATIFY_COL] = pd.to_numeric(df[STRATIFY_COL], errors="coerce")

    # Exclude rows where sip_diagnosis == 99 (incomplete data)
    df = df[df[STRATIFY_COL] != 99].copy()
    print(f"  After exclusion (99 removed): {len(df)} rows")

    return df
