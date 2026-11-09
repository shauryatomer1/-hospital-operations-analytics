# Functional Requirements Document (FRD)

Traceability: each requirement maps to a BRD function, SQL asset, DAX/KPI and dashboard page. Priority: **M** = must, **S** = should.

## 1. System context
```
Source CSV extracts (8 tables) -> clean_data.py -> PostgreSQL (schema `hospital`) -> views / analytics tables
                                                        |                              |
                                           41 analytical queries                build_star_schema.py -> Power BI model (5 pages)
```

## 2. Functional requirements
| ID | Requirement | BRD fn | Priority | SQL asset | KPI / DAX | Page |
|---|---|:-:|:-:|---|---|:-:|
| FR-01 | Show admissions and discharges by day, week, month with drilldown Year>Quarter>Month>Day | 1,9 | M | Q05-Q07, Q10, `vw_monthly_hospital_kpis` | Total Admissions, Total Discharges, growth | 1,2 |
| FR-02 | Distinguish completed, open and cancelled admissions everywhere | 1 | M | `vw_patient_admission_summary` flags | IsAdmission/IsCompleted/IsCancelled | all |
| FR-03 | Show admission type and discharge type distributions | 1 | M | Q08, Q09, Q13 | Emergency Admission % | 1,2 |
| FR-04 | Compute occupancy as occupied bed-days / staffed bed-days (interval based), by department, bed type, day | 2 | M | `fact_dept_daily_census`, `vw_bed_occupancy`, Q16-Q21 | Bed Occupancy Rate | 1,3 |
| FR-05 | Classify occupancy into Normal/High/Critical using configurable, labelled-illustrative thresholds | 2 | M | `config_thresholds` | BOR Status / thresholds parameters | 3 |
| FR-06 | Identify high-occupancy periods and peak days | 2,9 | M | Q18, Q21 | Peak Admission Day | 3 |
| FR-07 | Report ALOS on completed stays with median/P90 and long-stay share | 3 | M | Q12 | ALOS | 2,4 |
| FR-08 | ED waiting time (mean, median, P90) by month, triage, hour, weekday, department | 4 | M | Q22-Q24, Q27, `vw_emergency_performance` | Avg/Median ED Wait | 5 |
| FR-09 | ED turnaround overall and by disposition; admitted-patient boarding | 4,8 | M | Q25, Q28, Q41 | ED Turnaround | 5 |
| FR-10 | LWBS rate and relation to waiting time | 4 | S | Q24, Q26 | LWBS Rate | 5 |
| FR-11 | Doctor utilisation by doctor/department/shift/employment type | 5 | M | Q29-Q32, `vw_doctor_utilization` | Doctor Utilization Rate | 4 |
| FR-12 | Patients per doctor and patients attended per doctor-day | 5 | S | Q30 | Patients per Doctor | 4 |
| FR-13 | Department comparison matrix (volume, efficiency, resource use, outcomes) with context notes | 6 | M | `vw_department_performance`, Q39 | multiple | 4 |
| FR-14 | 30-day readmission rate with eligible denominator, by department/type/age | 7 | M | Q33-Q35, `vw_readmission_analysis` | 30-Day Readmission Rate | 1,2,4 |
| FR-15 | Patient flow: ED -> admitting dept; index dept -> readmitting dept | 8 | S | Q36, Q41 | flow counts | 2,5 |
| FR-16 | Trends/seasonality/weekday effects | 9 | M | Q05-Q08, Q14, Q19, Q20, Q38 | growth, YoY | 1,2,3 |
| FR-17 | Resource-alignment view (bed pressure vs doctor workload vs LOS) | 10 | M | Q39, Q40 | scatter | 3,4 |
| FR-18 | Global slicers: date, department, admission type; triage slicer on ED page | all | M | - | - | all |
| FR-19 | Executive page KPIs show change vs previous period of equal length | 1,9 | M | Q38 | Prev Period / Growth measures | 1 |
| FR-20 | Each KPI has a tooltip with definition and "actual/proxy" tag | NFR | S | `KPI_Dictionary.md` | - | all |

## 3. Business rules (system must enforce)
| ID | Rule |
|---|---|
| BR-01 | Discharge date >= admission date; completed LOS >= 1 day |
| BR-02 | ALOS uses status Discharged only |
| BR-03 | Cancelled admissions have no bed and no discharge data |
| BR-04 | A bed holds at most one stay at a time; beds and doctors belong to the admission's department; Closed beds are never allocated |
| BR-05 | Occupancy: midnight census, staffed beds (not Closed) as capacity |
| BR-06 | Readmission: Emergency-type admission of the same patient, 0-90 days after an index Discharged admission; 30-day KPI over eligible index discharges (alive, not transferred out, full follow-up) |
| BR-07 | ED wait = consultation - arrival (LWBS excluded); turnaround = disposition - arrival |
| BR-08 | Doctor consultation hours <= scheduled hours |
| BR-09 | Facts are never joined to each other; they share dimensions only |
| BR-10 | Carry-over inpatients (pre-2023 admissions) count for occupancy only |

## 4. Data requirements
Eight source tables (`data/data_dictionary.md`), one added column (`emergency_visits.admission_id`) to link ED visits to resulting admissions. Reference tables for thresholds. Validation: 72 pandas tests / 37 SQL checks.

## 5. Interface requirements
- **Dashboard:** 5 pages, 1280x720, light theme, blue/teal palette, synced slicers, drill-through (department), tooltip pages, report-level filter `InReportingWindow`.
- **Exports:** every visual supports "Export data"; KPI scorecard exportable to Excel.
- **Access:** (real deployment) workspace roles; RLS by department for department heads.

## 6. Acceptance
Requirement is accepted when (a) its KPI reconciles with `analysis/kpi_checkpoints.csv`, (b) validation suite passes, (c) page behaves per `powerbi/dashboard_build_guide.md`. Status of (c) is **pending Power BI Desktop build** - see Project Conclusion.
