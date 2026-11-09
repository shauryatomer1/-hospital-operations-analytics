-- =====================================================================================
-- analytical_queries.sql | 41 business-driven queries on the hospital database
-- Each block:  -- @Qnn | title   then   Purpose / Decision supported   then one SELECT.
-- Run all via  python scripts/load_database.py --steps queries   (results -> analysis/sql_results/)
-- or paste any block into psql / pgAdmin / DBeaver.   Needs transformations.sql + views.sql.
-- Reporting window = 2023-01-01 .. 2025-12-31 (views already filter on it).  Thresholds are ILLUSTRATIVE.
-- =====================================================================================
SET search_path = hospital, public;

-- ######################################  A. PATIENT ANALYSIS  ######################################

-- @Q01 | Total unique patients (admitted vs ED-only vs registered)
-- Purpose : separates the real inpatient population from registrations and ED-only walk-ins.
-- Decision: sizes the patient base for capacity planning; stops "registered patients" being quoted as "patients treated".
SELECT (SELECT COUNT(*) FROM patients)                                                    AS registered_patients_all_time,
       COUNT(DISTINCT patient_id) FILTER (WHERE NOT is_cancelled)                         AS unique_admitted_patients,
       (SELECT COUNT(DISTINCT patient_id) FROM emergency_visits e
         WHERE NOT EXISTS (SELECT 1 FROM admissions a WHERE a.patient_id = e.patient_id AND a.admission_status <> 'Cancelled')) AS ed_only_patients,
       COUNT(*) FILTER (WHERE NOT is_cancelled)                                           AS admissions,
       ROUND(COUNT(*) FILTER (WHERE NOT is_cancelled)::numeric
             / NULLIF(COUNT(DISTINCT patient_id) FILTER (WHERE NOT is_cancelled), 0), 3)  AS admissions_per_patient
FROM vw_patient_admission_summary WHERE in_reporting_window;

-- @Q02 | New vs returning admitted patients by year
-- Purpose : measures how much demand comes from patients new to the hospital (registered that year) vs known patients.
-- Decision: marketing/referral investment vs chronic-care pathway planning (returning patients drive readmission risk).
WITH pa AS (
    SELECT DISTINCT admission_year AS yr, patient_id, registration_date
    FROM vw_patient_admission_summary WHERE in_reporting_window AND NOT is_cancelled)
SELECT yr AS year, COUNT(*) AS admitted_patients,
       COUNT(*) FILTER (WHERE registration_date >= MAKE_DATE(yr, 1, 1)) AS new_patients,
       COUNT(*) FILTER (WHERE registration_date <  MAKE_DATE(yr, 1, 1)) AS returning_patients,
       ROUND(100.0 * COUNT(*) FILTER (WHERE registration_date >= MAKE_DATE(yr, 1, 1)) / COUNT(*), 1) AS new_pct
FROM pa GROUP BY yr ORDER BY yr;

-- @Q03 | Age-group distribution of admissions
-- Purpose : demographic mix with the clinical consequences (stay length, emergency share) per age band.
-- Decision: geriatric / paediatric service planning; staffing mix for older, longer-stay cohorts.
SELECT age_group, COUNT(*) AS admissions,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct,
       ROUND(AVG(los_days), 2) AS alos_days,
       ROUND(100.0 * COUNT(*) FILTER (WHERE admission_type = 'Emergency') / COUNT(*), 1) AS emergency_pct
FROM vw_patient_admission_summary WHERE in_reporting_window AND NOT is_cancelled
GROUP BY age_group ORDER BY MIN(age);

-- @Q04 | Gender distribution by department (conditional aggregation)
-- Purpose : checks service-line gender mix (e.g. cardiology skew) and flags data oddities such as males in obstetrics.
-- Decision: facility design (single-sex bays), targeted screening campaigns.
SELECT department_name,
       COUNT(*) FILTER (WHERE gender = 'Male')   AS male,
       COUNT(*) FILTER (WHERE gender = 'Female') AS female,
       COUNT(*) FILTER (WHERE gender = 'Other')  AS other,
       ROUND(100.0 * COUNT(*) FILTER (WHERE gender = 'Female') / COUNT(*), 1) AS female_pct
FROM vw_patient_admission_summary WHERE in_reporting_window AND NOT is_cancelled
GROUP BY department_name ORDER BY female_pct DESC;

-- @Q05 | Monthly admission trend with growth and 3-month moving average
-- Purpose : shows direction and seasonality of demand and smooths month-to-month noise.
-- Decision: annual budget / staffing rosters; confirms whether "admissions are increasing".
SELECT admission_year_month AS year_month, COUNT(*) AS admissions,
       ROUND(100.0 * (COUNT(*) - LAG(COUNT(*)) OVER (ORDER BY admission_year_month))
             / NULLIF(LAG(COUNT(*)) OVER (ORDER BY admission_year_month), 0), 1) AS mom_growth_pct,
       ROUND(AVG(COUNT(*)) OVER (ORDER BY admission_year_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1) AS moving_avg_3m
FROM vw_patient_admission_summary WHERE in_reporting_window AND NOT is_cancelled
GROUP BY admission_year_month ORDER BY 1;

-- ######################################  B. ADMISSION & DISCHARGE ANALYSIS  ######################################

-- @Q06 | Daily admissions with 7-day moving average and busiest days
-- Purpose : operational (day-level) demand curve; the calendar spine keeps zero-admission days visible.
-- Decision: surge-day staffing; identifying outlier days that need root-cause review.
SELECT dd.full_date AS admission_date, dd.day_short,
       COUNT(a.admission_id) AS admissions,
       ROUND(AVG(COUNT(a.admission_id)) OVER (ORDER BY dd.full_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2) AS moving_avg_7d,
       RANK() OVER (ORDER BY COUNT(a.admission_id) DESC) AS busiest_day_rank
FROM dim_date dd
LEFT JOIN admissions a ON a.admission_date = dd.full_date AND a.admission_status <> 'Cancelled'
WHERE dd.in_reporting_window
GROUP BY dd.full_date, dd.day_short ORDER BY dd.full_date;

-- @Q07 | Weekly admissions with week-over-week change
-- Purpose : mid-granularity view used for roster planning (weekly cadence).
-- Decision: weekly bed-meeting forecast; detect multi-week surges early.
SELECT admission_week_start AS week_start, COUNT(*) AS admissions,
       COUNT(*) - LAG(COUNT(*)) OVER (ORDER BY admission_week_start) AS wow_change,
       ROUND(AVG(COUNT(*)) OVER (ORDER BY admission_week_start ROWS BETWEEN 3 PRECEDING AND CURRENT ROW), 1) AS moving_avg_4w
FROM vw_patient_admission_summary WHERE in_reporting_window AND NOT is_cancelled
GROUP BY admission_week_start ORDER BY 1;

-- @Q08 | Weekday demand profile by admission type
-- Purpose : emergency demand is flat across the week; elective/referral demand is not - quantifies the difference.
-- Decision: move elective scheduling to smooth bed demand; staff weekends for emergencies, not electives.
SELECT admission_day_name AS weekday, admission_iso_dow,
       COUNT(*) FILTER (WHERE admission_type = 'Emergency') AS emergency,
       COUNT(*) FILTER (WHERE admission_type = 'Elective')  AS elective,
       COUNT(*) FILTER (WHERE admission_type = 'Referral')  AS referral,
       COUNT(*) AS total
FROM vw_patient_admission_summary WHERE in_reporting_window AND NOT is_cancelled
GROUP BY admission_day_name, admission_iso_dow ORDER BY admission_iso_dow;

-- @Q09 | Admission type distribution by department
-- Purpose : emergency-dependence of each department (unpredictable load) vs elective/referral (schedulable load).
-- Decision: which departments can use scheduling levers to relieve capacity, and which need surge capacity.
SELECT department_name, COUNT(*) AS admissions,
       ROUND(100.0 * COUNT(*) FILTER (WHERE admission_type = 'Emergency') / COUNT(*), 1) AS emergency_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE admission_type = 'Elective')  / COUNT(*), 1) AS elective_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE admission_type = 'Referral')  / COUNT(*), 1) AS referral_pct
FROM vw_patient_admission_summary WHERE in_reporting_window AND NOT is_cancelled
GROUP BY department_name ORDER BY emergency_pct DESC;

-- @Q10 | Monthly admissions vs discharges: net flow and cumulative inpatient change
-- Purpose : tests whether inflow outpaces outflow (bed pressure building) using a running sum of net flow.
-- Decision: if cumulative net flow keeps rising, discharge capacity - not admissions - is the bottleneck.
WITH a AS (SELECT admission_year_month AS ym, COUNT(*) AS admissions FROM vw_patient_admission_summary
           WHERE in_reporting_window AND NOT is_cancelled GROUP BY 1),
     d AS (SELECT dd.year_month AS ym, COUNT(*) AS discharges FROM admissions x JOIN dim_date dd ON dd.full_date = x.discharge_date
           WHERE x.admission_status = 'Discharged' AND dd.in_reporting_window GROUP BY 1)
SELECT a.ym AS year_month, a.admissions, COALESCE(d.discharges, 0) AS discharges,
       a.admissions - COALESCE(d.discharges, 0) AS net_flow,
       SUM(a.admissions - COALESCE(d.discharges, 0)) OVER (ORDER BY a.ym) AS cumulative_net_flow
FROM a LEFT JOIN d USING (ym) ORDER BY a.ym;

-- @Q11 | Department-wise admissions: share, rank and year-over-year growth
-- Purpose : volume league table with direction of travel per department.
-- Decision: where demand is growing fastest -> where to add capacity first.
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

-- @Q12 | Average length of stay by department (completed stays only) with P50 / P90 and long-stay share
-- Purpose : mean alone hides tails; P90 and the >14-day share expose outlier stays that block beds.
-- Decision: targets for discharge-planning reviews; which departments to benchmark against clinical pathways.
SELECT department_name, COUNT(*) AS completed_stays,
       ROUND(AVG(los_days), 2) AS alos_days,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY los_days) AS median_los,
       PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY los_days) AS p90_los,
       MAX(los_days) AS max_los,
       ROUND(100.0 * COUNT(*) FILTER (WHERE los_days > (SELECT value FROM config_thresholds WHERE parameter = 'long_stay_days')) / COUNT(*), 2) AS long_stay_pct
FROM vw_patient_admission_summary
WHERE is_completed AND discharge_date >= (SELECT reporting_start FROM data_window)
GROUP BY department_name ORDER BY alos_days DESC;

-- @Q13 | Discharge disposition pattern by department
-- Purpose : outcome mix (home / follow-up / transfer / LAMA / death) per department; context for LOS and readmission.
-- Decision: high LAMA -> counselling/cost review; high transfer-out -> service-gap review; deaths -> clinical audit trigger.
SELECT department_name, COUNT(*) AS discharges,
       ROUND(100.0 * COUNT(*) FILTER (WHERE discharge_type = 'Discharged Home') / COUNT(*), 1)                     AS home_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE discharge_type = 'Discharged Home with Follow-up') / COUNT(*), 1)      AS home_followup_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE discharge_type = 'Transferred to Another Facility') / COUNT(*), 1)    AS transfer_out_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE discharge_type = 'Left Against Medical Advice') / COUNT(*), 1)        AS lama_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE discharge_type = 'Deceased') / COUNT(*), 1)                           AS mortality_pct
FROM vw_patient_admission_summary
WHERE is_completed AND discharge_date >= (SELECT reporting_start FROM data_window)
GROUP BY department_name ORDER BY discharges DESC;

-- @Q14 | Discharges by weekday (weekend discharge dip)
-- Purpose : discharges bunching on Mondays and thinning on weekends signals a weekend discharge-process gap.
-- Decision: weekend discharge-coordinator / pharmacy / transport cover; target = release beds earlier in the week.
SELECT dd.day_short AS weekday, dd.iso_day_of_week AS iso_dow, COUNT(*) AS discharges,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_pct,
       ROUND(COUNT(*)::numeric / AVG(COUNT(*)) OVER (), 2) AS index_vs_average
FROM admissions a JOIN dim_date dd ON dd.full_date = a.discharge_date
WHERE a.admission_status = 'Discharged' AND dd.in_reporting_window
GROUP BY dd.day_short, dd.iso_day_of_week ORDER BY dd.iso_day_of_week;

-- @Q15 | Cancelled admissions by month and type (deferral / no-bed cancellations)
-- Purpose : cancellations are lost activity and patient inconvenience; spikes expose OT downtime or bed shortages.
-- Decision: trigger an RCA when the monthly cancellation rate exceeds the normal band (here ~2%).
SELECT admission_year_month AS year_month,
       COUNT(*) AS requests,
       COUNT(*) FILTER (WHERE is_cancelled) AS cancelled,
       COUNT(*) FILTER (WHERE is_cancelled AND admission_type = 'Elective') AS cancelled_elective,
       COUNT(*) FILTER (WHERE is_cancelled AND admission_type = 'Referral') AS cancelled_referral,
       ROUND(100.0 * COUNT(*) FILTER (WHERE is_cancelled) / COUNT(*), 2) AS cancellation_rate_pct
FROM vw_patient_admission_summary WHERE in_reporting_window
GROUP BY admission_year_month ORDER BY 1;

-- ######################################  C. BED UTILISATION  ######################################

-- @Q16 | Bed inventory: total, staffed and CURRENT snapshot status by department
-- Purpose : the capacity baseline. NOTE: bed_status is a point-in-time snapshot, never a historical measure.
-- Decision: confirms how many beds are actually staffed (closed beds reduce the capacity denominator).
SELECT d.department_name, COUNT(*) AS total_beds,
       COUNT(*) FILTER (WHERE b.bed_status <> 'Closed')      AS staffed_beds,
       COUNT(*) FILTER (WHERE b.bed_status = 'Occupied')     AS occupied_now,
       COUNT(*) FILTER (WHERE b.bed_status = 'Available')    AS available_now,
       COUNT(*) FILTER (WHERE b.bed_status = 'Maintenance')  AS under_maintenance,
       COUNT(*) FILTER (WHERE b.bed_status = 'Closed')       AS closed
FROM beds b JOIN departments d USING (department_id)
GROUP BY d.department_name ORDER BY total_beds DESC;

-- @Q17 | Bed occupancy rate by department (occupied bed-days / staffed bed-days) with band
-- Purpose : the correct BOR - interval based, never admissions/beds. Bands use configurable ILLUSTRATIVE thresholds.
-- Decision: departments in the High/Critical band need surge/flow actions; Under-utilised ones are candidates to lend beds.
SELECT department_name, SUM(occupied_beds) AS occupied_bed_days, SUM(staffed_beds) AS staffed_bed_days,
       ROUND(SUM(occupied_beds)::numeric / SUM(staffed_beds), 4) AS bed_occupancy_rate,
       ROUND(100.0 * AVG((occupancy_band IN ('High','Critical'))::int), 1) AS pct_days_high_or_critical,
       CASE WHEN SUM(occupied_beds)::numeric / SUM(staffed_beds) >= (SELECT value FROM config_thresholds WHERE parameter = 'bor_critical') THEN 'Critical'
            WHEN SUM(occupied_beds)::numeric / SUM(staffed_beds) >= (SELECT value FROM config_thresholds WHERE parameter = 'bor_high') THEN 'High'
            WHEN SUM(occupied_beds)::numeric / SUM(staffed_beds) <  (SELECT value FROM config_thresholds WHERE parameter = 'bor_low') THEN 'Under-utilised'
            ELSE 'Normal' END AS average_band
FROM vw_bed_occupancy GROUP BY department_name ORDER BY bed_occupancy_rate DESC;

-- @Q18 | High-occupancy periods: hospital-wide days >= 85% and longest consecutive streaks (gaps-and-islands)
-- Purpose : isolates sustained pressure periods (not just single bad days) using the classic date-minus-row_number trick.
-- Decision: sustained streaks justify temporary surge beds / elective deferral protocols.
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

-- @Q19 | Seasonal occupancy heat-map: department x calendar month
-- Purpose : reveals which months stress which departments (conditional aggregation = pivot).
-- Decision: seasonal staffing/bed plans (e.g. winter respiratory beds, monsoon medicine/paediatrics beds).
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

-- @Q20 | Weekday occupancy profile (hospital-wide)
-- Purpose : shows which weekday the hospital is fullest/emptiest (end-of-day census).
-- Decision: weekday-specific elective scheduling and discharge targets.
SELECT day_short AS weekday, iso_day_of_week,
       ROUND(SUM(occupied_beds)::numeric / SUM(staffed_beds), 4) AS bed_occupancy_rate,
       ROUND(AVG(occupied_beds) * 1.0, 1) AS avg_occupied_beds_per_dept_day
FROM vw_bed_occupancy GROUP BY day_short, iso_day_of_week ORDER BY iso_day_of_week;

-- @Q21 | Peak occupancy days per department (top 3, ROW_NUMBER)
-- Purpose : the worst capacity-pressure days with context - when and how bad.
-- Decision: evidence base for a surge-capacity business case and for scenario drills.
SELECT * FROM (
    SELECT department_name, census_date, occupied_beds, staffed_beds, occupancy_rate, occupancy_band,
           ROW_NUMBER() OVER (PARTITION BY department_name ORDER BY occupancy_rate DESC, census_date) AS rn
    FROM vw_bed_occupancy) t
WHERE rn <= 3 ORDER BY department_name, rn;

-- ######################################  D. EMERGENCY OPERATIONS  ######################################

-- @Q22 | ED waiting time: mean and median by month (arrival -> consultation, LWBS excluded)
-- Purpose : the median is the typical patient's wait; the mean is pulled up by long tails - both are reported.
-- Decision: detects deterioration windows (e.g. a staffing gap) and tracks improvement after interventions.
SELECT year_month, COUNT(*) FILTER (WHERE wait_minutes IS NOT NULL) AS seen_visits,
       ROUND(AVG(wait_minutes), 1) AS avg_wait_min,
       ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY wait_minutes))::numeric, 1) AS median_wait_min,
       ROUND((PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY wait_minutes))::numeric, 1) AS p90_wait_min
FROM vw_emergency_performance GROUP BY year_month ORDER BY year_month;

-- @Q23 | Waiting time by triage level vs illustrative target
-- Purpose : urgency-weighted performance - a 45-min average is fine for level 4 but dangerous for level 2.
-- Decision: prioritise improvement where compliance with the target is lowest and clinical risk highest.
SELECT triage_label, COUNT(*) FILTER (WHERE wait_minutes IS NOT NULL) AS seen_visits, MAX(target_wait_min) AS target_min,
       ROUND(AVG(wait_minutes), 1) AS avg_wait_min,
       ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY wait_minutes))::numeric, 1) AS median_wait_min,
       ROUND((PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY wait_minutes))::numeric, 1) AS p90_wait_min,
       ROUND(100.0 * COUNT(*) FILTER (WHERE met_wait_target) / NULLIF(COUNT(*) FILTER (WHERE wait_minutes IS NOT NULL), 0), 1) AS pct_within_target
FROM vw_emergency_performance GROUP BY triage_label, triage_level ORDER BY triage_level;

-- @Q24 | Hour-of-day ED arrivals, waits and walk-outs
-- Purpose : matches ED demand to staffing hour by hour; shows where waits exceed what volume alone explains.
-- Decision: shift start-times and break cover; add clinician hours in the peak and handover windows.
SELECT arrival_hour, COUNT(*) AS visits,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_pct,
       ROUND(AVG(wait_minutes), 1) AS avg_wait_min,
       ROUND(100.0 * COUNT(*) FILTER (WHERE is_lwbs) / COUNT(*), 2) AS lwbs_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE triage_level <= 2) / COUNT(*), 1) AS high_acuity_pct
FROM vw_emergency_performance GROUP BY arrival_hour ORDER BY arrival_hour;

-- @Q25 | ED turnaround time by disposition (arrival -> final disposition)
-- Purpose : total ED length of stay, split by outcome; admitted patients include time boarding for a ward bed.
-- Decision: a long admitted-patient turnaround points at inpatient bed availability, not ED efficiency.
SELECT disposition_type, COUNT(*) AS visits,
       ROUND(AVG(turnaround_minutes), 0) AS avg_turnaround_min,
       ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY turnaround_minutes))::numeric, 0) AS median_turnaround_min,
       ROUND((PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY turnaround_minutes))::numeric, 0) AS p90_turnaround_min
FROM vw_emergency_performance GROUP BY disposition_type ORDER BY visits DESC;

-- @Q26 | Left-without-being-seen rate by waiting-time band
-- Purpose : quantifies the patient-safety cost of long waits - the share who walk out before a clinician sees them.
-- Decision: sets a maximum-acceptable wait trigger (e.g. activate fast-track when waits pass the band where LWBS rises).
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

-- @Q27 | ED performance by routed department
-- Purpose : which specialty teams' ED patients wait longest and are most often admitted.
-- Decision: specialist-on-call cover and consult-response targets for the slowest teams.
SELECT department_name, COUNT(*) AS ed_visits,
       ROUND(AVG(wait_minutes), 1) AS avg_wait_min,
       ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY wait_minutes))::numeric, 1) AS median_wait_min,
       ROUND(AVG(turnaround_minutes), 0) AS avg_turnaround_min,
       ROUND(100.0 * COUNT(*) FILTER (WHERE is_admitted) / COUNT(*), 1) AS admit_rate_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE is_lwbs) / COUNT(*), 2) AS lwbs_pct
FROM vw_emergency_performance GROUP BY department_name ORDER BY ed_visits DESC;

-- @Q28 | ED boarding vs hospital occupancy (does a full hospital slow the ED?)
-- Purpose : for admitted ED patients, time from consultation to ward transfer by occupancy band; plus the correlation coefficient.
-- Decision: if boarding rises steeply at high occupancy, inpatient flow actions (earlier discharge) are the ED fix.
WITH occ AS (SELECT census_date, SUM(occupied_beds)::numeric / SUM(staffed_beds) AS occ FROM vw_bed_occupancy GROUP BY census_date),
j AS (SELECT e.treatment_and_boarding_minutes AS tb, o.occ,
             CASE WHEN o.occ < 0.70 THEN '1) <70%' WHEN o.occ < 0.80 THEN '2) 70-79%' WHEN o.occ < 0.85 THEN '3) 80-84%' ELSE '4) 85%+' END AS occ_band
      FROM vw_emergency_performance e JOIN occ o ON o.census_date = e.arrival_date WHERE e.is_admitted)
SELECT occ_band, COUNT(*) AS admitted_visits, ROUND(AVG(tb), 0) AS avg_minutes_consult_to_ward,
       ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tb))::numeric, 0) AS median_minutes,
       ROUND((SELECT CORR(tb, occ)::numeric FROM j), 3) AS corr_all_days
FROM j GROUP BY occ_band ORDER BY occ_band;

-- ######################################  E. DOCTOR UTILISATION  ######################################

-- @Q29 | Doctor utilisation league table (consultation hours / scheduled hours)
-- Purpose : individual workload with department context; ranks identify outliers in both directions.
-- Decision: rebalance rosters - spare-capacity doctors can support saturated colleagues (within specialty).
SELECT doctor_name, department_name, employment_type, shift,
       SUM(days_worked) AS days_worked, SUM(scheduled_hours) AS scheduled_hours, SUM(consultation_hours) AS consultation_hours,
       ROUND(SUM(consultation_hours) / SUM(scheduled_hours), 4) AS utilization_rate,
       SUM(patients_attended) AS patients_attended,
       RANK() OVER (PARTITION BY department_name ORDER BY SUM(consultation_hours) / SUM(scheduled_hours) DESC) AS rank_in_dept
FROM vw_doctor_utilization GROUP BY doctor_name, department_name, employment_type, shift
ORDER BY utilization_rate DESC LIMIT 25;

-- @Q30 | Department-wise doctor workload
-- Purpose : combines hours-based utilisation with patient-count workload and the size of the doctor pool.
-- Decision: identifies departments where workload per doctor, not volume, is the constraint.
SELECT department_name, COUNT(DISTINCT doctor_id) AS doctors,
       SUM(scheduled_hours) AS scheduled_hours, SUM(consultation_hours) AS consultation_hours,
       ROUND(SUM(consultation_hours) / SUM(scheduled_hours), 4) AS utilization_rate,
       ROUND(SUM(patients_attended)::numeric / SUM(days_worked), 1) AS patients_per_doctor_day,
       ROUND(SUM(scheduled_hours) / SUM(days_worked), 2) AS avg_shift_hours,
       ROUND(100.0 * SUM(saturated_days) / SUM(days_worked), 1) AS saturated_days_pct
FROM vw_doctor_utilization GROUP BY department_name ORDER BY utilization_rate DESC;

-- @Q31 | Utilisation by employment type and shift
-- Purpose : checks whether evening/night or part-time/visiting doctors carry disproportionate workload.
-- Decision: shift-mix redesign; roster rules (e.g. cap saturated night coverage).
SELECT employment_type, shift, COUNT(DISTINCT doctor_id) AS doctors,
       ROUND(SUM(consultation_hours) / SUM(scheduled_hours), 4) AS utilization_rate,
       ROUND(SUM(patients_attended)::numeric / SUM(days_worked), 1) AS patients_per_doctor_day
FROM vw_doctor_utilization GROUP BY employment_type, shift ORDER BY employment_type, shift;

-- @Q32 | Months with doctor overload (utilisation >= high threshold) by department
-- Purpose : turns utilisation into a time series per department - shows when workload breaches the high band.
-- Decision: temporary locum cover for the months/departments that repeatedly breach.
SELECT department_name,
       COUNT(*) FILTER (WHERE doctor_utilization_rate >= (SELECT value FROM config_thresholds WHERE parameter = 'util_high')) AS months_over_high_threshold,
       COUNT(*) AS months_observed,
       ROUND(MAX(doctor_utilization_rate), 3) AS peak_monthly_utilization,
       (ARRAY_AGG(year_month ORDER BY doctor_utilization_rate DESC))[1] AS peak_month
FROM vw_department_performance WHERE doctor_utilization_rate IS NOT NULL
GROUP BY department_name ORDER BY months_over_high_threshold DESC, peak_monthly_utilization DESC;

-- ######################################  F. READMISSIONS  ######################################

-- @Q33 | 30-day readmission rate: overall and by discharge year
-- Purpose : headline quality KPI. Denominator = ELIGIBLE discharges (alive, not transferred out, full 30-day follow-up).
-- Decision: trend vs target; justification for transitional-care investment.
SELECT discharge_year AS year, COUNT(*) AS eligible_discharges, COUNT(*) FILTER (WHERE readmitted_30d) AS readmissions_30d,
       ROUND(100.0 * COUNT(*) FILTER (WHERE readmitted_30d) / COUNT(*), 2) AS readmission_rate_pct
FROM vw_readmission_analysis WHERE followup_complete GROUP BY ROLLUP (discharge_year) ORDER BY discharge_year NULLS LAST;

-- @Q34 | 30-day readmission rate by department (with sample size)
-- Purpose : department comparison with the denominator shown - small denominators must not be over-interpreted.
-- Decision: where to pilot discharge-planning/follow-up programmes (high rate AND meaningful volume).
SELECT department_name, COUNT(*) AS eligible_discharges, COUNT(*) FILTER (WHERE readmitted_30d) AS readmissions_30d,
       ROUND(100.0 * COUNT(*) FILTER (WHERE readmitted_30d) / COUNT(*), 2) AS readmission_rate_pct,
       ROUND(AVG(index_los_days), 1) AS avg_index_los,
       RANK() OVER (ORDER BY COUNT(*) FILTER (WHERE readmitted_30d)::numeric / COUNT(*) DESC) AS rate_rank
FROM vw_readmission_analysis WHERE followup_complete GROUP BY department_name ORDER BY readmission_rate_pct DESC;

-- @Q35 | Readmission risk patterns: gap distribution, discharge type, age and weekday of index discharge
-- Purpose : who comes back, and how soon - one block, four lenses (UNION ALL of conditional aggregates).
-- Decision: target follow-up calls to the highest-risk groups within the first week.
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

-- @Q36 | Patient flow across departments: index department -> readmitting department
-- Purpose : shows whether patients return to the same service or leak into General Medicine / ICU.
-- Decision: cross-department pathways (e.g. cardiology patients returning via medicine) to include in discharge plans.
SELECT d1.department_name AS index_department, d2.department_name AS readmitted_to,
       COUNT(*) AS readmissions_30d,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY d1.department_name), 1) AS pct_of_index_dept_readmissions
FROM vw_readmission_analysis r
JOIN departments d1 ON d1.department_id = r.department_id
JOIN departments d2 ON d2.department_id = r.readmit_department_id
WHERE r.readmitted_30d GROUP BY d1.department_name, d2.department_name ORDER BY d1.department_name, readmissions_30d DESC;

-- @Q37 | Frequent patients (3+ admissions): who are they and what do they cost in bed-days?
-- Purpose : a small group of patients consumes a disproportionate share of bed-days - classic care-management target.
-- Decision: enrol in case-management / chronic-care programmes.
WITH p AS (
    SELECT patient_id, COUNT(*) AS admissions, SUM(COALESCE(los_days, open_stay_days_to_date)) AS bed_days,
           COUNT(DISTINCT department_id) AS departments, MAX(age) AS age
    FROM vw_patient_admission_summary WHERE in_reporting_window AND NOT is_cancelled GROUP BY patient_id)
SELECT admissions AS admissions_per_patient, COUNT(*) AS patients, SUM(bed_days) AS bed_days,
       ROUND(100.0 * SUM(bed_days) / SUM(SUM(bed_days)) OVER (), 1) AS pct_of_all_bed_days,
       ROUND(AVG(age), 0) AS avg_age, ROUND(AVG(departments), 2) AS avg_departments
FROM p GROUP BY admissions ORDER BY admissions;

-- ######################################  G. CROSS-FUNCTIONAL / ROOT-CAUSE ANALYSIS  ######################################

-- @Q38 | Executive monthly KPI scorecard with year-over-year comparison
-- Purpose : one table for the management pack - current month vs same month last year for the core KPIs.
-- Decision: board-level "are we getting better?" without opening the dashboard.
SELECT year_month, admissions, discharges, ROUND(alos_days, 2) AS alos_days, bed_occupancy_rate,
       median_wait_min, avg_turnaround_min, readmission_rate_30d, doctor_utilization_rate,
       ROUND(bed_occupancy_rate - LAG(bed_occupancy_rate, 12) OVER (ORDER BY year_month), 4) AS occupancy_vs_prev_year_pts,
       ROUND(median_wait_min - LAG(median_wait_min, 12) OVER (ORDER BY year_month), 1) AS median_wait_vs_prev_year_min,
       admission_growth_yoy
FROM vw_monthly_hospital_kpis ORDER BY year_month;

-- @Q39 | Resource-alignment matrix: bed pressure vs doctor workload vs length of stay
-- Purpose : surfaces misallocation - departments with full beds but idle doctors (or the reverse).
-- Decision: reallocate beds/nurses/doctor sessions; avoid blanket capacity adds.
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

-- @Q40 | Demand-surge detection: department-months more than 1 SD above that department's own mean
-- Purpose : z-scores each department against itself, so naturally busy departments are not always flagged.
-- Decision: validates surge triggers (e.g. start winter plan when a department crosses +1 SD two months running).
WITH m AS (
    SELECT department_name, year_month, admissions,
           AVG(admissions) OVER (PARTITION BY department_name) AS mean_adm,
           STDDEV_SAMP(admissions) OVER (PARTITION BY department_name) AS sd_adm
    FROM vw_department_performance)
SELECT department_name, year_month, admissions, ROUND(mean_adm, 1) AS dept_monthly_mean,
       ROUND((admissions - mean_adm) / NULLIF(sd_adm, 0), 2) AS z_score
FROM m WHERE (admissions - mean_adm) / NULLIF(sd_adm, 0) >= 1.5
ORDER BY z_score DESC, department_name LIMIT 20;

-- @Q41 | Patient flow via the ED: share of admissions arriving through the ED, and ED-to-admission conversion
-- Purpose : ties the ED to inpatient demand - how much of each department's load is ED-driven, and how fast.
-- Decision: departments with high ED-dependence need ED-to-ward fast-track pathways and reserved beds.
SELECT s.department_name, COUNT(*) AS admissions,
       COUNT(*) FILTER (WHERE s.came_via_ed) AS via_ed,
       ROUND(100.0 * COUNT(*) FILTER (WHERE s.came_via_ed) / COUNT(*), 1) AS via_ed_pct,
       ROUND(AVG(e.treatment_and_boarding_minutes) FILTER (WHERE s.came_via_ed), 0) AS avg_consult_to_ward_min,
       ROUND(AVG(e.turnaround_minutes) FILTER (WHERE s.came_via_ed), 0) AS avg_ed_los_min
FROM vw_patient_admission_summary s
LEFT JOIN vw_emergency_performance e ON e.emergency_visit_id = s.emergency_visit_id
WHERE s.in_reporting_window AND NOT s.is_cancelled
GROUP BY s.department_name ORDER BY via_ed_pct DESC;
