# Project Conclusion and Limitations

## 1. What was delivered
An end-to-end, reproducible healthcare operations analytics solution on a **synthetic** 106-bed hospital (2023-2025): requirements and KPI definitions; a simulation-based dataset (16,314 admissions incl. 396 cancelled and 75 open stays, 35,713 ED visits, 44,214 doctor-days, 1,866 readmissions, 27,007 patients); an automated data-quality framework; a PostgreSQL schema with constraints, indexes, transformations and 7 reusable views; 41 documented SQL analyses; a Power BI star schema (import-ready CSVs), Power Query, 18 KPI DAX measures, theme and build specification for 5 pages; 14 data-backed insights and a management report; interview and resume material.

## 2. Findings in one paragraph
Hospital-wide averages (70.7% occupancy, 41 min median ED wait, 8.6% readmission) hide concentrated pressure: Medicine, ICU, Cardiology and Pulmonology are full on 44-49% of days while four other departments carry the spare beds; demand is growing (+8.7% in two years) with flat length of stay; ED front-door waits are stable but boarding of admitted patients is long and tracks hospital occupancy; discharges bunch on Mondays; doctor workload and readmissions vary widely and need context. The recommended path is to improve flow and allocation first, then plan targeted capacity.

## 3. Verification status
| Item | Status |
|---|---|
| Dataset generated, reproducible (seed 42; identical file hash on re-run) | Done, verified |
| Raw defects detected (9 failing tests) and remediated; 72/72 tests pass on final data | Done, verified |
| PostgreSQL schema, load (Python `COPY` **and** psql `\copy`), 37 DQ checks (36 pass, 1 documented warning), transformations, views | Done, executed on PostgreSQL 16.2 |
| 41 analytical queries | Done, all executed |
| KPI reconciliation SQL vs independent pandas replica of DAX logic | 64 / 64 match (4 scopes x 16 KPIs) |
| Power BI star schema CSVs, M, DAX, model spec, theme, page specs | Authored |
| Power BI Project (`.pbip`), DAX executed in Power BI Desktop | Done - model loads, 53 measures evaluate, **64/64 KPI match vs SQL** (`analysis/powerbi_verification.md`) |
| Real Power BI screenshots (5 pages) | Done - `powerbi/dashboard_screenshots/` |
| `.pbix` file (`powerbi/hospital_operations_dashboard.pbix`) | Done - saved from Power BI Desktop |
| Excel workbook with live formulas, executed notebook | Done (formulas computed when opened in Excel) |
| Stakeholder validation of definitions | Not applicable (fictional engagement) |

## 4. Assumptions
Listed in BRD section G; the key ones: midnight-census occupancy with constant staffed beds; Emergency admission type = unplanned for readmission; `patient_type` = payer category; illustrative thresholds/targets; age at first encounter; ED `department_id` = routed specialty team; 1-day minimum stay (no day-cases).

## 5. Dependencies
PostgreSQL 14+ (or the bundled `pgserver`), Python 3.11 with pandas, numpy, psycopg2, matplotlib, nbformat/nbconvert, openpyxl, Power BI Desktop (Windows) for the report.

## 6. Risks (residual)
Metric misuse (utilisation/readmission used punitively); thresholds mistaken for standards; synthetic findings mistaken for real; DAX not yet executed in Power BI (mitigated by checkpoint table); privacy when moving to real data (pseudonymisation, RLS, small-cell suppression).

## 7. Data-quality issues
Raw extract: 8 duplicate doctor-activity rows, 403 non-standard gender codes, 270 city format issues, 4 reversed admission/discharge dates, 6 negative ED waits (quarantined), 15 missing diagnoses (back-filled "Unspecified", 0.09%). All resolved or documented; **no unresolved critical issue**. Residual by design: last ~30 days right-censored for readmission; carry-over inpatients before 2023 in occupancy only.

## 8. Scope limitations
- **Synthetic data with injected scenarios** - findings demonstrate method, not real performance; correlations are descriptive.
- No cost, revenue, nursing, theatre, OPD or diagnostics data; no case-mix/risk adjustment; no planned/unplanned flag; no historic staffing or bed-closure reasons; discharge time-of-day, step-down readiness and ED diversion reasons are missing.
- Age is static (first encounter); ED trolleys are not tracked as beds.
- Single site; three years; weekly/daily patterns subject to simulation design (Poisson arrivals).

## 9. Future enhancements
1. Build and publish the `.pbix` (RLS by department, tooltips, bookmarks) and capture screenshots.
2. Forecasting of admissions/occupancy (seasonal ARIMA/Prophet) and capacity simulation (what-if beds/staff).
3. Add data: theatre sessions, OPD, nurse rosters, bed closure reasons, discharge time-of-day, ED diversion reason, planned/unplanned readmission flag, cost per bed-day.
4. Risk-adjusted readmission and mortality; funnel plots with confidence limits for department comparison.
5. Near-real-time census and automated alerts when departments exceed thresholds.
6. dbt/Airflow orchestration, CI running `run_pipeline.py`, data-contract tests.
7. Patient-journey (process-mining) view across ED -> ward -> readmission.

## 10. Lessons learned (BA perspective)
Define metrics before charts (occupancy as bed-days, not admissions/beds; ALOS on completed stays; readmission denominators); separate facts from hypotheses; use context before comparing departments; validate with two independent implementations; keep the data pipeline reproducible.
