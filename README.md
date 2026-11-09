# Hospital Operations & Performance Analytics

*An end-to-end Business Analyst portfolio project: requirements -> KPIs -> synthetic data -> PostgreSQL -> SQL analysis -> Power BI model & DAX -> insights and recommendations.*

![Executive overview - Power BI Desktop](powerbi/dashboard_screenshots/page1_executive.png)
> Screenshot of page 1 of the Power BI report (`powerbi/HospitalOperations.pbip`), captured in Power BI Desktop's editing view on the synthetic data. The report is saved as `powerbi/hospital_operations_dashboard.pbix`; the source project is `powerbi/HospitalOperations.pbip` (see [Power BI setup](#power-bi-setup)). See [Implementation status](#implementation-status).

> **All data is synthetic** (seed 42) and includes deliberately injected operational scenarios. Findings demonstrate the *method*, not a real hospital.

## Contents
[Business problem](#business-problem) · [Objectives](#objectives) · [Tech stack](#technology-stack) · [Architecture](#architecture) · [Dataset](#dataset) · [Database schema](#database-schema) · [Dashboard pages](#dashboard-pages) · [KPIs](#kpi-definitions) · [Insights](#business-insights) · [Screenshots](#screenshots) · [Setup](#setup-instructions) · [SQL](#sql-execution) · [Power BI setup](#power-bi-setup) · [Status](#implementation-status) · [Limitations](#limitations) · [Future](#future-enhancements)

## Business problem
A multi-specialty hospital (106 beds, 10 inpatient departments, ED, 58 doctors) lacks one trusted view of admissions, bed occupancy, ED waiting times, doctor utilisation, length of stay and readmissions. Occupancy is quoted as "admissions / beds", averages hide department-level pressure, and ED delays are not linked to inpatient bed availability.

## Objectives
1. One reconciled definition for 18 KPIs (10 core + 8 supporting), tagged *actual* vs *proxy*.
2. Make capacity pressure visible by department, day and season (interval-based occupancy).
3. Quantify ED access and flow (wait, turnaround, LWBS, boarding).
4. Compare departments *with context*, not league tables.
5. Produce >= 10 evidence-labelled recommendations with monitoring metrics.
6. Zero unresolved critical data-quality issues; everything reproducible with one command.

## Technology stack
| Layer | Tools |
|---|---|
| Data generation / QA | Python 3.11, pandas, numpy (seeded simulation, 72 automated tests) |
| Database & analysis | **PostgreSQL 16** (tested), SQL: CTEs, window functions, conditional aggregation, percentiles |
| Excel | openpyxl workbook with live formulas (inspection, cleaning log, KPI validation) |
| BI | Power BI star schema, Power Query (M), DAX, theme JSON (build in Desktop) |
| Docs | Markdown BRD/FRD/KPI/stakeholder/user stories/insights/management report |

## Architecture
```mermaid
flowchart LR
  G[generate_dataset.py<br/>seeded simulation] --> R[(data/raw<br/>defects injected)]
  R --> C[clean_data.py<br/>log + quarantine] --> P[(data/processed)]
  P --> V[validate_data.py<br/>72 tests]
  P --> DB[(PostgreSQL schema hospital<br/>constraints + indexes)]
  DB --> T[transformations.sql<br/>dim_date, daily census] --> W[7 analytical views]
  W --> Q[41 analytical queries]
  P --> S[build_star_schema.py] --> PBI[Power BI model<br/>4 facts + 5 dims + DAX]
  DB --> K[reconcile_kpis.py<br/>SQL vs DAX-logic]
  S --> K
```

## Dataset
Simulation, not random columns: **beds are finite** (every admission gets a free bed of its own department; emergencies board in the ED and are diverted after 2 days; electives are deferred or cancelled), **emergency admissions originate from ED visits**, readmissions are **derived** from the final admissions table, doctor workload derives from census/admissions/ED volume. Seasonal, weekday and surge patterns are built in.

| Table | Rows | Table | Rows |
|---|---:|---|---:|
| admissions | 16,314 | emergency_visits | 35,713 |
| patients | 27,007 | doctor_activity | 44,214 |
| readmissions | 1,866 | beds / doctors / departments | 106 / 58 / 11 |

Admissions: 15,843 discharged, 75 still admitted, 396 cancelled. Injected scenarios: monsoon and respiratory surges, OT downtime (Mar 2024), ED staffing gap (Sep-Nov 2024), weekend discharge dip, ED evening/handover peaks, uneven doctor pools. Full column definitions: [`data/data_dictionary.md`](data/data_dictionary.md).

## Database schema
![ER diagram](assets/er_diagram.png)
`database/schema.sql` - 8 tables, PK/FK, CHECK constraints (status/discharge consistency, date order, ED time order, hours <= scheduled), 18 indexes. `transformations.sql` adds `dim_date`, `fact_dept_daily_census`, configurable thresholds. `views.sql`: `vw_patient_admission_summary`, `vw_department_performance`, `vw_bed_occupancy`, `vw_emergency_performance`, `vw_doctor_utilization`, `vw_readmission_analysis`, `vw_monthly_hospital_kpis`.

## Dashboard pages
| # | Page | Audience | Key content |
|---|---|---|---|
| 1 | Executive Overview | CEO | 6 KPI cards vs previous period; admissions vs discharges; department volume; admission type; occupancy trend; ED wait trend |
| 2 | Admissions & Discharges | Operations | Daily trend with Year>Quarter>Month>Day drilldown; weekday x type; ALOS by department; age; readmission trend |
| 3 | Bed Occupancy & Resources | Bed management | Occupancy by department (green/amber/red, configurable illustrative thresholds); seasonal heat-map; bed types; capacity vs doctor load |
| 4 | Department Performance | Dept heads | Volume, ALOS, readmission, utilisation, patients per doctor; comparison matrix with context |
| 5 | Waiting Time & Flow (ED) | ED manager | Wait mean/median/turnaround; by triage, hour, weekday, department; disposition; triage slicer |

Reference renderings: [`assets/reference_pages/`](assets/reference_pages/). Build spec: [`powerbi/dashboard_build_guide.md`](powerbi/dashboard_build_guide.md).

## KPI definitions
Headline results (2023-25; SQL and DAX-logic reconciled 64/64):

| KPI | Value | Definition (key rule) |
|---|---:|---|
| Total admissions | 15,865 | non-cancelled, by admission date |
| Unique patients | 12,311 | distinct admitted patients |
| Discharges | 15,843 | status Discharged, by discharge date |
| ALOS | 4.98 d | **completed stays only** |
| Bed occupancy | 70.7% | **occupied bed-days / staffed bed-days** (never admissions / beds) |
| ED wait (mean / median) | 50.8 / 41.2 min | arrival -> consultation (LWBS excluded) |
| ED turnaround | 308 min | arrival -> final disposition |
| 30-day readmission | 8.63% | unplanned readmits / **eligible** discharges (1,264 / 14,655) |
| Doctor utilisation | 79.5% | consultation hours / scheduled hours |
Full dictionary (formula, numerator, denominator, source, frequency, assumptions, actual vs proxy): [`documentation/KPI_Dictionary.md`](documentation/KPI_Dictionary.md). DAX: [`powerbi/dax_measures.md`](powerbi/dax_measures.md).

## Business insights
14 evidence-labelled insights (observation, data, impact, hypothesis, action, benefit, metric) in [`documentation/Business_Insights_Report.md`](documentation/Business_Insights_Report.md); management report: [`Management_Report.md`](documentation/Management_Report.md). Highlights:
- **Pressure is concentrated:** General Medicine 86% occupancy (full on 46% of days; Sep peak 96%); ICU/Pulmonology/Cardiology 82-84%; Pediatrics 52%, OB/GYN 56%, Surgery 61%.
- **ED back door:** admitted patients average **666 min** in the ED (P90 35 h); consultation-to-ward time rises 553 -> 798 min as hospital occupancy goes from <70% to 85%+; ED turnaround up 26% in two years while waits were flat.
- **Discharge timing:** Monday has 22.5% of discharges (Sunday 9.5%) and the longest ED waits.
- **ED peaks:** 17-21h = 32% of arrivals, average wait 60 min vs 32 at night.
- **Readmissions:** 16.6% Cardiology, 15.5% Pulmonology, 14.5% Oncology vs 3-5% surgical/obstetric - case-mix, not a performance verdict.
- **Workload:** Pulmonology 86% utilisation on 3 doctors; Oncology 63%.

## Screenshots
Captured from Power BI Desktop (editing view) on the synthetic data. Slicers are shown at their default "All" state.

| | |
|---|---|
| ![p1](powerbi/dashboard_screenshots/page1_executive.png) | ![p2](powerbi/dashboard_screenshots/page2_admissions.png) |
| ![p3](powerbi/dashboard_screenshots/page3_beds.png) | ![p4](powerbi/dashboard_screenshots/page4_departments.png) |
| ![p5](powerbi/dashboard_screenshots/page5_ed.png) | |

Python-rendered reference pages (same data, *not* Power BI) are in `assets/reference_pages/`.

## Setup instructions
Requirements: Python 3.11+. PostgreSQL is optional (an embedded PostgreSQL 16 is installed via pip). Tested on Windows 11.
```bash
git clone <repo> && cd hospital-operations-analytics
pip install -r requirements.txt
python scripts/run_pipeline.py            # generate -> clean -> validate -> star schema -> PostgreSQL -> 41 queries -> reconcile -> assets
```
`run_pipeline.py` stops at the first failing step. Re-running reproduces identical data (seed 42). Use `--skip-assets` to skip charts/notebook/Excel, or `--dsn postgresql://user:pwd@host:5432/hospital` to target your own server (create the empty database first).

Step by step: `python scripts/generate_dataset.py` · `clean_data.py` · `validate_data.py --data data/processed --report analysis/validation_report.md` · `build_star_schema.py` · `load_database.py` · `reconcile_kpis.py`.

## SQL execution
**Option A - Python (no psql needed):** `python scripts/load_database.py` (embedded PostgreSQL in `.pgdata/`, or `--dsn ...`). Use `--steps schema,load,dq,transform,views,queries` to run a subset; query results are written to `analysis/sql_results/`.

**Option B - psql, from the project root:**
```bash
createdb hospital
psql -d hospital -f database/schema.sql
psql -d hospital -f database/data_import.sql          # client-side \copy of data/processed/*.csv
psql -d hospital -f database/data_quality_checks.sql  # expect 36 PASS, 1 WARN, 0 FAIL
psql -d hospital -f database/transformations.sql
psql -d hospital -f database/views.sql
psql -d hospital -f database/analytical_queries.sql   # or run blocks individually
```
Both routes were executed and verified on PostgreSQL 16.2. Query catalogue with purpose, decision supported and result previews: [`documentation/SQL_Analysis_Documentation.md`](documentation/SQL_Analysis_Documentation.md).

## Power BI setup
**Fast route (Power BI Project):** run the pipeline, then `python scripts/build_pbip.py` (writes the `DataFolder` path for your machine), open `powerbi/HospitalOperations.pbip` in Power BI Desktop and press *Refresh*. To re-check the DAX against SQL: `powershell -ExecutionPolicy Bypass -File scripts/verify_powerbi_model.ps1 -Refresh` (writes `analysis/powerbi_verification.md`). Then *File > Save as* `.pbix`.

**Manual route:** requires **Power BI Desktop (Windows)**. 1) Run the pipeline (creates `data/processed/powerbi/*.csv`). 2) Create parameter `DataFolder`, paste the queries in [`powerbi/power_query/load_tables.pq`](powerbi/power_query/load_tables.pq). 3) Build relationships and mark `DimDate` per [`powerbi/data_model.md`](powerbi/data_model.md). 4) Paste measures from [`powerbi/dax_measures.md`](powerbi/dax_measures.md), create the two threshold parameters. 5) Apply [`powerbi/theme/hospital_theme.json`](powerbi/theme/hospital_theme.json). 6) Build pages per [`powerbi/dashboard_build_guide.md`](powerbi/dashboard_build_guide.md). 7) Check every card against [`analysis/kpi_checkpoints.csv`](analysis/kpi_checkpoints.csv).

## Implementation status
| Component | Status |
|---|---|
| Synthetic dataset, cleaning, 72 automated tests | ✅ Done and verified (reproducible) |
| PostgreSQL schema, load (2 routes), 37 SQL checks, views, 41 queries | ✅ Executed on PostgreSQL 16.2 |
| KPI reconciliation SQL vs DAX-logic | ✅ 64 / 64 match |
| Excel workbook, executed EDA notebook, ER and star diagrams | ✅ Done |
| BRD, FRD, KPI dictionary, stakeholders, user stories, insights, management report, guides | ✅ Done |
| Power BI Project (`.pbip`): model, M, 18 KPI + supporting DAX measures, 5 report pages | ✅ Generated; **model and DAX verified in Power BI Desktop (64/64 vs SQL)**; layout reviewed in Desktop screenshots |
| Real Power BI screenshots (5 pages) | ✅ `powerbi/dashboard_screenshots/` |
| `powerbi/hospital_operations_dashboard.pbix` (4 MB, data embedded) | ✅ Saved from Desktop. Model/DAX verified 64/64; Desktop-built, layout is a reviewed first version |

## Limitations
Synthetic data with injected scenarios; illustrative occupancy/utilisation/ED thresholds; unplanned readmission proxied by Emergency admission type; staffed beds constant over time; no cost, nursing, OPD or theatre data; descriptive correlations only. Details: [`documentation/Project_Conclusion.md`](documentation/Project_Conclusion.md).

## Future enhancements
Build and publish the PBIX with RLS; forecasting and capacity simulation; closure reasons, discharge times, ED diversion reasons, planned/unplanned flags; risk-adjusted readmission; real-time census alerts; orchestration/CI.

## Repository structure
```
hospital-operations-analytics/
├── README.md · requirements.txt
├── data/            raw/ (defects injected) · processed/ (cleaned, + powerbi/ star schema, cleaning_log, rejected_records) · data_dictionary.md
├── database/        schema.sql · data_import.sql · data_quality_checks.sql · transformations.sql · analytical_queries.sql · views.sql
├── powerbi/         dax_measures.md · data_model.md · dashboard_build_guide.md · power_query/ · theme/ · dashboard_screenshots/
├── documentation/   BRD · FRD · KPI_Dictionary · Stakeholder_Analysis · User_Stories · SQL_Analysis_Documentation
│                    Business_Insights_Report · Management_Report · Dashboard_User_Guide · Project_Conclusion · Interview_Prep
├── analysis/        exploratory_analysis.ipynb · excel_data_inspection.xlsx · validation_report.md · kpi_reconciliation.md · kpi_checkpoints.csv · sql_results/
├── scripts/         generate_dataset · clean_data · validate_data · load_database · build_star_schema · reconcile_kpis · make_assets/notebook/excel/sql_docs · run_pipeline
└── assets/          er_diagram.png · star_schema_diagram.png · dashboard_preview.png · reference_pages/
```

## Resume bullets & interview prep
[`documentation/Interview_Prep.md`](documentation/Interview_Prep.md): 3 resume bullets, 2-minute pitch, 15 BA + 10 SQL + 10 Power BI/DAX + 5 business-case questions.
