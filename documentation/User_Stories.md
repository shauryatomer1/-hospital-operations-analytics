# User Stories and Acceptance Criteria

Format: *As a [role], I want [capability] so that [benefit].* Acceptance criteria use Given/When/Then. Priority via MoSCoW. FR = functional requirement in `FRD.md`.

---

### US-01 (M) Daily bed occupancy - Hospital Operations Manager (FR-04, FR-05)
**As a Hospital Operations Manager, I want to monitor daily bed occupancy so that I can identify capacity constraints and optimize bed allocation.**
- Given the Bed Occupancy page, when I choose any date range, then occupancy = occupied bed-days / staffed bed-days and equals the SQL value for the same range (checkpoint table).
- When occupancy for a department is >= the High threshold, then its bar turns amber; >= Critical, red; thresholds are editable and labelled "illustrative".
- Closed (unstaffed) beds are excluded from the denominator; cancelled and open stays are handled per the KPI dictionary.

### US-02 (M) Executive overview - CEO (FR-01, FR-19)
**As the Hospital CEO, I want a single page with admissions, discharges, ALOS, occupancy, readmission rate and their change vs the previous period so that I can judge overall efficiency in under a minute.**
- Given the Executive page, then 6 KPI cards show value + change vs previous period of equal length (blank if no prior data).
- Each card tooltip shows definition, numerator/denominator and the "actual/proxy" tag.
- Changing the date/department/admission-type slicer updates all visuals consistently.

### US-03 (M) ED waiting by hour and triage - ED Manager (FR-08)
**As the Emergency Department Manager, I want waiting times by hour of day and triage level so that I can schedule additional staff in the busiest windows.**
- Given the ED page, then arrivals by hour and average wait by hour are shown on the same hour axis (no dual axis).
- Waiting time by triage shows the illustrative target marker and "% seen within target".
- LWBS visits are excluded from waits and shown separately; median is provided next to mean.

### US-04 (M) ED boarding - ED Manager (FR-09)
**As the ED Manager, I want turnaround time of admitted patients split from discharged patients so that I can tell whether delays come from the ED or from inpatient bed availability.**
- Given admitted visits, then turnaround (arrival -> ward transfer) is shown with P50/P90 and by admitting department.
- Boarding by hospital-occupancy band is available.

### US-05 (M) Length of stay by department - Operations Manager (FR-07)
**As an Operations Manager, I want ALOS by department with median and P90 so that I can target departments whose long stays block beds.**
- Only completed (Discharged) stays are used; open stays are listed separately as a count.
- Departments are sorted by ALOS; the long-stay (>14 days) share is shown.

### US-06 (M) Department comparison with context - Department Head (FR-13)
**As a Department Head, I want to compare my department's volume, ALOS, readmissions, utilisation and occupancy with peers, with context, so that I can see where I differ without being judged on one metric.**
- Matrix shows readmission rate with its denominator; a note explains case-mix effects.
- No visual labels a department "poor"/"best"; colours indicate relative position only.

### US-07 (M) Readmission patterns - Department Head / Quality (FR-14)
**As a Department Head, I want 30-day readmissions by department, discharge type and age band so that I can target follow-up for high-risk patients.**
- Denominator = eligible discharged patients (alive, not transferred out, complete follow-up window).
- Readmission gap distribution (0-3, 4-7, 8-14, 15-30, 31-90 days) is available.
- Last ~30 days are not shown as 0% but as not available.

### US-08 (M) Doctor utilisation - Operations Manager / Department Head (FR-11)
**As an Operations Manager, I want doctor utilisation (consultation hours / scheduled hours) by department and shift so that I can rebalance rosters.**
- Utilisation is a ratio of sums; department values are not averages of doctor values.
- Over-threshold months and saturated doctor-days are highlighted.
- Doctor-level names are visible only on the drill-through page for authorised roles.

### US-09 (M) Discharge-day pattern - Bed Management Team (FR-16)
**As a member of the Bed Management Team, I want discharges by weekday so that I can see when beds free up relative to demand and push earlier discharges.**
- Discharges by weekday are shown with an index vs average; admissions by weekday are on the same page for comparison.

### US-10 (S) Seasonal planning - Operations Manager (FR-16)
**As an Operations Manager, I want department-by-month occupancy so that I can plan seasonal surge capacity.**
- A heat-map shows occupancy by department x month; peaks above the High threshold are visible; works across years via slicer.

### US-11 (S) Resource alignment - CEO / Operations Manager (FR-17)
**As a CEO, I want to see which departments combine high bed pressure with high or low doctor workload so that I can direct resources where they are actually constrained.**
- Scatter of occupancy vs doctor utilisation with segment labels; underlying table available.

### US-12 (S) Data trust - Business Analyst (FR-02, NFR)
**As a Business Analyst, I want automated validation and a reconciliation of KPIs between SQL and Power BI so that stakeholders can trust the numbers.**
- Running `python scripts/run_pipeline.py` regenerates data, runs 72 + 37 checks and reconciles KPIs; failures stop the pipeline.
- A validation report lists test, expected, actual, status and remediation.

### US-13 (S) Frequent patients - Care Management (FR-14)
**As a care manager, I want to see patients with repeat admissions and their share of bed-days so that I can propose case management.**
- Distribution of admissions per patient with bed-day share (SQL Q37); no patient-identifiable fields on the shared dashboard.

### US-14 (C) Cancelled requests - Operations Manager
**As an Operations Manager, I want cancelled/deferred admission requests by month and type so that I can spot planned-downtime or bed-shortage effects.**
- Cancellation rate by month; cancelled records excluded from volume KPIs.
