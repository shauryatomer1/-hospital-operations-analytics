# Data Dictionary

All data is **synthetic** (seed 42; `scripts/generate_dataset.py`). Window: 2023-01-01 to 2025-12-31 (snapshot date 2025-12-31). Row counts below are for `data/processed` (after cleaning).
`data/raw` holds the same tables with a small, documented set of injected data-entry defects (see `analysis/validation_report.md`).

**Simulation logic (why the relationships hold):** beds are a finite resource - every admission is placed in a physically free bed of its own department; emergency admissions originate from an ED visit; readmissions are derived from the final admissions table; doctor workload derives from simulated census/admissions/ED volume. **Burn-in:** the simulation started 2022-11-15 so the hospital is not empty on 1 Jan 2023; ~60 carry-over inpatients admitted in Nov-Dec 2022 are kept (they occupy beds on 1 Jan 2023) and are excluded from volume KPIs by the *reporting window* flag.

Primary keys = **PK**, foreign keys = **FK**. "Null?" = whether blank values are valid.

## departments (11 rows)
| Column | Type | Null? | Meaning |
|---|---|---|---|
| department_id | CHAR(3) **PK** | No | `D01`..`D11` |
| department_name | text | No | e.g. General Medicine, Cardiology, Critical Care (ICU). D01 *Emergency Medicine* has **no inpatient beds** (capacity 0): ED trolleys are not tracked |
| department_category | text | No | Emergency, Medical, Surgical, Maternal & Child, Critical Care |
| department_capacity | int | No | Sanctioned **physical** inpatient beds; must equal the number of rows in `beds` for the department (DQ-25). Staffed capacity (excl. Closed beds) is smaller |

## patients (27,007 rows)
| Column | Type | Null? | Meaning |
|---|---|---|---|
| patient_id | **PK** `P000001` | No | Every patient has >= 1 admission *or* ED visit in the dataset |
| age | smallint | No | Age in years **at first encounter in the dataset** (static; used for age groups; later-year drift ignored) |
| gender | text | No | Male / Female / Other (raw data had M/F/male/FEMALE variants - standardised) |
| city | text | No | Residence city (8 cities of a fictional catchment: Pune, Pimpri-Chinchwad, Satara, Ahmednagar, Nashik, Kolhapur, Solapur, Mumbai) |
| patient_type | text | No | **Payer category** (assumption): Insured, Self-Pay, Government Scheme, Corporate |
| registration_date | date | No | First registration with the hospital. Never later than the patient's first encounter. Pre-2023 dates = known patients |

## admissions (16,314 rows)
| Column | Type | Null? | Meaning |
|---|---|---|---|
| admission_id | **PK** `ADM000001` | No | Ordered by admission date |
| patient_id | FK -> patients | No | |
| admission_date | date | No | Date the bed was occupied (for *Cancelled*: the scheduled date) |
| discharge_date | date | **Yes** | Null for `Admitted` (open) and `Cancelled`. Always >= admission_date; completed stays have LOS >= 1 day (day-cases are out of scope) |
| admission_type | text | No | Emergency (via ED or unplanned readmission), Elective (scheduled), Referral (external/GP referral) |
| department_id | FK -> departments | No | Admitting inpatient department (never D01) |
| doctor_id | FK -> doctors | No | Attending doctor; belongs to the same department (DQ-22) |
| bed_id | FK -> beds | **Yes** | Null only when `Cancelled`. Bed belongs to the admission's department; never a `Closed` bed; no two stays overlap in a bed (DQ-31) |
| diagnosis_category | text | Yes | ICD-chapter-style group: Circulatory, Respiratory, Digestive, Infectious & Parasitic, Injury & Poisoning, Musculoskeletal, Neoplasms, Nervous System, Genitourinary, Pregnancy & Childbirth, Endocrine & Metabolic, Neonatal & Perinatal, Other; `Unspecified` for 15 back-filled rows |
| admission_status | text | No | **Discharged** = completed stay (used for LOS, discharges, readmission cohort); **Admitted** = still in-house at snapshot (75; excluded from completed-LOS); **Cancelled** = request never occupied a bed (396; deferred/cancelled elective or referral, incl. no-bed) |
| discharge_type | text | **Yes** | Null unless Discharged: Discharged Home, Discharged Home with Follow-up, Transferred to Another Facility, Left Against Medical Advice, Deceased |

## emergency_visits (35,713 rows)
| Column | Type | Null? | Meaning |
|---|---|---|---|
| emergency_visit_id | **PK** `ED000001` | No | |
| patient_id | FK -> patients | No | |
| arrival_datetime | timestamp | No | ED arrival (start of the waiting clock) |
| triage_level | smallint 1-5 | No | 1 = Resuscitation (most urgent) ... 5 = Non-urgent (ESI-style) |
| consultation_datetime | timestamp | **Yes** | First clinician contact. Null **only** for *Left Without Being Seen* (DQ-26) |
| disposition_datetime | timestamp | No | Final outcome time. For Admitted = time the patient left the ED for the ward (includes boarding) |
| disposition_type | text | No | Admitted, Discharged Home, Referred for Outpatient Follow-up, Transferred (incl. diversions when no bed), Left Against Medical Advice, Left Without Being Seen, Deceased |
| department_id | FK -> departments | No | Specialty team the visit was routed to. For admitted visits = the admitting department; for others mostly Emergency Medicine (D01), Pediatrics for children, etc. |
| admission_id | FK -> admissions | **Yes** | **Extension column (not in the original field list):** resulting admission when `disposition_type = 'Admitted'`; enables ED -> ward flow and boarding analysis |

**Derived:** wait = consultation - arrival; turnaround = disposition - arrival.

## doctors (58 rows)
| Column | Type | Meaning |
|---|---|---|
| doctor_id | **PK** `DR001` | |
| doctor_name | text | Fictional names |
| department_id | FK -> departments | Home department (valid; DQ-09) |
| specialization | text | Sub-specialty |
| employment_type | text | Full-Time, Part-Time, Visiting Consultant |
| shift | text | Morning, Evening, Night (only 24x7 departments), Rotational |

## beds (106 rows)
| Column | Type | Meaning |
|---|---|---|
| bed_id | **PK** `B001` | |
| department_id | FK -> departments | |
| bed_type | text | General Ward, Semi-Private, Private, HDU, ICU, Isolation, Maternity, Pediatric Ward |
| bed_status | text | **Current snapshot (2025-12-31)**: Available, Occupied, Maintenance, Closed. `Closed` = unstaffed (4 beds), never allocated. **Do not use for historical occupancy** - use admission/discharge intervals |

## doctor_activity (44,214 rows)
| Column | Type | Meaning |
|---|---|---|
| activity_id | **PK** `ACT000001` | One row per doctor per **working** day (no row on days off/leave) |
| doctor_id | FK -> doctors | UNIQUE with activity_date |
| activity_date | date | |
| scheduled_hours | numeric | Rostered hours (8 full-time, 5 part-time, 3.5 visiting) |
| patient_consultation_hours | numeric | Hours spent in patient contact (ward rounds, OPD, ED); never above scheduled hours (DQ-29). Excludes documentation/teaching - hence a *proxy* for workload |
| patients_attended | int | Patients seen that day |

## readmissions (1,866 rows)
Derived from `admissions`: for each completed index admission, if the **same patient's next admission** is an **Emergency (unplanned)** admission within 0-90 days of discharge, one row is created. 30-day KPI = rows with `days_between_admissions <= 30` over the eligible index discharges.
| Column | Type | Meaning |
|---|---|---|
| readmission_id | **PK** `RA00001` | |
| patient_id | FK -> patients | Same patient on both admissions |
| original_admission_id | FK -> admissions | Index admission (status Discharged) |
| readmission_admission_id | FK -> admissions, UNIQUE | The returning admission |
| days_between_admissions | int 0-90 | readmission admission_date - original discharge_date (validated, DQ-33) |

## Derived tables created by `database/transformations.sql`
`data_window` (reporting window), `config_thresholds` (illustrative bands), `ed_triage_targets` (illustrative waiting targets), `dim_date`, `fact_dept_daily_census` (occupied/staffed beds per department-day).

## Power BI star schema columns
See `powerbi/data_model.md` - the CSVs in `data/processed/powerbi/` add deterministic row-level flags (`IsAdmission`, `IsCompleted`, `LOSDays`, `BedReleaseDate`, `IsReadmissionEligible`, `FollowupComplete`, `Readmitted30d`, `WaitMinutes`, `TurnaroundMinutes`, `IsLWBS`, `IsAdmitted`, `MetWaitTarget`, ...).

## Injected scenarios (synthetic, for analysis - **not** real events)
S1 monsoon/viral surge 2024-08-05..09-25 · S2 respiratory surge 2025-01-06..02-20 · S3 OT maintenance 2024-03-11..03-24 · S4 ED staffing gap 2024-09-01..11-30 (waits x1.30) · S5 weekend discharge dip · S6 ED handover (14-16h) and evening (18-22h) peaks · S7 uneven doctor pools. Insights must therefore be read as *method demonstrations*; with real data the same SQL/DAX would surface real patterns.
