# KPI Dictionary

**Classification used throughout**
- **A = Actual operational KPI** - computed directly from recorded events (a dated admission, a timestamped ED event, a recorded readmission).
- **P = Proxy metric** - an approximation because the underlying data is incomplete or definitions had to be assumed. Proxies are labelled in every dashboard tooltip.

Reporting window 2023-01-01..2025-12-31. Values shown are the reconciled results for the whole window (`analysis/kpi_checkpoints.csv`; SQL and DAX-logic agree). Data is synthetic.

| # | KPI | Type | Result (2023-25) |
|---|---|---|---|
| 1 | Total Admissions | A | 15,865 |
| 2 | Total Unique Patients | A | 12,311 |
| 3 | Total Discharges | A | 15,843 |
| 4 | ALOS | A | 4.98 days |
| 5 | Bed Occupancy Rate | **P** | 70.7% (79,025 / 111,792 bed-days) |
| 6 | Avg ED Waiting Time | A | 50.8 min |
| 7 | Median ED Waiting Time | A | 41.2 min |
| 8 | ED Turnaround Time | A | 308 min |
| 9 | 30-Day Readmission Rate | **P** (unplanned = Emergency type) | 8.63% (1,264 / 14,655) |
| 10 | Doctor Utilization Rate | **P** | 79.5% |
| 11 | Admission Growth Rate | A | +6.6% (2024 vs 2023), +1.9% (2025 vs 2024) |
| 12 | Discharge Growth Rate | A | +6.9% / +1.7% |
| 13 | Patients per Doctor | **P** | 212 admitted patients per active doctor (hospital-wide) |
| 14 | Available Bed Count | **P** | 29.9 average free staffed beds |
| 15 | Peak Admission Day | A | computed in DAX (date of maximum daily admissions) |
| 16 | Department-wise Patient Load | A/P | avg daily census & share of bed-days |
| 17 | Average Daily Admissions | A | 14.5 |
| 18 | Emergency Admission % | A | 61.7% |

---

## 1. Total Admissions - *Actual*
| Field | Definition |
|---|---|
| Business definition | Admission requests that occupied an inpatient bed during the period |
| Formula | COUNT(admissions) where status in (Discharged, Admitted) by `admission_date` |
| Numerator / denominator | count of rows / n.a. |
| Source | `admissions` (`FactAdmissions[IsAdmission]`) |
| Frequency | Daily; reported weekly/monthly |
| Interpretation | Demand volume. Compare with the same period last year and with discharges (net flow) |
| Assumptions | Cancelled requests excluded (reported separately); open stays included; carry-over inpatients admitted before 2023 excluded by reporting window |

## 2. Total Unique Patients - *Actual*
Distinct `patient_id` among admissions (non-cancelled) in the period. Not additive across departments. ED-only visitors (14,442 patients) are *not* inpatients and excluded. Interpretation: population served; 1.29 admissions per patient. Assumption: patient identity is reliable (no duplicate registrations).

## 3. Total Discharges - *Actual*
Count of `Discharged` admissions by `discharge_date`. Source `admissions`. Open stays and cancelled requests excluded. Net flow = admissions - discharges.

## 4. Average Length of Stay (ALOS) - *Actual*
| Field | Definition |
|---|---|
| Formula | SUM(discharge_date - admission_date) / COUNT(completed stays) for stays **discharged in the period** |
| Numerator / denominator | total completed bed-days / number of completed stays |
| Source | `admissions` |
| Interpretation | Efficiency of flow; longer stays consume bed capacity (bed-days = admissions x ALOS). Read with median and P90 - the distribution is right-skewed |
| Assumptions | **Completed admissions only**; open stays are *not* ALOS (a separate "open stay" count exists); day-cases not in data; LOS in whole days |

## 5. Bed Occupancy Rate (BOR) - *Proxy*
| Field | Definition |
|---|---|
| Formula | **Occupied bed-days / available staffed bed-days** for the selected period |
| Numerator | sum over days of beds occupied on that day (admission_date <= day < discharge_date; open stays to snapshot) |
| Denominator | staffed beds x number of days (staffed = bed_status <> Closed) |
| Source | `admissions`, `beds` (`fact_dept_daily_census`) |
| Frequency | Daily; reported monthly |
| Interpretation | Share of staffed capacity in use. Sustained > 85% (illustrative) = limited ability to absorb surges; < 60% = potential under-utilisation |
| Assumptions | Midnight census; same-day bed re-use; staffed beds constant over time (no historic staffing data) - hence *proxy*; **never** admissions / total beds; `bed_status` is a snapshot and is not used for history |

## 6. Average Emergency Waiting Time - *Actual*
`AVG(consultation_datetime - arrival_datetime)` over visits with a consultation. LWBS visits (no consultation) are excluded and reported through the LWBS rate. Interpretation: access; read by triage level - averages mix urgencies. Assumption: timestamps are accurate to the minute; 6 visits with negative waits were quarantined.

## 7. Median Emergency Waiting Time - *Actual*
50th percentile of the same distribution (`PERCENTILE_CONT(0.5)`; DAX `MEDIAN`). Robust to long tails; never average medians across groups.

## 8. Emergency Department Turnaround Time - *Actual*
`AVG(disposition_datetime - arrival_datetime)` over **all** visits. For admitted patients includes boarding until the ward transfer. Interpretation: total ED length of stay; the admitted-patient split indicates inpatient bed availability problems rather than ED efficiency.

## 9. 30-Day Readmission Rate - *Proxy*
| Field | Definition |
|---|---|
| Formula | eligible discharges followed by an **unplanned** readmission within 30 days / eligible discharges |
| Numerator | eligible index discharges with a row in `readmissions` where `days_between_admissions <= 30` |
| Denominator | **eligible discharged** index admissions: status Discharged, discharge_type not Deceased and not Transferred to Another Facility, with a complete 30-day follow-up window (discharge_date + 30 <= snapshot) |
| Source | `admissions`, `readmissions` (`vw_readmission_analysis`) |
| Frequency | Monthly (by discharge month) |
| Interpretation | Proxy for quality of discharge/transition; varies with case-mix - compare like with like and show denominators |
| Assumptions | Unplanned = `admission_type = Emergency` (no planned/unplanned flag exists - *proxy*); any department counts as a readmission; last ~30 days right-censored and excluded |

## 10. Doctor Utilization Rate - *Proxy*
`SUM(patient_consultation_hours) / SUM(scheduled_hours)`. Numerator: hours in patient contact; denominator: rostered available hours (days with no roster row = off duty). Interpretation: >= 85% (illustrative) leaves little slack for unplanned work; < 55% suggests spare capacity. Proxy because consultation hours exclude documentation, teaching, procedures and on-call time.

## 11-12. Admission / Discharge Growth Rate - *Actual*
`(current - previous) / previous`, previous = preceding period of equal length (or same period last year). Blank if no prior data. Neutral colour: growth is not automatically good/bad.

## 13. Patients per Doctor - *Proxy*
Unique admitted patients / distinct doctors with activity in the period (department level uses that department's doctors). Ignores shared care, OPD and ED load - complement with *patients attended per doctor-day*.

## 14. Available Bed Count - *Proxy*
Staffed beds - average daily census (period average of free staffed beds). A separate snapshot measure counts beds with `bed_status = 'Available'` as at 31 Dec 2025 only.

## 15. Peak Admission Day - *Actual*
Date with the highest admission count in the selection (earliest if tied); companion "Peak weekday" gives the structural pattern.

## 16. Department-wise Patient Load - *Actual / Proxy*
Average daily census (occupied bed-days / days) and share of total bed-days per department; paired with admissions share. Census is interval-based (see BOR).

## 17. Average Daily Admissions - *Actual*
Total admissions / calendar days in period.

## 18. Emergency Admission Percentage - *Actual*
Emergency admissions / total admissions. High values = unscheduled demand that cannot be smoothed by scheduling.

---

## Supporting / secondary metrics
LWBS rate (Left-Without-Being-Seen visits / ED visits) - A · % seen within illustrative triage target - P (targets illustrative) · ED admit rate - A · Cancellation rate - A · Saturated doctor-days % (>= 95% of scheduled hours) - P · Median/P90 LOS - A.

## Handling of blank / incomplete / cancelled records (all KPIs)
| Situation | Treatment |
|---|---|
| Cancelled admission | Excluded from admissions, patients, ALOS, occupancy; reported as "cancelled requests" |
| Open stay (no discharge yet) | Counted as an admission and in occupied bed-days through the snapshot; excluded from ALOS, discharges, readmission cohort |
| LWBS (no consultation time) | Excluded from waiting-time metrics; included in turnaround, volumes and LWBS rate |
| Missing diagnosis | Kept; shown as "Unspecified" |
| Follow-up window incomplete | Excluded from readmission denominator and numerator |
| Divide by zero / empty context | `DIVIDE()` returns blank, never 0% |
| Carry-over inpatients (admitted before 2023) | In occupancy only; out of volume KPIs |

## Illustrative thresholds (configurable - `config_thresholds`, Power BI parameters)
Occupancy: High >= 85%, Critical >= 95%, Under-utilised < 60% · Doctor utilisation: High >= 85%, Spare < 55% · ED wait targets by triage: 5 / 15 / 30 / 60 / 120 min. **These are not external standards.**
