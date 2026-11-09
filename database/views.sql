-- =====================================================================================
-- views.sql | reusable analytical views (single source of KPI logic shared by SQL, Excel and Power BI)
-- Prerequisite: transformations.sql.   All views live in schema "hospital".
--
-- KPI conventions used everywhere (see documentation/KPI_Dictionary.md):
--   * Admissions      = non-cancelled admissions (Discharged + Admitted) by admission_date
--   * Discharges/ALOS = status 'Discharged' only, by discharge_date; LOS = discharge_date - admission_date
--   * Occupancy       = occupied bed-days / staffed bed-days  (midnight census, interval based)
--   * Readmission     = unplanned (Emergency) readmission <= 30 days; eligible index = Discharged, not Deceased,
--                       not transferred out, with a complete 30-day follow-up window
--   * ED wait         = consultation - arrival (excludes Left-Without-Being-Seen); ED turnaround = disposition - arrival
--   * Doctor util.    = SUM(consultation hours) / SUM(scheduled hours)
-- =====================================================================================
SET search_path = hospital, public;

-- -------------------------------------------------------------------------------------
-- 1. vw_patient_admission_summary  | grain: one row per admission (incl. cancelled & open)
-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_patient_admission_summary AS
WITH w AS (SELECT * FROM data_window),
seq AS (
    SELECT admission_id,
           ROW_NUMBER() OVER (PARTITION BY patient_id ORDER BY admission_date, admission_id) AS admission_seq
    FROM admissions WHERE admission_status <> 'Cancelled'
)
SELECT a.admission_id, a.patient_id,
       p.age,
       CASE WHEN p.age < 15 THEN '0-14' WHEN p.age < 30 THEN '15-29' WHEN p.age < 45 THEN '30-44'
            WHEN p.age < 60 THEN '45-59' WHEN p.age < 75 THEN '60-74' ELSE '75+' END AS age_group,
       p.gender, p.city, p.patient_type, p.registration_date,
       a.admission_date, a.discharge_date, a.admission_type,
       a.department_id, d.department_name, d.department_category,
       a.doctor_id, doc.doctor_name, a.bed_id, b.bed_type,
       a.diagnosis_category, a.admission_status, a.discharge_type,
       (a.admission_status = 'Discharged') AS is_completed,
       (a.admission_status = 'Cancelled')  AS is_cancelled,
       (a.admission_status = 'Admitted')   AS is_open_stay,
       CASE WHEN a.admission_status = 'Discharged' THEN a.discharge_date - a.admission_date END AS los_days,
       CASE WHEN a.admission_status = 'Admitted'   THEN w.data_end - a.admission_date END       AS open_stay_days_to_date,
       dd.year AS admission_year, dd.quarter AS admission_quarter, dd.year_month AS admission_year_month,
       dd.week_start_date AS admission_week_start, dd.iso_day_of_week AS admission_iso_dow, dd.day_short AS admission_day_name,
       (a.admission_date >= w.reporting_start) AS in_reporting_window,
       s.admission_seq,
       (s.admission_seq > 1) AS is_repeat_admission,
       (e.emergency_visit_id IS NOT NULL) AS came_via_ed,
       e.emergency_visit_id,
       r.days_between_admissions AS days_since_prev_discharge,
       (r.readmission_id IS NOT NULL) AS is_unplanned_readmission_90d,
       (r.days_between_admissions <= 30) AS is_unplanned_readmission_30d,
       oa.department_id AS prev_department_id
FROM admissions a
CROSS JOIN w
JOIN patients p     ON p.patient_id = a.patient_id
JOIN departments d  ON d.department_id = a.department_id
JOIN doctors doc    ON doc.doctor_id = a.doctor_id
LEFT JOIN beds b    ON b.bed_id = a.bed_id
JOIN dim_date dd    ON dd.full_date = a.admission_date
LEFT JOIN seq s     ON s.admission_id = a.admission_id
LEFT JOIN emergency_visits e ON e.admission_id = a.admission_id
LEFT JOIN readmissions r     ON r.readmission_admission_id = a.admission_id
LEFT JOIN admissions oa      ON oa.admission_id = r.original_admission_id;

-- -------------------------------------------------------------------------------------
-- 2. vw_bed_occupancy | grain: department x day  (interval-based census) + configurable bands
-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_bed_occupancy AS
SELECT c.census_date, dd.year, dd.year_month, dd.iso_day_of_week, dd.day_short, dd.is_weekend,
       c.department_id, d.department_name,
       c.physical_beds, c.staffed_beds, c.occupied_beds, c.available_beds, c.occupancy_rate,
       CASE WHEN c.occupancy_rate >= (SELECT value FROM config_thresholds WHERE parameter = 'bor_critical') THEN 'Critical'
            WHEN c.occupancy_rate >= (SELECT value FROM config_thresholds WHERE parameter = 'bor_high')     THEN 'High'
            WHEN c.occupancy_rate <  (SELECT value FROM config_thresholds WHERE parameter = 'bor_low')      THEN 'Under-utilised'
            ELSE 'Normal' END AS occupancy_band
FROM fact_dept_daily_census c
JOIN departments d ON d.department_id = c.department_id
JOIN dim_date dd   ON dd.full_date = c.census_date
WHERE dd.in_reporting_window;

-- -------------------------------------------------------------------------------------
-- 3. vw_readmission_analysis | grain: ELIGIBLE index discharge (denominator rows); flag = numerator
-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_readmission_analysis AS
SELECT a.admission_id AS index_admission_id, a.patient_id, a.department_id, d.department_name,
       a.admission_type, a.diagnosis_category, a.discharge_type, a.admission_date, a.discharge_date,
       (a.discharge_date - a.admission_date) AS index_los_days,
       p.age, CASE WHEN p.age < 15 THEN '0-14' WHEN p.age < 30 THEN '15-29' WHEN p.age < 45 THEN '30-44'
                   WHEN p.age < 60 THEN '45-59' WHEN p.age < 75 THEN '60-74' ELSE '75+' END AS age_group,
       dd.year AS discharge_year, dd.year_month AS discharge_year_month, dd.iso_day_of_week AS discharge_iso_dow,
       (a.discharge_date + (SELECT value::int FROM config_thresholds WHERE parameter = 'readmit_window') <= w.data_end) AS followup_complete,
       r.readmission_id, r.readmission_admission_id, r.days_between_admissions,
       ra.department_id AS readmit_department_id,
       COALESCE(r.days_between_admissions <= (SELECT value::int FROM config_thresholds WHERE parameter = 'readmit_window'), FALSE) AS readmitted_30d,
       COALESCE(r.days_between_admissions <= 90, FALSE) AS readmitted_90d
FROM admissions a
CROSS JOIN data_window w
JOIN departments d ON d.department_id = a.department_id
JOIN patients p    ON p.patient_id = a.patient_id
JOIN dim_date dd   ON dd.full_date = a.discharge_date
LEFT JOIN readmissions r ON r.original_admission_id = a.admission_id
LEFT JOIN admissions ra  ON ra.admission_id = r.readmission_admission_id
WHERE a.admission_status = 'Discharged'
  AND a.discharge_type NOT IN ('Deceased', 'Transferred to Another Facility')   -- eligibility rule
  AND a.discharge_date >= w.reporting_start;
COMMENT ON VIEW vw_readmission_analysis IS 'Rate = AVG(readmitted_30d::int) over rows WHERE followup_complete (denominator = eligible discharges).';

-- -------------------------------------------------------------------------------------
-- 4. vw_emergency_performance | grain: one row per ED visit
-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_emergency_performance AS
SELECT e.emergency_visit_id, e.patient_id, e.department_id, d.department_name,
       e.arrival_datetime, e.consultation_datetime, e.disposition_datetime,
       e.triage_level, t.triage_label, t.target_wait_min,
       e.disposition_type, e.admission_id,
       dd.year, dd.year_month, dd.full_date AS arrival_date, dd.iso_day_of_week AS arrival_iso_dow, dd.day_short AS arrival_day_name,
       EXTRACT(HOUR FROM e.arrival_datetime)::int AS arrival_hour,
       (e.disposition_type = 'Left Without Being Seen') AS is_lwbs,
       (e.disposition_type = 'Admitted')                AS is_admitted,
       ROUND((EXTRACT(EPOCH FROM (e.consultation_datetime - e.arrival_datetime)) / 60)::numeric, 1) AS wait_minutes,
       ROUND((EXTRACT(EPOCH FROM (e.disposition_datetime - e.arrival_datetime)) / 60)::numeric, 1)  AS turnaround_minutes,
       ROUND((EXTRACT(EPOCH FROM (e.disposition_datetime - e.consultation_datetime)) / 60)::numeric, 1) AS treatment_and_boarding_minutes,
       (EXTRACT(EPOCH FROM (e.consultation_datetime - e.arrival_datetime)) / 60 <= t.target_wait_min) AS met_wait_target
FROM emergency_visits e
JOIN departments d        ON d.department_id = e.department_id
JOIN ed_triage_targets t  ON t.triage_level = e.triage_level
JOIN dim_date dd          ON dd.full_date = e.arrival_datetime::date
WHERE dd.in_reporting_window;

-- -------------------------------------------------------------------------------------
-- 5. vw_doctor_utilization | grain: doctor x month
-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_doctor_utilization AS
SELECT dd.year_month, dd.month_start_date, doc.doctor_id, doc.doctor_name, doc.department_id, d.department_name,
       doc.employment_type, doc.shift,
       COUNT(*)                                       AS days_worked,
       SUM(da.scheduled_hours)                        AS scheduled_hours,
       SUM(da.patient_consultation_hours)             AS consultation_hours,
       SUM(da.patients_attended)                      AS patients_attended,
       ROUND(SUM(da.patient_consultation_hours) / NULLIF(SUM(da.scheduled_hours), 0), 4) AS utilization_rate,
       ROUND(SUM(da.patients_attended)::numeric / COUNT(*), 2)                           AS patients_per_day,
       COUNT(*) FILTER (WHERE da.patient_consultation_hours >= 0.95 * da.scheduled_hours) AS saturated_days
FROM doctor_activity da
JOIN doctors doc     ON doc.doctor_id = da.doctor_id
JOIN departments d   ON d.department_id = doc.department_id
JOIN dim_date dd     ON dd.full_date = da.activity_date
WHERE dd.in_reporting_window
GROUP BY dd.year_month, dd.month_start_date, doc.doctor_id, doc.doctor_name, doc.department_id, d.department_name,
         doc.employment_type, doc.shift;

-- -------------------------------------------------------------------------------------
-- 6. vw_department_performance | grain: department x month (inpatient departments + ED team)
-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_department_performance AS
WITH spine AS (
    SELECT m.year_month, m.month_start_date, d.department_id, d.department_name, d.department_category
    FROM (SELECT DISTINCT year_month, month_start_date FROM dim_date WHERE in_reporting_window) m
    CROSS JOIN departments d
),
adm AS (
    SELECT department_id, admission_year_month AS ym,
           COUNT(*) FILTER (WHERE NOT is_cancelled)                    AS admissions,
           COUNT(*) FILTER (WHERE is_cancelled)                        AS cancelled_admissions,
           COUNT(*) FILTER (WHERE admission_type = 'Emergency' AND NOT is_cancelled) AS emergency_admissions,
           COUNT(DISTINCT patient_id) FILTER (WHERE NOT is_cancelled)  AS unique_patients
    FROM vw_patient_admission_summary WHERE in_reporting_window GROUP BY 1, 2
),
dis AS (
    SELECT a.department_id, dd.year_month AS ym, COUNT(*) AS discharges,
           AVG(a.discharge_date - a.admission_date)::numeric(6,2) AS alos_days,
           COUNT(*) FILTER (WHERE a.discharge_date - a.admission_date > (SELECT value FROM config_thresholds WHERE parameter='long_stay_days')) AS long_stays,
           COUNT(*) FILTER (WHERE a.discharge_type = 'Deceased') AS deaths,
           COUNT(*) FILTER (WHERE a.discharge_type = 'Left Against Medical Advice') AS lama
    FROM admissions a JOIN dim_date dd ON dd.full_date = a.discharge_date
    WHERE a.admission_status = 'Discharged' AND dd.in_reporting_window GROUP BY 1, 2
),
bed AS (
    SELECT department_id, year_month AS ym, SUM(occupied_beds) AS occupied_bed_days, SUM(staffed_beds) AS staffed_bed_days
    FROM vw_bed_occupancy GROUP BY 1, 2
),
rd AS (
    SELECT department_id, discharge_year_month AS ym, COUNT(*) AS eligible_total,
           COUNT(*) FILTER (WHERE followup_complete) AS eligible_discharges,
           COUNT(*) FILTER (WHERE followup_complete AND readmitted_30d) AS readmissions_30d
    FROM vw_readmission_analysis GROUP BY 1, 2
),
doc AS (
    SELECT department_id, year_month AS ym, SUM(scheduled_hours) AS scheduled_hours, SUM(consultation_hours) AS consultation_hours,
           SUM(patients_attended) AS patients_attended, COUNT(DISTINCT doctor_id) AS active_doctors
    FROM vw_doctor_utilization GROUP BY 1, 2
),
ed AS (
    SELECT department_id, year_month AS ym, COUNT(*) AS ed_visits,
           AVG(wait_minutes) AS avg_ed_wait_min
    FROM vw_emergency_performance GROUP BY 1, 2
)
SELECT s.year_month, s.month_start_date, s.department_id, s.department_name, s.department_category,
       COALESCE(adm.admissions, 0) AS admissions, COALESCE(adm.cancelled_admissions, 0) AS cancelled_admissions,
       COALESCE(adm.emergency_admissions, 0) AS emergency_admissions, COALESCE(adm.unique_patients, 0) AS unique_patients,
       COALESCE(dis.discharges, 0) AS discharges, dis.alos_days, COALESCE(dis.long_stays, 0) AS long_stays,
       COALESCE(dis.deaths, 0) AS deaths, COALESCE(dis.lama, 0) AS lama_discharges,
       bed.occupied_bed_days, bed.staffed_bed_days,
       ROUND(bed.occupied_bed_days::numeric / NULLIF(bed.staffed_bed_days, 0), 4) AS bed_occupancy_rate,
       COALESCE(rd.eligible_discharges, 0) AS eligible_discharges, COALESCE(rd.readmissions_30d, 0) AS readmissions_30d,
       CASE WHEN rd.eligible_discharges = rd.eligible_total   -- hide right-censored months (30-day follow-up incomplete)
            THEN ROUND(rd.readmissions_30d::numeric / NULLIF(rd.eligible_discharges, 0), 4) END AS readmission_rate_30d,
       doc.scheduled_hours, doc.consultation_hours, doc.patients_attended, doc.active_doctors,
       ROUND(doc.consultation_hours / NULLIF(doc.scheduled_hours, 0), 4) AS doctor_utilization_rate,
       ROUND(adm.unique_patients::numeric / NULLIF(doc.active_doctors, 0), 2) AS admitted_patients_per_doctor,
       COALESCE(ed.ed_visits, 0) AS ed_visits, ROUND(ed.avg_ed_wait_min::numeric, 1) AS avg_ed_wait_min
FROM spine s
LEFT JOIN adm ON adm.department_id = s.department_id AND adm.ym = s.year_month
LEFT JOIN dis ON dis.department_id = s.department_id AND dis.ym = s.year_month
LEFT JOIN bed ON bed.department_id = s.department_id AND bed.ym = s.year_month
LEFT JOIN rd  ON rd.department_id  = s.department_id AND rd.ym  = s.year_month
LEFT JOIN doc ON doc.department_id = s.department_id AND doc.ym = s.year_month
LEFT JOIN ed  ON ed.department_id  = s.department_id AND ed.ym  = s.year_month;

-- -------------------------------------------------------------------------------------
-- 7. vw_monthly_hospital_kpis | grain: month (hospital level) - the executive scorecard
-- -------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_monthly_hospital_kpis AS
WITH m AS (SELECT DISTINCT year_month, month_start_date, year FROM dim_date WHERE in_reporting_window),
adm AS (
    SELECT admission_year_month AS ym,
           COUNT(*) FILTER (WHERE NOT is_cancelled) AS admissions,
           COUNT(*) FILTER (WHERE is_cancelled) AS cancelled_admissions,
           COUNT(DISTINCT patient_id) FILTER (WHERE NOT is_cancelled) AS unique_patients,
           COUNT(*) FILTER (WHERE admission_type = 'Emergency' AND NOT is_cancelled) AS emergency_admissions
    FROM vw_patient_admission_summary WHERE in_reporting_window GROUP BY 1
),
dis AS (
    SELECT dd.year_month AS ym, COUNT(*) AS discharges, AVG(a.discharge_date - a.admission_date)::numeric(6,2) AS alos_days
    FROM admissions a JOIN dim_date dd ON dd.full_date = a.discharge_date
    WHERE a.admission_status = 'Discharged' AND dd.in_reporting_window GROUP BY 1
),
bed AS (SELECT year_month AS ym, SUM(occupied_beds) AS occupied_bed_days, SUM(staffed_beds) AS staffed_bed_days
        FROM vw_bed_occupancy GROUP BY 1),
ed AS (
    SELECT year_month AS ym, COUNT(*) AS ed_visits,
           ROUND(AVG(wait_minutes), 1) AS avg_wait_min,
           ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY wait_minutes))::numeric, 1) AS median_wait_min,
           ROUND(AVG(turnaround_minutes), 1) AS avg_turnaround_min,
           ROUND(100.0 * COUNT(*) FILTER (WHERE is_lwbs) / COUNT(*), 2) AS lwbs_pct
    FROM vw_emergency_performance GROUP BY 1
),
rd AS (
    SELECT discharge_year_month AS ym, COUNT(*) AS eligible_total,
           COUNT(*) FILTER (WHERE followup_complete) AS eligible_discharges,
           COUNT(*) FILTER (WHERE followup_complete AND readmitted_30d) AS readmissions_30d
    FROM vw_readmission_analysis GROUP BY 1
),
doc AS (SELECT year_month AS ym, SUM(scheduled_hours) AS scheduled_hours, SUM(consultation_hours) AS consultation_hours
        FROM vw_doctor_utilization GROUP BY 1),
k AS (
    SELECT m.year_month, m.month_start_date, m.year,
           COALESCE(adm.admissions, 0) AS admissions, COALESCE(adm.cancelled_admissions, 0) AS cancelled_admissions,
           COALESCE(adm.unique_patients, 0) AS unique_patients, COALESCE(adm.emergency_admissions, 0) AS emergency_admissions,
           COALESCE(dis.discharges, 0) AS discharges, dis.alos_days,
           bed.occupied_bed_days, bed.staffed_bed_days,
           ROUND(bed.occupied_bed_days::numeric / NULLIF(bed.staffed_bed_days, 0), 4) AS bed_occupancy_rate,
           ed.ed_visits, ed.avg_wait_min, ed.median_wait_min, ed.avg_turnaround_min, ed.lwbs_pct,
           rd.eligible_discharges, rd.readmissions_30d,
           CASE WHEN rd.eligible_discharges = rd.eligible_total   -- hide right-censored months (30-day follow-up incomplete)
                THEN ROUND(rd.readmissions_30d::numeric / NULLIF(rd.eligible_discharges, 0), 4) END AS readmission_rate_30d,
           ROUND(doc.consultation_hours / NULLIF(doc.scheduled_hours, 0), 4) AS doctor_utilization_rate
    FROM m
    LEFT JOIN adm ON adm.ym = m.year_month LEFT JOIN dis ON dis.ym = m.year_month
    LEFT JOIN bed ON bed.ym = m.year_month LEFT JOIN ed ON ed.ym = m.year_month
    LEFT JOIN rd  ON rd.ym  = m.year_month LEFT JOIN doc ON doc.ym = m.year_month
)
SELECT k.*,
       ROUND(100.0 * emergency_admissions / NULLIF(admissions, 0), 2) AS emergency_admission_pct,
       ROUND((admissions - LAG(admissions) OVER (ORDER BY year_month))::numeric / NULLIF(LAG(admissions) OVER (ORDER BY year_month), 0), 4) AS admission_growth_mom,
       ROUND((discharges - LAG(discharges) OVER (ORDER BY year_month))::numeric / NULLIF(LAG(discharges) OVER (ORDER BY year_month), 0), 4) AS discharge_growth_mom,
       ROUND((admissions - LAG(admissions, 12) OVER (ORDER BY year_month))::numeric / NULLIF(LAG(admissions, 12) OVER (ORDER BY year_month), 0), 4) AS admission_growth_yoy
FROM k;
