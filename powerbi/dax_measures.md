# DAX Measures

> **Status:** the measures below are loaded in the generated Power BI project (`powerbi/HospitalOperations.pbip`, built by `scripts/build_pbip.py`). Verified in the real Power BI Desktop engine (v2.159): all 53 measures evaluate without error and 64/64 KPI comparisons match `analysis/kpi_checkpoints.csv` - see `analysis/powerbi_verification.md` (re-run with `scripts/verify_powerbi_model.ps1`). They were also reconciled with PostgreSQL SQL and an independent pandas replica (`analysis/kpi_reconciliation.md`).

**Conventions**
- All measures live in a disconnected table `_Measures` (Home > Enter Data > one blank row, then move measures into it, hide the column).
- Boolean columns arrive from the CSV as `True/False` (set data type *True/False* in Power Query).
- A **report-level filter** `DimDate[InReportingWindow] = TRUE` is applied. It removes the ~60 carry-over inpatients admitted in Nov-Dec 2022 from volume KPIs while their bed-days still count for occupancy on 1 Jan 2023 (the occupancy measure removes the date filter and iterates dates itself).
- Period membership: **admissions** by `AdmissionDate`; **discharges / ALOS / readmission rate** by `DischargeDate` (inactive relationship activated with `USERELATIONSHIP`); **ED** by `ArrivalDate`; **doctor activity** by `ActivityDate`.

---

## 0. Support measures

```DAX
Days in Period = COUNTROWS ( DimDate )   -- rows of DimDate in the current filter context

Staffed Beds =
CALCULATE ( COUNTROWS ( DimBeds ), DimBeds[IsStaffed] = TRUE () )

Active Doctors = DISTINCTCOUNT ( FactDoctorActivity[DoctorID] )
```

*Blank handling:* `COUNTROWS` returns blank for an empty context; wrap with `+ 0` only where a 0 is wanted on a card.

---

## 1. Total Admissions
```DAX
Total Admissions =
CALCULATE ( COUNTROWS ( FactAdmissions ), FactAdmissions[IsAdmission] = TRUE () )
```
- **Explanation:** counts admission requests that actually occupied a bed (Discharged + still-Admitted). **Cancelled** requests are excluded and reported separately.
- **Business relevance:** headline demand/volume KPI.
- **Aggregation:** row count; additive across department, type, time (not additive across patients).
- **Blanks/incomplete:** open stays (no discharge date yet) **are** admissions; cancelled rows are removed by `IsAdmission`.

```DAX
Cancelled Admission Requests =
CALCULATE ( COUNTROWS ( FactAdmissions ), FactAdmissions[IsCancelled] = TRUE () )
```

## 2. Total Unique Patients
```DAX
Total Unique Patients =
CALCULATE ( DISTINCTCOUNT ( FactAdmissions[PatientID] ), FactAdmissions[IsAdmission] = TRUE () )
```
- **Explanation:** distinct patients with >= 1 admission in the context. **Not additive** (a patient admitted in two departments counts once in each department but once in the total).
- **Relevance:** population served; denominator for admissions per patient.
- **Avoids double counting:** counts only `FactAdmissions` (never joins ED/doctor facts). ED-only walk-ins are *not* inpatients and are excluded by design.

## 3. Total Discharges
```DAX
Total Discharges =
CALCULATE (
    COUNTROWS ( FactAdmissions ),
    FactAdmissions[IsCompleted] = TRUE (),
    USERELATIONSHIP ( DimDate[Date], FactAdmissions[DischargeDate] )
)
```
- **Explanation:** completed stays, dated by discharge date (so a month's discharges line up with the month's outflow).
- **Relevance:** outflow side of patient flow; compared with admissions to see net flow.
- **Blanks:** open stays have a blank `DischargeDate` and are never counted.

## 4. Average Length of Stay (ALOS)
```DAX
ALOS =
CALCULATE (
    AVERAGE ( FactAdmissions[LOSDays] ),
    FactAdmissions[IsCompleted] = TRUE (),
    USERELATIONSHIP ( DimDate[Date], FactAdmissions[DischargeDate] )
)
```
- **Explanation:** mean of (`DischargeDate - AdmissionDate`) over **completed** stays discharged in the period. `LOSDays` is blank for open/cancelled rows and `AVERAGE` ignores blanks - double protection.
- **Relevance:** efficiency of patient flow; drives bed demand (bed-days = admissions x ALOS).
- **Aggregation:** *weighted* (average of rows, not an average of department averages) - never average the department ALOS values.
- **Optional separate metric** (ongoing stays, explicitly *not* ALOS):
```DAX
Open Stays at Snapshot = CALCULATE ( COUNTROWS ( FactAdmissions ), FactAdmissions[IsOpenStay] = TRUE () )
```

## 5. Bed Occupancy Rate (BOR)
```DAX
Occupied Bed-Days =
SUMX (
    VALUES ( DimDate[Date] ),
    VAR _d = DimDate[Date]
    RETURN
        CALCULATE (
            COUNTROWS ( FactAdmissions ),
            FactAdmissions[IsAdmission] = TRUE (),
            FactAdmissions[AdmissionDate] <= _d,
            FactAdmissions[BedReleaseDate] > _d,      -- midnight census: bed released on discharge date is free that day
            REMOVEFILTERS ( DimDate )                  -- drop the date filter; the iterator supplies the date
        )
)

Available Bed-Days = [Staffed Beds] * [Days in Period]

Bed Occupancy Rate = DIVIDE ( [Occupied Bed-Days], [Available Bed-Days] )
```
- **Explanation:** for each date in the selection count admissions whose stay interval `[AdmissionDate, BedReleaseDate)` covers it, sum over the period, divide by staffed beds x days. `BedReleaseDate` = discharge date, or snapshot+1 for open stays.
- **Why not admissions / beds:** admissions are a flow, beds a stock; ratio is unit-inconsistent and ignores stay length. **Why not `BedStatus`:** it is today's snapshot, useless for history.
- **Department / bed-type slicers** work because `DimDepartments` filters both `FactAdmissions` and `DimBeds` (staffed denominator).
- **Aggregation:** ratio of sums (never average the daily/department percentages).
- **Assumption:** staffed beds are constant over time (`IsStaffed` = status <> Closed) - historical staffing is not in the data.
- **Blanks:** cancelled rows excluded; open stays counted through the snapshot date.
- **Performance:** one CALCULATE per visible date (<= 1,157 rows, ~16k fact rows) - fine in Import mode.

## 6. Average Emergency Waiting Time
```DAX
Avg ED Wait (min) = AVERAGE ( FactEmergencyVisits[WaitMinutes] )
```
- **Explanation:** arrival -> consultation. `WaitMinutes` is blank for **Left-Without-Being-Seen** (never consulted), so they are excluded and shown through `LWBS Rate`.
- **Relevance:** patient access/safety; core ED KPI.
- **Aggregation:** weighted mean over visits.

## 7. Median Emergency Waiting Time
```DAX
Median ED Wait (min) = MEDIAN ( FactEmergencyVisits[WaitMinutes] )
```
- **Explanation:** typical patient's wait, robust to long tails. `MEDIAN` ignores blanks. Never average medians across groups - always recompute.

## 8. Emergency Department Turnaround Time
```DAX
ED Turnaround (min) = AVERAGE ( FactEmergencyVisits[TurnaroundMinutes] )
```
- **Explanation:** arrival -> final disposition (discharge, admission to ward, transfer, LWBS...). All visits have a disposition time, so no blanks. For admitted patients this includes **boarding** time waiting for a ward bed.
```DAX
ED Turnaround - Admitted (min) =
CALCULATE ( AVERAGE ( FactEmergencyVisits[TurnaroundMinutes] ), FactEmergencyVisits[IsAdmitted] = TRUE () )
```

## 9. 30-Day Readmission Rate
```DAX
Eligible Discharges =
CALCULATE (
    COUNTROWS ( FactAdmissions ),
    FactAdmissions[IsReadmissionEligible] = TRUE (),
    FactAdmissions[FollowupComplete] = TRUE (),
    USERELATIONSHIP ( DimDate[Date], FactAdmissions[DischargeDate] )
)

Readmissions 30d =
CALCULATE ( [Eligible Discharges], FactAdmissions[Readmitted30d] = TRUE () )

30-Day Readmission Rate = DIVIDE ( [Readmissions 30d], [Eligible Discharges] )
```
- **Explanation:** share of **eligible index discharges** followed by an unplanned (Emergency) readmission within 30 days. Eligible = Discharged, not Deceased, not transferred to another facility, with a full 30-day follow-up window before the snapshot (`FollowupComplete`).
- **Why flags live on `FactAdmissions`:** numerator and denominator come from the same table and the same row grain, so the rate cannot be distorted by a join to `FactReadmissions`. `FactReadmissions` is used for *patterns* (days-to-readmit buckets, department-to-department flow).
- **Right-censoring:** the last ~30 days of discharges have an incomplete follow-up window and are excluded; show the card as blank/"n/a" rather than 0% for such periods (`DIVIDE` returns blank when the denominator is 0).
- **Aggregation:** ratio of sums.

```DAX
-- Pattern analysis from FactReadmissions (department-to-department flow, matrix: IndexDepartment rows x ReadmitDepartment columns)
Readmission Flow Count =
CALCULATE ( COUNTROWS ( FactReadmissions ), FactReadmissions[Within30Days] = TRUE () )

Readmission Flow Count (to dept) =
CALCULATE (
    COUNTROWS ( FactReadmissions ), FactReadmissions[Within30Days] = TRUE (),
    USERELATIONSHIP ( DimDepartments[DepartmentID], FactReadmissions[ReadmitDepartmentID] )
)
```

## 10. Doctor Utilization Rate
```DAX
Doctor Utilization Rate =
DIVIDE ( SUM ( FactDoctorActivity[ConsultationHours] ), SUM ( FactDoctorActivity[ScheduledHours] ) )
```
- **Explanation:** consultation hours / **scheduled available** hours. Ratio of sums, so a doctor's long shift weighs proportionally more.
- **Relevance:** workload balance and staffing adequacy (both over- and under-use).
- **Blanks:** days without a roster entry have no row (not zero scheduled hours).
- **Caution:** consultation hours exclude non-clinical work (notes, teaching, procedures not logged) - hence a "proxy" metric (see KPI dictionary).

---

## 11. Admission Growth Rate
```DAX
Prev Period Admissions =
VAR _min = MIN ( DimDate[Date] )
VAR _max = MAX ( DimDate[Date] )
VAR _len = _max - _min + 1
RETURN
    CALCULATE (
        [Total Admissions],
        REMOVEFILTERS ( DimDate ),
        DATESBETWEEN ( DimDate[Date], _min - _len, _max - _len ),
        DimDate[InReportingWindow] = TRUE ()
    )

Admission Growth Rate = DIVIDE ( [Total Admissions] - [Prev Period Admissions], [Prev Period Admissions] )
```
- **Explanation:** growth vs. the immediately preceding period **of equal length** (month vs previous ~30 days, year vs previous year). Blank when no earlier data (e.g. first 2023 period). Used for the Executive page "vs previous period" deltas.
- **Alternatives:** `Admission Growth MoM = DIVIDE([Total Admissions] - CALCULATE([Total Admissions], DATEADD(DimDate[Date], -1, MONTH)), CALCULATE([Total Admissions], DATEADD(DimDate[Date], -1, MONTH)))`; for YoY use `SAMEPERIODLASTYEAR`.

## 12. Discharge Growth Rate
```DAX
Prev Period Discharges =
VAR _min = MIN ( DimDate[Date] )
VAR _max = MAX ( DimDate[Date] )
VAR _len = _max - _min + 1
RETURN
    CALCULATE ( [Total Discharges], REMOVEFILTERS ( DimDate ),
                DATESBETWEEN ( DimDate[Date], _min - _len, _max - _len ), DimDate[InReportingWindow] = TRUE () )

Discharge Growth Rate = DIVIDE ( [Total Discharges] - [Prev Period Discharges], [Prev Period Discharges] )
```
*(The inactive discharge relationship is activated inside `[Total Discharges]`; `DATESBETWEEN` filters `DimDate[Date]`, which that relationship then propagates.)*

## 13. Patients per Doctor
```DAX
Patients per Doctor = DIVIDE ( [Total Unique Patients], [Active Doctors] )
```
- **Explanation:** unique admitted patients per doctor who worked in the period. Both inputs respond to the department slicer (`DimDepartments` filters `FactAdmissions` and `FactDoctorActivity`) and to `DimDate`; no cross-fact join is created.
- **Companion:** `Patients Attended per Doctor-Day = DIVIDE ( SUM ( FactDoctorActivity[PatientsAttended] ), COUNTROWS ( FactDoctorActivity ) )` (consultation-level workload incl. OPD/ED).

## 14. Available Bed Count
```DAX
Avg Daily Census = DIVIDE ( [Occupied Bed-Days], [Days in Period] )
Available Bed Count = [Staffed Beds] - [Avg Daily Census]          -- average free staffed beds in the period

Beds Available Now (snapshot) =
CALCULATE ( COUNTROWS ( DimBeds ), DimBeds[BedStatus] = "Available" )   -- as at 31 Dec 2025 only
```
- **Explanation:** the first is the period-average free staffed beds; the second is the *current* snapshot count (label it "as at snapshot").

## 15. Peak Admission Day
```DAX
Peak Admission Day =
VAR _t = ADDCOLUMNS ( VALUES ( DimDate[Date] ), "Adm", [Total Admissions] )
VAR _mx = MAXX ( _t, [Adm] )
RETURN MINX ( FILTER ( _t, [Adm] = _mx ), DimDate[Date] )      -- earliest date if tied

Peak Day Admissions = MAXX ( ADDCOLUMNS ( VALUES ( DimDate[Date] ), "Adm", [Total Admissions] ), [Adm] )

Peak Weekday =
VAR _t = ADDCOLUMNS ( VALUES ( DimDate[DayName] ), "Adm", [Total Admissions] )
RETURN MAXX ( TOPN ( 1, _t, [Adm], DESC ), DimDate[DayName] )
```
- **Relevance:** staffing - the single busiest day and the structurally busiest weekday (the latter is the actionable one).

## 16. Department-wise Patient Load
```DAX
Dept Patient Load (avg daily census) = [Avg Daily Census]     -- use with DimDepartments on rows
Dept Load Share % = DIVIDE ( [Occupied Bed-Days], CALCULATE ( [Occupied Bed-Days], ALLSELECTED ( DimDepartments ) ) )
Dept Admission Share % = DIVIDE ( [Total Admissions], CALCULATE ( [Total Admissions], ALLSELECTED ( DimDepartments ) ) )
```
- **Explanation:** "load" = average inpatients in-house (bed-days / days) *and* share of total bed-days; admissions share shows volume. Both are needed: a department can admit few patients but carry a heavy load through long stays.

## 17. Average Daily Admissions
```DAX
Avg Daily Admissions = DIVIDE ( [Total Admissions], [Days in Period] )
```

## 18. Emergency Admission Percentage
```DAX
Emergency Admission % =
DIVIDE ( CALCULATE ( [Total Admissions], FactAdmissions[AdmissionType] = "Emergency" ), [Total Admissions] )
```

---

## Supporting measures for the pages

```DAX
ED Visits = COUNTROWS ( FactEmergencyVisits )
LWBS Rate = DIVIDE ( CALCULATE ( COUNTROWS ( FactEmergencyVisits ), FactEmergencyVisits[IsLWBS] = TRUE () ), [ED Visits] )
ED Admit Rate = DIVIDE ( CALCULATE ( [ED Visits], FactEmergencyVisits[IsAdmitted] = TRUE () ), [ED Visits] )
% Seen within Target =
DIVIDE ( CALCULATE ( COUNTROWS ( FactEmergencyVisits ), FactEmergencyVisits[MetWaitTarget] = 1 ),
         CALCULATE ( COUNTROWS ( FactEmergencyVisits ), NOT ISBLANK ( FactEmergencyVisits[MetWaitTarget] ) ) )
Avg Wait Hour Index = DIVIDE ( [Avg ED Wait (min)], CALCULATE ( [Avg ED Wait (min)], REMOVEFILTERS ( FactEmergencyVisits[ArrivalHour] ) ) )

Discharges Net Flow = [Total Admissions] - [Total Discharges]
Cancellation Rate = DIVIDE ( [Cancelled Admission Requests], [Total Admissions] + [Cancelled Admission Requests] )
Saturated Doctor-Days % =
DIVIDE ( COUNTROWS ( FILTER ( FactDoctorActivity, FactDoctorActivity[ConsultationHours] >= 0.95 * FactDoctorActivity[ScheduledHours] ) ),
         COUNTROWS ( FactDoctorActivity ) )
```
> A doctor-day is "saturated" when consultation hours reach >= 95% of scheduled hours (illustrative overload flag).

## Configurable thresholds (what-if parameters) and conditional formatting

Create two parameters (Modeling > New parameter > Numeric range): **BOR High Threshold** (0.50-1.00, step 0.01, default 0.85) and **BOR Critical Threshold** (0.50-1.00, step 0.01, default 0.95). Power BI generates the tables and `[BOR High Threshold Value]`, `[BOR Critical Threshold Value]` measures. Equivalent hand-written DAX:

```DAX
BOR High Threshold = GENERATESERIES ( 0.5, 1, 0.01 )
BOR High Threshold Value = SELECTEDVALUE ( 'BOR High Threshold'[BOR High Threshold], 0.85 )
BOR Critical Threshold = GENERATESERIES ( 0.5, 1, 0.01 )
BOR Critical Threshold Value = SELECTEDVALUE ( 'BOR Critical Threshold'[BOR Critical Threshold], 0.95 )

BOR Status =
SWITCH ( TRUE (),
    ISBLANK ( [Bed Occupancy Rate] ), BLANK (),
    [Bed Occupancy Rate] >= [BOR Critical Threshold Value], "Critical",
    [Bed Occupancy Rate] >= [BOR High Threshold Value], "High",
    "Normal" )

BOR Color =   -- Format > Conditional formatting > Field value
SWITCH ( [BOR Status], "Critical", "#C0392B", "High", "#E6A117", "Normal", "#2E8B57", "#B8C2CC" )

Doctor Util Color =
VAR u = [Doctor Utilization Rate]
RETURN SWITCH ( TRUE (), ISBLANK ( u ), "#B8C2CC", u >= 0.95, "#C0392B", u >= 0.85, "#E6A117", u < 0.55, "#7FB3D5", "#2E8B57" )

KPI Delta Color = IF ( [Admission Growth Rate] >= 0, "#1A9E9A", "#1F5FA8" )   -- neutral: growth is not automatically good or bad
```
Label the thresholds on the page as **"illustrative operational thresholds - set by hospital policy"**.

## Optional: DAX calendar (if you prefer to create DimDate in the model)
```DAX
DimDate =
ADDCOLUMNS ( CALENDAR ( DATE ( 2022, 11, 1 ), DATE ( 2025, 12, 31 ) ),
    "Year", YEAR ( [Date] ), "Quarter", QUARTER ( [Date] ), "MonthNumber", MONTH ( [Date] ),
    "MonthShort", FORMAT ( [Date], "mmm" ), "YearMonth", FORMAT ( [Date], "yyyy-mm" ),
    "DayOfWeekNumber", WEEKDAY ( [Date], 2 ), "DayName", FORMAT ( [Date], "dddd" ),
    "InReportingWindow", [Date] >= DATE ( 2023, 1, 1 ) )
```
Then *Table tools > Mark as date table > Date*. (The shipped `DimDate.csv` already contains these columns plus `YearMonthSort`, `WeekStart`, `MonthStart`; sort `MonthName` by `MonthNumber` and `YearMonth` by `YearMonthSort`.)
