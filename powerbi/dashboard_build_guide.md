# Dashboard Build Guide (Power BI Desktop)

**Implementation status:** `powerbi/HospitalOperations.pbip` is a generated Power BI Project (TMDL semantic model + PBIR report: 5 pages, 71 visuals) that opens in Power BI Desktop. The model, relationships and DAX are verified in the Desktop engine (64/64 against SQL). The **visual layout was reviewed from Desktop screenshots (`dashboard_screenshots/`) but is a first version that you may want to polish, and the `.pbix` was saved from it (`hospital_operations_dashboard.pbix`)** - open the `.pbip`, press *Refresh*, review each page, then *File > Save as* `.pbix` and capture real screenshots. The manual build steps below remain valid if you prefer to build from scratch. `assets/reference_pages/*.png` are Python-rendered references, *not* Power BI screenshots.

| Step | Where | Needs Power BI Desktop? |
|---|---|---|
| Run `scripts/build_star_schema.py` (creates CSVs) | terminal | No |
| Load tables (M), set types, relationships, mark date table | Desktop | **Yes** |
| Paste measures, create threshold parameters | Desktop | **Yes** |
| Build visuals per page spec, apply theme, bookmarks, tooltips | Desktop | **Yes** |
| Verify cards against `analysis/kpi_checkpoints.csv` | Desktop | **Yes** |
| Save as `powerbi/hospital_operations_dashboard.pbix`, screenshots to `dashboard_screenshots/` | Desktop | **Yes** |

## Build order
1. **Parameter + load** - create `DataFolder`, paste `fnLoadCsv` and the nine table queries. *Close & Apply.*
2. **Model view** - create relationships exactly as in `data_model.md` (3 inactive ones: untick *Make this relationship active*). *Mark `DimDate` as date table.* Sort columns (MonthName by MonthNumber, YearMonth by YearMonthSort, DayName by DayOfWeekNumber).
3. **Measures** - create table `_Measures`, paste all of `dax_measures.md`; create the two threshold parameters.
4. **Theme** - View > Themes > Browse for themes > `theme/hospital_theme.json`.
5. **Report-level filter** - on *Filters pane > Filters on all pages*: `DimDate[InReportingWindow]` = True.
6. **Pages** - below. Canvas 1280 x 720; 16 px outer margin, 12 px gutter, 12-column grid; KPI cards row height 88 px.
7. **Verify** - slicers cleared -> compare cards to `kpi_checkpoints.csv` scope "All (2023-2025)"; year slicer -> compare to 2023/2024/2025 rows.

## Global slicers / conventions
- Sync slicers across pages: **Date** (between, `DimDate[Date]`), **Department** (`DimDepartments[DepartmentName]`, dropdown, exclude "Emergency Medicine" on bed pages via visual filter `HasInpatientBeds = True`), **Admission type** (`FactAdmissions[AdmissionType]`).
- Date formats `dd-mmm-yyyy` on axes/tooltips, `mmm yyyy` for months. Percent: 1 decimal. Minutes: 0-1 decimal.
- Titles state the metric *and* its definition where non-obvious (e.g. "ED waiting time (arrival to consultation, min)").
- Colours: blue `#1F5FA8` primary, teal `#1A9E9A` secondary, grey for context; **traffic-light colours only for status** (BOR/utilisation), never as series colours.
- Page navigator (buttons) on the top-right; tooltips pages for KPI cards and department bars.

---

## Page 1 - Executive Overview
*Audience: CEO / management. Answers: Is the hospital efficient? Are admissions rising? Which departments are under pressure? Are occupancy and waits improving?*

| Visual | Type | Fields |
|---|---|---|
| 6 KPI cards | Card (new) with reference label | `Total Admissions`, `Total Discharges`, `Total Unique Patients`, `ALOS`, `Bed Occupancy Rate`, `30-Day Readmission Rate`; reference label = growth vs previous period (`Admission Growth Rate` etc.) |
| Monthly admissions & discharges | Line chart | X `DimDate[YearMonth]`; Y `Total Admissions`, `Total Discharges` |
| Department-wise volume | Bar (horizontal) | Y `DimDepartments[DepartmentName]`; X `Total Admissions`; sort desc; tooltip: ALOS, BOR, share % |
| Admission type distribution | Donut | Legend `AdmissionType`; Values `Total Admissions` |
| Bed occupancy trend | Line | X `YearMonth`; Y `Bed Occupancy Rate`; constant line at `BOR High Threshold Value` (analytics pane > Constant line, fx) |
| ED waiting-time trend | Line | X `YearMonth`; Y `Avg ED Wait (min)`, `Median ED Wait (min)` |
| KPI vs previous period | Table / matrix | Rows = KPI name (disconnected table), values current, previous, delta (use the *Prev Period* measures) |
| Slicers | Date, Department, Admission type | |

Conditional formatting: BOR card font colour by `BOR Color`; delta labels via `KPI Delta Color` (neutral colours - growth is not good/bad in itself).

## Page 2 - Patient Admission & Discharge Analysis
*Audience: Operations manager. Answers: when is demand highest, which departments carry load, which admission categories increase, which departments keep patients longest?*

| Visual | Type | Fields |
|---|---|---|
| Daily admissions | Line (drill-enabled) | Axis hierarchy **Year > Quarter > Month > Day** (`DimDate[Year]`, `QuarterLabel`, `MonthName`, `Date`); Y `Total Admissions`; enable *Drill down* mode |
| Weekly & monthly trend | Line + column | Column: monthly (`YearMonth`); line: `Total Admissions` rolling via 4-week `WeekStart` series (small multiple or second visual) |
| Admission type distribution | 100% stacked column by year | Axis `Year`; Legend `AdmissionType` |
| Discharge type distribution | Bar | `DischargeType` x `Total Discharges` |
| ALOS by department | Bar | `DepartmentName` x `ALOS` (conditional colour by value quartile) |
| Age-group distribution | Column | `DimPatients[AgeGroup]` x `Total Admissions` |
| Readmission trends | Line | X `YearMonth`; Y `30-Day Readmission Rate` (blank for censored months - keep blanks as gaps) |
| Admission vs discharge | Clustered column | `YearMonth` x `Total Admissions`, `Total Discharges`; tooltip: `Discharges Net Flow` |
| Weekday profile | Matrix heat-map | Rows `DayName`, Columns `AdmissionType`, Values `Total Admissions` |

## Page 3 - Bed Occupancy & Resource Utilization
*Audience: bed management / operations. All visuals are interval-based; thresholds are **illustrative** and configurable through the two parameter slicers.*

| Visual | Type | Fields |
|---|---|---|
| KPI cards | Card | `Staffed Beds`, `Avg Daily Census`, `Available Bed Count`, `Bed Occupancy Rate` |
| Total vs occupied beds | Clustered bar | `DepartmentName`; `Staffed Beds`, `Avg Daily Census` |
| Available vs occupied distribution | 100% stacked bar | `DepartmentName`; Occupied = `Avg Daily Census`, Available = `Available Bed Count` |
| Department-wise occupancy | Bar | `DepartmentName` x `Bed Occupancy Rate`; **bar colour = Field value `BOR Color`** |
| Daily occupancy trend | Line | X `Date`; Y `Bed Occupancy Rate`; constant lines at the two thresholds |
| Bed type distribution | Column | `DimBeds[BedType]` x `Staffed Beds`; second visual: `FactAdmissions[BedType]` x `Occupied Bed-Days` |
| Peak occupancy periods | Matrix heat-map | Rows `DepartmentName`; Columns `MonthShort`; Values `Bed Occupancy Rate`; conditional background by rules (green < high, amber >= high, red >= critical) |
| Capacity utilisation comparison | Scatter | X `Bed Occupancy Rate`; Y `Doctor Utilization Rate`; size `Total Admissions`; details `DepartmentName` |
| Parameter slicers | BOR High / Critical | Labelled "illustrative operational thresholds" |

## Page 4 - Department-wise Performance
*Audience: department heads. Provide context; do not rank departments as "good/poor" from one metric.*

| Visual | Type | Fields |
|---|---|---|
| Admissions / discharges | Clustered bar | `DepartmentName`; `Total Admissions`, `Total Discharges` |
| ALOS | Bar | `ALOS` |
| Readmission rate | Bar with data labels; tooltip shows `Eligible Discharges` (denominator) | `30-Day Readmission Rate` |
| Doctor utilisation | Bar coloured by `Doctor Util Color` | `Doctor Utilization Rate` |
| Patients per doctor | Bar | `Patients per Doctor` |
| Comparison matrix | Matrix | Rows `DepartmentName`; values: Admissions, Discharges, ALOS, BOR, Readmission rate, Doctor utilisation, Patients per doctor, Avg ED wait; conditional formatting = data bars / colour scale (relative), caption "colour shows relative position, not a verdict" |
| Context card | Text box | "High readmission may reflect chronic case-mix (cardiology, pulmonology, oncology); high volume is demand, not inefficiency" |
| Department slicer (single select) | | drives a detail card strip |

## Page 5 - Waiting Time & Patient Flow (ED)
*Audience: ED manager.*

| Visual | Type | Fields |
|---|---|---|
| KPI cards | Card | `Avg ED Wait (min)`, `Median ED Wait (min)`, `ED Turnaround (min)`, `ED Visits`, `LWBS Rate` |
| Wait by triage | Clustered bar + marker | `TriageLabel`; `Avg ED Wait (min)`, target from `TargetWaitMin` (illustrative) ; tooltip `% Seen within Target` |
| Wait by department | Bar | `DepartmentName` x `Avg ED Wait (min)` |
| Hourly arrivals | Column | X `FactEmergencyVisits[ArrivalHour]`; Y `ED Visits` (highlight 17-21h with conditional colour) |
| Hour-of-day waits | Line | X `ArrivalHour`; Y `Avg ED Wait (min)` |
| Day-of-week analysis | Column / heat-map | X `DayName`; Y `ED Visits`; heat-map rows `DayName` x cols `ArrivalHour` (volume) |
| Disposition distribution | Bar | `DispositionType` x `ED Visits` |
| ED visits trend | Line | `YearMonth` x `ED Visits` |
| Admitted-patient turnaround | Card + column | `ED Turnaround - Admitted (min)` vs overall (boarding signal) |
| Slicers | Triage level (`TriageLevel`), Date, Hour range | |

---

## Interactivity checklist
- Cross-filtering on; edit interactions so slicers don't filter the "previous period" table.
- Drill-through page *Department detail* (drill-through field `DepartmentName`).
- Tooltip pages for KPI cards (sparkline + definition) and for department bars.
- Bookmarks: "Winter surge", "Monsoon surge" (date + department filters) for management demos.
- Accessibility: alt text on visuals, tab order, >= 4.5:1 text contrast, no colour-only status (labels/icons accompany colours).

## Performance tips
Import mode; hide unused columns; disable *Auto date/time*; `Occupied Bed-Days` iterates dates, so avoid placing it on a visual that has both `Date` and many categories at once (e.g. daily x department heat-map - use month granularity there).
