#!/usr/bin/env python3
"""
Phase 3/11 - automated data validation (pandas implementation of the same rules as database/data_quality_checks.sql).

    python validate_data.py --data ../data/processed --report ../analysis/validation_report.md
    python validate_data.py --data ../data/raw            # prints results only (expected to show the injected defects)

Exit code is non-zero if any CRITICAL test fails.
"""
import argparse
import sys
from pathlib import Path
import pandas as pd

TABLES = ["patients", "admissions", "departments", "doctors", "beds", "emergency_visits",
          "doctor_activity", "readmissions"]
PK = {"patients": "patient_id", "admissions": "admission_id", "departments": "department_id", "doctors": "doctor_id",
      "beds": "bed_id", "emergency_visits": "emergency_visit_id", "doctor_activity": "activity_id",
      "readmissions": "readmission_id"}
CRITICAL_NOT_NULL = {
    "patients": ["patient_id", "age", "gender", "registration_date"],
    "admissions": ["admission_id", "patient_id", "admission_date", "admission_type", "department_id", "doctor_id",
                   "admission_status"],
    "emergency_visits": ["emergency_visit_id", "patient_id", "arrival_datetime", "triage_level",
                         "disposition_datetime", "disposition_type", "department_id"],
    "doctor_activity": ["activity_id", "doctor_id", "activity_date", "scheduled_hours"],
    "readmissions": ["readmission_id", "patient_id", "original_admission_id", "readmission_admission_id"],
    "beds": ["bed_id", "department_id", "bed_type", "bed_status"], "doctors": ["doctor_id", "department_id"],
    "departments": ["department_id", "department_name", "department_capacity"]}

REMEDIATION = {
    "pk": "Deduplicate on the primary key; investigate the source extract.",
    "null": "Reject/quarantine the record or back-fill from the source system.",
    "fk": "Add the missing parent record or quarantine orphans; never join orphans into KPIs.",
    "date": "Correct the entry error at source; clean_data.py swaps reversed dates and re-validates.",
    "logic": "Quarantine and log the record; fix generation/ETL rule.",
}


def main():
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(root / "data" / "processed"))
    ap.add_argument("--report", default=None)
    a = ap.parse_args()
    d = Path(a.data)
    T = {n: pd.read_csv(d / f"{n}.csv", dtype=str, keep_default_na=False) for n in TABLES}
    R = []

    def add(name, expected, actual, kind, critical=True, note="", ok=None):
        if ok is None:
            ok = (actual == expected) if not isinstance(expected, str) else (str(actual) == expected)
        R.append(dict(Test=name, Expected=expected, Actual=actual, Status="PASS" if ok else "FAIL",
                      Severity="Critical" if critical else "Warning", Remediation=REMEDIATION[kind] if not ok else note or "-"))

    # ---- PK duplicates + critical nulls
    for n in TABLES:
        add(f"{n}: duplicate primary keys ({PK[n]})", 0, int(T[n][PK[n]].duplicated().sum()), "pk")
    for n, cols in CRITICAL_NOT_NULL.items():
        add(f"{n}: nulls in critical fields", 0, int(sum((T[n][c] == "").sum() for c in cols)), "null")

    P, A, D, Dr, B, E, DA, RA = (T[k] for k in ["patients", "admissions", "departments", "doctors", "beds",
                                               "emergency_visits", "doctor_activity", "readmissions"])
    num = lambda s: pd.to_numeric(s.replace("", pd.NA))

    # ---- foreign keys
    def fk(child, col, parent_ids, label="", allow_blank=False):
        s = child[col]
        if allow_blank: s = s[s != ""]
        return int((~s.isin(parent_ids)).sum())
    add("admissions.patient_id -> patients", 0, fk(A, "patient_id", set(P.patient_id)), "fk")
    add("admissions.department_id -> departments", 0, fk(A, "department_id", set(D.department_id)), "fk")
    add("admissions.doctor_id -> doctors", 0, fk(A, "doctor_id", set(Dr.doctor_id)), "fk")
    add("admissions.bed_id -> beds (non-cancelled)", 0, fk(A[A.admission_status != "Cancelled"], "bed_id", set(B.bed_id)), "fk")
    add("doctors.department_id -> departments", 0, fk(Dr, "department_id", set(D.department_id)), "fk")
    add("beds.department_id -> departments", 0, fk(B, "department_id", set(D.department_id)), "fk")
    add("emergency_visits.patient_id -> patients", 0, fk(E, "patient_id", set(P.patient_id)), "fk")
    add("emergency_visits.department_id -> departments", 0, fk(E, "department_id", set(D.department_id)), "fk")
    add("emergency_visits.admission_id -> admissions", 0, fk(E, "admission_id", set(A.admission_id), "", True), "fk")
    add("doctor_activity.doctor_id -> doctors", 0, fk(DA, "doctor_id", set(Dr.doctor_id)), "fk")
    add("readmissions.patient_id -> patients", 0, fk(RA, "patient_id", set(P.patient_id)), "fk")
    add("readmissions.original_admission_id -> admissions", 0, fk(RA, "original_admission_id", set(A.admission_id)), "fk")
    add("readmissions.readmission_admission_id -> admissions", 0, fk(RA, "readmission_admission_id", set(A.admission_id)), "fk")

    # ---- domain checks
    age = num(P.age)
    add("patients: age outside 0-110", 0, int(((age < 0) | (age > 110)).sum()), "logic")
    add("patients: gender outside {Male,Female,Other}", 0, int((~P.gender.isin(["Male", "Female", "Other"])).sum()), "logic")
    add("patients: city with whitespace / inconsistent case", 0,
        int((P.city != P.city.str.strip().str.title()).sum()), "logic", critical=False)
    add("emergency_visits: triage_level outside 1-5", 0, int((~E.triage_level.isin(list("12345"))).sum()), "logic")
    add("admissions: unknown admission_type", 0, int((~A.admission_type.isin(["Emergency", "Elective", "Referral"])).sum()), "logic")
    add("admissions: blank diagnosis_category", 0, int((A.diagnosis_category == "").sum()), "null")
    n_un = int((A.diagnosis_category == "Unspecified").sum())
    add("admissions: 'Unspecified' diagnosis share <= 0.5% of rows", "<= 0.5%", f"{n_un} rows ({100 * n_un / len(A):.2f}%)", "null",
        critical=False, ok=(n_un / len(A) <= .005), note="Back-filled as 'Unspecified' by clean_data.py (documented, excluded from diagnosis mix)")

    # ---- admission dates / LOS
    Ad = pd.to_datetime(A.admission_date); Dd = pd.to_datetime(A.discharge_date.replace("", pd.NA))
    done = A.admission_status == "Discharged"
    add("admissions: discharge_date before admission_date", 0, int((Dd < Ad).sum()), "date")
    add("admissions: negative length of stay", 0, int(((Dd - Ad).dt.days < 0).sum()), "date")
    add("admissions: Discharged stay LOS < 1 or > 60 days", 0,
        int((((Dd - Ad).dt.days < 1) | ((Dd - Ad).dt.days > 60))[done].sum()), "logic")
    add("admissions: status/discharge consistency (Discharged needs date+type)", 0,
        int((done & ((A.discharge_date == "") | (A.discharge_type == ""))).sum()), "logic")
    add("admissions: Admitted/Cancelled rows carrying a discharge date/type", 0,
        int((~done & ((A.discharge_date != "") | (A.discharge_type != ""))).sum()), "logic")
    add("admissions: Cancelled rows with a bed / Non-cancelled without a bed", 0,
        int((((A.admission_status == "Cancelled") & (A.bed_id != "")) | ((A.admission_status != "Cancelled") & (A.bed_id == ""))).sum()), "logic")
    add("admissions: unknown admission_status", 0, int((~A.admission_status.isin(["Discharged", "Admitted", "Cancelled"])).sum()), "logic")
    reg = P.set_index("patient_id").registration_date
    add("admissions: admission before patient registration_date", 0,
        int((pd.to_datetime(A.patient_id.map(reg)) > Ad).sum()), "date")

    # ---- impossible bed / doctor assignments
    bed_dept = B.set_index("bed_id").department_id
    doc_dept = Dr.set_index("doctor_id").department_id
    nc = A[A.admission_status != "Cancelled"]
    add("admissions: bed belongs to a different department", 0, int((nc.bed_id.map(bed_dept) != nc.department_id).sum()), "logic")
    add("admissions: doctor belongs to a different department", 0, int((A.doctor_id.map(doc_dept) != A.department_id).sum()), "logic")
    bst = B.set_index("bed_id").bed_status
    add("admissions: allocated bed has status 'Closed'", 0, int((nc.bed_id.map(bst) == "Closed").sum()), "logic")
    add("beds: Occupied bed status without an open admission", 0,
        int(len(set(B[B.bed_status == "Occupied"].bed_id) - set(A[A.admission_status == "Admitted"].bed_id))), "logic")
    add("admissions: Admitted rows whose bed is not flagged Occupied", 0,
        int((A[A.admission_status == "Admitted"].bed_id.map(bst) != "Occupied").sum()), "logic")
    # overlapping stays in the same bed / same patient (half-open [admission, discharge))
    nc2 = nc.assign(s=pd.to_datetime(nc.admission_date), e=pd.to_datetime(nc.discharge_date.replace("", pd.NA)).fillna(pd.Timestamp("2100-01-01")))
    def overlaps(key):
        x = nc2.sort_values([key, "s"]).copy()
        x["prev_e"] = x.groupby(key)["e"].shift()
        return int((x["s"] < x["prev_e"]).sum())
    add("admissions: overlapping stays in the same bed (double-booked bed)", 0, overlaps("bed_id"), "logic")
    add("admissions: overlapping stays for the same patient", 0, overlaps("patient_id"), "logic")
    dead = nc[nc.discharge_type == "Deceased"].set_index("patient_id")
    dd_ = pd.to_datetime(dead.discharge_date)
    later = nc2.merge(dd_.rename("death"), left_on="patient_id", right_index=True)
    add("admissions: admissions after a patient's recorded death", 0, int((later.s > later.death).sum()), "logic")

    # ---- department capacity
    cap = D.set_index("department_id").department_capacity.astype(int)
    bc = B.groupby("department_id").size().reindex(cap.index).fillna(0).astype(int)
    add("departments: capacity <> number of physical beds", 0, int((cap != bc).sum()), "logic")

    # ---- emergency
    arr = pd.to_datetime(E.arrival_datetime); con = pd.to_datetime(E.consultation_datetime.replace("", pd.NA))
    dis = pd.to_datetime(E.disposition_datetime)
    add("emergency_visits: negative waiting time (consult < arrival)", 0, int((con < arr).sum()), "date")
    add("emergency_visits: disposition before consultation/arrival", 0, int(((dis < con) | (dis < arr)).sum()), "date")
    add("emergency_visits: missing consultation without LWBS disposition", 0,
        int(((E.consultation_datetime == "") & (E.disposition_type != "Left Without Being Seen")).sum()), "logic")
    add("emergency_visits: wait > 8 hours (outlier screen)", 0, int((((con - arr).dt.total_seconds() / 60) > 480).sum()), "logic", critical=False)
    adm_e = E[E.admission_id != ""]
    m = adm_e.merge(A, on="admission_id", suffixes=("_e", "_a"))
    add("emergency_visits: linked admission patient mismatch", 0, int((m.patient_id_e != m.patient_id_a).sum()), "logic")
    add("emergency_visits: linked admission is not type Emergency", 0, int((m.admission_type != "Emergency").sum()), "logic")
    add("emergency_visits: admission_date <> date of disposition", 0,
        int((pd.to_datetime(m.disposition_datetime).dt.normalize() != pd.to_datetime(m.admission_date)).sum()), "logic")
    add("emergency_visits: 'Admitted' without admission link or vice-versa", 0,
        int(((E.disposition_type == "Admitted") != (E.admission_id != "")).sum()), "logic")
    add("emergency_visits: one admission linked to >1 ED visit", 0, int(adm_e.admission_id.duplicated().sum()), "logic")

    # ---- doctor activity
    sh, ch, pa = num(DA.scheduled_hours), num(DA.patient_consultation_hours), num(DA.patients_attended)
    add("doctor_activity: consultation hours > scheduled hours", 0, int((ch > sh + 1e-9).sum()), "logic")
    add("doctor_activity: negative hours or patients", 0, int(((sh < 0) | (ch < 0) | (pa < 0)).sum()), "logic")
    add("doctor_activity: duplicate doctor-date rows", 0, int(DA.duplicated(["doctor_id", "activity_date"]).sum()), "pk")

    # ---- readmissions
    mm = RA.merge(A[["admission_id", "patient_id", "admission_date", "discharge_date", "admission_type", "admission_status"]]
                  .add_prefix("o_"), left_on="original_admission_id", right_on="o_admission_id")
    mm = mm.merge(A[["admission_id", "patient_id", "admission_date", "admission_type"]].add_prefix("r_"),
                  left_on="readmission_admission_id", right_on="r_admission_id")
    calc = (pd.to_datetime(mm.r_admission_date) - pd.to_datetime(mm.o_discharge_date)).dt.days
    add("readmissions: days_between <> readmission admission - original discharge", 0, int((calc != num(mm.days_between_admissions)).sum()), "logic")
    add("readmissions: days_between outside 0-90", 0, int(((num(mm.days_between_admissions) < 0) | (num(mm.days_between_admissions) > 90)).sum()), "logic")
    add("readmissions: patient differs between the two admissions", 0, int(((mm.patient_id != mm.o_patient_id) | (mm.patient_id != mm.r_patient_id)).sum()), "logic")
    add("readmissions: original index admission not Discharged", 0, int((mm.o_admission_status != "Discharged").sum()), "logic")
    add("readmissions: readmission is not an Emergency (unplanned) admission", 0, int((mm.r_admission_type != "Emergency").sum()), "logic")
    add("readmissions: original admission not before readmission", 0, int((pd.to_datetime(mm.o_admission_date) >= pd.to_datetime(mm.r_admission_date)).sum()), "logic")
    add("readmissions: same readmission admission referenced twice", 0, int(RA.readmission_admission_id.duplicated().sum()), "pk")

    res = pd.DataFrame(R)
    fails = res[res.Status == "FAIL"]
    crit = fails[fails.Severity == "Critical"]
    print(res[["Test", "Expected", "Actual", "Status", "Severity"]].to_string(index=False))
    print(f"\n{len(res)} tests | {int((res.Status == 'PASS').sum())} PASS | {len(fails)} FAIL | critical fails: {len(crit)}")
    if a.report:
        md = [f"# Data Validation Report\n",
              f"*Dataset validated:* `{d.as_posix().split('hospital-operations-analytics/')[-1]}`  ",
              f"*Result:* **{int((res.Status == 'PASS').sum())} / {len(res)} tests passed** · critical failures: **{len(crit)}**\n",
              "| # | Test | Expected | Actual | Status | Severity | Remediation |", "|---|------|----------|--------|--------|----------|-------------|"]
        for i, r in enumerate(res.itertuples(), 1):
            md.append(f"| {i} | {r.Test} | {r.Expected} | {r.Actual} | {'✅ PASS' if r.Status == 'PASS' else '❌ FAIL'} | {r.Severity} | {r.Remediation} |")
        Path(a.report).write_text("\n".join(md) + "\n", encoding="utf-8")
    sys.exit(1 if len(crit) else 0)


if __name__ == "__main__":
    main()
