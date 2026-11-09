-- =====================================================================================
-- data_import.sql | loads the CLEANED csv files with psql's client-side \copy
-- Run from the PROJECT ROOT (paths are relative):
--     psql -d hospital -f database/schema.sql
--     psql -d hospital -f database/data_import.sql
-- Load order respects foreign keys. Unquoted empty CSV fields become NULL.
-- (scripts/load_database.py performs the identical load with psycopg2 COPY.)
-- =====================================================================================
SET search_path = hospital, public;

\copy departments       FROM 'data/processed/departments.csv'       WITH (FORMAT csv, HEADER true)
\copy patients          FROM 'data/processed/patients.csv'          WITH (FORMAT csv, HEADER true)
\copy doctors           FROM 'data/processed/doctors.csv'           WITH (FORMAT csv, HEADER true)
\copy beds              FROM 'data/processed/beds.csv'              WITH (FORMAT csv, HEADER true)
\copy admissions        FROM 'data/processed/admissions.csv'        WITH (FORMAT csv, HEADER true)
\copy emergency_visits  FROM 'data/processed/emergency_visits.csv'  WITH (FORMAT csv, HEADER true)
\copy doctor_activity   FROM 'data/processed/doctor_activity.csv'   WITH (FORMAT csv, HEADER true)
\copy readmissions      FROM 'data/processed/readmissions.csv'      WITH (FORMAT csv, HEADER true)

-- refresh planner statistics and print row counts
ANALYZE;
SELECT 'departments' AS table_name, COUNT(*) AS row_count FROM departments
UNION ALL SELECT 'patients', COUNT(*) FROM patients
UNION ALL SELECT 'doctors', COUNT(*) FROM doctors
UNION ALL SELECT 'beds', COUNT(*) FROM beds
UNION ALL SELECT 'admissions', COUNT(*) FROM admissions
UNION ALL SELECT 'emergency_visits', COUNT(*) FROM emergency_visits
UNION ALL SELECT 'doctor_activity', COUNT(*) FROM doctor_activity
UNION ALL SELECT 'readmissions', COUNT(*) FROM readmissions;
