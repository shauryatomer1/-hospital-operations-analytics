# SQL execution summary

| Query | Title | Rows | Seconds |
|---|---|---|---|
| Q01 | Total unique patients (admitted vs ED-only vs registered) | 1 | 0.17 |
| Q02 | New vs returning admitted patients by year | 3 | 0.09 |
| Q03 | Age-group distribution of admissions | 6 | 0.08 |
| Q04 | Gender distribution by department (conditional aggregation) | 10 | 0.08 |
| Q05 | Monthly admission trend with growth and 3-month moving average | 36 | 0.08 |
| Q06 | Daily admissions with 7-day moving average and busiest days | 1096 | 0.01 |
| Q07 | Weekly admissions with week-over-week change | 158 | 0.08 |
| Q08 | Weekday demand profile by admission type | 7 | 0.08 |
| Q09 | Admission type distribution by department | 10 | 0.08 |
| Q10 | Monthly admissions vs discharges: net flow and cumulative inpatient change | 36 | 0.08 |
| Q11 | Department-wise admissions: share, rank and year-over-year growth | 10 | 0.08 |
| Q12 | Average length of stay by department (completed stays only) with P50 / P90 and long-stay share | 10 | 0.06 |
| Q13 | Discharge disposition pattern by department | 10 | 0.06 |
| Q14 | Discharges by weekday (weekend discharge dip) | 7 | 0.01 |
| Q15 | Cancelled admissions by month and type (deferral / no-bed cancellations) | 36 | 0.08 |
| Q16 | Bed inventory: total, staffed and CURRENT snapshot status by department | 10 | 0.00 |
| Q17 | Bed occupancy rate by department (occupied bed-days / staffed bed-days) with band | 10 | 0.01 |
| Q18 | High-occupancy periods: hospital-wide days >= 85% and longest consecutive streaks (gaps-and-islands) | 9 | 0.00 |
| Q19 | Seasonal occupancy heat-map: department x calendar month | 10 | 0.02 |
| Q20 | Weekday occupancy profile (hospital-wide) | 7 | 0.01 |
| Q21 | Peak occupancy days per department (top 3, ROW_NUMBER) | 30 | 0.02 |
| Q22 | ED waiting time: mean and median by month (arrival -> consultation, LWBS excluded) | 36 | 0.05 |
| Q23 | Waiting time by triage level vs illustrative target | 5 | 0.06 |
| Q24 | Hour-of-day ED arrivals, waits and walk-outs | 24 | 0.04 |
| Q25 | ED turnaround time by disposition (arrival -> final disposition) | 7 | 0.05 |
| Q26 | Left-without-being-seen rate by waiting-time band | 5 | 0.03 |
| Q27 | ED performance by routed department | 11 | 0.06 |
| Q28 | ED boarding vs hospital occupancy (does a full hospital slow the ED?) | 4 | 0.03 |
| Q29 | Doctor utilisation league table (consultation hours / scheduled hours) | 25 | 0.13 |
| Q30 | Department-wise doctor workload | 11 | 0.15 |
| Q31 | Utilisation by employment type and shift | 8 | 0.14 |
| Q32 | Months with doctor overload (utilisation >= high threshold) by department | 11 | 0.13 |
| Q33 | 30-day readmission rate: overall and by discharge year | 4 | 0.02 |
| Q34 | 30-day readmission rate by department (with sample size) | 10 | 0.07 |
| Q35 | Readmission risk patterns: gap distribution, discharge type, age and weekday of index discharge | 16 | 0.21 |
| Q36 | Patient flow across departments: index department -> readmitting department | 62 | 0.02 |
| Q37 | Frequent patients (3+ admissions): who are they and what do they cost in bed-days? | 9 | 0.12 |
| Q38 | Executive monthly KPI scorecard with year-over-year comparison | 36 | 0.28 |
| Q39 | Resource-alignment matrix: bed pressure vs doctor workload vs length of stay | 10 | 0.22 |
| Q40 | Demand-surge detection: department-months more than 1 SD above that department's own mean | 20 | 0.08 |
| Q41 | Patient flow via the ED: share of admissions arriving through the ED, and ED-to-admission conversion | 10 | 0.11 |
