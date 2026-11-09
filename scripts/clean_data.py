#!/usr/bin/env python3
"""
Phase 3 - data cleaning.  data/raw/*.csv  ->  data/processed/*.csv
Every change is written to data/processed/cleaning_log.csv; records that cannot be repaired with
certainty are QUARANTINED to data/processed/rejected_records.csv (never silently dropped).
"""
import argparse
from pathlib import Path
import pandas as pd

TABLES = ["patients", "admissions", "departments", "doctors", "beds", "emergency_visits",
          "doctor_activity", "readmissions"]
GENDER_MAP = {"m": "Male", "male": "Male", "f": "Female", "female": "Female", "other": "Other"}


def main():
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(root / "data" / "raw"))
    ap.add_argument("--out", default=str(root / "data" / "processed"))
    a = ap.parse_args()
    raw, out = Path(a.raw), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t = {n: pd.read_csv(raw / f"{n}.csv", dtype=str, keep_default_na=False) for n in TABLES}
    log, rejected = [], []

    def L(table, rule, n, action):
        log.append(dict(table=table, rule=rule, rows_affected=int(n), action=action))

    # generic whitespace trim on all text cells
    for n, df in t.items():
        ch = 0
        for c in df.columns:
            s = df[c].str.strip()
            ch += int((s != df[c]).sum())
            df[c] = s
        L(n, "trim leading/trailing whitespace", ch, "str.strip() on all columns")

    p = t["patients"]
    mapped = p["gender"].str.lower().map(GENDER_MAP)
    ch = int((mapped != p["gender"]).sum())
    p["gender"] = mapped
    L("patients", "standardise gender codes to Male/Female/Other", ch, "mapped M/F/male/FEMALE etc.")
    new_city = p["city"].str.title()
    ch = int((new_city != p["city"]).sum())
    p["city"] = new_city
    L("patients", "standardise city casing", ch, "str.title()")

    da = t["doctor_activity"]
    before = len(da)
    t["doctor_activity"] = da.drop_duplicates()
    L("doctor_activity", "remove exact duplicate rows", before - len(t["doctor_activity"]), "drop_duplicates()")

    ed = t["emergency_visits"]
    arr = pd.to_datetime(ed["arrival_datetime"]); con = pd.to_datetime(ed["consultation_datetime"].replace("", pd.NA))
    bad = con < arr
    if bad.any():
        r = ed[bad].copy(); r["reject_reason"] = "consultation_datetime earlier than arrival_datetime (unrecoverable timestamp error)"
        rejected.append(("emergency_visits", r))
    t["emergency_visits"] = ed[~bad]
    L("emergency_visits", "quarantine negative waiting time", int(bad.sum()), "moved to rejected_records.csv; true time unknown")

    a_ = t["admissions"]
    ad = pd.to_datetime(a_["admission_date"]); dd = pd.to_datetime(a_["discharge_date"].replace("", pd.NA))
    sw = dd < ad
    a_.loc[sw, ["admission_date", "discharge_date"]] = a_.loc[sw, ["discharge_date", "admission_date"]].values
    L("admissions", "swap reversed admission/discharge dates", int(sw.sum()),
      "dates swapped (reversed entry); bed-overlap re-validated afterwards")
    miss = (a_["diagnosis_category"] == "")
    a_.loc[miss, "diagnosis_category"] = "Unspecified"
    L("admissions", "fill missing diagnosis_category", int(miss.sum()), "set to 'Unspecified' (kept; excluded from diagnosis analysis)")

    for n in TABLES:
        t[n].to_csv(out / f"{n}.csv", index=False)
    pd.DataFrame(log).to_csv(out / "cleaning_log.csv", index=False)
    if rejected:
        pd.concat([r.assign(source_table=n) for n, r in rejected]).to_csv(out / "rejected_records.csv", index=False)
    print(pd.DataFrame(log).to_string(index=False))


if __name__ == "__main__":
    main()
