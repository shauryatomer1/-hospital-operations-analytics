#!/usr/bin/env python3
"""
Phase 6 - KPI reconciliation.
Computes the core KPIs two independent ways and compares them:
  (A) PANDAS on the Power BI star-schema CSVs, written to mirror the DAX measures (filter-context logic),
  (B) SQL on the PostgreSQL base tables (not the views), so view logic is also tested.
Writes analysis/kpi_reconciliation.md and analysis/kpi_checkpoints.csv  (expected values to compare with the
Power BI cards after you build the report - see analysis/powerbi_verification.md for the verification inside Power BI Desktop).
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2

ROOT = Path(__file__).resolve().parent.parent
PBI = ROOT / "data" / "processed" / "powerbi"
SNAP = pd.Timestamp("2025-12-31")
SCOPES = {"All (2023-2025)": ("2023-01-01", "2025-12-31"), "2023": ("2023-01-01", "2023-12-31"),
          "2024": ("2024-01-01", "2024-12-31"), "2025": ("2025-01-01", "2025-12-31")}


def pandas_kpis(s, e):
    s, e = pd.Timestamp(s), pd.Timestamp(e)
    A = pd.read_csv(PBI / "FactAdmissions.csv", parse_dates=["AdmissionDate", "DischargeDate", "BedReleaseDate"])
    E = pd.read_csv(PBI / "FactEmergencyVisits.csv", parse_dates=["ArrivalDateTime", "ArrivalDate"])
    D = pd.read_csv(PBI / "FactDoctorActivity.csv", parse_dates=["ActivityDate"])
    B = pd.read_csv(PBI / "DimBeds.csv")
    days = (e - s).days + 1
    adm = A[A.IsAdmission & A.AdmissionDate.between(s, e)]
    dis = A[A.IsCompleted & A.DischargeDate.between(s, e)]
    # occupied bed-days: sum over days of count(AdmissionDate <= d < BedReleaseDate)   (DAX SUMX over DimDate)
    occ = A[A.IsAdmission]
    dates = pd.date_range(s, e)
    ad = occ.AdmissionDate.values.astype("datetime64[D]"); rl = occ.BedReleaseDate.values.astype("datetime64[D]")
    start_off = np.maximum(ad, np.datetime64(s.date())); end_off = np.minimum(rl, np.datetime64((e + pd.Timedelta(days=1)).date()))
    occupied = int(np.clip((end_off - start_off).astype(int), 0, None).sum())
    staffed = int(B.IsStaffed.sum()) * days
    el = A[A.IsReadmissionEligible & A.FollowupComplete & A.DischargeDate.between(s, e)]
    ev = E[E.ArrivalDate.between(s, e)]
    wait = ev.WaitMinutes.dropna()
    act = D[D.ActivityDate.between(s, e)]
    emerg = adm[adm.AdmissionType == "Emergency"]
    return {
        "Total Admissions": len(adm), "Total Unique Patients": adm.PatientID.nunique(), "Total Discharges": len(dis),
        "ALOS (days)": dis.LOSDays.mean(), "Bed Occupancy Rate": occupied / staffed, "Occupied Bed-Days": occupied,
        "Staffed Bed-Days": staffed, "Avg ED Wait (min)": wait.mean(), "Median ED Wait (min)": wait.median(),
        "ED Turnaround (min)": ev.TurnaroundMinutes.mean(), "30-Day Readmission Rate": el.Readmitted30d.mean(),
        "Eligible Discharges": len(el), "Doctor Utilization": act.ConsultationHours.sum() / act.ScheduledHours.sum(),
        "Avg Daily Admissions": len(adm) / days, "Emergency Admission %": len(emerg) / len(adm),
        "Patients per Doctor": adm.PatientID.nunique() / act.DoctorID.nunique(),
    }


SQL = {  # independent SQL on BASE tables (parameters: %(s)s, %(e)s)
    "Total Admissions": "SELECT COUNT(*) FROM admissions WHERE admission_status<>'Cancelled' AND admission_date BETWEEN %(s)s AND %(e)s",
    "Total Unique Patients": "SELECT COUNT(DISTINCT patient_id) FROM admissions WHERE admission_status<>'Cancelled' AND admission_date BETWEEN %(s)s AND %(e)s",
    "Total Discharges": "SELECT COUNT(*) FROM admissions WHERE admission_status='Discharged' AND discharge_date BETWEEN %(s)s AND %(e)s",
    "ALOS (days)": "SELECT AVG(discharge_date-admission_date) FROM admissions WHERE admission_status='Discharged' AND discharge_date BETWEEN %(s)s AND %(e)s",
    "Occupied Bed-Days": """SELECT COALESCE(SUM(GREATEST(0, LEAST(COALESCE(discharge_date, DATE '2026-01-01'), %(e)s::date + 1) - GREATEST(admission_date, %(s)s::date))),0)
                            FROM admissions WHERE admission_status<>'Cancelled'""",
    "Staffed Bed-Days": "SELECT (SELECT COUNT(*) FROM beds WHERE bed_status<>'Closed') * (%(e)s::date - %(s)s::date + 1)",
    "Bed Occupancy Rate": "SELECT SUM(occupied_beds)::numeric/SUM(staffed_beds) FROM fact_dept_daily_census WHERE census_date BETWEEN %(s)s AND %(e)s",
    "Avg ED Wait (min)": "SELECT AVG(EXTRACT(EPOCH FROM consultation_datetime-arrival_datetime)/60) FROM emergency_visits WHERE arrival_datetime::date BETWEEN %(s)s AND %(e)s",
    "Median ED Wait (min)": "SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM consultation_datetime-arrival_datetime)/60) FROM emergency_visits WHERE arrival_datetime::date BETWEEN %(s)s AND %(e)s",
    "ED Turnaround (min)": "SELECT AVG(EXTRACT(EPOCH FROM disposition_datetime-arrival_datetime)/60) FROM emergency_visits WHERE arrival_datetime::date BETWEEN %(s)s AND %(e)s",
    "30-Day Readmission Rate": """SELECT AVG((r.readmission_id IS NOT NULL AND r.days_between_admissions<=30)::int)::numeric
                                  FROM admissions a LEFT JOIN readmissions r ON r.original_admission_id=a.admission_id
                                  WHERE a.admission_status='Discharged' AND a.discharge_type NOT IN ('Deceased','Transferred to Another Facility')
                                    AND a.discharge_date + 30 <= DATE '2025-12-31' AND a.discharge_date BETWEEN %(s)s AND %(e)s""",
    "Eligible Discharges": """SELECT COUNT(*) FROM admissions a WHERE a.admission_status='Discharged'
                              AND a.discharge_type NOT IN ('Deceased','Transferred to Another Facility')
                              AND a.discharge_date + 30 <= DATE '2025-12-31' AND a.discharge_date BETWEEN %(s)s AND %(e)s""",
    "Doctor Utilization": "SELECT SUM(patient_consultation_hours)/SUM(scheduled_hours) FROM doctor_activity WHERE activity_date BETWEEN %(s)s AND %(e)s",
    "Avg Daily Admissions": "SELECT COUNT(*)::numeric/(%(e)s::date-%(s)s::date+1) FROM admissions WHERE admission_status<>'Cancelled' AND admission_date BETWEEN %(s)s AND %(e)s",
    "Emergency Admission %": "SELECT AVG((admission_type='Emergency')::int)::numeric FROM admissions WHERE admission_status<>'Cancelled' AND admission_date BETWEEN %(s)s AND %(e)s",
    "Patients per Doctor": """SELECT (SELECT COUNT(DISTINCT patient_id) FROM admissions WHERE admission_status<>'Cancelled' AND admission_date BETWEEN %(s)s AND %(e)s)::numeric
                              / (SELECT COUNT(DISTINCT doctor_id) FROM doctor_activity WHERE activity_date BETWEEN %(s)s AND %(e)s)""",
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn")
    ap.add_argument("--pgdata", default=str(ROOT / ".pgdata"))
    a = ap.parse_args()
    if a.dsn:
        conn = psycopg2.connect(a.dsn)
    else:
        import pgserver
        srv = pgserver.get_server(str(Path(a.pgdata).resolve()), cleanup_mode=None)
        conn = psycopg2.connect(re.sub(r"/[^/?]*(\?|$)", r"/hospital\1", srv.get_uri(), count=1))
    cur = conn.cursor(); cur.execute("SET search_path = hospital, public")
    rows, bad = [], 0
    for scope, (s, e) in SCOPES.items():
        pk = pandas_kpis(s, e)
        for k, v in pk.items():
            cur.execute(SQL[k], dict(s=s, e=e)); sv = cur.fetchone()[0]; sv = float(sv)
            ok = abs(sv - float(v)) <= max(1e-9, 1e-6 * abs(sv))
            bad += (not ok)
            rows.append(dict(Scope=scope, KPI=k, Pandas_DAX_logic=round(float(v), 6), SQL=round(sv, 6), Match="PASS" if ok else "FAIL"))
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "analysis" / "kpi_checkpoints.csv", index=False)
    md = ["# KPI Reconciliation: SQL vs DAX-logic (pandas)\n",
          "Independent recomputation of every core KPI. **SQL** = queries on the PostgreSQL *base tables*; **Pandas** = a line-by-line "
          "replica of the DAX measure logic running on the Power BI import CSVs (`data/processed/powerbi`).  "
          "The DAX itself was verified in the Power BI Desktop engine (64/64, `analysis/powerbi_verification.md`); in any rebuilt report "
          "compare each card to the `Pandas_DAX_logic` column below (same values as `analysis/kpi_checkpoints.csv`).\n",
          f"**Result: {(df.Match == 'PASS').sum()} / {len(df)} comparisons match** (tolerance 1e-6 relative).\n"]
    for scope in SCOPES:
        d = df[df.Scope == scope]
        md += [f"\n### Scope: {scope}\n", "| KPI | Pandas / DAX logic | SQL | Match |", "|---|---:|---:|:---:|"]
        md += [f"| {r.KPI} | {r.Pandas_DAX_logic:,.4f} | {r.SQL:,.4f} | {'✅' if r.Match == 'PASS' else '❌'} |" for r in d.itertuples()]
    (ROOT / "analysis" / "kpi_reconciliation.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(df[df.Scope == "All (2023-2025)"].to_string(index=False))
    print(f"\n{(df.Match == 'PASS').sum()}/{len(df)} match")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
