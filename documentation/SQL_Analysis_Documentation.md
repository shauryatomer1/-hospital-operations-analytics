# SQL Analysis Documentation

41 queries in `database/analytical_queries.sql`, executed on PostgreSQL 16 against the cleaned dataset (all run without error; results saved in `analysis/sql_results/`). Every query lists its **business purpose** and the **decision it supports**.

Run: `python scripts/load_database.py --steps queries` (embedded PostgreSQL) or paste any block into psql/pgAdmin. Views used: `vw_patient_admission_summary`, `vw_bed_occupancy`, `vw_readmission_analysis`, `vw_emergency_performance`, `vw_doctor_utilization`, `vw_department_performance`, `vw_monthly_hospital_kpis`.

## Techniques coverage

| Technique | Queries using it |
|---|---|
| CTE | 9 |
| Window function | 16 |
| CASE | 5 |
| Conditional aggregation | 21 |
| Subquery | 14 |
| JOIN | 8 |
| Date functions | 2 |
| Percentile | 6 |
| UNION ALL | 2 |
| ROLLUP | 1 |
| Gaps-and-islands | 1 |

## A. Patient analysis

### Q01 - Total unique patients (admitted vs ED-only vs registered)
- **Business purpose:** separates the real inpatient population from registrations and ED-only walk-ins.
- **Decision supported:** sizes the patient base for capacity planning; stops "registered patients" being quoted as "patients treated".
- **SQL techniques:** Conditional aggregation, Subquery
- **Result preview** (1 rows):

| registered_patients_all_time | unique_admitted_patients | ed_only_patients | admissions | admissions_per_patient |
|---|---|---|---|---|
| 27007 | 12311 | 14442 | 15865 | 1.289 |

```sql
SELECT (SELECT COUNT(*) FROM patients)                                                    AS registered_patients_all_time,
       COUNT(DISTINCT patient_id) FILTER (WHERE NOT is_cancelled)                         AS unique_admitted_patients,
       (SELECT COUNT(DISTINCT patient_id) FROM emergency_visits e
         WHERE NOT EXISTS (SELECT 1 FROM admissions a WHERE a.patient_id = e.patient_id AND a.admission_status <> 'Cancelled')) AS ed_only_patients,
       COUNT(*) FILTER (WHERE NOT is_cancelled)                                           AS admissions,
       ROUND(COUNT(*) FILTER (WHERE NOT is_cancelled)::numeric
             / NULLIF(COUNT(DISTINCT patient_id) FILTER (WHERE NOT is_cancelled), 0), 3)  AS admissions_per_patient
FROM vw_patient_admission_summary WHERE in_reporting_window;
```

### Q02 - New vs returning admitted patients by year
- **Business purpose:** measures how much demand comes from patients new to the hospital (registered that year) vs known patients.
- **Decision supported:** marketing/referral investment vs chronic-care pathway planning (returning patients drive readmission risk).
- **SQL techniques:** CTE, Conditional aggregation, Subquery, Date functions
- **Result preview** (3 rows):

| year | admitted_patients | new_patients | returning_patients | new_pct |
|---|---|---|---|---|
| 2023 | 4139 | 3408 | 731 | 82.3 |
| 2024 | 4595 | 3495 | 1100 | 76.1 |
| 2025 | 4727 | 3506 | 1221 | 74.2 |

```sql
WITH pa AS (
    SELECT DISTINCT admission_year AS yr, patient_id, registration_date
    FROM vw_patient_admission_summary WHERE in_reporting_window AND NOT is_cancelled)
SELECT yr AS year, COUNT(*) AS admitted_patients,
       COUNT(*) FILTER (WHERE registration_date >= MAKE_DATE(yr, 1, 1)) AS new_patients,
       COUNT(*) FILTER (WHERE registration_date <  MAKE_DATE(yr, 1, 1)) AS returning_patients,
       ROUND(100.0 * COUNT(*) FILTER (WHERE registration_date >= MAKE_DATE(yr, 1, 1)) / COUNT(*), 1) AS new_pct
FROM pa GROUP BY yr ORDER BY yr;
```

### Q03 - Age-group distribution of admissions
- **Business purpose:** demographic mix with the clinical consequences (stay length, emergency share) per age band.
- **Decision supported:** geriatric / paediatric service planning; staffing mix for older, longer-stay cohorts.
- **SQL techniques:** Window function, Conditional aggregation
- **Result preview** (6 rows):

| age_group | admissions | share_pct | alos_days | emergency_pct |
|---|---|---|---|---|
| 0-14 | 2278 | 14.4 | 3.41 | 71.9 |
| 15-29 | 1927 | 12.1 | 4.23 | 53.9 |
| 30-44 | 3069 | 19.3 | 4.79 | 57.2 |
| 45-59 | 4376 | 27.6 | 5.34 | 61.2 |

```sql
SELECT age_group, COUNT(*) AS admissions,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct,
       ROUND(AVG(los_days), 2) AS alos_days,
       ROUND(100.0 * COUNT(*) FILTER (WHERE admission_type = 'Emergency') / COUNT(*), 1) AS emergency_pct
FROM vw_patient_admission_summary WHERE in_reporting_window AND NOT is_cancelled
GROUP BY age_group ORDER BY MIN(age);
```

### Q04 - Gender distribution by department (conditional aggregation)
- **Business purpose:** checks service-line gender mix (e.g. cardiology skew) and flags data oddities such as males in obstetrics.
- **Decision supported:** facility design (single-sex bays), targeted screening campaigns.
- **SQL techniques:** Conditional aggregation
- **Result preview** (10 rows):

| department_name | male | female | other | female_pct |
|---|---|---|---|---|
| Obstetrics & Gynecology | 0 | 1867 | 0 | 100.0 |
| Critical Care (ICU) | 500 | 553 | 1 | 52.5 |
| General Surgery | 1126 | 1252 | 8 | 52.5 |
| General Medicine | 1235 | 1338 | 9 | 51.8 |

```sql
SELECT department_name,
       COUNT(*) FILTER (WHERE gender = 'Male')   AS male,
       COUNT(*) FILTER (WHERE gender = 'Female') AS female,
       COUNT(*) FILTER (WHERE gender = 'Other')  AS other,
       ROUND(100.0 * COUNT(*) FILTER (WHERE gender = 'Female') / COUNT(*), 1) AS female_pct
FROM vw_patient_admission_summary WHERE in_reporting_window AND NOT is_cancelled
GROUP BY department_name ORDER BY female_pct DESC;
```

### Q05 - Monthly admission trend with growth and 3-month moving average
- **Business purpose:** shows direction and seasonality of demand and smooths month-to-month noise.
- **Decision supported:** annual budget / staffing rosters; confirms whether "admissions are increasing".
- **SQL techniques:** Window function
- **Result preview** (36 rows):

| year_month | admissions | mom_growth_pct | moving_avg_3m |
|---|---|---|---|
| 2023-01 | 416 |  | 416.0 |
| 2023-02 | 373 | -10.3 | 394.5 |
| 2023-03 | 438 | 17.4 | 409.0 |
| 2023-04 | 413 | -5.7 | 408.0 |

```sql
SELECT admission_year_month AS year_month, COUNT(*) AS admissions,
       ROUND(100.0 * (COUNT(*) - LAG(COUNT(*)) OVER (ORDER BY admission_year_month))
             / NULLIF(LAG(COUNT(*)) OVER (ORDER BY admission_year_month), 0), 1) AS mom_growth_pct,
       ROUND(AVG(COUNT(*)) OVER (ORDER BY admission_year_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1) AS moving_avg_3m
FROM vw_patient_admission_summary WHERE in_reporting_window AND NOT is_cancelled
GROUP BY admission_year_month ORDER BY 1;
```


## B. Admission and discharge analysis

### Q06 - Daily admissions with 7-day moving average and busiest days
- **Business purpose:** operational (day-level) demand curve; the calendar spine keeps zero-admission days visible.
- **Decision supported:** surge-day staffing; identifying outlier days that need root-cause review.
- **SQL techniques:** Window function, JOIN
- **Result preview** (1096 rows):

| admission_date | day_short | admissions | moving_avg_7d | busiest_day_rank |
|---|---|---|---|---|
| 2023-01-01 | Sun | 3 | 3.00 | 1093 |
| 2023-01-02 | Mon | 18 | 10.50 | 241 |
| 2023-01-03 | Tue | 15 | 12.00 | 469 |
| 2023-01-04 | Wed | 12 | 12.00 | 698 |

```sql
SELECT dd.full_date AS admission_date, dd.day_short,
       COUNT(a.admission_id) AS admissions,
       ROUND(AVG(COUNT(a.admission_id)) OVER (ORDER BY dd.full_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2) AS moving_avg_7d,
       RANK() OVER (ORDER BY COUNT(a.admission_id) DESC) AS busiest_day_rank
FROM dim_date dd
LEFT JOIN admissions a ON a.admission_date = dd.full_date AND a.admission_status <> 'Cancelled'
WHERE dd.in_reporting_window
GROUP BY dd.full_date, dd.day_short ORDER BY dd.full_date;
```

### Q07 - Weekly admissions with week-over-week change
- **Business purpose:** mid-granularity view used for roster planning (weekly cadence).
- **Decision supported:** weekly bed-meeting forecast; detect multi-week surges early.
- **SQL techniques:** Window function
- **Result preview** (158 rows):

| week_start | admissions | wow_change | moving_avg_4w |
|---|---|---|---|
| 2022-12-26 | 3 |  | 3.0 |
| 2023-01-02 | 88 | 85 | 45.5 |
| 2023-01-09 | 88 | 0 | 59.7 |
| 2023-01-16 | 96 | 8 | 68.8 |

```sql
SELECT admission_week_start AS week_start, COUNT(*) AS admissions,
       COUNT(*) - LAG(COUNT(*)) OVER (ORDER BY admission_week_start) AS wow_change,
       ROUND(AVG(COUNT(*)) OVER (ORDER BY admission_week_start ROWS BETWEEN 3 PRECEDING AND CURRENT ROW), 1) AS moving_avg_4w
FROM vw_patient_admission_summary WHERE in_reporting_window AND NOT is_cancelled
GROUP BY admission_week_start ORDER BY 1;
```

### Q08 - Weekday demand profile by admission type
- **Business purpose:** emergency demand is flat across the week; elective/referral demand is not - quantifies the difference.
- **Decision supported:** move elective scheduling to smooth bed demand; staff weekends for emergencies, not electives.
- **SQL techniques:** Conditional aggregation
- **Result preview** (7 rows):

| weekday | admission_iso_dow | emergency | elective | referral | total |
|---|---|---|---|---|---|
| Mon | 1 | 1683 | 830 | 546 | 3059 |
| Tue | 2 | 1446 | 654 | 475 | 2575 |
| Wed | 3 | 1401 | 649 | 446 | 2496 |
| Thu | 4 | 1367 | 625 | 474 | 2466 |

```sql
SELECT admission_day_name AS weekday, admission_iso_dow,
       COUNT(*) FILTER (WHERE admission_type = 'Emergency') AS emergency,
       COUNT(*) FILTER (WHERE admission_type = 'Elective')  AS elective,
       COUNT(*) FILTER (WHERE admission_type = 'Referral')  AS referral,
       COUNT(*) AS total
FROM vw_patient_admission_summary WHERE in_reporting_window AND NOT is_cancelled
GROUP BY admission_day_name, admission_iso_dow ORDER BY admission_iso_dow;
```

### Q09 - Admission type distribution by department
- **Business purpose:** emergency-dependence of each department (unpredictable load) vs elective/referral (schedulable load).
- **Decision supported:** which departments can use scheduling levers to relieve capacity, and which need surge capacity.
- **SQL techniques:** Conditional aggregation
- **Result preview** (10 rows):

| department_name | admissions | emergency_pct | elective_pct | referral_pct |
|---|---|---|---|---|
| Critical Care (ICU) | 1054 | 83.9 | 0.0 | 16.1 |
| General Medicine | 2582 | 77.8 | 6.2 | 16.0 |
| Pediatrics | 1832 | 74.5 | 8.5 | 17.0 |
| Pulmonology | 984 | 72.4 | 8.1 | 19.5 |

```sql
SELECT department_name, COUNT(*) AS admissions,
       ROUND(100.0 * COUNT(*) FILTER (WHERE admission_type = 'Emergency') / COUNT(*), 1) AS emergency_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE admission_type = 'Elective')  / COUNT(*), 1) AS elective_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE admission_type = 'Referral')  / COUNT(*), 1) AS referral_pct
FROM vw_patient_admission_summary WHERE in_reporting_window AND NOT is_cancelled
GROUP BY department_name ORDER BY emergency_pct DESC;
```

### Q10 - Monthly admissions vs discharges: net flow and cumulative inpatient change
- **Business purpose:** tests whether inflow outpaces outflow (bed pressure building) using a running sum of net flow.
- **Decision supported:** if cumulative net flow keeps rising, discharge capacity - not admissions - is the bottleneck.
- **SQL techniques:** CTE, Window function, Subquery, JOIN
- **Result preview** (36 rows):

| year_month | admissions | discharges | net_flow | cumulative_net_flow |
|---|---|---|---|---|
| 2023-01 | 416 | 402 | 14 | 14 |
| 2023-02 | 373 | 371 | 2 | 16 |
| 2023-03 | 438 | 428 | 10 | 26 |
| 2023-04 | 413 | 429 | -16 | 10 |

```sql
WITH a AS (SELECT admission_year_month AS ym, COUNT(*) AS admissions FROM vw_patient_admission_summary
           WHERE in_reporting_window AND NOT is_cancelled GROUP BY 1),
     d AS (SELECT dd.year_month AS ym, COUNT(*) AS discharges FROM admissions x JOIN dim_date dd ON dd.full_date = x.discharge_date
           WHERE x.admission_status = 'Discharged' AND dd.in_reporting_window GROUP BY 1)
SELECT a.ym AS year_month, a.admissions, COALESCE(d.discharges, 0) AS discharges,
       a.admissions - COALESCE(d.discharges, 0) AS net_flow,
       SUM(a.admissions - COALESCE(d.discharges, 0)) OVER (ORDER BY a.ym) AS cumulative_net_flow
FROM a LEFT JOIN d USING (ym) ORDER BY a.ym;
```

### Q11 - Department-wise admissions: share, rank and year-over-year growth
- **Business purpose:** volume league table with direction of travel per department.
- **Decision supported:** where demand is growing fastest -> where to add capacity first.
- **SQL techniques:** Window function, Conditional aggregation
- **Result preview** (10 rows):

| department_name | admissions | share_pct | volume_rank | adm_2023 | adm_2024 | adm_2025 | growth_2023_to_2025_pct |
|---|---|---|---|---|---|---|---|
| General Medicine | 2582 | 16.3 | 1 | 836 | 849 | 897 | 7.3 |
| General Surgery | 2386 | 15.0 | 2 | 756 | 809 | 821 | 8.6 |
| Cardiology | 2270 | 14.3 | 3 | 716 | 797 | 757 | 5.7 |
| Obstetrics & Gynecology | 1867 | 11.8 | 4 | 618 | 615 | 634 | 2.6 |

```sql
SELECT department_name,
       COUNT(*) AS admissions,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct,
       RANK() OVER (ORDER BY COUNT(*) DESC) AS volume_rank,
       COUNT(*) FILTER (WHERE admission_year = 2023) AS adm_2023,
       COUNT(*) FILTER (WHERE admission_year = 2024) AS adm_2024,
       COUNT(*) FILTER (WHERE admission_year = 2025) AS adm_2025,
       ROUND(100.0 * (COUNT(*) FILTER (WHERE admission_year = 2025) - COUNT(*) FILTER (WHERE admission_year = 2023))
             / NULLIF(COUNT(*) FILTER (WHERE admission_year = 2023), 0), 1) AS growth_2023_to_2025_pct
FROM vw_patient_admission_summary WHERE in_reporting_window AND NOT is_cancelled
GROUP BY department_name ORDER BY admissions DESC;
```

### Q12 - Average length of stay by department (completed stays only) with P50 / P90 and long-stay share
- **Business purpose:** mean alone hides tails; P90 and the >14-day share expose outlier stays that block beds.
- **Decision supported:** targets for discharge-planning reviews; which departments to benchmark against clinical pathways.
- **SQL techniques:** Conditional aggregation, Subquery, Percentile
- **Result preview** (10 rows):

| department_name | completed_stays | alos_days | median_los | p90_los | max_los | long_stay_pct |
|---|---|---|---|---|---|---|
| Critical Care (ICU) | 1054 | 6.93 | 5.0 | 15.0 | 60 | 10.34 |
| Neurology | 816 | 6.93 | 6.0 | 12.0 | 39 | 6.25 |
| Pulmonology | 984 | 6.40 | 6.0 | 11.0 | 26 | 3.56 |
| Orthopedics | 1252 | 6.29 | 6.0 | 10.0 | 41 | 3.83 |

```sql
SELECT department_name, COUNT(*) AS completed_stays,
       ROUND(AVG(los_days), 2) AS alos_days,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY los_days) AS median_los,
       PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY los_days) AS p90_los,
       MAX(los_days) AS max_los,
       ROUND(100.0 * COUNT(*) FILTER (WHERE los_days > (SELECT value FROM config_thresholds WHERE parameter = 'long_stay_days')) / COUNT(*), 2) AS long_stay_pct
FROM vw_patient_admission_summary
WHERE is_completed AND discharge_date >= (SELECT reporting_start FROM data_window)
GROUP BY department_name ORDER BY alos_days DESC;
```

### Q13 - Discharge disposition pattern by department
- **Business purpose:** outcome mix (home / follow-up / transfer / LAMA / death) per department; context for LOS and readmission.
- **Decision supported:** high LAMA -> counselling/cost review; high transfer-out -> service-gap review; deaths -> clinical audit trigger.
- **SQL techniques:** CTE, Conditional aggregation, Subquery
- **Result preview** (10 rows):

| department_name | discharges | home_pct | home_followup_pct | transfer_out_pct | lama_pct | mortality_pct |
|---|---|---|---|---|---|---|
| General Medicine | 2574 | 87.2 | 5.6 | 2.1 | 3.6 | 1.5 |
| General Surgery | 2383 | 86.5 | 9.2 | 2.3 | 1.4 | 0.6 |
| Cardiology | 2271 | 83.8 | 9.8 | 3.0 | 1.5 | 1.9 |
| Obstetrics & Gynecology | 1861 | 96.6 | 1.5 | 1.0 | 0.8 | 0.1 |

```sql
SELECT department_name, COUNT(*) AS discharges,
       ROUND(100.0 * COUNT(*) FILTER (WHERE discharge_type = 'Discharged Home') / COUNT(*), 1)                     AS home_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE discharge_type = 'Discharged Home with Follow-up') / COUNT(*), 1)      AS home_followup_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE discharge_type = 'Transferred to Another Facility') / COUNT(*), 1)    AS transfer_out_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE discharge_type = 'Left Against Medical Advice') / COUNT(*), 1)        AS lama_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE discharge_type = 'Deceased') / COUNT(*), 1)                           AS mortality_pct
FROM vw_patient_admission_summary
WHERE is_completed AND discharge_date >= (SELECT reporting_start FROM data_window)
GROUP BY department_name ORDER BY discharges DESC;
```

### Q14 - Discharges by weekday (weekend discharge dip)
- **Business purpose:** discharges bunching on Mondays and thinning on weekends signals a weekend discharge-process gap.
- **Decision supported:** weekend discharge-coordinator / pharmacy / transport cover; target = release beds earlier in the week.
- **SQL techniques:** Window function, JOIN
- **Result preview** (7 rows):

| weekday | iso_dow | discharges | share_pct | index_vs_average |
|---|---|---|---|---|
| Mon | 1 | 3558 | 22.5 | 1.57 |
| Tue | 2 | 2043 | 12.9 | 0.90 |
| Wed | 3 | 2090 | 13.2 | 0.92 |
| Thu | 4 | 2248 | 14.2 | 0.99 |

```sql
SELECT dd.day_short AS weekday, dd.iso_day_of_week AS iso_dow, COUNT(*) AS discharges,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct,
       ROUND(COUNT(*)::numeric / AVG(COUNT(*)) OVER (), 2) AS index_vs_average
FROM admissions a JOIN dim_date dd ON dd.full_date = a.discharge_date
WHERE a.admission_status = 'Discharged' AND dd.in_reporting_window
GROUP BY dd.day_short, dd.iso_day_of_week ORDER BY dd.iso_day_of_week;
```

### Q15 - Cancelled admissions by month and type (deferral / no-bed cancellations)
- **Business purpose:** cancellations are lost activity and patient inconvenience; spikes expose OT downtime or bed shortages.
- **Decision supported:** trigger an RCA when the monthly cancellation rate exceeds the normal band (here ~2%).
- **SQL techniques:** Conditional aggregation
- **Result preview** (36 rows):

| year_month | requests | cancelled | cancelled_elective | cancelled_referral | cancellation_rate_pct |
|---|---|---|---|---|---|
| 2023-01 | 421 | 5 | 3 | 2 | 1.19 |
| 2023-02 | 384 | 11 | 6 | 5 | 2.86 |
| 2023-03 | 446 | 8 | 4 | 4 | 1.79 |
| 2023-04 | 422 | 9 | 5 | 4 | 2.13 |

```sql
SELECT admission_year_month AS year_month,
       COUNT(*) AS requests,
       COUNT(*) FILTER (WHERE is_cancelled) AS cancelled,
       COUNT(*) FILTER (WHERE is_cancelled AND admission_type = 'Elective') AS cancelled_elective,
       COUNT(*) FILTER (WHERE is_cancelled AND admission_type = 'Referral') AS cancelled_referral,
       ROUND(100.0 * COUNT(*) FILTER (WHERE is_cancelled) / COUNT(*), 2) AS cancellation_rate_pct
FROM vw_patient_admission_summary WHERE in_reporting_window
GROUP BY admission_year_month ORDER BY 1;
```


## C. Bed utilisation

### Q16 - Bed inventory: total, staffed and CURRENT snapshot status by department
- **Business purpose:** the capacity baseline. NOTE: bed_status is a point-in-time snapshot, never a historical measure.
- **Decision supported:** confirms how many beds are actually staffed (closed beds reduce the capacity denominator).
- **SQL techniques:** Conditional aggregation, JOIN
- **Result preview** (10 rows):

| department_name | total_beds | staffed_beds | occupied_now | available_now | under_maintenance | closed |
|---|---|---|---|---|---|---|
| General Medicine | 16 | 16 | 15 | 0 | 1 | 0 |
| General Surgery | 14 | 14 | 8 | 5 | 1 | 0 |
| Orthopedics | 12 | 11 | 6 | 5 | 0 | 1 |
| Cardiology | 12 | 12 | 9 | 3 | 0 | 0 |

```sql
SELECT d.department_name, COUNT(*) AS total_beds,
       COUNT(*) FILTER (WHERE b.bed_status <> 'Closed')      AS staffed_beds,
       COUNT(*) FILTER (WHERE b.bed_status = 'Occupied')     AS occupied_now,
       COUNT(*) FILTER (WHERE b.bed_status = 'Available')    AS available_now,
       COUNT(*) FILTER (WHERE b.bed_status = 'Maintenance')  AS under_maintenance,
       COUNT(*) FILTER (WHERE b.bed_status = 'Closed')       AS closed
FROM beds b JOIN departments d USING (department_id)
GROUP BY d.department_name ORDER BY total_beds DESC;
```

### Q17 - Bed occupancy rate by department (occupied bed-days / staffed bed-days) with band
- **Business purpose:** the correct BOR - interval based, never admissions/beds. Bands use configurable ILLUSTRATIVE thresholds.
- **Decision supported:** departments in the High/Critical band need surge/flow actions; Under-utilised ones are candidates to lend beds.
- **SQL techniques:** CASE, Subquery
- **Result preview** (10 rows):

| department_name | occupied_bed_days | staffed_bed_days | bed_occupancy_rate | pct_days_high_or_critical | average_band |
|---|---|---|---|---|---|
| General Medicine | 15103 | 17536 | 0.8613 | 64.1 | High |
| Cardiology | 11015 | 13152 | 0.8375 | 55.5 | Normal |
| Critical Care (ICU) | 7316 | 8768 | 0.8344 | 63.0 | Normal |
| Pulmonology | 6300 | 7672 | 0.8212 | 67.2 | Normal |

```sql
SELECT department_name, SUM(occupied_beds) AS occupied_bed_days, SUM(staffed_beds) AS staffed_bed_days,
       ROUND(SUM(occupied_beds)::numeric / SUM(staffed_beds), 4) AS bed_occupancy_rate,
       ROUND(100.0 * AVG((occupancy_band IN ('High','Critical'))::int), 1) AS pct_days_high_or_critical,
       CASE WHEN SUM(occupied_beds)::numeric / SUM(staffed_beds) >= (SELECT value FROM config_thresholds WHERE parameter = 'bor_critical') THEN 'Critical'
            WHEN SUM(occupied_beds)::numeric / SUM(staffed_beds) >= (SELECT value FROM config_thresholds WHERE parameter = 'bor_high') THEN 'High'
            WHEN SUM(occupied_beds)::numeric / SUM(staffed_beds) <  (SELECT value FROM config_thresholds WHERE parameter = 'bor_low') THEN 'Under-utilised'
            ELSE 'Normal' END AS average_band
FROM vw_bed_occupancy GROUP BY department_name ORDER BY bed_occupancy_rate DESC;
```

### Q18 - High-occupancy periods: hospital-wide days >= 85% and longest consecutive streaks (gaps-and-islands)
- **Business purpose:** isolates sustained pressure periods (not just single bad days) using the classic date-minus-row_number trick.
- **Decision supported:** sustained streaks justify temporary surge beds / elective deferral protocols.
- **SQL techniques:** CTE, Window function, Subquery, Gaps-and-islands
- **Result preview** (9 rows):

| streak_start | streak_end | days_in_streak | avg_occupancy | peak_occupancy |
|---|---|---|---|---|
| 2025-09-24 | 2025-09-28 | 5 | 0.8784 | 0.9118 |
| 2025-10-09 | 2025-10-12 | 4 | 0.8824 | 0.9216 |
| 2024-04-17 | 2024-04-19 | 3 | 0.8889 | 0.9020 |
| 2024-12-12 | 2024-12-14 | 3 | 0.8693 | 0.8824 |

```sql
WITH daily AS (
    SELECT census_date, SUM(occupied_beds)::numeric / SUM(staffed_beds) AS occ
    FROM vw_bed_occupancy GROUP BY census_date),
flagged AS (
    SELECT census_date, occ, (occ >= (SELECT value FROM config_thresholds WHERE parameter = 'bor_high')) AS is_high FROM daily),
islands AS (
    SELECT census_date, occ, census_date - (ROW_NUMBER() OVER (ORDER BY census_date))::int AS grp FROM flagged WHERE is_high)
SELECT MIN(census_date) AS streak_start, MAX(census_date) AS streak_end, COUNT(*) AS days_in_streak,
       ROUND(AVG(occ), 4) AS avg_occupancy, ROUND(MAX(occ), 4) AS peak_occupancy
FROM islands GROUP BY grp HAVING COUNT(*) >= 2 ORDER BY days_in_streak DESC, streak_start LIMIT 15;
```

### Q19 - Seasonal occupancy heat-map: department x calendar month
- **Business purpose:** reveals which months stress which departments (conditional aggregation = pivot).
- **Decision supported:** seasonal staffing/bed plans (e.g. winter respiratory beds, monsoon medicine/paediatrics beds).
- **SQL techniques:** Conditional aggregation, Date functions
- **Result preview** (10 rows):

| department_name | jan | feb | mar | apr | may | jun | jul |
|---|---|---|---|---|---|---|---|
| Cardiology | 0.862 | 0.874 | 0.810 | 0.894 | 0.797 | 0.844 | 0.835 |
| Critical Care (ICU) | 0.806 | 0.894 | 0.806 | 0.718 | 0.772 | 0.819 | 0.871 |
| General Medicine | 0.730 | 0.781 | 0.806 | 0.851 | 0.882 | 0.884 | 0.940 |
| General Surgery | 0.653 | 0.618 | 0.558 | 0.668 | 0.558 | 0.580 | 0.600 |

```sql
SELECT department_name,
       ROUND(SUM(occupied_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 1)::numeric  / NULLIF(SUM(staffed_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 1), 0), 3) AS jan,
       ROUND(SUM(occupied_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 2)::numeric  / NULLIF(SUM(staffed_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 2), 0), 3) AS feb,
       ROUND(SUM(occupied_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 3)::numeric  / NULLIF(SUM(staffed_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 3), 0), 3) AS mar,
       ROUND(SUM(occupied_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 4)::numeric  / NULLIF(SUM(staffed_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 4), 0), 3) AS apr,
       ROUND(SUM(occupied_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 5)::numeric  / NULLIF(SUM(staffed_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 5), 0), 3) AS may,
       ROUND(SUM(occupied_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 6)::numeric  / NULLIF(SUM(staffed_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 6), 0), 3) AS jun,
       ROUND(SUM(occupied_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 7)::numeric  / NULLIF(SUM(staffed_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 7), 0), 3) AS jul,
       ROUND(SUM(occupied_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 8)::numeric  / NULLIF(SUM(staffed_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 8), 0), 3) AS aug,
       ROUND(SUM(occupied_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 9)::numeric  / NULLIF(SUM(staffed_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 9), 0), 3) AS sep,
       ROUND(SUM(occupied_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 10)::numeric / NULLIF(SUM(staffed_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 10), 0), 3) AS oct,
       ROUND(SUM(occupied_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 11)::numeric / NULLIF(SUM(staffed_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 11), 0), 3) AS nov,
       ROUND(SUM(occupied_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 12)::numeric / NULLIF(SUM(staffed_beds) FILTER (WHERE EXTRACT(MONTH FROM census_date) = 12), 0), 3) AS dec_
FROM vw_bed_occupancy GROUP BY department_name ORDER BY department_name;
```

### Q20 - Weekday occupancy profile (hospital-wide)
- **Business purpose:** shows which weekday the hospital is fullest/emptiest (end-of-day census).
- **Decision supported:** weekday-specific elective scheduling and discharge targets.
- **SQL techniques:** 
- **Result preview** (7 rows):

| weekday | iso_day_of_week | bed_occupancy_rate | avg_occupied_beds_per_dept_day |
|---|---|---|---|
| Mon | 1 | 0.6629 | 6.8 |
| Tue | 2 | 0.6961 | 7.1 |
| Wed | 3 | 0.7214 | 7.4 |
| Thu | 4 | 0.7350 | 7.5 |

```sql
SELECT day_short AS weekday, iso_day_of_week,
       ROUND(SUM(occupied_beds)::numeric / SUM(staffed_beds), 4) AS bed_occupancy_rate,
       ROUND(AVG(occupied_beds) * 1.0, 1) AS avg_occupied_beds_per_dept_day
FROM vw_bed_occupancy GROUP BY day_short, iso_day_of_week ORDER BY iso_day_of_week;
```

### Q21 - Peak occupancy days per department (top 3, ROW_NUMBER)
- **Business purpose:** the worst capacity-pressure days with context - when and how bad.
- **Decision supported:** evidence base for a surge-capacity business case and for scenario drills.
- **SQL techniques:** Window function, Subquery
- **Result preview** (30 rows):

| department_name | census_date | occupied_beds | staffed_beds | occupancy_rate | occupancy_band | rn |
|---|---|---|---|---|---|---|
| Cardiology | 2023-01-16 | 12 | 12 | 1.0000 | Critical | 1 |
| Cardiology | 2023-01-17 | 12 | 12 | 1.0000 | Critical | 2 |
| Cardiology | 2023-01-24 | 12 | 12 | 1.0000 | Critical | 3 |
| Critical Care (ICU) | 2023-01-01 | 8 | 8 | 1.0000 | Critical | 1 |

```sql
SELECT * FROM (
    SELECT department_name, census_date, occupied_beds, staffed_beds, occupancy_rate, occupancy_band,
           ROW_NUMBER() OVER (PARTITION BY department_name ORDER BY occupancy_rate DESC, census_date) AS rn
    FROM vw_bed_occupancy) t
WHERE rn <= 3 ORDER BY department_name, rn;
```


## D. Emergency operations

### Q22 - ED waiting time: mean and median by month (arrival -> consultation, LWBS excluded)
- **Business purpose:** the median is the typical patient's wait; the mean is pulled up by long tails - both are reported.
- **Decision supported:** detects deterioration windows (e.g. a staffing gap) and tracks improvement after interventions.
- **SQL techniques:** Conditional aggregation, Percentile
- **Result preview** (36 rows):

| year_month | seen_visits | avg_wait_min | median_wait_min | p90_wait_min |
|---|---|---|---|---|
| 2023-01 | 882 | 48.8 | 38.0 | 98.3 |
| 2023-02 | 807 | 49.2 | 38.7 | 98.7 |
| 2023-03 | 913 | 48.5 | 38.9 | 97.0 |
| 2023-04 | 882 | 48.0 | 37.0 | 94.5 |

```sql
SELECT year_month, COUNT(*) FILTER (WHERE wait_minutes IS NOT NULL) AS seen_visits,
       ROUND(AVG(wait_minutes), 1) AS avg_wait_min,
       ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY wait_minutes))::numeric, 1) AS median_wait_min,
       ROUND((PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY wait_minutes))::numeric, 1) AS p90_wait_min
FROM vw_emergency_performance GROUP BY year_month ORDER BY year_month;
```

### Q23 - Waiting time by triage level vs illustrative target
- **Business purpose:** urgency-weighted performance - a 45-min average is fine for level 4 but dangerous for level 2.
- **Decision supported:** prioritise improvement where compliance with the target is lowest and clinical risk highest.
- **SQL techniques:** Conditional aggregation, Percentile
- **Result preview** (5 rows):

| triage_label | seen_visits | target_min | avg_wait_min | median_wait_min | p90_wait_min | pct_within_target |
|---|---|---|---|---|---|---|
| 1 - Resuscitation | 1294 | 5 | 3.3 | 2.4 | 6.8 | 81.9 |
| 2 - Emergent | 5888 | 15 | 18.1 | 15.4 | 31.9 | 48.3 |
| 3 - Urgent | 14279 | 30 | 49.6 | 42.1 | 88.3 | 28.5 |
| 4 - Less Urgent | 9634 | 60 | 68.2 | 57.7 | 122.0 | 52.5 |

```sql
SELECT triage_label, COUNT(*) FILTER (WHERE wait_minutes IS NOT NULL) AS seen_visits, MAX(target_wait_min) AS target_min,
       ROUND(AVG(wait_minutes), 1) AS avg_wait_min,
       ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY wait_minutes))::numeric, 1) AS median_wait_min,
       ROUND((PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY wait_minutes))::numeric, 1) AS p90_wait_min,
       ROUND(100.0 * COUNT(*) FILTER (WHERE met_wait_target) / NULLIF(COUNT(*) FILTER (WHERE wait_minutes IS NOT NULL), 0), 1) AS pct_within_target
FROM vw_emergency_performance GROUP BY triage_label, triage_level ORDER BY triage_level;
```

### Q24 - Hour-of-day ED arrivals, waits and walk-outs
- **Business purpose:** matches ED demand to staffing hour by hour; shows where waits exceed what volume alone explains.
- **Decision supported:** shift start-times and break cover; add clinician hours in the peak and handover windows.
- **SQL techniques:** Window function, Conditional aggregation
- **Result preview** (24 rows):

| arrival_hour | visits | share_pct | avg_wait_min | lwbs_pct | high_acuity_pct |
|---|---|---|---|---|---|
| 0 | 700 | 1.96 | 31.4 | 0.71 | 20.3 |
| 1 | 548 | 1.54 | 29.7 | 1.09 | 20.4 |
| 2 | 431 | 1.21 | 32.1 | 0.46 | 20.0 |
| 3 | 340 | 0.95 | 30.0 | 0.88 | 18.8 |

```sql
SELECT arrival_hour, COUNT(*) AS visits,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_pct,
       ROUND(AVG(wait_minutes), 1) AS avg_wait_min,
       ROUND(100.0 * COUNT(*) FILTER (WHERE is_lwbs) / COUNT(*), 2) AS lwbs_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE triage_level <= 2) / COUNT(*), 1) AS high_acuity_pct
FROM vw_emergency_performance GROUP BY arrival_hour ORDER BY arrival_hour;
```

### Q25 - ED turnaround time by disposition (arrival -> final disposition)
- **Business purpose:** total ED length of stay, split by outcome; admitted patients include time boarding for a ward bed.
- **Decision supported:** a long admitted-patient turnaround points at inpatient bed availability, not ED efficiency.
- **SQL techniques:** Percentile
- **Result preview** (7 rows):

| disposition_type | visits | avg_turnaround_min | median_turnaround_min | p90_turnaround_min |
|---|---|---|---|---|
| Discharged Home | 18905 | 171 | 155 | 269 |
| Admitted | 9791 | 666 | 335 | 2099 |
| Referred for Outpatient Foll | 3927 | 167 | 153 | 265 |
| Transferred | 1187 | 273 | 247 | 453 |

```sql
SELECT disposition_type, COUNT(*) AS visits,
       ROUND(AVG(turnaround_minutes), 0) AS avg_turnaround_min,
       ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY turnaround_minutes))::numeric, 0) AS median_turnaround_min,
       ROUND((PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY turnaround_minutes))::numeric, 0) AS p90_turnaround_min
FROM vw_emergency_performance GROUP BY disposition_type ORDER BY visits DESC;
```

### Q26 - Left-without-being-seen rate by waiting-time band
- **Business purpose:** quantifies the patient-safety cost of long waits - the share who walk out before a clinician sees them.
- **Decision supported:** sets a maximum-acceptable wait trigger (e.g. activate fast-track when waits pass the band where LWBS rises).
- **SQL techniques:** CTE, CASE, Subquery, UNION ALL
- **Result preview** (5 rows):

| metric | wait_band | visits |
|---|---|---|
| LWBS (triage 3-5) | n/a (never seen) | 792 |
| seen patients by wait band | 1) <30 min | 5718 |
| seen patients by wait band | 2) 30-59 min | 11408 |
| seen patients by wait band | 3) 60-89 min | 5920 |

```sql
WITH v AS (
    SELECT is_lwbs,
           CASE WHEN is_lwbs THEN NULL
                WHEN wait_minutes < 30 THEN '1) <30 min' WHEN wait_minutes < 60 THEN '2) 30-59 min'
                WHEN wait_minutes < 90 THEN '3) 60-89 min' ELSE '4) 90+ min' END AS wait_band
    FROM vw_emergency_performance WHERE triage_level >= 3)
SELECT 'seen patients by wait band' AS metric, wait_band, COUNT(*) AS visits FROM v WHERE NOT is_lwbs GROUP BY wait_band
UNION ALL
SELECT 'LWBS (triage 3-5)', 'n/a (never seen)', COUNT(*) FROM v WHERE is_lwbs
ORDER BY 1, 2;
```

### Q27 - ED performance by routed department
- **Business purpose:** which specialty teams' ED patients wait longest and are most often admitted.
- **Decision supported:** specialist-on-call cover and consult-response targets for the slowest teams.
- **SQL techniques:** Conditional aggregation, Percentile
- **Result preview** (11 rows):

| department_name | ed_visits | avg_wait_min | median_wait_min | avg_turnaround_min | admit_rate_pct | lwbs_pct |
|---|---|---|---|---|---|---|
| Emergency Medicine | 11839 | 56.8 | 46.8 | 169 | 0.0 | 3.07 |
| Pediatrics | 7783 | 52.6 | 43.2 | 199 | 17.5 | 2.58 |
| General Medicine | 4517 | 48.0 | 38.7 | 515 | 44.5 | 1.51 |
| General Surgery | 2384 | 47.7 | 37.0 | 260 | 49.8 | 1.51 |

```sql
SELECT department_name, COUNT(*) AS ed_visits,
       ROUND(AVG(wait_minutes), 1) AS avg_wait_min,
       ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY wait_minutes))::numeric, 1) AS median_wait_min,
       ROUND(AVG(turnaround_minutes), 0) AS avg_turnaround_min,
       ROUND(100.0 * COUNT(*) FILTER (WHERE is_admitted) / COUNT(*), 1) AS admit_rate_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE is_lwbs) / COUNT(*), 2) AS lwbs_pct
FROM vw_emergency_performance GROUP BY department_name ORDER BY ed_visits DESC;
```

### Q28 - ED boarding vs hospital occupancy (does a full hospital slow the ED?)
- **Business purpose:** for admitted ED patients, time from consultation to ward transfer by occupancy band; plus the correlation coefficient.
- **Decision supported:** if boarding rises steeply at high occupancy, inpatient flow actions (earlier discharge) are the ED fix.
- **SQL techniques:** CTE, CASE, Subquery, JOIN, Percentile
- **Result preview** (4 rows):

| occ_band | admitted_visits | avg_minutes_consult_to_ward | median_minutes | corr_all_days |
|---|---|---|---|---|
| 1) <70% | 4275 | 553 | 287 | 0.096 |
| 2) 70-79% | 4293 | 674 | 310 | 0.096 |
| 3) 80-84% | 846 | 714 | 310 | 0.096 |
| 4) 85%+ | 377 | 798 | 316 | 0.096 |

```sql
WITH occ AS (SELECT census_date, SUM(occupied_beds)::numeric / SUM(staffed_beds) AS occ FROM vw_bed_occupancy GROUP BY census_date),
j AS (SELECT e.treatment_and_boarding_minutes AS tb, o.occ,
             CASE WHEN o.occ < 0.70 THEN '1) <70%' WHEN o.occ < 0.80 THEN '2) 70-79%' WHEN o.occ < 0.85 THEN '3) 80-84%' ELSE '4) 85%+' END AS occ_band
      FROM vw_emergency_performance e JOIN occ o ON o.census_date = e.arrival_date WHERE e.is_admitted)
SELECT occ_band, COUNT(*) AS admitted_visits, ROUND(AVG(tb), 0) AS avg_minutes_consult_to_ward,
       ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tb))::numeric, 0) AS median_minutes,
       ROUND((SELECT CORR(tb, occ)::numeric FROM j), 3) AS corr_all_days
FROM j GROUP BY occ_band ORDER BY occ_band;
```


## E. Doctor utilisation

### Q29 - Doctor utilisation league table (consultation hours / scheduled hours)
- **Business purpose:** individual workload with department context; ranks identify outliers in both directions.
- **Decision supported:** rebalance rosters - spare-capacity doctors can support saturated colleagues (within specialty).
- **SQL techniques:** Window function
- **Result preview** (25 rows):

| doctor_name | department_name | employment_type | shift | days_worked | scheduled_hours | consultation_hours | utilization_rate |
|---|---|---|---|---|---|---|---|
| Dr. Anjali Gupta | Emergency Medicine | Visiting Consultant | Morning | 294 | 1029.00 | 987.01 | 0.9592 |
| Dr. Tanvi More | Emergency Medicine | Full-Time | Morning | 885 | 7080.00 | 6621.07 | 0.9352 |
| Dr. Ananya Patil | Emergency Medicine | Part-Time | Evening | 445 | 2225.00 | 2002.72 | 0.9001 |
| Dr. Suresh Gupta | Cardiology | Full-Time | Evening | 893 | 7144.00 | 6405.38 | 0.8966 |

```sql
SELECT doctor_name, department_name, employment_type, shift,
       SUM(days_worked) AS days_worked, SUM(scheduled_hours) AS scheduled_hours, SUM(consultation_hours) AS consultation_hours,
       ROUND(SUM(consultation_hours) / SUM(scheduled_hours), 4) AS utilization_rate,
       SUM(patients_attended) AS patients_attended,
       RANK() OVER (PARTITION BY department_name ORDER BY SUM(consultation_hours) / SUM(scheduled_hours) DESC) AS rank_in_dept
FROM vw_doctor_utilization GROUP BY doctor_name, department_name, employment_type, shift
ORDER BY utilization_rate DESC LIMIT 25;
```

### Q30 - Department-wise doctor workload
- **Business purpose:** combines hours-based utilisation with patient-count workload and the size of the doctor pool.
- **Decision supported:** identifies departments where workload per doctor, not volume, is the constraint.
- **SQL techniques:** 
- **Result preview** (11 rows):

| department_name | doctors | scheduled_hours | consultation_hours | utilization_rate | patients_per_doctor_day | avg_shift_hours | saturated_days_pct |
|---|---|---|---|---|---|---|---|
| Pulmonology | 3 | 21512.00 | 18577.53 | 0.8636 | 25.9 | 8.00 | 49.4 |
| General Surgery | 6 | 31717.00 | 26693.64 | 0.8416 | 23.3 | 7.38 | 44.8 |
| Critical Care (ICU) | 5 | 29590.50 | 24504.45 | 0.8281 | 9.5 | 7.65 | 53.7 |
| Cardiology | 6 | 32979.00 | 27302.83 | 0.8279 | 20.4 | 7.41 | 59.5 |

```sql
SELECT department_name, COUNT(DISTINCT doctor_id) AS doctors,
       SUM(scheduled_hours) AS scheduled_hours, SUM(consultation_hours) AS consultation_hours,
       ROUND(SUM(consultation_hours) / SUM(scheduled_hours), 4) AS utilization_rate,
       ROUND(SUM(patients_attended)::numeric / SUM(days_worked), 1) AS patients_per_doctor_day,
       ROUND(SUM(scheduled_hours) / SUM(days_worked), 2) AS avg_shift_hours,
       ROUND(100.0 * SUM(saturated_days) / SUM(days_worked), 1) AS saturated_days_pct
FROM vw_doctor_utilization GROUP BY department_name ORDER BY utilization_rate DESC;
```

### Q31 - Utilisation by employment type and shift
- **Business purpose:** checks whether evening/night or part-time/visiting doctors carry disproportionate workload.
- **Decision supported:** shift-mix redesign; roster rules (e.g. cap saturated night coverage).
- **SQL techniques:** 
- **Result preview** (8 rows):

| employment_type | shift | doctors | utilization_rate | patients_per_doctor_day |
|---|---|---|---|---|
| Full-Time | Evening | 9 | 0.8010 | 24.7 |
| Full-Time | Morning | 13 | 0.8027 | 21.8 |
| Full-Time | Night | 8 | 0.8053 | 21.1 |
| Full-Time | Rotational | 13 | 0.7840 | 22.8 |

```sql
SELECT employment_type, shift, COUNT(DISTINCT doctor_id) AS doctors,
       ROUND(SUM(consultation_hours) / SUM(scheduled_hours), 4) AS utilization_rate,
       ROUND(SUM(patients_attended)::numeric / SUM(days_worked), 1) AS patients_per_doctor_day
FROM vw_doctor_utilization GROUP BY employment_type, shift ORDER BY employment_type, shift;
```

### Q32 - Months with doctor overload (utilisation >= high threshold) by department
- **Business purpose:** turns utilisation into a time series per department - shows when workload breaches the high band.
- **Decision supported:** temporary locum cover for the months/departments that repeatedly breach.
- **SQL techniques:** Conditional aggregation, Subquery
- **Result preview** (11 rows):

| department_name | months_over_high_threshold | months_observed | peak_monthly_utilization | peak_month |
|---|---|---|---|---|
| Pulmonology | 26 | 36 | 0.899 | 2023-08 |
| General Surgery | 11 | 36 | 0.872 | 2025-01 |
| Critical Care (ICU) | 9 | 36 | 0.892 | 2025-08 |
| Cardiology | 4 | 36 | 0.863 | 2024-02 |

```sql
SELECT department_name,
       COUNT(*) FILTER (WHERE doctor_utilization_rate >= (SELECT value FROM config_thresholds WHERE parameter = 'util_high')) AS months_over_high_threshold,
       COUNT(*) AS months_observed,
       ROUND(MAX(doctor_utilization_rate), 3) AS peak_monthly_utilization,
       (ARRAY_AGG(year_month ORDER BY doctor_utilization_rate DESC))[1] AS peak_month
FROM vw_department_performance WHERE doctor_utilization_rate IS NOT NULL
GROUP BY department_name ORDER BY months_over_high_threshold DESC, peak_monthly_utilization DESC;
```


## F. Readmissions

### Q33 - 30-day readmission rate: overall and by discharge year
- **Business purpose:** headline quality KPI. Denominator = ELIGIBLE discharges (alive, not transferred out, full 30-day follow-up).
- **Decision supported:** trend vs target; justification for transitional-care investment.
- **SQL techniques:** Conditional aggregation, ROLLUP
- **Result preview** (4 rows):

| year | eligible_discharges | readmissions_30d | readmission_rate_pct |
|---|---|---|---|
| 2023 | 4791 | 433 | 9.04 |
| 2024 | 5076 | 409 | 8.06 |
| 2025 | 4788 | 422 | 8.81 |
|  | 14655 | 1264 | 8.63 |

```sql
SELECT discharge_year AS year, COUNT(*) AS eligible_discharges, COUNT(*) FILTER (WHERE readmitted_30d) AS readmissions_30d,
       ROUND(100.0 * COUNT(*) FILTER (WHERE readmitted_30d) / COUNT(*), 2) AS readmission_rate_pct
FROM vw_readmission_analysis WHERE followup_complete GROUP BY ROLLUP (discharge_year) ORDER BY discharge_year NULLS LAST;
```

### Q34 - 30-day readmission rate by department (with sample size)
- **Business purpose:** department comparison with the denominator shown - small denominators must not be over-interpreted.
- **Decision supported:** where to pilot discharge-planning/follow-up programmes (high rate AND meaningful volume).
- **SQL techniques:** Window function, Conditional aggregation
- **Result preview** (10 rows):

| department_name | eligible_discharges | readmissions_30d | readmission_rate_pct | avg_index_los | rate_rank |
|---|---|---|---|---|---|
| Cardiology | 2088 | 347 | 16.62 | 4.9 | 1 |
| Pulmonology | 895 | 139 | 15.53 | 6.4 | 2 |
| Oncology | 709 | 103 | 14.53 | 5.6 | 3 |
| General Medicine | 2420 | 248 | 10.25 | 5.9 | 4 |

```sql
SELECT department_name, COUNT(*) AS eligible_discharges, COUNT(*) FILTER (WHERE readmitted_30d) AS readmissions_30d,
       ROUND(100.0 * COUNT(*) FILTER (WHERE readmitted_30d) / COUNT(*), 2) AS readmission_rate_pct,
       ROUND(AVG(index_los_days), 1) AS avg_index_los,
       RANK() OVER (ORDER BY COUNT(*) FILTER (WHERE readmitted_30d)::numeric / COUNT(*) DESC) AS rate_rank
FROM vw_readmission_analysis WHERE followup_complete GROUP BY department_name ORDER BY readmission_rate_pct DESC;
```

### Q35 - Readmission risk patterns: gap distribution, discharge type, age and weekday of index discharge
- **Business purpose:** who comes back, and how soon - one block, four lenses (UNION ALL of conditional aggregates).
- **Decision supported:** target follow-up calls to the highest-risk groups within the first week.
- **SQL techniques:** CASE, Conditional aggregation, UNION ALL
- **Result preview** (16 rows):

| lens | segment | n | rate_pct |
|---|---|---|---|
| age group | 0-14 | 2157 | 5.42 |
| age group | 15-29 | 1834 | 4.91 |
| age group | 30-44 | 2857 | 6.76 |
| age group | 45-59 | 3981 | 10.75 |

```sql
SELECT 'days to readmission' AS lens, CASE WHEN days_between_admissions <= 3 THEN '0-3 days' WHEN days_between_admissions <= 7 THEN '4-7 days'
            WHEN days_between_admissions <= 14 THEN '8-14 days' WHEN days_between_admissions <= 30 THEN '15-30 days' ELSE '31-90 days' END AS segment,
       COUNT(*) AS n, NULL::numeric AS rate_pct
FROM vw_readmission_analysis WHERE readmission_id IS NOT NULL AND followup_complete GROUP BY 2
UNION ALL
SELECT 'discharge type', discharge_type, COUNT(*), ROUND(100.0 * COUNT(*) FILTER (WHERE readmitted_30d) / COUNT(*), 2)
FROM vw_readmission_analysis WHERE followup_complete GROUP BY discharge_type
UNION ALL
SELECT 'age group', age_group, COUNT(*), ROUND(100.0 * COUNT(*) FILTER (WHERE readmitted_30d) / COUNT(*), 2)
FROM vw_readmission_analysis WHERE followup_complete GROUP BY age_group
UNION ALL
SELECT 'index discharge on weekend', CASE WHEN discharge_iso_dow >= 6 THEN 'Weekend' ELSE 'Weekday' END, COUNT(*),
       ROUND(100.0 * COUNT(*) FILTER (WHERE readmitted_30d) / COUNT(*), 2)
FROM vw_readmission_analysis WHERE followup_complete GROUP BY 2
ORDER BY 1, 2;
```

### Q36 - Patient flow across departments: index department -> readmitting department
- **Business purpose:** shows whether patients return to the same service or leak into General Medicine / ICU.
- **Decision supported:** cross-department pathways (e.g. cardiology patients returning via medicine) to include in discharge plans.
- **SQL techniques:** Window function, JOIN
- **Result preview** (62 rows):

| index_department | readmitted_to | readmissions_30d | pct_of_index_dept_readmissions |
|---|---|---|---|
| Cardiology | Cardiology | 271 | 76.8 |
| Cardiology | General Medicine | 37 | 10.5 |
| Cardiology | Critical Care (ICU) | 31 | 8.8 |
| Cardiology | Pulmonology | 5 | 1.4 |

```sql
SELECT d1.department_name AS index_department, d2.department_name AS readmitted_to,
       COUNT(*) AS readmissions_30d,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY d1.department_name), 1) AS pct_of_index_dept_readmissions
FROM vw_readmission_analysis r
JOIN departments d1 ON d1.department_id = r.department_id
JOIN departments d2 ON d2.department_id = r.readmit_department_id
WHERE r.readmitted_30d GROUP BY d1.department_name, d2.department_name ORDER BY d1.department_name, readmissions_30d DESC;
```

### Q37 - Frequent patients (3+ admissions): who are they and what do they cost in bed-days?
- **Business purpose:** a small group of patients consumes a disproportionate share of bed-days - classic care-management target.
- **Decision supported:** enrol in case-management / chronic-care programmes.
- **SQL techniques:** CTE, Window function, Subquery
- **Result preview** (9 rows):

| admissions_per_patient | patients | bed_days | pct_of_all_bed_days | avg_age | avg_departments |
|---|---|---|---|---|---|
| 1 | 9864 | 47553 | 60.4 | 41 | 1.00 |
| 2 | 1727 | 17795 | 22.6 | 46 | 1.45 |
| 3 | 481 | 7575 | 9.6 | 49 | 1.97 |
| 4 | 147 | 3042 | 3.9 | 52 | 2.44 |

```sql
WITH p AS (
    SELECT patient_id, COUNT(*) AS admissions, SUM(COALESCE(los_days, open_stay_days_to_date)) AS bed_days,
           COUNT(DISTINCT department_id) AS departments, MAX(age) AS age
    FROM vw_patient_admission_summary WHERE in_reporting_window AND NOT is_cancelled GROUP BY patient_id)
SELECT admissions AS admissions_per_patient, COUNT(*) AS patients, SUM(bed_days) AS bed_days,
       ROUND(100.0 * SUM(bed_days) / SUM(SUM(bed_days)) OVER (), 1) AS pct_of_all_bed_days,
       ROUND(AVG(age), 0) AS avg_age, ROUND(AVG(departments), 2) AS avg_departments
FROM p GROUP BY admissions ORDER BY admissions;
```


## G. Cross-functional / root-cause

### Q38 - Executive monthly KPI scorecard with year-over-year comparison
- **Business purpose:** one table for the management pack - current month vs same month last year for the core KPIs.
- **Decision supported:** board-level "are we getting better?" without opening the dashboard.
- **SQL techniques:** Window function
- **Result preview** (36 rows):

| year_month | admissions | discharges | alos_days | bed_occupancy_rate | median_wait_min | avg_turnaround_min | readmission_rate_30d |
|---|---|---|---|---|---|---|---|
| 2023-01 | 416 | 402 | 5.01 | 0.6559 | 38.0 | 246.7 | 0.0930 |
| 2023-02 | 373 | 371 | 4.86 | 0.6282 | 38.7 | 251.9 | 0.1143 |
| 2023-03 | 438 | 428 | 5.06 | 0.6977 | 38.9 | 245.7 | 0.1005 |
| 2023-04 | 413 | 429 | 5.02 | 0.6879 | 37.0 | 272.8 | 0.0927 |

```sql
SELECT year_month, admissions, discharges, ROUND(alos_days, 2) AS alos_days, bed_occupancy_rate,
       median_wait_min, avg_turnaround_min, readmission_rate_30d, doctor_utilization_rate,
       ROUND(bed_occupancy_rate - LAG(bed_occupancy_rate, 12) OVER (ORDER BY year_month), 4) AS occupancy_vs_prev_year_pts,
       ROUND(median_wait_min - LAG(median_wait_min, 12) OVER (ORDER BY year_month), 1) AS median_wait_vs_prev_year_min,
       admission_growth_yoy
FROM vw_monthly_hospital_kpis ORDER BY year_month;
```

### Q39 - Resource-alignment matrix: bed pressure vs doctor workload vs length of stay
- **Business purpose:** surfaces misallocation - departments with full beds but idle doctors (or the reverse).
- **Decision supported:** reallocate beds/nurses/doctor sessions; avoid blanket capacity adds.
- **SQL techniques:** CTE, CASE, Subquery, JOIN
- **Result preview** (10 rows):

| department_name | bed_occupancy | doctor_utilization | alos_days | alignment_segment |
|---|---|---|---|---|
| General Medicine | 0.861 | 0.781 | 5.85 | B. Bed pressure, doctors hav |
| Cardiology | 0.838 | 0.828 | 4.85 | D. Balanced / monitor |
| Critical Care (ICU) | 0.834 | 0.828 | 6.89 | D. Balanced / monitor |
| Pulmonology | 0.821 | 0.864 | 6.39 | C. Doctor pressure, beds hav |

```sql
WITH b AS (SELECT department_name, SUM(occupied_beds)::numeric / SUM(staffed_beds) AS bor FROM vw_bed_occupancy GROUP BY 1),
     d AS (SELECT department_name, SUM(consultation_hours) / SUM(scheduled_hours) AS util FROM vw_doctor_utilization GROUP BY 1),
     l AS (SELECT department_name, AVG(los_days) AS alos FROM vw_patient_admission_summary WHERE is_completed AND in_reporting_window GROUP BY 1)
SELECT b.department_name, ROUND(b.bor, 3) AS bed_occupancy, ROUND(d.util, 3) AS doctor_utilization, ROUND(l.alos, 2) AS alos_days,
       CASE WHEN b.bor >= (SELECT value FROM config_thresholds WHERE parameter = 'bor_high') AND d.util >= (SELECT value FROM config_thresholds WHERE parameter = 'util_high') THEN 'A. Capacity AND workload pressure'
            WHEN b.bor >= (SELECT value FROM config_thresholds WHERE parameter = 'bor_high') THEN 'B. Bed pressure, doctors have headroom -> flow/discharge focus'
            WHEN d.util >= (SELECT value FROM config_thresholds WHERE parameter = 'util_high') THEN 'C. Doctor pressure, beds have headroom -> staffing focus'
            WHEN b.bor < (SELECT value FROM config_thresholds WHERE parameter = 'bor_low') AND d.util < (SELECT value FROM config_thresholds WHERE parameter = 'util_low') THEN 'E. Under-utilised on both -> review capacity'
            ELSE 'D. Balanced / monitor' END AS alignment_segment
FROM b JOIN d USING (department_name) JOIN l USING (department_name) ORDER BY b.bor DESC;
```

### Q40 - Demand-surge detection: department-months more than 1 SD above that department's own mean
- **Business purpose:** z-scores each department against itself, so naturally busy departments are not always flagged.
- **Decision supported:** validates surge triggers (e.g. start winter plan when a department crosses +1 SD two months running).
- **SQL techniques:** CTE, Window function, Subquery
- **Result preview** (20 rows):

| department_name | year_month | admissions | dept_monthly_mean | z_score |
|---|---|---|---|---|
| Oncology | 2024-08 | 35 | 22.8 | 3.10 |
| Pediatrics | 2024-08 | 78 | 50.9 | 2.88 |
| General Surgery | 2024-04 | 85 | 66.3 | 2.26 |
| Critical Care (ICU) | 2025-08 | 38 | 29.3 | 2.03 |

```sql
WITH m AS (
    SELECT department_name, year_month, admissions,
           AVG(admissions) OVER (PARTITION BY department_name) AS mean_adm,
           STDDEV_SAMP(admissions) OVER (PARTITION BY department_name) AS sd_adm
    FROM vw_department_performance)
SELECT department_name, year_month, admissions, ROUND(mean_adm, 1) AS dept_monthly_mean,
       ROUND((admissions - mean_adm) / NULLIF(sd_adm, 0), 2) AS z_score
FROM m WHERE (admissions - mean_adm) / NULLIF(sd_adm, 0) >= 1.5
ORDER BY z_score DESC, department_name LIMIT 20;
```

### Q41 - Patient flow via the ED: share of admissions arriving through the ED, and ED-to-admission conversion
- **Business purpose:** ties the ED to inpatient demand - how much of each department's load is ED-driven, and how fast.
- **Decision supported:** departments with high ED-dependence need ED-to-ward fast-track pathways and reserved beds.
- **SQL techniques:** Conditional aggregation, JOIN
- **Result preview** (10 rows):

| department_name | admissions | via_ed | via_ed_pct | avg_consult_to_ward_min | avg_ed_los_min |
|---|---|---|---|---|---|
| Critical Care (ICU) | 1054 | 884 | 83.9 | 935 | 954 |
| General Medicine | 2582 | 2010 | 77.8 | 895 | 933 |
| Pediatrics | 1832 | 1365 | 74.5 | 307 | 345 |
| Pulmonology | 984 | 712 | 72.4 | 870 | 911 |

```sql
SELECT s.department_name, COUNT(*) AS admissions,
       COUNT(*) FILTER (WHERE s.came_via_ed) AS via_ed,
       ROUND(100.0 * COUNT(*) FILTER (WHERE s.came_via_ed) / COUNT(*), 1) AS via_ed_pct,
       ROUND(AVG(e.treatment_and_boarding_minutes) FILTER (WHERE s.came_via_ed), 0) AS avg_consult_to_ward_min,
       ROUND(AVG(e.turnaround_minutes) FILTER (WHERE s.came_via_ed), 0) AS avg_ed_los_min
FROM vw_patient_admission_summary s
LEFT JOIN vw_emergency_performance e ON e.emergency_visit_id = s.emergency_visit_id
WHERE s.in_reporting_window AND NOT s.is_cancelled
GROUP BY s.department_name ORDER BY via_ed_pct DESC;
```


## Reading guide / pitfalls handled

- **Occupancy** is always occupied bed-days / staffed bed-days from admission/discharge intervals - never admissions / beds, never `bed_status`.
- **ALOS/discharges** use `Discharged` status only; open stays and cancelled requests are separated.
- **Readmission** uses eligible discharges with a complete 30-day window; denominators are shown.
- **Calendar spine** (`dim_date`) used wherever zero-count days/months must stay visible.
- **No fact-to-fact joins that multiply rows** (ED, activity and admissions are aggregated separately before comparison).
