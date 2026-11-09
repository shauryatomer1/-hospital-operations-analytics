# Dashboard User Guide

> **Status:** this guide describes the five-page report in `powerbi/HospitalOperations.pbip` (spec: `powerbi/dashboard_build_guide.md`). Open it in Power BI Desktop and press *Refresh* (data path = the `DataFolder` parameter). The layout is a generated first version; the Python-rendered pages in `assets/reference_pages/` show the intended content, not Power BI screenshots.

## 1. Who uses what
| Page | Audience | Use it to answer |
|---|---|---|
| 1 Executive Overview | CEO, management | Are we efficient? Are admissions rising? Which departments are under pressure? Are occupancy and waits improving? |
| 2 Admissions & Discharges | Operations Manager | When is demand highest? Which categories grow? Which departments hold patients longest? |
| 3 Bed Occupancy & Resources | Bed Management, Operations | Which departments are at capacity? Where are beds under-used? When is demand highest? |
| 4 Department Performance | Department heads | How does my department compare - in context? |
| 5 Waiting Time & Patient Flow | ED Manager | Which hours/triage groups wait longest? Where does flow break? When to add staff? |

## 2. Slicers and interactions
- **Date** (top-left): any range 2023-2025. Cards and charts recalculate; "vs previous period" always compares with the immediately preceding period of the same length.
- **Department**: filters every visual (Emergency Medicine has no inpatient beds and is hidden on bed visuals).
- **Admission type** (Emergency / Elective / Referral) - pages 1-4. **Triage level** and **hour range** - page 5.
- Click any bar/column to cross-filter other visuals; click again to clear. **Ctrl+click** selects several.
- **Drilldown (page 2):** use the down-arrow icons on the daily chart: Year -> Quarter -> Month -> Day. The forked-arrow expands one level for all.
- **Drill-through:** right-click a department -> *Drill through* -> Department detail.
- **Tooltips:** hover any KPI card for its definition, numerator/denominator and whether it is an *actual* KPI or a *proxy*.

## 3. Reading the colours
| Colour | Meaning |
|---|---|
| Blue / teal | Normal data series (no good/bad meaning) |
| Green / amber / red | **Status only**: occupancy and utilisation against *illustrative* thresholds (amber >= 85%, red >= 95% for occupancy). Thresholds are adjustable with the parameter sliders and must be set to hospital policy |
| Grey | Context / not applicable |
Growth arrows are neutral - rising admissions are not automatically good or bad.

## 4. KPI cheat-sheet
| KPI | How to read it | Watch-outs |
|---|---|---|
| Total Admissions / Discharges | Volume in / out; compare to detect net inflow | Cancelled requests are excluded; open stays count as admissions only |
| Unique Patients | People served | Not additive across departments |
| ALOS | Mean stay of **completed** stays | Skewed - see median/P90; open stays excluded |
| Bed Occupancy Rate | Occupied bed-days / staffed bed-days | Small units flip between 87% and 100% with one patient; closed beds are outside the denominator |
| Avg / Median ED Wait | Arrival -> consultation | Excludes patients who left unseen (shown as LWBS %) |
| ED Turnaround | Arrival -> final disposition | Admitted patients include boarding for a bed |
| 30-Day Readmission | Eligible discharges returning unplanned within 30 days | Last 30 days of data show *n/a*; compare departments only with their denominators; not risk-adjusted |
| Doctor Utilization | Consultation hours / scheduled hours | Excludes non-clinical work; not a performance appraisal |

## 5. Page notes
**Page 1** - The six cards show the period value and the change vs previous period. The bottom trend charts show occupancy (with the amber line) and ED waits (mean and median).
**Page 2** - Use the weekday matrix to see elective vs emergency demand; ALOS is for completed stays; the readmission trend has gaps for periods without complete follow-up.
**Page 3** - Left: occupancy by department (bar colour = status). Middle: month x department heat-map (seasonality). Right: bed types. Bottom: daily occupancy with threshold lines. The scatter compares bed pressure with doctor utilisation.
**Page 4** - The matrix colours show *relative position within each column*, never a verdict. Read high readmission rates alongside case-mix notes (chronic diseases).
**Page 5** - Arrivals and waits by hour share an axis (no dual axis). The triage chart marks the illustrative target. Use the triage slicer to look only at high-acuity patients.

## 6. Refresh and data currency
Import mode; refresh monthly (or daily in production). The footer shows the data snapshot date (2025-12-31). Numbers can be verified against `analysis/kpi_checkpoints.csv`.

## 7. Known limitations visible to users
Synthetic data; illustrative thresholds; unplanned readmission proxied by Emergency admission type; staffed beds assumed constant; admissions before Jan 2023 (carry-over patients) are hidden by the report-level filter but counted in occupancy.

## 8. Support
Definitions: `documentation/KPI_Dictionary.md`. Data fields: `data/data_dictionary.md`. Questions on the analysis: Business Analytics team.
