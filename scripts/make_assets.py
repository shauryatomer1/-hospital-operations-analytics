#!/usr/bin/env python3
"""
Builds assets/ : ER diagram (PostgreSQL), star-schema diagram (Power BI) and five data-driven REFERENCE PAGES.
The reference pages are rendered with matplotlib from the same star-schema CSVs the Power BI model uses.
They are NOT Power BI screenshots - they show what each page should contain / roughly look like.
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PBI, OUT = ROOT / "data" / "processed" / "powerbi", ROOT / "assets"
(OUT / "reference_pages").mkdir(parents=True, exist_ok=True)
BLUE, TEAL, GREY, DARK, LIGHT = "#1F5FA8", "#1A9E9A", "#B8C2CC", "#1B2A3A", "#F4F7FA"
GREEN, AMBER, RED = "#2E8B57", "#E6A117", "#C0392B"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": GREY, "axes.labelcolor": DARK, "xtick.color": DARK, "ytick.color": DARK,
                     "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left", "font.size": 8})
NOTE = "Python-rendered reference page from the project data - NOT a Power BI screenshot"


# ------------------------------------------------------------------ ER diagrams
def box(ax, x, y, w, title, cols, color):
    h = 0.34 + 0.26 * len(cols)
    ax.add_patch(FancyBboxPatch((x, y - h), w, h, boxstyle="round,pad=0.02", fc="white", ec=color, lw=1.6))
    ax.add_patch(FancyBboxPatch((x, y - 0.34), w, 0.34, boxstyle="round,pad=0.02", fc=color, ec=color))
    ax.text(x + w / 2, y - 0.17, title, ha="center", va="center", color="white", fontweight="bold", fontsize=9)
    for i, c in enumerate(cols):
        ax.text(x + 0.1, y - 0.34 - 0.26 * (i + 0.6), c, fontsize=7.2, va="center", color=DARK)
    return dict(x=x, y=y, w=w, h=h)


def link(ax, a, b, label="1 : *", dashed=False, rad=0.0):
    p = (a["x"] + a["w"] / 2, a["y"] - a["h"] / 2); q = (b["x"] + b["w"] / 2, b["y"] - b["h"] / 2)
    ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="-", color=GREY if not dashed else AMBER, lw=1.4, ls="--" if dashed else "-", connectionstyle=f"arc3,rad={rad}"), zorder=0)
    if label:
        ax.text(p[0] + 0.3 * (q[0] - p[0]), p[1] + 0.3 * (q[1] - p[1]), label, fontsize=7, color=DARK, bbox=dict(fc="white", ec="none", pad=0.3), zorder=0.5)


def er_postgres():
    fig, ax = plt.subplots(figsize=(15, 9)); ax.set_xlim(0, 15); ax.set_ylim(-9.9, 0.5); ax.axis("off")
    d = box(ax, 0.3, 0, 3.4, "departments", ["PK department_id", "department_name", "department_category", "department_capacity"], BLUE)
    dr = box(ax, 5.3, 0, 3.4, "doctors", ["PK doctor_id", "FK department_id", "doctor_name", "specialization", "employment_type", "shift"], BLUE)
    b = box(ax, 10.3, 0, 3.4, "beds", ["PK bed_id", "FK department_id", "bed_type", "bed_status (snapshot)"], BLUE)
    p = box(ax, 0.3, -3.5, 3.4, "patients", ["PK patient_id", "age", "gender", "city", "patient_type", "registration_date"], TEAL)
    a = box(ax, 5.3, -3.2, 3.9, "admissions", ["PK admission_id", "FK patient_id", "FK department_id", "FK doctor_id", "FK bed_id (null if cancelled)",
            "admission_date / discharge_date", "admission_type / admission_status", "diagnosis_category / discharge_type"], TEAL)
    e = box(ax, 10.3, -3.4, 4.2, "emergency_visits", ["PK emergency_visit_id", "FK patient_id", "FK department_id", "FK admission_id (null)",
            "arrival / consultation / disposition datetime", "triage_level, disposition_type"], TEAL)
    da = box(ax, 0.3, -7.2, 3.6, "doctor_activity", ["PK activity_id", "FK doctor_id", "activity_date", "scheduled_hours", "patient_consultation_hours", "patients_attended"], GREY)
    r = box(ax, 5.3, -7.0, 4.3, "readmissions", ["PK readmission_id", "FK patient_id", "FK original_admission_id", "FK readmission_admission_id (unique)", "days_between_admissions"], GREY)
    for t in [(d, dr, "1:*"), (d, b, "1:*", 0.35), (d, a, "1:*"), (dr, a, "1:*"), (b, a, "1:0..*"), (p, a, "1:*"), (p, e, "1:*"),
                    (a, e, "1:0..1"), (dr, da, "1:*"), (a, r, "1:*"), (p, r, "1:*")]:
        link(ax, t[0], t[1], t[2], rad=(t[3] if len(t) > 3 else 0.0))
    ax.set_title("PostgreSQL schema `hospital` - entity relationship diagram", loc="left", fontsize=13)
    fig.savefig(OUT / "er_diagram.png", dpi=150, bbox_inches="tight"); plt.close(fig)


def star():
    fig, ax = plt.subplots(figsize=(15, 9)); ax.set_xlim(0, 15); ax.set_ylim(-9, 0.5); ax.axis("off")
    dd = box(ax, 5.8, 0, 3.4, "DimDate", ["PK Date  (marked date table)", "Year / Quarter / Month", "YearMonth, DayName", "IsWeekend", "InReportingWindow"], BLUE)
    dp = box(ax, 0.2, -2.8, 3.2, "DimPatients", ["PK PatientID", "Age, AgeGroup", "Gender, City", "PatientType", "RegistrationDate"], BLUE)
    dep = box(ax, 0.2, -6.8, 3.2, "DimDepartments", ["PK DepartmentID", "DepartmentName", "DepartmentCategory", "DepartmentCapacity", "StaffedBeds"], BLUE)
    dc = box(ax, 11.6, -6.8, 3.2, "DimDoctors", ["PK DoctorID", "DoctorName", "Specialization", "EmploymentType, Shift"], BLUE)
    bd = box(ax, 11.6, -2.8, 3.2, "DimBeds", ["PK BedID", "FK DepartmentID", "BedType", "BedStatus, IsStaffed"], BLUE)
    fa = box(ax, 4.0, -3.0, 3.6, "FactAdmissions", ["PK AdmissionID", "AdmissionDate (active -> DimDate)", "DischargeDate (inactive)", "PatientID / DepartmentID / DoctorID", "BedType, LOSDays, BedReleaseDate",
            "IsAdmission / IsCompleted / IsCancelled", "IsReadmissionEligible, Readmitted30d"], TEAL)
    fe = box(ax, 8.0, -3.0, 3.3, "FactEmergencyVisits", ["PK EmergencyVisitID", "ArrivalDate (active -> DimDate)", "PatientID / DepartmentID", "TriageLevel, ArrivalHour", "WaitMinutes, TurnaroundMinutes", "IsLWBS, IsAdmitted"], TEAL)
    fda = box(ax, 8.0, -6.9, 3.3, "FactDoctorActivity", ["PK ActivityID", "ActivityDate (active -> DimDate)", "DoctorID / DepartmentID", "ScheduledHours", "ConsultationHours, PatientsAttended"], TEAL)
    fr = box(ax, 4.0, -6.9, 3.6, "FactReadmissions", ["PK ReadmissionID", "ReadmitAdmissionDate (active)", "IndexDischargeDate (inactive)", "IndexDepartmentID (active)", "ReadmitDepartmentID (inactive)", "DaysBetweenAdmissions"], TEAL)
    for x, y in [(dd, fa), (dd, fe), (dd, fda), (dd, fr), (dp, fa), (dp, fe), (dp, fr), (dep, fa), (dep, fe), (dep, fda), (dep, fr), (dep, bd), (dc, fa), (dc, fda)]:
        link(ax, x, y, None)
    ax.text(0.2, -8.7, "All relationships are one-to-many, single direction (dimension -> fact). Inactive (USERELATIONSHIP): DimDate -> FactAdmissions[DischargeDate], DimDate -> FactReadmissions[IndexDischargeDate], DimDepartments -> FactReadmissions[ReadmitDepartmentID].", fontsize=8, color=DARK)
    ax.set_title("Power BI star schema - 4 facts, 5 dimensions, single-direction 1:* relationships", loc="left", fontsize=12)
    fig.savefig(OUT / "star_schema_diagram.png", dpi=150, bbox_inches="tight"); plt.close(fig)


# ------------------------------------------------------------------ reference pages
def load():
    f = lambda n, **k: pd.read_csv(PBI / f"{n}.csv", **k)
    A = f("FactAdmissions", parse_dates=["AdmissionDate", "DischargeDate", "BedReleaseDate"])
    return dict(A=A, E=f("FactEmergencyVisits", parse_dates=["ArrivalDate"]), D=f("FactDoctorActivity", parse_dates=["ActivityDate"]),
                R=f("FactReadmissions"), dep=f("DimDepartments"), bed=f("DimBeds"), doc=f("DimDoctors"))


def census(A, bed, dep):
    days = pd.date_range("2023-01-01", "2025-12-31")
    occ = A[A.IsAdmission]
    frames = []
    for did, g in occ.groupby("DepartmentID"):
        ad, rl = g.AdmissionDate.values.astype("datetime64[D]"), g.BedReleaseDate.values.astype("datetime64[D]")
        d64 = days.values.astype("datetime64[D]")
        c = ((ad[None, :] <= d64[:, None]) & (rl[None, :] > d64[:, None])).sum(axis=1)
        frames.append(pd.DataFrame({"Date": days, "DepartmentID": did, "Occupied": c}))
    c = pd.concat(frames)
    st = bed[bed.IsStaffed].groupby("DepartmentID").size().rename("Staffed")
    c = c.join(st, on="DepartmentID"); c["Dept"] = c.DepartmentID.map(dep.set_index("DepartmentID").DepartmentName)
    return c


def frame(title, subtitle, n):
    fig = plt.figure(figsize=(15, 8.4), facecolor=LIGHT)
    fig.text(0.03, 0.955, title, fontsize=17, fontweight="bold", color=DARK)
    fig.text(0.03, 0.925, subtitle, fontsize=9.5, color="#51606F")
    fig.text(0.97, 0.955, "REFERENCE PAGE %d / 5" % n, ha="right", fontsize=9, color=BLUE, fontweight="bold")
    fig.text(0.97, 0.025, NOTE, ha="right", fontsize=7.5, color="#7A8794", style="italic")
    return fig


def kpis(fig, items, y=0.80):
    w = 0.94 / len(items)
    for i, (lab, val, sub) in enumerate(items):
        ax = fig.add_axes([0.03 + i * w, y, w - 0.012, 0.095]); ax.axis("off")
        ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.06", fc="white", ec="#DDE4EA", transform=ax.transAxes))
        ax.text(0.06, 0.74, lab, fontsize=8, color="#51606F", transform=ax.transAxes)
        ax.text(0.06, 0.30, val, fontsize=17, fontweight="bold", color=DARK, transform=ax.transAxes)
        ax.text(0.96, 0.30, sub, fontsize=7.5, color="#51606F", ha="right", transform=ax.transAxes)


def panel(fig, rect, title):
    ax = fig.add_axes(rect, facecolor="white"); ax.set_title(title, pad=8)
    ax.yaxis.grid(True, color="#EEF2F5"); ax.set_axisbelow(True); return ax


def bar_band(v, hi=.85, crit=.95):
    return [RED if x >= crit else AMBER if x >= hi else GREEN for x in v]


def pages():
    d = load(); A, E, D, R, dep, bed = d["A"], d["E"], d["D"], d["R"], d["dep"], d["bed"]
    dname = dep.set_index("DepartmentID").DepartmentName
    ER = E[E.InReportingWindow]; DA = D[D.InReportingWindow]
    cen = census(A, bed, dep)
    short = lambda s: s.replace("Obstetrics & Gynecology", "OB/GYN").replace("Critical Care (ICU)", "ICU").replace("General ", "Gen. ")
    adm = A[A.IsAdmission & A.InReportingWindow]; dis = A[A.IsCompleted & (A.DischargeDate >= "2023-01-01")]
    el = A[A.IsReadmissionEligible & A.FollowupComplete & (A.DischargeDate >= "2023-01-01")]
    Ar = A[A.InReportingWindow]
    bor_all = cen.Occupied.sum() / cen.Staffed.sum()
    # ---- page 1
    fig = frame("Hospital Operations - Executive Overview", "Jan 2023 - Dec 2025  |  all departments  |  all admission types", 1)
    kpis(fig, [("Total Admissions", f"{len(adm):,}", ""), ("Total Discharges", f"{len(dis):,}", ""), ("Unique Patients", f"{adm.PatientID.nunique():,}", ""),
               ("ALOS (days)", f"{dis.LOSDays.mean():.2f}", "completed"), ("Bed Occupancy", f"{bor_all:.1%}", "illustrative bands"),
               ("30-Day Readmission", f"{el.Readmitted30d.mean():.1%}", f"n={len(el):,}")])
    m = adm.groupby(adm.AdmissionDate.dt.to_period("M")).size(); mdis = dis.groupby(dis.DischargeDate.dt.to_period("M")).size()
    ax = panel(fig, [0.04, 0.42, 0.40, 0.33], "Monthly admissions vs discharges")
    ax.plot(m.index.to_timestamp(), m.values, color=BLUE, lw=2, label="Admissions"); ax.plot(mdis.index.to_timestamp(), mdis.values, color=TEAL, lw=2, label="Discharges"); ax.legend(frameon=False, loc="lower right")
    ax = panel(fig, [0.52, 0.42, 0.20, 0.33], "Admissions by department")
    v = adm.groupby("DepartmentID").size().sort_values(); ax.barh([short(dname[i]) for i in v.index], v.values, color=BLUE)
    ax = panel(fig, [0.79, 0.42, 0.18, 0.33], "Admission type")
    t = adm.AdmissionType.value_counts(); ax.pie(t.values, labels=t.index, colors=[BLUE, TEAL, GREY], autopct="%1.0f%%", textprops={"fontsize": 8}, wedgeprops=dict(width=.45, edgecolor="white"))
    mo = cen.groupby(cen.Date.dt.to_period("M")).apply(lambda g: g.Occupied.sum() / g.Staffed.sum())
    ax = panel(fig, [0.04, 0.07, 0.40, 0.27], "Bed occupancy trend (occupied / staffed bed-days)")
    ax.plot(mo.index.to_timestamp(), mo.values, color=BLUE, lw=2); ax.axhline(.85, color=AMBER, ls="--", lw=1); ax.text(mo.index.to_timestamp()[0], .855, "illustrative High 85%", fontsize=7, color=AMBER); ax.set_ylim(.5, .95)
    w = ER.groupby(ER.ArrivalDate.dt.to_period("M")).WaitMinutes.agg(["mean", "median"])
    ax = panel(fig, [0.52, 0.07, 0.45, 0.27], "ED waiting time - arrival to consultation (min)")
    ax.plot(w.index.to_timestamp(), w["mean"], color=BLUE, lw=2, label="Mean"); ax.plot(w.index.to_timestamp(), w["median"], color=TEAL, lw=2, label="Median"); ax.legend(frameon=False); ax.set_ylim(30, 70)
    fig.savefig(OUT / "reference_pages" / "page1_executive_overview.png", dpi=130); fig.savefig(OUT / "dashboard_preview.png", dpi=130); plt.close(fig)

    # ---- page 2
    fig = frame("Patient Admission & Discharge Analysis", "Audience: Operations Manager  |  drilldown Year > Quarter > Month > Day in Power BI", 2)
    kpis(fig, [("Avg Daily Admissions", f"{len(adm) / 1096:.1f}", ""), ("Emergency Admission %", f"{(adm.AdmissionType == 'Emergency').mean():.1%}", ""),
               ("Cancelled Requests", f"{Ar.IsCancelled.sum():,}", f"{Ar.IsCancelled.mean():.1%}"), ("Open Stays at Snapshot", f"{A.IsOpenStay.sum()}", "excluded from ALOS")])
    dly = adm.groupby("AdmissionDate").size().reindex(pd.date_range("2023-01-01", "2025-12-31"), fill_value=0)
    ax = panel(fig, [0.04, 0.42, 0.45, 0.33], "Daily admissions (grey) and 7-day average")
    ax.plot(dly.index, dly.values, color=GREY, lw=.6); ax.plot(dly.index, dly.rolling(7).mean(), color=BLUE, lw=1.8)
    wk = adm.groupby(adm.AdmissionDate.dt.dayofweek)["AdmissionType"].value_counts().unstack().reindex(range(7))
    ax = panel(fig, [0.56, 0.42, 0.40, 0.33], "Weekday demand by admission type")
    b = np.zeros(7)
    for col, c in zip(["Emergency", "Elective", "Referral"], [BLUE, TEAL, GREY]):
        ax.bar(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], wk[col].values, bottom=b, color=c, label=col, edgecolor="white", lw=1); b += wk[col].values
    ax.legend(frameon=False, ncol=3)
    ax = panel(fig, [0.10, 0.07, 0.22, 0.28], "ALOS by department (completed stays)")
    v = dis.groupby("DepartmentID").LOSDays.mean().sort_values(); ax.barh([short(dname[i]) for i in v.index], v.values, color=TEAL)
    ax = panel(fig, [0.45, 0.07, 0.22, 0.28], "Discharge type")
    v = dis.DischargeType.value_counts().sort_values(); ax.barh(v.index.str.replace("Discharged ", "").str.replace("Another ", ""), v.values, color=BLUE)
    ag = adm.merge(pd.read_csv(PBI / "DimPatients.csv")[["PatientID", "AgeGroup"]], on="PatientID").AgeGroup.value_counts().reindex(["0-14", "15-29", "30-44", "45-59", "60-74", "75+"])
    ax = panel(fig, [0.72, 0.07, 0.25, 0.28], "Age-group distribution"); ax.bar(ag.index, ag.values, color=BLUE)
    fig.savefig(OUT / "reference_pages" / "page2_admissions_discharges.png", dpi=130); plt.close(fig)

    # ---- page 3
    fig = frame("Bed Occupancy & Resource Utilisation", "Occupied bed-days / staffed bed-days (interval based)  |  thresholds ILLUSTRATIVE: amber >= 85%, red >= 95%", 3)
    st = bed[bed.IsStaffed]
    kpis(fig, [("Staffed Beds", f"{len(st)}", f"of {len(bed)} physical"), ("Avg Daily Census", f"{cen.groupby('Date').Occupied.sum().mean():.1f}", "occupied beds"),
               ("Avg Available Beds", f"{len(st) - cen.groupby('Date').Occupied.sum().mean():.1f}", ""), ("Bed Occupancy", f"{bor_all:.1%}", "")])
    by = cen.groupby("Dept").apply(lambda g: g.Occupied.sum() / g.Staffed.sum()).sort_values()
    ax = panel(fig, [0.09, 0.42, 0.25, 0.33], "Occupancy by department"); ax.barh([short(i) for i in by.index], by.values, color=bar_band(by.values)); ax.set_xlim(0, 1)
    for i, x in enumerate(by.values): ax.text(x + .01, i, f"{x:.0%}", va="center", fontsize=7.5)
    h = cen.groupby([cen.Date.dt.month, "Dept"]).apply(lambda g: g.Occupied.sum() / g.Staffed.sum()).unstack().T
    ax = fig.add_axes([0.42, 0.42, 0.34, 0.33]); im = ax.imshow(h.values, cmap="Blues", aspect="auto", vmin=.4, vmax=1)
    ax.set_yticks(range(len(h))); ax.set_yticklabels([short(i) for i in h.index], fontsize=7); ax.set_xticks(range(12)); ax.set_xticklabels(list("JFMAMJJASOND"), fontsize=7); ax.set_title("Seasonal occupancy heat-map", loc="left", fontweight="bold", fontsize=10)
    ax = panel(fig, [0.82, 0.42, 0.15, 0.33], "Bed types (staffed)"); v = st.BedType.value_counts().sort_values(); ax.barh(v.index, v.values, color=TEAL)
    daily = cen.groupby("Date").apply(lambda g: g.Occupied.sum() / g.Staffed.sum())
    ax = panel(fig, [0.04, 0.07, 0.60, 0.27], "Daily hospital occupancy"); ax.plot(daily.index, daily.values, color=BLUE, lw=.9); ax.axhline(.85, color=AMBER, ls="--", lw=1); ax.set_ylim(.4, 1)
    pct = cen.assign(hi=cen.Occupied / cen.Staffed >= .85).groupby("Dept").hi.mean().sort_values()
    ax = panel(fig, [0.71, 0.07, 0.26, 0.27], "% of days at High/Critical (>= 85%)"); ax.barh([short(i) for i in pct.index], pct.values, color=bar_band(pct.values, .5, .9)); ax.xaxis.set_major_formatter(lambda x, p: f"{x:.0%}")
    fig.savefig(OUT / "reference_pages" / "page3_bed_occupancy.png", dpi=130); plt.close(fig)

    # ---- page 4
    fig = frame("Department-wise Performance", "Context first: volume, efficiency, utilisation and outcomes side by side - no single metric defines 'poor performance'", 4)
    rate = el.groupby("DepartmentID").Readmitted30d.mean(); alos = dis.groupby("DepartmentID").LOSDays.mean()
    util = DA.groupby("DepartmentID").apply(lambda g: g.ConsultationHours.sum() / g.ScheduledHours.sum())
    ndoc = DA.groupby("DepartmentID").DoctorID.nunique(); bor = cen.groupby("DepartmentID").apply(lambda g: g.Occupied.sum() / g.Staffed.sum())
    vol = adm.groupby("DepartmentID").size()
    M = pd.DataFrame({"Admissions": vol, "Discharges": dis.groupby("DepartmentID").size(), "ALOS": alos, "Occupancy": bor, "Readmit30d": rate, "DoctorUtil": util, "Adm/Doctor": vol / ndoc}).dropna()
    M.index = [short(dname[i]) for i in M.index]
    ax = panel(fig, [0.10, 0.50, 0.22, 0.30], "Admissions vs discharges"); M2 = M[["Admissions", "Discharges"]].sort_values("Admissions"); y = np.arange(len(M2))
    ax.barh(y - .2, M2.Admissions, .4, color=BLUE, label="Admissions"); ax.barh(y + .2, M2.Discharges, .4, color=TEAL, label="Discharges"); ax.set_yticks(y); ax.set_yticklabels(M2.index); ax.legend(frameon=False)
    ax = panel(fig, [0.38, 0.50, 0.27, 0.30], "30-day readmission rate"); v = M.Readmit30d.sort_values(); ax.barh(v.index, v.values, color=BLUE); ax.xaxis.set_major_formatter(lambda x, p: f"{x:.0%}")
    ax = panel(fig, [0.72, 0.50, 0.25, 0.30], "Doctor utilisation"); v = M.DoctorUtil.sort_values(); ax.barh(v.index, v.values, color=bar_band(v.values, .85, .95)); ax.set_xlim(0, 1)
    ax = fig.add_axes([0.11, 0.04, 0.86, 0.36]); ax.axis("off"); ax.set_title("Department comparison matrix (colour = relative position within column, not a verdict)", loc="left", fontweight="bold", fontsize=10)
    cols = ["Admissions", "Discharges", "ALOS", "Occupancy", "Readmit30d", "DoctorUtil", "Adm/Doctor"]; Mx = M[cols].sort_values("Admissions", ascending=False)
    cell = [[f"{r.Admissions:,.0f}", f"{r.Discharges:,.0f}", f"{r.ALOS:.1f}", f"{r.Occupancy:.0%}", f"{r.Readmit30d:.1%}", f"{r.DoctorUtil:.0%}", f"{r['Adm/Doctor']:.0f}"] for _, r in Mx.iterrows()]
    colors = [[plt.cm.Blues(.1 + .5 * (Mx[c].rank(pct=True).loc[i])) for c in cols] for i in Mx.index]
    tb = ax.table(cellText=cell, rowLabels=Mx.index, colLabels=cols, cellColours=colors, loc="upper center", cellLoc="center"); tb.auto_set_font_size(False); tb.set_fontsize(8); tb.scale(1, 1.25)
    fig.savefig(OUT / "reference_pages" / "page4_department_performance.png", dpi=130); plt.close(fig)

    # ---- page 5
    fig = frame("Waiting Time & Patient Flow - Emergency Department", "Wait = arrival to consultation (Left-Without-Being-Seen excluded)  |  Turnaround = arrival to final disposition", 5)
    kpis(fig, [("Avg Wait (min)", f"{ER.WaitMinutes.mean():.1f}", ""), ("Median Wait (min)", f"{ER.WaitMinutes.median():.1f}", ""), ("Avg Turnaround (min)", f"{ER.TurnaroundMinutes.mean():.0f}", ""),
               ("ED Visits", f"{len(ER):,}", ""), ("LWBS Rate", f"{ER.IsLWBS.mean():.1%}", "")])
    h = ER.groupby("ArrivalHour").agg(v=("EmergencyVisitID", "size"), w=("WaitMinutes", "mean"))
    ax = panel(fig, [0.04, 0.42, 0.30, 0.33], "Arrivals by hour of day (amber = 17-21h peak)"); ax.bar(h.index, h.v, color=[AMBER if 17 <= i <= 21 else BLUE for i in h.index])
    t = ER.groupby("TriageLabel").WaitMinutes.mean(); tgt = ER.groupby("TriageLabel").TargetWaitMin.first()
    ax = panel(fig, [0.43, 0.42, 0.24, 0.33], "Avg wait by triage vs illustrative target"); y = np.arange(len(t)); ax.barh(y, t.values, color=BLUE); ax.scatter(tgt.values, y, color=AMBER, marker="|", s=300, zorder=3, label="target"); ax.set_yticks(y); ax.set_yticklabels(t.index, fontsize=7); ax.invert_yaxis(); ax.legend(frameon=False)
    dp = ER.groupby("DispositionType").size().sort_values(); ax = panel(fig, [0.74, 0.42, 0.23, 0.33], "Disposition"); ax.barh(dp.index.str.replace("Referred for Outpatient Follow-up", "Referred OPD").str.replace("Left Against Medical Advice", "LAMA").str.replace("Left Without Being Seen", "LWBS"), dp.values, color=TEAL)
    q = ER.groupby(ER.ArrivalDate.dt.to_period("Q")).WaitMinutes.mean(); ax = panel(fig, [0.04, 0.07, 0.30, 0.27], "Avg wait by quarter (min)"); ax.bar([str(i) for i in q.index], q.values, color=[AMBER if v > 55 else BLUE for v in q.values]); ax.tick_params(axis="x", rotation=60, labelsize=7)
    dw = ER.groupby(ER.ArrivalDate.dt.dayofweek).agg(v=("EmergencyVisitID", "size"), w=("WaitMinutes", "mean")); ax = panel(fig, [0.43, 0.07, 0.24, 0.27], "Avg wait (min) by hour of day"); hw = h.w; ax.plot(hw.index, hw.values, color=BLUE, lw=2); ax.set_ylim(0, 80)
    dd_ = ER.groupby("DepartmentID").WaitMinutes.mean().sort_values(); ax = panel(fig, [0.74, 0.07, 0.23, 0.27], "Avg wait by routed department"); ax.barh([short(dname[i]) for i in dd_.index], dd_.values, color=TEAL)
    fig.savefig(OUT / "reference_pages" / "page5_ed_waiting_flow.png", dpi=130); plt.close(fig)


if __name__ == "__main__":
    er_postgres(); star(); pages()
    for p in sorted(OUT.rglob("*.png")): print(p.relative_to(ROOT))
