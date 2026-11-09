-- =====================================================================================
-- transformations.sql | derived / analytics-ready tables built on top of the loaded data
-- Idempotent: safe to re-run.  Run after data_import.sql and data_quality_checks.sql.
--   1. data_window          single-row table: reporting window + snapshot date
--   2. config_thresholds    configurable illustrative thresholds (occupancy bands, utilisation)
--   3. ed_triage_targets    illustrative ED waiting-time targets per triage level
--   4. dim_date             calendar dimension
--   5. fact_dept_daily_census   occupied vs staffed beds per department per day (interval based)
-- =====================================================================================
SET search_path = hospital, public;

-- 1 ---------------------------------------------------------------------------------
DROP TABLE IF EXISTS data_window CASCADE;
CREATE TABLE data_window AS
SELECT DATE '2023-01-01' AS reporting_start,       -- first day of the reporting window
       DATE '2025-12-31' AS data_end;              -- snapshot date (open stays are in-house on this date)
COMMENT ON TABLE data_window IS 'Admissions before reporting_start are carry-over inpatients from the 6-week burn-in (still in-house on 2023-01-01); they count for occupancy only.';

-- 2 ---------------------------------------------------------------------------------
DROP TABLE IF EXISTS config_thresholds CASCADE;
CREATE TABLE config_thresholds (parameter VARCHAR(40) PRIMARY KEY, value NUMERIC NOT NULL, description TEXT);
INSERT INTO config_thresholds VALUES
 ('bor_high',       0.85, 'ILLUSTRATIVE: bed occupancy >= this value = High (amber)'),
 ('bor_critical',   0.95, 'ILLUSTRATIVE: bed occupancy >= this value = Critical (red)'),
 ('bor_low',        0.60, 'ILLUSTRATIVE: bed occupancy < this value = Under-utilised'),
 ('util_high',      0.85, 'ILLUSTRATIVE: doctor utilisation >= this value = High workload'),
 ('util_low',       0.55, 'ILLUSTRATIVE: doctor utilisation < this value = Spare capacity'),
 ('readmit_window', 30,   'Days after discharge defining a readmission'),
 ('long_stay_days', 14,   'Stays longer than this are flagged as long-stay outliers');

-- 3 ---------------------------------------------------------------------------------
DROP TABLE IF EXISTS ed_triage_targets CASCADE;
CREATE TABLE ed_triage_targets (triage_level SMALLINT PRIMARY KEY, triage_label VARCHAR(30) NOT NULL, target_wait_min INTEGER NOT NULL);
INSERT INTO ed_triage_targets VALUES
 (1,'1 - Resuscitation',5),(2,'2 - Emergent',15),(3,'3 - Urgent',30),(4,'4 - Less Urgent',60),(5,'5 - Non-Urgent',120);
COMMENT ON TABLE ed_triage_targets IS 'ILLUSTRATIVE internal targets (not an external standard). Adjust to hospital policy.';

-- 4 ---------------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_date CASCADE;
CREATE TABLE dim_date AS
SELECT d::date                                         AS full_date,
       TO_CHAR(d, 'YYYYMMDD')::int                     AS date_key,
       EXTRACT(YEAR FROM d)::int                       AS year,
       EXTRACT(QUARTER FROM d)::int                    AS quarter,
       'Q' || EXTRACT(QUARTER FROM d)::int || ' ' || EXTRACT(YEAR FROM d)::int AS year_quarter,
       EXTRACT(MONTH FROM d)::int                      AS month_number,
       TO_CHAR(d, 'Mon')                               AS month_short,
       TO_CHAR(d, 'YYYY-MM')                           AS year_month,
       DATE_TRUNC('month', d)::date                    AS month_start_date,
       DATE_TRUNC('week', d)::date                     AS week_start_date,
       EXTRACT(ISODOW FROM d)::int                     AS iso_day_of_week,
       TO_CHAR(d, 'Dy')                                AS day_short,
       EXTRACT(DAY FROM d)::int                        AS day_of_month,
       (EXTRACT(ISODOW FROM d) >= 6)                   AS is_weekend,
       (d >= (SELECT reporting_start FROM data_window)) AS in_reporting_window
FROM generate_series(DATE '2022-11-01', DATE '2025-12-31', INTERVAL '1 day') AS g(d);
ALTER TABLE dim_date ADD PRIMARY KEY (full_date);
CREATE INDEX ix_dim_date_ym ON dim_date (year_month);

-- 5 ---------------------------------------------------------------------------------
-- Occupancy convention (midnight census): a bed is occupied on day D when admission_date <= D < discharge_date.
-- Open stays (no discharge yet) are occupied through data_end.  Same-day turnover is therefore double-booking safe.
-- Capacity: staffed beds = beds whose CURRENT status is not 'Closed' (constant over time - documented assumption).
DROP TABLE IF EXISTS fact_dept_daily_census CASCADE;
CREATE TABLE fact_dept_daily_census AS
WITH occ AS (
    SELECT dd.full_date AS census_date, a.department_id, COUNT(*) AS occupied_beds
    FROM admissions a
    JOIN dim_date dd
      ON dd.full_date >= a.admission_date
     AND dd.full_date <  COALESCE(a.discharge_date, (SELECT data_end FROM data_window) + 1)
    WHERE a.admission_status IN ('Discharged', 'Admitted')
    GROUP BY dd.full_date, a.department_id
), cap AS (
    SELECT department_id, COUNT(*) FILTER (WHERE bed_status <> 'Closed') AS staffed_beds, COUNT(*) AS physical_beds
    FROM beds GROUP BY department_id
)
SELECT dd.full_date AS census_date, c.department_id, c.physical_beds, c.staffed_beds,
       COALESCE(o.occupied_beds, 0)::int AS occupied_beds,
       (c.staffed_beds - COALESCE(o.occupied_beds, 0))::int AS available_beds,
       ROUND(COALESCE(o.occupied_beds, 0)::numeric / NULLIF(c.staffed_beds, 0), 4) AS occupancy_rate
FROM dim_date dd
CROSS JOIN cap c
LEFT JOIN occ o ON o.census_date = dd.full_date AND o.department_id = c.department_id
WHERE c.staffed_beds > 0;
ALTER TABLE fact_dept_daily_census ADD PRIMARY KEY (census_date, department_id);
COMMENT ON TABLE fact_dept_daily_census IS 'Grain: department x day. occupied_beds derived from admission/discharge intervals, NOT from beds.bed_status.';

ANALYZE;
SELECT 'dim_date' AS built, COUNT(*) AS row_count FROM dim_date
UNION ALL SELECT 'fact_dept_daily_census', COUNT(*) FROM fact_dept_daily_census;
