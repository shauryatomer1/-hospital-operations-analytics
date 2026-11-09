# Business Requirements Document (BRD)
**Project:** Hospital Operations & Performance Analytics  |  **Version:** 1.0  |  **Author:** Business Analyst  |  **Status:** Portfolio baseline (no real stakeholder sign-off)
*All data in this portfolio project is synthetic. The hospital is fictional.*

---

## A. Project overview

### A1. Background
A fictional 106-bed, multi-specialty hospital (10 inpatient departments + an Emergency Department, 58 doctors) records admissions, discharges, ED visits, bed allocations and doctor rosters in separate operational systems. Management reviews each in isolation, in spreadsheets, weeks after month-end.

### A2. Business problem
Management has **no consolidated, trusted view** of patient flow and resource use. Assumed pain points for this fictional engagement (written as a problem statement; to be validated with stakeholders and by the analysis):
- Bed pressure is felt on the wards but not measured consistently (occupancy is quoted as "admissions / beds", which is not a valid measure).
- ED waiting times and boarding of admitted patients are not tracked by hour, triage level, or link to inpatient bed availability.
- Doctor workload is judged anecdotally; departments cannot see whether they are over- or under-resourced.
- Readmissions and length of stay are reported as hospital-wide averages that hide department differences.

### A3. Objectives (SMART-style)
| # | Objective | Measure of success |
|---|---|---|
| O1 | One reconciled source of truth for 10 core and 8 supporting operational KPIs | KPI values identical in SQL, Excel checks and Power BI (reconciliation report: 64/64 match) |
| O2 | Make capacity pressure visible by department and period | Interval-based occupancy by department/day with configurable bands |
| O3 | Quantify ED access and flow (wait, turnaround, LWBS, boarding) | ED KPIs by hour, weekday, triage, department |
| O4 | Compare departments fairly with context | Department matrix covering volume, efficiency, resource use, outcomes |
| O5 | Identify >= 10 evidence-based improvement opportunities with owners and monitoring metrics | Business Insights Report |
| O6 | Data trust | 0 unresolved critical data-quality issues; automated checks re-runnable |

### A4. Expected business outcomes
Faster, evidence-based capacity and staffing decisions; earlier detection of surges; a basis for discharge-flow and ED-boarding initiatives; a repeatable monthly management pack. *No financial benefit is claimed - benefits would be measured after implementation (see monitoring metrics).*

### A5. Scope
**In scope:** admissions/discharges, bed occupancy, ED waiting & turnaround, doctor utilisation, readmissions, department comparison, patient flow (ED -> ward, department -> readmitting department), trends 2023-2025; PostgreSQL model, SQL analytics, Power BI model/DAX/dashboard specification, documentation.
**Out of scope:** clinical outcomes beyond discharge disposition/readmission (no mortality risk-adjustment), financials/billing, OPD and theatre scheduling, nurse staffing data, real-time (streaming) feeds, predictive modelling, patient-identifiable data, integration with live HIS.

## B. Stakeholders (summary - detail in `Stakeholder_Analysis.md`)
| Stakeholder | Primary interest / requirement |
|---|---|
| Hospital CEO / Management | One-page view: efficiency, growth, pressure points, quality; comparison with previous period |
| Hospital Operations Manager | Daily/weekly demand, occupancy, discharge flow; capacity constraints; resource allocation |
| Department Heads | Their department's volume, ALOS, readmissions, doctor load vs peers - with context |
| Doctors | Fair workload measures; no punitive use of utilisation figures |
| Nursing Staff | Predictable occupancy / patient load by ward; early warning of surges |
| Bed Management Team | Real-time-like census, high-occupancy periods, discharge timing |
| Emergency Department Manager | Arrival patterns by hour/day, waits by triage, boarding, LWBS, staffing windows |
| Data / Business Analyst | Documented definitions, reproducible pipeline, data-quality controls |

## C. Functional requirements (summary - detail with IDs in `FRD.md`)
1. Monitor patient admissions and discharges (daily/weekly/monthly; drilldown Year>Quarter>Month>Day).
2. Track bed occupancy and availability (interval-based, by department and bed type).
3. Measure average length of stay (completed stays only).
4. Analyse ED waiting times (mean, median, by triage/hour/day/department).
5. Monitor doctor utilisation (consultation / scheduled hours).
6. Compare department-wise performance with context.
7. Identify readmission patterns (30-day, eligible denominator, by department, discharge type, age).
8. Analyse patient flow across departments (ED -> admission, index -> readmitting department).
9. Monitor operational trends over time (growth, seasonality, weekday effects).
10. Identify resource-allocation inefficiencies (bed pressure vs doctor workload; under-utilised capacity).

## D. Non-functional requirements
| Area | Requirement |
|---|---|
| Data accuracy | Automated validation (72 pandas tests, 37 SQL checks); KPIs reconciled between two independent implementations; documented definitions; critical defects = 0 |
| Usability | Executive page readable in < 30 s; <= 8 visuals per page; consistent colours; every KPI has a tooltip definition; thresholds labelled illustrative |
| Performance | Page load < 5 s in Import mode on the 100k-row model; heavy measures (occupied bed-days) restricted to month grain for matrix visuals |
| Data privacy | No real patient data; in a real deployment: pseudonymised IDs, no names/addresses in the model, role-based access (department heads see own department - RLS), aggregation of small cells (< 5) in shared reports; compliance review against applicable health-data law |
| Scalability | Star schema, indexed PostgreSQL; incremental refresh on ED and activity facts; model scales to millions of rows |
| Data refresh | Monthly in this project; production target daily (overnight ETL) with a data-freshness stamp on every page |
| Maintainability | Single pipeline command, version-controlled SQL/DAX, config table for thresholds |
| Auditability | Cleaning log and quarantined-records file; no silent deletions |

## E. User stories
See `User_Stories.md` (12 stories with acceptance criteria).

## F. KPI dictionary
See `KPI_Dictionary.md` (definition, formula, numerator/denominator, source, frequency, interpretation, assumptions; *actual* vs *proxy* KPIs separated).

## G. Assumptions
1. **Synthetic data** with injected scenarios; patterns are illustrative.
2. Reporting window 2023-01-01..2025-12-31; snapshot date 2025-12-31.
3. Occupancy uses a **midnight census**; staffed beds = beds not `Closed`, constant over time (no historic staffing records).
4. A bed released on the discharge date is available that day (no turnaround/cleaning gap modelled).
5. Readmission = unplanned (Emergency-type) admission within 30 days; planned/unplanned flag is proxied by `admission_type`.
6. LOS minimum 1 day; day-cases are excluded from the data.
7. `patient_type` is interpreted as payer category.
8. ED triage targets and occupancy/utilisation bands are **illustrative**, to be replaced by hospital policy.
9. `age` is age at first encounter in the dataset.
10. Illustrative nature of ED `department_id`: the specialty team the visit was routed to.

## H. Dependencies
PostgreSQL 14+ (or the embedded `pgserver`), Python 3.11 + pandas/numpy/psycopg2/matplotlib, Power BI Desktop (for the `.pbix` build), agreement on KPI definitions with stakeholders, data owners for each source system (real deployment).

## I. Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| KPI definitions disputed (e.g. occupancy, readmission) | High | High | Definitions signed off in the KPI dictionary; assumptions visible on pages |
| Poor source data quality | Medium | High | Validation suite + cleaning log + quarantine |
| Misuse of utilisation / readmission metrics to blame individuals/departments | Medium | High | Context panels; no league-table language; peer-comparison only with denominators |
| Illustrative thresholds read as standards | Medium | Medium | Always labelled "illustrative"; configurable parameters |
| Power BI measure errors | Medium | Medium | Checkpoint table (`kpi_checkpoints.csv`) to verify every card |
| Synthetic findings mistaken for real | Low | High | Explicit disclaimers in every report |

## J. Data-quality issues identified (raw extract) and treatment
9 failing tests on the raw extract: 8 duplicate activity rows, 403 non-standard gender codes, 270 city format issues, 4 reversed admission/discharge dates, 6 negative ED waits, 15 missing diagnosis categories. All remediated or quarantined; see `analysis/validation_report.md`.

## K. Scope limitations / future enhancements
Limitations: see `Project_Conclusion.md`. Future: real-time census feed, theatre and OPD data, nurse-to-patient ratios, forecasting (ARIMA/Prophet) of admissions and occupancy, ED simulation for staffing, cost per bed-day, risk-adjusted readmission, RLS by department.

## L. Approval
| Role | Name | Date |
|---|---|---|
| Sponsor (CEO) | (placeholder for portfolio) | - |
| Business owner (Operations Manager) | (placeholder for portfolio) | - |
