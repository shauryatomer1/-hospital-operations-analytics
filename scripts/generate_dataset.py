#!/usr/bin/env python3
"""
Synthetic hospital dataset generator  (Hospital Operations & Performance Analytics)

Design principle: this is a *simulation*, not independent random columns.
  * Beds are a finite resource. Every admission is placed into a physically free bed
    of its own department; if none is free, emergencies board in the ED (and are
    diverted after 2 days), elective/referral admissions are deferred or cancelled.
  * Emergency admissions originate from an ED visit (emergency_visits.admission_id).
  * Readmissions are generated from patient risk, and the readmissions table is
    DERIVED from the final admissions table, so it can never disagree with it.
  * Doctor workload is derived from the simulated census, admissions and ED volume.

Controlled, documented operational scenarios injected (synthetic, for analysis):
  S1 Monsoon/viral surge   2024-08-05..2024-09-25  (General Medicine, Pediatrics, ICU)
  S2 Respiratory surge     2025-01-06..2025-02-20  (Pulmonology, ICU, General Medicine, Cardiology)
  S3 OT maintenance        2024-03-11..2024-03-24  (elective Ortho/Surgery volume collapses, cancellations)
  S4 ED staffing gap       2024-09-01..2024-11-30  (ED waiting times x1.30)
  S5 Weekend discharge dip (Sat/Sun discharges pushed to Monday) -> Monday occupancy peaks
  S6 Shift-handover + evening ED peaks (14-16h and 18-22h)
  S7 Under-resourced GM / Pulmonology / Cardiology doctor pools vs. light Oncology / Neurology load

Usage:  python generate_dataset.py [--out ../data/raw] [--seed 42] [--clean-only]
Writes the RAW extract (with a small, documented set of injected data-entry defects).
clean_data.py produces data/processed from it.
"""
import argparse
import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

START = date(2023, 1, 1)
END = date(2025, 12, 31)          # data snapshot date
S_ORD, E_ORD = START.toordinal(), END.toordinal()
S_SIM = date(2022, 11, 15).toordinal()      # burn-in start so the hospital is not empty on 2023-01-01

# --------------------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------------------
# id, name, category, beds{type:n}, requests/day, ALOS, LOS sigma, mix(em,el,ref), season, readmit30,
# p_deceased, p_transfer, p_followup, p_lama, p_returning_patient, age(mean,sd), diag distribution
DEPTS = {
    1: dict(name="Emergency Medicine", cat="Emergency", beds={}, lam=0, alos=0, sig=0, mix=(1, 0, 0)),
    2: dict(name="General Medicine", cat="Medical", beds={"General Ward": 8, "Semi-Private": 5, "Private": 3},
            lam=2.55, alos=5.2, sig=.60, mix=(.72, .08, .20), season="monsoon", rd=.10, dead=.018, trf=.025,
            fu=.06, lama=.035, pret=.26, age=(52, 20),
            dx={"Infectious & Parasitic": 30, "Endocrine & Metabolic": 20, "Digestive": 15, "Respiratory": 12,
                "Genitourinary": 10, "Circulatory": 8, "Other": 5}),
    3: dict(name="Cardiology", cat="Medical", beds={"HDU": 4, "General Ward": 5, "Private": 3},
            lam=2.15, alos=4.3, sig=.55, mix=(.60, .15, .25), season="winter_mild", rd=.14, dead=.020, trf=.03,
            fu=.10, lama=.02, pret=.32, age=(62, 12),
            dx={"Circulatory": 92, "Endocrine & Metabolic": 4, "Other": 4}),
    4: dict(name="Orthopedics", cat="Surgical", beds={"General Ward": 6, "Semi-Private": 4, "Private": 2},
            lam=1.40, alos=6.0, sig=.55, mix=(.35, .50, .15), season="flat", rd=.035, dead=.004, trf=.015,
            fu=.12, lama=.012, pret=.07, age=(50, 22),
            dx={"Musculoskeletal": 55, "Injury & Poisoning": 45}),
    5: dict(name="General Surgery", cat="Surgical", beds={"General Ward": 7, "Semi-Private": 4, "Private": 3},
            lam=2.60, alos=3.8, sig=.60, mix=(.45, .45, .10), season="flat", rd=.04, dead=.008, trf=.02,
            fu=.10, lama=.015, pret=.10, age=(45, 17),
            dx={"Digestive": 45, "Genitourinary": 15, "Injury & Poisoning": 15, "Neoplasms": 10,
                "Endocrine & Metabolic": 5, "Other": 10}),
    6: dict(name="Pediatrics", cat="Maternal & Child", beds={"Pediatric Ward": 8, "Isolation": 2},
            lam=1.90, alos=3.4, sig=.50, mix=(.70, .10, .20), season="monsoon", rd=.045, dead=.004, trf=.02,
            fu=.04, lama=.02, pret=.15, age=(5, 4),
            dx={"Respiratory": 28, "Infectious & Parasitic": 30, "Digestive": 15, "Neonatal & Perinatal": 10,
                "Injury & Poisoning": 7, "Other": 10}),
    7: dict(name="Obstetrics & Gynecology", cat="Maternal & Child", beds={"Maternity": 6, "Semi-Private": 2, "Private": 2},
            lam=2.05, alos=3.2, sig=.35, mix=(.45, .40, .15), season="flat", rd=.03, dead=.001, trf=.01,
            fu=.02, lama=.008, pret=.12, age=(30, 8),
            dx={"Pregnancy & Childbirth": 78, "Genitourinary": 15, "Neoplasms": 3, "Other": 4}),
    8: dict(name="Neurology", cat="Medical", beds={"HDU": 2, "General Ward": 4, "Private": 2},
            lam=.92, alos=6.5, sig=.65, mix=(.55, .15, .30), season="flat", rd=.08, dead=.045, trf=.04,
            fu=.08, lama=.025, pret=.22, age=(58, 17),
            dx={"Nervous System": 85, "Circulatory": 15}),
    9: dict(name="Oncology", cat="Medical", beds={"General Ward": 4, "Semi-Private": 2, "Private": 2},
            lam=.82, alos=5.5, sig=.55, mix=(.15, .50, .35), season="flat", rd=.11, dead=.06, trf=.05,
            fu=.10, lama=.02, pret=.50, age=(58, 13),
            dx={"Neoplasms": 100}),
    10: dict(name="Pulmonology", cat="Medical", beds={"General Ward": 4, "Isolation": 2, "HDU": 2},
             lam=1.05, alos=6.0, sig=.55, mix=(.65, .10, .25), season="winter", rd=.15, dead=.035, trf=.025,
             fu=.07, lama=.03, pret=.35, age=(56, 18),
             dx={"Respiratory": 90, "Infectious & Parasitic": 10}),
    11: dict(name="Critical Care (ICU)", cat="Critical Care", beds={"ICU": 8},
             lam=1.08, alos=6.5, sig=.80, mix=(.80, 0, .20), season="mixed", rd=.06, dead=.16, trf=.06,
             fu=.03, lama=.02, pret=.18, age=(60, 17),
             dx={"Circulatory": 25, "Respiratory": 25, "Infectious & Parasitic": 22, "Injury & Poisoning": 10,
                 "Nervous System": 8, "Digestive": 5, "Other": 5}),
}
ADM_DEPTS = [d for d in DEPTS if d != 1]
LAM_SCALE = 0.80   # calibrates overall demand so mean occupancy sits in a realistic 70-75% band
for _k in ADM_DEPTS:
    DEPTS[_k]['lam'] *= LAM_SCALE

SEASON = {  # month 1..12 multipliers for emergency demand (normalised to mean 1 in code)
    "flat": [1] * 12,
    "monsoon": [.90, .88, .90, .92, .95, 1.10, 1.22, 1.30, 1.20, 1.05, .90, .88],
    "winter": [1.28, 1.20, 1.00, .90, .85, .85, .90, .90, .92, .95, 1.10, 1.20],
    "winter_mild": [1.12, 1.08, 1.0, .95, .92, .92, .95, .95, .97, 1.0, 1.05, 1.10],
    "mixed": [1.1, 1.05, .98, .95, .92, 1.0, 1.05, 1.08, 1.02, .98, .97, 1.05],
}
EL_MONTH = [1, 1.02, 1.05, 1.0, .95, .95, .95, .98, 1.0, 1.0, .9, .85]
WD_EM = [1.12, 1.02, 1.0, 1.0, 1.03, .95, .88]
WD_EL = [1.15, 1.2, 1.2, 1.1, .95, .35, .0]
WD_RF = [1.2, 1.2, 1.15, 1.1, 1.0, .5, .0]
WD_ED = [1.14, 1.04, 1.0, .99, 1.02, .97, .92]
GROWTH = {2023: 1.0, 2024: 1.045, 2025: 1.08}

SURGES = [  # (start, end, {dept: multiplier on emergency demand})
    (date(2024, 8, 5), date(2024, 9, 25), {2: 1.35, 6: 1.35, 11: 1.25}),
    (date(2025, 1, 6), date(2025, 2, 20), {10: 1.35, 2: 1.15, 11: 1.25, 3: 1.10}),
]
OT_SHUTDOWN = (date(2024, 3, 11), date(2024, 3, 24), {4, 5})
ED_STAFF_GAP = (date(2024, 9, 1), date(2024, 11, 30))

ED_HOUR_W = np.array([2.0, 1.6, 1.3, 1.1, 1.0, 1.2, 1.8, 2.8, 4.2, 5.6, 6.4, 6.5, 6.0, 5.4, 5.0, 5.0, 5.4, 6.0,
                      6.8, 7.0, 6.6, 5.6, 4.2, 2.8])
ED_HOUR_W = ED_HOUR_W / ED_HOUR_W.sum()
ED_HOUR_WAIT = np.array([.70, .70, .70, .70, .70, .70, .80, .80, .95, .95, 1.15, 1.15, 1.15, 1.05, 1.30, 1.30,
                         1.10, 1.10, 1.40, 1.40, 1.40, 1.40, 1.10, .90])
ED_WD_WAIT = [1.15, 1.02, 1.0, .98, 1.03, 1.0, .95]
WAIT_MED = {1: 2.0, 2: 13.0, 3: 36.0, 4: 50.0, 5: 58.0}   # median minutes, before multipliers
TREAT_MED = {1: 150, 2: 170, 3: 140, 4: 70, 5: 45}

CITIES = ["Pune", "Pimpri-Chinchwad", "Satara", "Ahmednagar", "Nashik", "Kolhapur", "Solapur", "Mumbai"]
CITY_W = [.55, .18, .05, .05, .05, .04, .04, .04]
PTYPES = ["Insured", "Self-Pay", "Government Scheme", "Corporate"]
PTYPE_W = [.38, .32, .18, .12]

FIRST = ["Aarav", "Vivaan", "Aditya", "Arjun", "Rohan", "Kabir", "Ishaan", "Rahul", "Sameer", "Nikhil", "Vikram",
         "Anil", "Suresh", "Manish", "Rajesh", "Deepak", "Amit", "Karan", "Varun", "Harsh", "Priya", "Ananya",
         "Neha", "Sneha", "Pooja", "Kavita", "Meera", "Isha", "Anjali", "Divya", "Shruti", "Radhika", "Nandini",
         "Swati", "Aishwarya", "Tanvi", "Rekha", "Sunita", "Lata", "Mamta"]
LAST = ["Sharma", "Verma", "Kulkarni", "Deshmukh", "Patil", "Joshi", "Iyer", "Nair", "Menon", "Reddy", "Rao",
        "Gupta", "Mehta", "Shah", "Kapoor", "Bhatt", "Chopra", "Banerjee", "Chatterjee", "Das", "Pillai", "Naidu",
        "Jadhav", "Pawar", "More", "Gokhale", "Apte", "Bhide", "Phadke", "Ranade", "Sathe", "Tilak"]

DOCTORS_PER_DEPT = {1: 10, 2: 7, 3: 6, 4: 5, 5: 6, 6: 5, 7: 5, 8: 3, 9: 3, 10: 3, 11: 5}
SPECIALIZATION = {
    1: ["Emergency Medicine", "Trauma Care"], 2: ["Internal Medicine", "Infectious Diseases", "Endocrinology"],
    3: ["Interventional Cardiology", "Clinical Cardiology"], 4: ["Joint Replacement", "Trauma & Fracture Care"],
    5: ["Laparoscopic Surgery", "GI Surgery", "General Surgery"], 6: ["General Pediatrics", "Neonatology"],
    7: ["Obstetrics", "Gynecology"], 8: ["Stroke Neurology", "General Neurology"],
    9: ["Medical Oncology", "Surgical Oncology"], 10: ["Pulmonary Medicine", "Critical Respiratory Care"],
    11: ["Intensive Care Medicine", "Anesthesiology & Critical Care"]}
SEVEN_DAY = {1, 2, 3, 6, 7, 11}
NIGHT_DEPTS = {1, 2, 3, 7, 11}
# workload model (minutes): inpatient round/pt/day, admission work, ED consult, mean minutes per patient, target utilisation
WORK = {1: (0, 0, 24, 15, .90), 2: (18, 40, 20, 14, .88), 3: (20, 45, 25, 18, .84), 4: (14, 50, 20, 15, .72),
        5: (15, 55, 20, 16, .76), 6: (16, 35, 20, 14, .78), 7: (18, 60, 25, 20, .66), 8: (25, 45, 25, 22, .58),
        9: (25, 40, 0, 25, .52), 10: (18, 40, 20, 16, .80), 11: (100, 90, 0, 40, .86)}

TRIAGE_ADMITTED_P = [.07, .33, .50, .09, .01]
TRIAGE_NONADM_P = [.012, .09, .38, .36, .158]
NONADM_DISPO = {  # triage -> [(disposition, p)]
    1: [("Discharged Home", .35), ("Referred for Outpatient Follow-up", .05), ("Transferred", .35), ("Deceased", .25)],
    2: [("Discharged Home", .70), ("Referred for Outpatient Follow-up", .12), ("Transferred", .12),
        ("Left Against Medical Advice", .05), ("Deceased", .01)],
    3: [("Discharged Home", .78), ("Referred for Outpatient Follow-up", .13), ("Transferred", .03),
        ("Left Against Medical Advice", .06)],
    4: [("Discharged Home", .80), ("Referred for Outpatient Follow-up", .165), ("Transferred", .005),
        ("Left Against Medical Advice", .03)],
    5: [("Discharged Home", .75), ("Referred for Outpatient Follow-up", .23), ("Left Against Medical Advice", .02)]}
ED_DEPT_W = {1: .56, 2: .12, 4: .08, 5: .06, 6: .08, 3: .04, 8: .02, 10: .02, 7: .02}
ED_ADMIT_RATE = .26


def norm(a):
    a = np.array(a, dtype=float)
    return a / a.mean()


def build(seed=42):
    rng = np.random.default_rng(seed)

    # ---------------- departments / beds / doctors ----------------
    departments, beds = [], []
    bed_seq = 0
    for did, c in DEPTS.items():
        n = sum(c["beds"].values())
        departments.append(dict(department_id=f"D{did:02d}", department_name=c["name"],
                                department_category=c["cat"], department_capacity=n))
        for btype, k in c["beds"].items():
            for _ in range(k):
                bed_seq += 1
                beds.append(dict(bed_id=f"B{bed_seq:03d}", did=did, bed_type=btype, status="Available"))
    # closed (unstaffed) beds: never allocated
    closed_pick = {4: "Private", 8: "General Ward", 9: "Semi-Private", 10: "Isolation"}
    for did, bt in closed_pick.items():
        cand = [b for b in beds if b["did"] == did and b["bed_type"] == bt]
        cand[-1]["status"] = "Closed"
    for b in beds:
        b["free"] = S_SIM - 1
    dept_beds = {did: [b for b in beds if b["did"] == did and b["status"] != "Closed"] for did in DEPTS}
    staffed = [b for b in beds if b["status"] != "Closed"]

    # doctors
    doctors = []
    used_names = set()
    doc_seq = 0
    for did, n in DOCTORS_PER_DEPT.items():
        for i in range(n):
            while True:
                nm = f"Dr. {rng.choice(FIRST)} {rng.choice(LAST)}"
                if nm not in used_names:
                    used_names.add(nm)
                    break
            doc_seq += 1
            emp = rng.choice(["Full-Time", "Part-Time", "Visiting Consultant"], p=[.62, .23, .15])
            if i < max(2, n // 2):
                emp = "Full-Time"          # every department keeps a full-time core
            shifts = ["Morning", "Evening", "Rotational"] + (["Night"] if did in NIGHT_DEPTS else [])
            sh = rng.choice(shifts) if emp == "Full-Time" else rng.choice(["Morning", "Evening"])
            doctors.append(dict(doctor_id=f"DR{doc_seq:03d}", doctor_name=nm, did=did,
                                specialization=SPECIALIZATION[did][i % len(SPECIALIZATION[did])],
                                employment_type=emp, shift=sh, load_w=float(np.exp(rng.normal(0, .35)))))
    dept_docs = defaultdict(list)
    for d in doctors:
        dept_docs[d["did"]].append(d)

    # ---------------- patients ----------------
    P = dict(age=[], gender=[], city=[], ptype=[], reg=[], frail=[], free=[], dead=[], used=[])
    groups = {"kid": [], "adult": [], "f_repro": [], "f_adult": []}

    def add_patient(age, gender, reg_ord):
        pid = len(P["age"])
        P["age"].append(int(age)); P["gender"].append(gender)
        P["city"].append(str(rng.choice(CITIES, p=CITY_W))); P["ptype"].append(str(rng.choice(PTYPES, p=PTYPE_W)))
        P["reg"].append(int(reg_ord)); P["frail"].append(float(np.exp(rng.normal(0, .8))))
        P["free"].append(0); P["dead"].append(False); P["used"].append(False)
        groups["kid" if age < 15 else "adult"].append(pid)
        if gender == "Female" and age >= 18:
            groups["f_adult"].append(pid)
            if age <= 44:
                groups["f_repro"].append(pid)
        return pid

    def gender_draw(p_male=.5):
        r = rng.random()
        return "Other" if r < .003 else ("Male" if r < .003 + (1 - .003) * p_male else "Female")

    # pre-existing (registered before the window) patients
    for _ in range(500):
        add_patient(min(13, int(rng.gamma(1.3, 3.2))), gender_draw(.52), S_ORD - int(rng.integers(30, 3000)))
    for _ in range(3200):
        add_patient(int(np.clip(rng.normal(48, 20), 15, 95)), gender_draw(.5), S_ORD - int(rng.integers(30, 3000)))
    for _ in range(900):
        add_patient(int(np.clip(rng.normal(29, 5), 18, 44)), "Female", S_ORD - int(rng.integers(30, 3000)))

    def age_score(did, age):
        if did == 6:
            return 1.0
        m, s = DEPTS[did]["age"]
        return max(0.03, math.exp(-0.5 * ((age - m) / s) ** 2))

    def new_patient(did, grp, d_ord, p_male=.5):
        if grp == "kid":
            age, g = min(13, int(rng.gamma(1.3, 3.2))), gender_draw(.52)
        elif grp == "f_repro":
            age, g = int(np.clip(rng.normal(29, 5), 18, 44)), "Female"
        elif grp == "f_adult":
            m, s = (42, 14)
            age, g = int(np.clip(rng.normal(m, s), 18, 80)), "Female"
        else:
            m, s = DEPTS[did]["age"] if did in DEPTS and did != 6 else (48, 20)
            age, g = int(np.clip(rng.normal(m, s), 15, 95)), gender_draw(p_male)
        return add_patient(age, g, d_ord - int(rng.integers(0, 4)))

    def pick_patient(did, grp, d_ord, p_ret, p_male=.5):
        lst = groups[grp]
        if lst and rng.random() < p_ret:
            best, bs = None, -1
            for ci in rng.integers(0, len(lst), size=8):
                pid = lst[ci]
                if P["free"][pid] <= d_ord and P["reg"][pid] <= d_ord and not P["dead"][pid]:
                    s = P["frail"][pid] * age_score(did, P["age"][pid])
                    if s > bs:
                        best, bs = pid, s
            if best is not None:
                return best
        return new_patient(did, grp, d_ord, p_male)

    def group_for(did, dx):
        if did == 6:
            return "kid"
        if did == 7:
            return "f_repro" if dx == "Pregnancy & Childbirth" else "f_adult"
        kid_share = {5: .08, 11: .05, 10: .10, 4: .06, 8: .03, 2: .0}.get(did, 0)
        return "kid" if rng.random() < kid_share else "adult"

    # ---------------- bookkeeping ----------------
    adm, ed = [], []
    readmit_due = defaultdict(list)

    def sample_dx(did):
        d = DEPTS[did]["dx"]
        k, w = list(d), np.array(list(d.values()), float)
        return str(rng.choice(k, p=w / w.sum()))

    def choose_bed(did, d_ord, dx, kidpt):
        cand = [b for b in dept_beds[did] if b["free"] <= d_ord]
        if not cand:
            return None
        w = []
        for b in cand:
            t = b["bed_type"]
            base = {"Private": .8, "Semi-Private": 1.2, "General Ward": 2.0}.get(t, 1.0)
            if t == "Isolation":
                base = 6.0 if dx == "Infectious & Parasitic" else .15
            w.append(base)
        w = np.array(w); w /= w.sum()
        return cand[int(rng.choice(len(cand), p=w))]

    def doctor_for(did):
        ds = dept_docs[did]
        w = np.array([{"Full-Time": 1.0, "Part-Time": .5, "Visiting Consultant": .3}[d["employment_type"]] * d["load_w"]
                      for d in ds])
        return ds[int(rng.choice(len(ds), p=w / w.sum()))]["doctor_id"]

    def make_stay(did, atype, pid, a_ord, dx):
        """Draw LOS + discharge outcome, return (discharge_ord, discharge_type, deceased)."""
        c = DEPTS[did]
        r = rng.random()
        dead = r < c["dead"]
        lama = (not dead) and r < c["dead"] + c["lama"]
        trf = (not dead and not lama) and r < c["dead"] + c["lama"] + c["trf"]
        fu = (not dead and not lama and not trf) and r < c["dead"] + c["lama"] + c["trf"] + c["fu"]
        mu = math.log(c["alos"]) - c["sig"] ** 2 / 2
        los = rng.lognormal(mu, c["sig"])
        age = P["age"][pid]
        if age >= 70: los *= 1.2
        elif age < 15: los *= .85
        los *= {"Emergency": 1.1, "Elective": .9, "Referral": 1.0}[atype]
        if dead: los *= .8
        if lama: los *= .7
        if did == 7 and dx == "Pregnancy & Childbirth":
            los = rng.choice([2, 3, 3, 4, 4, 5], p=[.2, .3, .2, .15, .1, .05])
        los = int(min(60, max(1, round(los))))
        dis = a_ord + los
        wd = date.fromordinal(dis).weekday()
        if not dead and did != 11:                      # S5 weekend discharge dip
            if wd == 6 and rng.random() < .40: dis += 1
            elif wd == 5 and rng.random() < .22: dis += 2
        dt = ("Deceased" if dead else "Left Against Medical Advice" if lama else
              "Transferred to Another Facility" if trf else
              "Discharged Home with Follow-up" if fu else "Discharged Home")
        return dis, dt, dead

    def book(did, atype, pid, a_ord, bed, dx, ed_idx=None, ed_cancel=False):
        dis, dt, dead = make_stay(did, atype, pid, a_ord, dx)
        rec = dict(patient=pid, a_ord=a_ord, atype=atype, did=did, bed=bed["bed_id"], dx=dx,
                   doctor=doctor_for(did), dis_ord=dis, dis_type=dt)
        bed["free"] = dis
        P["free"][pid] = dis + 1
        P["used"][pid] = True
        if dead:
            P["dead"][pid] = True
        adm.append(rec)
        # readmission risk (only for stays that finish inside the window)
        if not dead and dt != "Transferred to Another Facility" and dis <= E_ORD:
            c = DEPTS[did]
            p = c["rd"]
            if dt == "Left Against Medical Advice": p *= 1.8
            if P["age"][pid] >= 65: p *= 1.25
            if dis - a_ord <= 1 and did in (2, 3, 10): p *= 1.15
            if date.fromordinal(dis).weekday() >= 5: p *= 1.15
            if rng.random() < p:
                gap = int(min(30, 1 + rng.gamma(1.6, 6.0)))
                tgt = did if rng.random() < .80 else (2 if rng.random() < .6 and did != 2 else 11 if did != 11 else 2)
                readmit_due[dis + gap].append((pid, tgt))
            elif rng.random() < p * .35:                 # late (31-90d) emergency return
                readmit_due[dis + int(rng.integers(31, 91))].append((pid, did))
        return len(adm) - 1

    def cancel_rec(did, atype, pid, a_ord, dx):
        adm.append(dict(patient=pid, a_ord=a_ord, atype=atype, did=did, bed=None, dx=dx, doctor=doctor_for(did),
                        dis_ord=None, dis_type=None, cancelled=True))

    # ---------------- ED helpers ----------------
    def surge_mult(d, did):
        m = 1.0
        for s, e, mm in SURGES:
            if s <= d <= e and did in mm:
                m *= mm[did]
        return m

    def ed_times(d, triage, occ_h, admitted):
        hour = int(rng.choice(24, p=ED_HOUR_W))
        arr = datetime(d.year, d.month, d.day, hour, int(rng.integers(0, 60)), int(rng.integers(0, 60)))
        mult = ED_HOUR_WAIT[hour] * ED_WD_WAIT[d.weekday()] * (1 + 1.6 * max(0, occ_h - .78))
        if ED_STAFF_GAP[0] <= d <= ED_STAFF_GAP[1]: mult *= 1.30
        wait = WAIT_MED[triage] * mult * rng.lognormal(0, .55 if triage > 1 else .8)
        wait = float(min(480, max(0.5, wait)))
        treat = TREAT_MED[triage] * (1.3 if admitted else 1.0) * rng.lognormal(0, .45)
        return arr, wait, float(treat), hour

    ed_rows = []

    def new_ed(d, pid, triage, dept_id, arr, wait, dispo, consult, dispo_dt, adm_idx=None):
        ed_rows.append(dict(patient=pid, arrival=arr, triage=triage, consult=consult, dispo_dt=dispo_dt,
                            dispo=dispo, did=dept_id, adm=adm_idx))

    # ---------------- main daily loop ----------------
    se = {k: norm(v) for k, v in SEASON.items()}
    wd_em, wd_el, wd_rf, wd_ed = norm(WD_EM), norm(WD_EL), norm(WD_RF), norm(WD_ED)
    base_em_total = sum(DEPTS[k]["lam"] * DEPTS[k]["mix"][0] for k in ADM_DEPTS)
    d_ord = S_SIM
    n_staffed = len(staffed)
    while d_ord <= E_ORD:
        d = date.fromordinal(d_ord)
        m, wd, g = d.month - 1, d.weekday(), GROWTH.get(d.year, 1.0)
        free_arr = np.array([b["free"] for b in staffed])
        occ_h = float((free_arr > d_ord).sum()) / n_staffed

        # ---- emergency requests
        ems = []   # (did, preset_pid)
        for (pid, tgt) in readmit_due.pop(d_ord, []):
            if P["free"][pid] <= d_ord and not P["dead"][pid]:
                ems.append((tgt, pid))
        exp_em = 0.0
        for did in ADM_DEPTS:
            c = DEPTS[did]
            lam = c["lam"] * c["mix"][0] * se[c["season"]][m] * wd_em[wd] * g * surge_mult(d, did)
            exp_em += lam
            for _ in range(rng.poisson(lam)):
                ems.append((did, None))
        # build ED timelines first, then allocate beds in order of decision time
        pend = []
        for did, preset in ems:
            tri = int(rng.choice([1, 2, 3, 4, 5], p=([.35, .50, .15, 0, 0] if did == 11 else TRIAGE_ADMITTED_P)))
            arr, wait, treat, hour = ed_times(d, tri, occ_h, True)
            consult = arr + timedelta(minutes=wait)
            decision = consult + timedelta(minutes=treat)
            pend.append((decision, did, preset, tri, arr, consult))
        pend.sort(key=lambda x: x[0])
        for decision, did, preset, tri, arr, consult in pend:
            dx = sample_dx(did)
            if preset is None:
                pid = pick_patient(did, group_for(did, dx), d_ord, min(.8, DEPTS[did]["pret"] * 1.5), .58 if did == 3 else .5)
            else:
                pid = preset
            dd = decision.date().toordinal()
            placed = None
            for delta in range(0, 3):
                if dd + delta > E_ORD:
                    break
                b = choose_bed(did, dd + delta, dx, False)
                if b is not None:
                    placed = (delta, b)
                    break
            if placed is None:       # diverted / transferred out
                dispo_dt = decision + timedelta(minutes=float(rng.uniform(60, 240)))
                new_ed(d, pid, tri, did, arr, 0, "Transferred", consult, dispo_dt)
                continue
            delta, b = placed
            a_ord = dd + delta
            if delta == 0:
                board = float(np.clip(70 * (1 + 2 * max(0, occ_h - .75)) * rng.lognormal(0, .6), 10, 600))
                dispo_dt = decision + timedelta(minutes=board)
                eod = datetime(decision.year, decision.month, decision.day, 23, 59)
                dispo_dt = min(dispo_dt, eod)
                if dispo_dt < decision: dispo_dt = decision
            else:
                day = date.fromordinal(a_ord)
                dispo_dt = datetime(day.year, day.month, day.day, int(rng.integers(7, 15)), int(rng.integers(0, 60)))
            ai = book(did, "Emergency", pid, a_ord, b, dx)
            new_ed(d, pid, tri, did, arr, 0, "Admitted", consult, dispo_dt, ai)

        # ---- non-admitted ED visits
        lam_na = 22.0 * (exp_em / base_em_total) * wd_ed[wd]
        n_na = rng.poisson(lam_na)
        for _ in range(n_na):
            tri = int(rng.choice([1, 2, 3, 4, 5], p=TRIAGE_NONADM_P))
            arr, wait, treat, hour = ed_times(d, tri, occ_h, False)
            kid = rng.random() < .22
            did_ed = 6 if (kid and rng.random() < .85) else 1 if kid else int(rng.choice(
                list(ED_DEPT_W), p=np.array(list(ED_DEPT_W.values())) / sum(ED_DEPT_W.values())))
            pid = pick_patient(did_ed if did_ed in DEPTS and did_ed != 1 else 2, "kid" if kid else "adult",
                               d_ord, .42)
            lw_p = 0 if tri <= 2 else min(.25, max(0.0, .008 + .0007 * (wait - 40)) * (1.5 if tri >= 4 else 1.0))
            if rng.random() < lw_p:
                dispo_dt = arr + timedelta(minutes=wait * float(rng.uniform(.6, 1.0)))
                new_ed(d, pid, tri, did_ed, arr, 0, "Left Without Being Seen", None, dispo_dt)
                P["used"][pid] = True
                continue
            opts = NONADM_DISPO[tri]
            names = [o[0] for o in opts]; ps = np.array([o[1] for o in opts]); ps /= ps.sum()
            dispo = str(rng.choice(names, p=ps))
            consult = arr + timedelta(minutes=wait)
            dispo_dt = consult + timedelta(minutes=treat)
            if dispo == "Deceased":
                P["dead"][pid] = True
            P["used"][pid] = True
            new_ed(d, pid, tri, did_ed, arr, 0, dispo, consult, dispo_dt)

        # ---- elective + referral
        direct = []
        for did in ADM_DEPTS:
            c = DEPTS[did]
            el = c["lam"] * c["mix"][1] * EL_MONTH[m] * wd_el[wd] * g
            if OT_SHUTDOWN[0] <= d <= OT_SHUTDOWN[1] and did in OT_SHUTDOWN[2]:
                el *= .35
            rf = c["lam"] * c["mix"][2] * wd_rf[wd] * g
            for _ in range(rng.poisson(el)): direct.append((did, "Elective"))
            for _ in range(rng.poisson(rf)): direct.append((did, "Referral"))
        rng.shuffle(direct)
        for did, atype in direct:
            dx = sample_dx(did)
            pid = pick_patient(did, group_for(did, dx), d_ord, min(.8, DEPTS[did]["pret"] * 1.5), .58 if did == 3 else .5)
            p_cancel = .04
            if OT_SHUTDOWN[0] <= d <= OT_SHUTDOWN[1] and did in OT_SHUTDOWN[2] and atype == "Elective":
                p_cancel = .40
            if rng.random() < p_cancel:
                cancel_rec(did, atype, pid, d_ord, dx)
                continue
            placed = None
            for delta in range(0, 8 if atype == "Elective" else 4):
                a = d_ord + delta
                if a > E_ORD: break
                if date.fromordinal(a).weekday() == 6: continue          # no Sunday elective/referral admissions
                if atype == "Elective" and date.fromordinal(a).weekday() == 5 and rng.random() < .6: continue
                b = choose_bed(did, a, dx, False)
                if b is not None:
                    placed = (a, b); break
            if placed is None:
                cancel_rec(did, atype, pid, d_ord, dx)     # cancelled / deferred out - no bed available
                continue
            book(did, atype, pid, placed[0], placed[1], dx)
        d_ord += 1

    # ======================================================================================
    # Assemble tables
    # ======================================================================================
    # ---- trim burn-in: keep activity inside the window + carry-over inpatients (admitted earlier, still in-house on START)
    def keep_adm(r):
        if r["a_ord"] >= S_ORD: return True
        return (not r.get("cancelled", False)) and (r["dis_ord"] is not None) and r["dis_ord"] > S_ORD
    keep_idx = {i for i, r in enumerate(adm) if keep_adm(r)}
    ed_rows = [r for r in ed_rows if r["arrival"].date() >= START or (r["adm"] is not None and r["adm"] in keep_idx)]
    adm_all = adm
    adm = [dict(r, _orig=i) for i, r in enumerate(adm_all) if i in keep_idx]
    A = pd.DataFrame(adm)
    A["cancelled"] = A.get("cancelled", False)
    A["cancelled"] = A["cancelled"].fillna(False).astype(bool)
    A["seq"] = A["_orig"]
    A = A.sort_values(["a_ord", "seq"]).reset_index(drop=True)
    A["admission_id"] = [f"ADM{i + 1:06d}" for i in range(len(A))]
    old2new = {int(s): i for s, i in zip(A["seq"], A["admission_id"])}

    # keep only patients with at least one encounter
    pat_used_ids = set(A["patient"]) | {r["patient"] for r in ed_rows}
    pidmap = {}
    patients = []
    for pid in sorted(pat_used_ids, key=lambda i: (P["reg"][i], i)):
        pidmap[pid] = f"P{len(patients) + 1:06d}"
        patients.append(dict(patient_id=pidmap[pid], age=P["age"][pid], gender=P["gender"][pid],
                             city=P["city"][pid], patient_type=P["ptype"][pid],
                             registration_date=date.fromordinal(P["reg"][pid]).isoformat()))
    patients = pd.DataFrame(patients)

    # admission status
    def status(r):
        if r["cancelled"]: return "Cancelled"
        return "Discharged" if r["dis_ord"] <= E_ORD else "Admitted"
    A["admission_status"] = A.apply(status, axis=1)
    open_mask = A["admission_status"] == "Admitted"
    A.loc[open_mask, "dis_ord"] = np.nan
    A.loc[open_mask, "dis_type"] = None
    admissions = pd.DataFrame({
        "admission_id": A["admission_id"],
        "patient_id": A["patient"].map(pidmap),
        "admission_date": A["a_ord"].map(lambda o: date.fromordinal(int(o)).isoformat()),
        "discharge_date": A["dis_ord"].map(lambda o: "" if pd.isna(o) else date.fromordinal(int(o)).isoformat()),
        "admission_type": A["atype"],
        "department_id": A["did"].map(lambda i: f"D{i:02d}"),
        "doctor_id": A["doctor"],
        "bed_id": A["bed"].fillna(""),
        "diagnosis_category": A["dx"],
        "admission_status": A["admission_status"],
        "discharge_type": A["dis_type"].fillna(""),
    })

    # emergency visits
    E = pd.DataFrame(ed_rows).sort_values("arrival").reset_index(drop=True)
    E["emergency_visit_id"] = [f"ED{i + 1:06d}" for i in range(len(E))]
    seq2adm = {int(s): a for s, a in old2new.items()}
    emergency = pd.DataFrame({
        "emergency_visit_id": E["emergency_visit_id"],
        "patient_id": E["patient"].map(pidmap),
        "arrival_datetime": E["arrival"].dt.strftime("%Y-%m-%d %H:%M:%S"),
        "triage_level": E["triage"],
        "consultation_datetime": E["consult"].map(lambda t: "" if pd.isna(t) else t.strftime("%Y-%m-%d %H:%M:%S")),
        "disposition_datetime": E["dispo_dt"].dt.strftime("%Y-%m-%d %H:%M:%S"),
        "disposition_type": E["dispo"],
        "department_id": E["did"].map(lambda i: f"D{i:02d}"),
        "admission_id": E["adm"].map(lambda s: "" if pd.isna(s) else seq2adm[int(s)]),
    })

    # readmissions - derived from the final admissions table
    B = admissions[admissions["admission_status"].isin(["Discharged", "Admitted"])].copy()
    B["a"] = pd.to_datetime(B["admission_date"]); B["dsc"] = pd.to_datetime(B["discharge_date"], errors="coerce")
    B = B.sort_values(["patient_id", "a", "admission_id"])
    B["prev_id"] = B.groupby("patient_id")["admission_id"].shift()
    B["prev_dsc"] = B.groupby("patient_id")["dsc"].shift()
    B["prev_stat"] = B.groupby("patient_id")["admission_status"].shift()
    B["gap"] = (B["a"] - B["prev_dsc"]).dt.days
    R = B[(B["prev_stat"] == "Discharged") & (B["admission_type"] == "Emergency") & B["gap"].between(0, 90)]
    R = R.sort_values(["a", "admission_id"]).reset_index(drop=True)
    readmissions = pd.DataFrame({
        "readmission_id": [f"RA{i + 1:05d}" for i in range(len(R))],
        "patient_id": R["patient_id"], "original_admission_id": R["prev_id"],
        "readmission_admission_id": R["admission_id"], "days_between_admissions": R["gap"].astype(int)})

    # beds - snapshot status at END
    occupied_beds = set(admissions.loc[admissions["admission_status"] == "Admitted", "bed_id"])
    maint_cand = [b for b in beds if b["status"] == "Available" and b["bed_id"] not in occupied_beds]
    for did in (2, 5, 6):
        c = [b for b in maint_cand if b["did"] == did]
        if c: c[0]["status"] = "Maintenance"
    for b in beds:
        if b["bed_id"] in occupied_beds: b["status"] = "Occupied"
    beds_df = pd.DataFrame([dict(bed_id=b["bed_id"], department_id=f"D{b['did']:02d}", bed_type=b["bed_type"],
                                 bed_status=b["status"]) for b in beds])
    docs_df = pd.DataFrame([dict(doctor_id=d["doctor_id"], doctor_name=d["doctor_name"],
                                 department_id=f"D{d['did']:02d}", specialization=d["specialization"],
                                 employment_type=d["employment_type"], shift=d["shift"]) for d in doctors])
    dept_df = pd.DataFrame(departments)

    # ---------------- doctor activity ----------------
    n_days = E_ORD - S_ORD + 1
    census = {did: np.zeros(n_days + 2) for did in ADM_DEPTS}
    newadm = {did: np.zeros(n_days + 1) for did in ADM_DEPTS}
    stay = A[~A["cancelled"]]
    for did, a, dsc in zip(stay["did"], stay["a_ord"], stay["dis_ord"]):
        e = E_ORD + 1 if pd.isna(dsc) else int(dsc)
        census[did][max(0, int(a) - S_ORD)] += 1
        census[did][min(e, E_ORD + 1) - S_ORD] -= 1
        if int(a) >= S_ORD: newadm[did][int(a) - S_ORD] += 1
    census = {k: np.cumsum(v)[:n_days] for k, v in census.items()}
    edcount = {did: np.zeros(n_days) for did in DEPTS}
    for did, t in zip(E["did"], E["arrival"]):
        if t.date() >= START: edcount[did][t.date().toordinal() - S_ORD] += 1

    # schedules
    sched = {}
    for d in doctors:
        did = d["did"]
        if d["employment_type"] == "Full-Time":
            off = int(rng.integers(0, 7)) if did in SEVEN_DAY else 6
            days, hrs = set(range(7)) - {off}, 8.0
            if did in SEVEN_DAY and False: pass
        elif d["employment_type"] == "Part-Time":
            days = set(rng.choice(7 if did in SEVEN_DAY else 6, size=3, replace=False).tolist()); hrs = 5.0
        else:
            days = set(rng.choice(6, size=2, replace=False).tolist()); hrs = 3.5
        sched[d["doctor_id"]] = (days, hrs)

    def sched_minutes_baseline(did):
        tot = 0.0
        for d in dept_docs[did]:
            days, hrs = sched[d["doctor_id"]]
            tot += len(days) / 7 * hrs * 0.95 * 60
        return tot

    rows = []
    act_id = 0
    for did in DEPTS:
        rnd, adm_m, ed_m, mpp, tgt = WORK[did]
        dd_docs = dept_docs[did]
        inp = (census[did] * rnd + newadm[did][:n_days] * adm_m) if did != 1 else np.zeros(n_days)
        work_base = inp + edcount[did] * ed_m
        base_sched = sched_minutes_baseline(did)
        fill = max(0.0, tgt * 1.40 * base_sched - float(work_base.mean()))
        # ED doctors see every ED visit routed to *any* department's ED team? keep own dept only
        for i in range(n_days):
            dte = date.fromordinal(S_ORD + i)
            wd = dte.weekday()
            on = []
            for d in dd_docs:
                days, hrs = sched[d["doctor_id"]]
                if wd in days and rng.random() > .05:
                    on.append((d, hrs))
            if not on:
                continue
            opd_f = [1.2, 1.1, 1.05, 1.0, 1.0, .7, .1][wd]
            total_min = work_base[i] + fill * opd_f
            tot_h = sum(h for _, h in on)
            for d, hrs in on:
                share = hrs / tot_h
                minutes = total_min * share * float(rng.lognormal(0, .22))
                cap = hrs * 60 * .97
                minutes = min(minutes, cap)
                ch = round(minutes / 60.0, 2)
                pts = int(round(minutes / mpp * float(rng.uniform(.92, 1.08)))) if minutes > 0 else 0
                if ch > 0 and pts == 0: pts = 1
                act_id += 1
                rows.append((f"ACT{act_id:06d}", d["doctor_id"], dte.isoformat(), hrs, ch, pts))
    activity = pd.DataFrame(rows, columns=["activity_id", "doctor_id", "activity_date", "scheduled_hours",
                                           "patient_consultation_hours", "patients_attended"])
    return dict(patients=patients, admissions=admissions, departments=dept_df, doctors=docs_df, beds=beds_df,
                emergency_visits=emergency, doctor_activity=activity, readmissions=readmissions)


def inject_defects(t, seed):
    """Inject a small, documented set of realistic data-entry defects into the RAW extract."""
    rng = np.random.default_rng(seed + 1)
    log = []
    t = {k: v.copy() for k, v in t.items()}
    p = t["patients"]
    idx = rng.choice(len(p), size=int(len(p) * .015), replace=False)
    m = {"Male": ["M", "male", "MALE"], "Female": ["F", "female", "FEMALE"]}
    for i in idx:
        g = p.at[i, "gender"]
        if g in m: p.at[i, "gender"] = rng.choice(m[g])
    log.append(("patients.gender", "non-standard gender codes (M/F/male/FEMALE)", len(idx)))
    idx = rng.choice(len(p), size=int(len(p) * .01), replace=False)
    for i in idx:
        c = p.at[i, "city"]
        p.at[i, "city"] = rng.choice([f" {c}", f"{c} ", c.upper(), c.lower()])
    log.append(("patients.city", "leading/trailing whitespace and inconsistent case in city", len(idx)))
    da = t["doctor_activity"]
    dup = da.sample(8, random_state=seed)
    t["doctor_activity"] = pd.concat([da, dup], ignore_index=True).sample(frac=1, random_state=seed).reset_index(drop=True)
    log.append(("doctor_activity", "exact duplicate rows (same activity_id)", 8))
    ed = t["emergency_visits"]
    cand = ed[(ed["disposition_type"].isin(["Discharged Home", "Referred for Outpatient Follow-up"])) &
              (ed["consultation_datetime"] != "")]
    sel = cand.sample(6, random_state=seed).index
    for i in sel:
        arr = pd.Timestamp(ed.at[i, "arrival_datetime"])
        ed.at[i, "consultation_datetime"] = (arr - pd.Timedelta(minutes=int(rng.integers(5, 60)))).strftime("%Y-%m-%d %H:%M:%S")
    log.append(("emergency_visits.consultation_datetime", "consultation timestamp earlier than arrival (negative wait)", 6))
    a = t["admissions"]
    used = set(t["emergency_visits"]["admission_id"]) | set(t["readmissions"]["original_admission_id"]) | \
        set(t["readmissions"]["readmission_admission_id"])
    cand = a[(a["admission_status"] == "Discharged") & (~a["admission_id"].isin(used)) &
             (a["admission_date"] != a["discharge_date"])]
    sel = cand.sample(4, random_state=seed).index
    for i in sel:
        a.at[i, "admission_date"], a.at[i, "discharge_date"] = a.at[i, "discharge_date"], a.at[i, "admission_date"]
    log.append(("admissions.admission_date/discharge_date", "dates entered in swapped order (discharge < admission)", 4))
    cand = a[(a["admission_status"] == "Discharged")].sample(15, random_state=seed + 2).index
    a.loc[cand, "diagnosis_category"] = ""
    log.append(("admissions.diagnosis_category", "missing diagnosis category on discharged admissions", 15))
    return t, log


def main():
    ap = argparse.ArgumentParser()
    root = Path(__file__).resolve().parent.parent
    ap.add_argument("--out", default=str(root / "data" / "raw"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--clean-only", action="store_true", help="write defect-free tables (for debugging)")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tables = build(a.seed)
    defects = []
    if not a.clean_only:
        tables, defects = inject_defects(tables, a.seed)
    for name, df in tables.items():
        df.to_csv(out / f"{name}.csv", index=False)
    meta = dict(seed=a.seed, window=[START.isoformat(), END.isoformat()],
                rows={k: int(len(v)) for k, v in tables.items()},
                injected_defects=[dict(field=f, issue=i, rows=n) for f, i, n in defects],
                scenarios=["S1 monsoon/viral surge 2024-08-05..2024-09-25", "S2 respiratory surge 2025-01-06..2025-02-20",
                           "S3 OT maintenance 2024-03-11..2024-03-24", "S4 ED staffing gap 2024-09-01..2024-11-30",
                           "S5 weekend discharge dip", "S6 ED handover/evening peaks", "S7 uneven doctor pools"])
    (out / "generation_metadata.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta["rows"], indent=1))


if __name__ == "__main__":
    main()
