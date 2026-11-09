#!/usr/bin/env python3
"""
Phase 7 - builds the Power BI star-schema CSVs from data/processed  ->  data/processed/powerbi/
Facts : FactAdmissions, FactEmergencyVisits, FactDoctorActivity, FactReadmissions
Dims  : DimPatients, DimDepartments, DimDoctors, DimBeds, DimDate
Only deterministic, row-level derived columns are added here (flags, minutes, keys). All KPIs stay in DAX.
"""
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC, OUT = ROOT / "data" / "processed", ROOT / "data" / "processed" / "powerbi"
REPORT_START, DATA_END = pd.Timestamp("2023-01-01"), pd.Timestamp("2025-12-31")
TRIAGE = {1: ("1 - Resuscitation", 5), 2: ("2 - Emergent", 15), 3: ("3 - Urgent", 30), 4: ("4 - Less Urgent", 60),
          5: ("5 - Non-Urgent", 120)}   # ILLUSTRATIVE targets (see KPI dictionary)


def age_group(a):
    return np.select([a < 15, a < 30, a < 45, a < 60, a < 75], ["0-14", "15-29", "30-44", "45-59", "60-74"], "75+")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rd = lambda n, **k: pd.read_csv(SRC / f"{n}.csv", **k)
    pat, adm, dep, doc, bed = rd("patients"), rd("admissions"), rd("departments"), rd("doctors"), rd("beds")
    ed, act, rea = rd("emergency_visits"), rd("doctor_activity"), rd("readmissions")

    # ---------------- DimDate
    d = pd.date_range("2022-11-01", "2025-12-31")
    dim_date = pd.DataFrame({
        "Date": d, "DateKey": d.strftime("%Y%m%d").astype(int), "Year": d.year, "Quarter": d.quarter,
        "QuarterLabel": [f"Q{q} {y}" for q, y in zip(d.quarter, d.year)], "MonthNumber": d.month,
        "MonthName": d.strftime("%B"), "MonthShort": d.strftime("%b"), "YearMonth": d.strftime("%Y-%m"),
        "YearMonthSort": (d.year * 100 + d.month), "MonthStart": d.to_period("M").start_time,
        "WeekStart": (d - pd.to_timedelta(d.day_of_week, unit="D")), "ISOWeek": d.isocalendar().week.values,
        "DayOfMonth": d.day, "DayOfWeekNumber": d.day_of_week + 1, "DayName": d.strftime("%A"), "DayShort": d.strftime("%a"),
        "IsWeekend": (d.day_of_week >= 5), "InReportingWindow": (d >= REPORT_START)})
    dim_date.to_csv(OUT / "DimDate.csv", index=False, date_format="%Y-%m-%d")

    # ---------------- Dimensions
    p = pat.rename(columns=lambda c: "".join(w.title() for w in c.split("_")))
    p = p.rename(columns={"PatientId": "PatientID"})
    p.insert(2, "AgeGroup", age_group(pat["age"].values))
    p.to_csv(OUT / "DimPatients.csv", index=False)

    staffed = bed[bed.bed_status != "Closed"].groupby("department_id").size()
    dd = dep.copy()
    dd["staffed_beds"] = dd.department_id.map(staffed).fillna(0).astype(int)
    dd["has_inpatient_beds"] = dd.department_capacity > 0
    dd.columns = ["DepartmentID", "DepartmentName", "DepartmentCategory", "DepartmentCapacity", "StaffedBeds", "HasInpatientBeds"]
    dd.to_csv(OUT / "DimDepartments.csv", index=False)

    doc.columns = ["DoctorID", "DoctorName", "DepartmentID", "Specialization", "EmploymentType", "Shift"]
    doc.to_csv(OUT / "DimDoctors.csv", index=False)
    bd = bed.copy()
    bd["is_staffed"] = bd.bed_status != "Closed"
    bd.columns = ["BedID", "DepartmentID", "BedType", "BedStatus", "IsStaffed"]
    bd.to_csv(OUT / "DimBeds.csv", index=False)

    # ---------------- FactAdmissions
    a = adm.copy()
    ad, dc = pd.to_datetime(a.admission_date), pd.to_datetime(a.discharge_date)
    a["is_completed"] = a.admission_status == "Discharged"
    a["is_cancelled"] = a.admission_status == "Cancelled"
    a["is_open_stay"] = a.admission_status == "Admitted"
    a["is_admission"] = ~a["is_cancelled"]
    a["los_days"] = np.where(a.is_completed, (dc - ad).dt.days, np.nan)
    a["bed_release_date"] = np.where(a.is_cancelled, pd.NaT, dc.fillna(DATA_END + pd.Timedelta(days=1)))
    a["bed_release_date"] = pd.to_datetime(a["bed_release_date"]).dt.strftime("%Y-%m-%d")
    a.loc[a.is_cancelled, "bed_release_date"] = ""
    a["in_reporting_window"] = ad >= REPORT_START
    a["admission_seq"] = a[~a.is_cancelled].assign(_d=ad).sort_values(["patient_id", "_d", "admission_id"]) \
        .groupby("patient_id").cumcount() + 1
    # readmission flags live on the INDEX admission so the rate never needs a cross-fact join
    elig = a.is_completed & ~a.discharge_type.isin(["Deceased", "Transferred to Another Facility"])
    a["is_readmission_eligible"] = elig
    a["followup_complete"] = elig & (dc + pd.Timedelta(days=30) <= DATA_END)
    r30 = set(rea[rea.days_between_admissions <= 30].original_admission_id)
    a["readmitted_30d"] = a.admission_id.isin(r30)
    a["is_unplanned_readmission_30d"] = a.admission_id.isin(set(rea[rea.days_between_admissions <= 30].readmission_admission_id))
    a["bed_type"] = a.bed_id.map(bed.set_index("bed_id").bed_type)
    a["from_ed"] = a.admission_id.isin(set(ed.admission_id.dropna()))
    cols = {"admission_id": "AdmissionID", "patient_id": "PatientID", "admission_date": "AdmissionDate", "discharge_date": "DischargeDate",
            "admission_type": "AdmissionType", "department_id": "DepartmentID", "doctor_id": "DoctorID", "bed_id": "BedID",
            "diagnosis_category": "DiagnosisCategory", "admission_status": "AdmissionStatus", "discharge_type": "DischargeType",
            "is_completed": "IsCompleted", "is_cancelled": "IsCancelled", "is_open_stay": "IsOpenStay", "is_admission": "IsAdmission",
            "los_days": "LOSDays", "bed_release_date": "BedReleaseDate", "in_reporting_window": "InReportingWindow",
            "admission_seq": "AdmissionSeq", "is_readmission_eligible": "IsReadmissionEligible", "followup_complete": "FollowupComplete",
            "bed_type": "BedType", "readmitted_30d": "Readmitted30d", "is_unplanned_readmission_30d": "IsUnplannedReadmission30d", "from_ed": "FromED"}
    fa = a[list(cols)].rename(columns=cols)
    fa["LOSDays"] = fa["LOSDays"].astype("Int64"); fa["AdmissionSeq"] = fa["AdmissionSeq"].astype("Int64")
    fa.to_csv(OUT / "FactAdmissions.csv", index=False)

    # ---------------- FactEmergencyVisits
    e = ed.copy()
    arr = pd.to_datetime(e.arrival_datetime); con = pd.to_datetime(e.consultation_datetime); dis = pd.to_datetime(e.disposition_datetime)
    e["arrival_date"] = arr.dt.strftime("%Y-%m-%d")
    e["arrival_hour"] = arr.dt.hour
    e["triage_label"] = e.triage_level.map(lambda t: TRIAGE[t][0])
    e["target_wait_min"] = e.triage_level.map(lambda t: TRIAGE[t][1])
    e["wait_minutes"] = ((con - arr).dt.total_seconds() / 60).round(4)
    e["turnaround_minutes"] = ((dis - arr).dt.total_seconds() / 60).round(4)
    e["consult_to_disposition_minutes"] = ((dis - con).dt.total_seconds() / 60).round(4)
    e["is_lwbs"] = e.disposition_type == "Left Without Being Seen"
    e["is_admitted"] = e.disposition_type == "Admitted"
    e["met_wait_target"] = np.where(e.wait_minutes.notna(), e.wait_minutes <= e.target_wait_min, np.nan)
    e["in_reporting_window"] = arr >= REPORT_START
    ecols = {"emergency_visit_id": "EmergencyVisitID", "patient_id": "PatientID", "arrival_datetime": "ArrivalDateTime",
             "arrival_date": "ArrivalDate", "arrival_hour": "ArrivalHour", "triage_level": "TriageLevel", "triage_label": "TriageLabel",
             "target_wait_min": "TargetWaitMin", "consultation_datetime": "ConsultationDateTime", "disposition_datetime": "DispositionDateTime",
             "disposition_type": "DispositionType", "department_id": "DepartmentID", "admission_id": "AdmissionID",
             "wait_minutes": "WaitMinutes", "turnaround_minutes": "TurnaroundMinutes",
             "consult_to_disposition_minutes": "ConsultToDispositionMinutes", "is_lwbs": "IsLWBS", "is_admitted": "IsAdmitted",
             "met_wait_target": "MetWaitTarget", "in_reporting_window": "InReportingWindow"}
    fe = e[list(ecols)].rename(columns=ecols)
    fe["MetWaitTarget"] = fe["MetWaitTarget"].astype("Int64")
    fe.to_csv(OUT / "FactEmergencyVisits.csv", index=False)

    # ---------------- FactDoctorActivity
    t = act.copy(); t.insert(2, "department_id", t.doctor_id.map(doc.set_index("DoctorID").DepartmentID))
    t["in_reporting_window"] = pd.to_datetime(t.activity_date) >= REPORT_START
    t.columns = ["ActivityID", "DoctorID", "DepartmentID", "ActivityDate", "ScheduledHours", "ConsultationHours", "PatientsAttended", "InReportingWindow"]
    t.to_csv(OUT / "FactDoctorActivity.csv", index=False)

    # ---------------- FactReadmissions
    amap = adm.set_index("admission_id")
    r = rea.copy()
    r["index_department_id"] = r.original_admission_id.map(amap.department_id)
    r["readmit_department_id"] = r.readmission_admission_id.map(amap.department_id)
    r["index_discharge_date"] = r.original_admission_id.map(amap.discharge_date)
    r["readmit_admission_date"] = r.readmission_admission_id.map(amap.admission_date)
    r["within_30_days"] = r.days_between_admissions <= 30
    r.columns = ["ReadmissionID", "PatientID", "OriginalAdmissionID", "ReadmissionAdmissionID", "DaysBetweenAdmissions",
                 "IndexDepartmentID", "ReadmitDepartmentID", "IndexDischargeDate", "ReadmitAdmissionDate", "Within30Days"]
    r.to_csv(OUT / "FactReadmissions.csv", index=False)

    for f in sorted(OUT.glob("*.csv")):
        print(f"{f.name:<28}{sum(1 for _ in open(f, encoding='utf-8')) - 1:>8,} rows")


if __name__ == "__main__":
    main()
