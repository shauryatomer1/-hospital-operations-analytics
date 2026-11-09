-- =====================================================================================
-- data_quality_checks.sql | one result set: check_id, category, check_name, expected, actual, status, severity
-- Run right after data_import.sql (it only needs the 8 base tables).  Every check counts VIOLATIONS, so expected = 0.
--   psql -d hospital -f database/data_quality_checks.sql
-- A Critical row with status FAIL means the dataset must not be used for reporting until remediated.
-- =====================================================================================
SET search_path = hospital, public;

WITH checks AS (
  -- ---------------------------------------------------------------- 1. Primary keys / uniqueness
  SELECT 'DQ-01' id, 'Uniqueness' cat, 'duplicate doctor-day rows in doctor_activity' nm, 'Critical' sev,
         (SELECT COUNT(*) FROM (SELECT doctor_id, activity_date FROM doctor_activity GROUP BY 1,2 HAVING COUNT(*) > 1) x) AS actual
  UNION ALL SELECT 'DQ-02','Uniqueness','readmission_admission_id referenced more than once','Critical',
         (SELECT COUNT(*) FROM (SELECT readmission_admission_id FROM readmissions GROUP BY 1 HAVING COUNT(*) > 1) x)
  UNION ALL SELECT 'DQ-03','Uniqueness','ED visit linked to the same admission more than once','Critical',
         (SELECT COUNT(*) FROM (SELECT admission_id FROM emergency_visits WHERE admission_id IS NOT NULL GROUP BY 1 HAVING COUNT(*) > 1) x)
  -- ---------------------------------------------------------------- 2. Critical nulls
  UNION ALL SELECT 'DQ-04','Completeness','admissions with NULL critical field (patient/date/type/dept/doctor/status)','Critical',
         (SELECT COUNT(*) FROM admissions WHERE patient_id IS NULL OR admission_date IS NULL OR admission_type IS NULL
                 OR department_id IS NULL OR doctor_id IS NULL OR admission_status IS NULL)
  UNION ALL SELECT 'DQ-05','Completeness','emergency_visits with NULL arrival/triage/disposition/department','Critical',
         (SELECT COUNT(*) FROM emergency_visits WHERE arrival_datetime IS NULL OR triage_level IS NULL
                 OR disposition_datetime IS NULL OR disposition_type IS NULL OR department_id IS NULL)
  UNION ALL SELECT 'DQ-06','Completeness','Discharged admissions missing discharge_date or discharge_type','Critical',
         (SELECT COUNT(*) FROM admissions WHERE admission_status = 'Discharged' AND (discharge_date IS NULL OR discharge_type IS NULL))
  UNION ALL SELECT 'DQ-07','Completeness','Discharged admissions with missing diagnosis_category','Warning',
         (SELECT COUNT(*) FROM admissions WHERE admission_status = 'Discharged' AND (diagnosis_category IS NULL OR diagnosis_category IN ('', 'Unspecified')))
  -- ---------------------------------------------------------------- 3. Referential integrity (declared FKs make most of these impossible; verified anyway)
  UNION ALL SELECT 'DQ-08','Integrity','admissions with unknown patient_id','Critical',
         (SELECT COUNT(*) FROM admissions a LEFT JOIN patients p USING (patient_id) WHERE p.patient_id IS NULL)
  UNION ALL SELECT 'DQ-09','Integrity','doctors with unknown department','Critical',
         (SELECT COUNT(*) FROM doctors d LEFT JOIN departments x USING (department_id) WHERE x.department_id IS NULL)
  UNION ALL SELECT 'DQ-10','Integrity','beds with unknown department','Critical',
         (SELECT COUNT(*) FROM beds b LEFT JOIN departments x USING (department_id) WHERE x.department_id IS NULL)
  UNION ALL SELECT 'DQ-11','Integrity','readmissions pointing at missing admissions','Critical',
         (SELECT COUNT(*) FROM readmissions r LEFT JOIN admissions o ON o.admission_id = r.original_admission_id
                 LEFT JOIN admissions n ON n.admission_id = r.readmission_admission_id WHERE o.admission_id IS NULL OR n.admission_id IS NULL)
  UNION ALL SELECT 'DQ-12','Integrity','doctor_activity with unknown doctor','Critical',
         (SELECT COUNT(*) FROM doctor_activity a LEFT JOIN doctors d USING (doctor_id) WHERE d.doctor_id IS NULL)
  -- ---------------------------------------------------------------- 4. Date logic
  UNION ALL SELECT 'DQ-13','Dates','discharge_date earlier than admission_date','Critical',
         (SELECT COUNT(*) FROM admissions WHERE discharge_date < admission_date)
  UNION ALL SELECT 'DQ-14','Dates','negative length of stay','Critical',
         (SELECT COUNT(*) FROM admissions WHERE discharge_date - admission_date < 0)
  UNION ALL SELECT 'DQ-15','Dates','Discharged stay with LOS < 1 or > 60 days (implausible)','Critical',
         (SELECT COUNT(*) FROM admissions WHERE admission_status = 'Discharged' AND (discharge_date - admission_date < 1 OR discharge_date - admission_date > 60))
  UNION ALL SELECT 'DQ-16','Dates','admission before patient registration_date','Critical',
         (SELECT COUNT(*) FROM admissions a JOIN patients p USING (patient_id) WHERE a.admission_date < p.registration_date)
  UNION ALL SELECT 'DQ-17','Dates','negative ED waiting time (consultation < arrival)','Critical',
         (SELECT COUNT(*) FROM emergency_visits WHERE consultation_datetime < arrival_datetime)
  UNION ALL SELECT 'DQ-18','Dates','ED disposition before consultation or arrival','Critical',
         (SELECT COUNT(*) FROM emergency_visits WHERE disposition_datetime < COALESCE(consultation_datetime, arrival_datetime) OR disposition_datetime < arrival_datetime)
  UNION ALL SELECT 'DQ-19','Dates','ED waiting time over 8 hours (outlier screen)','Warning',
         (SELECT COUNT(*) FROM emergency_visits WHERE consultation_datetime - arrival_datetime > INTERVAL '8 hours')
  -- ---------------------------------------------------------------- 5. Business-rule consistency
  UNION ALL SELECT 'DQ-20','Business rule','non-discharged rows carrying discharge data / cancelled rows with a bed','Critical',
         (SELECT COUNT(*) FROM admissions WHERE (admission_status <> 'Discharged' AND (discharge_date IS NOT NULL OR discharge_type IS NOT NULL))
                 OR (admission_status = 'Cancelled' AND bed_id IS NOT NULL))
  UNION ALL SELECT 'DQ-21','Business rule','bed belongs to a different department than the admission','Critical',
         (SELECT COUNT(*) FROM admissions a JOIN beds b USING (bed_id) WHERE a.department_id <> b.department_id)
  UNION ALL SELECT 'DQ-22','Business rule','doctor belongs to a different department than the admission','Critical',
         (SELECT COUNT(*) FROM admissions a JOIN doctors d USING (doctor_id) WHERE a.department_id <> d.department_id)
  UNION ALL SELECT 'DQ-23','Business rule','admission allocated to a Closed (unstaffed) bed','Critical',
         (SELECT COUNT(*) FROM admissions a JOIN beds b USING (bed_id) WHERE b.bed_status = 'Closed')
  UNION ALL SELECT 'DQ-24','Business rule','bed_status Occupied without an open admission (or open admission on non-Occupied bed)','Critical',
         (SELECT COUNT(*) FROM (
              SELECT b.bed_id FROM beds b WHERE b.bed_status = 'Occupied'
                 AND NOT EXISTS (SELECT 1 FROM admissions a WHERE a.bed_id = b.bed_id AND a.admission_status = 'Admitted')
              UNION ALL
              SELECT a.bed_id FROM admissions a JOIN beds b USING (bed_id) WHERE a.admission_status = 'Admitted' AND b.bed_status <> 'Occupied') x)
  UNION ALL SELECT 'DQ-25','Business rule','department_capacity differs from number of physical beds','Critical',
         (SELECT COUNT(*) FROM departments d WHERE d.department_capacity <> (SELECT COUNT(*) FROM beds b WHERE b.department_id = d.department_id))
  UNION ALL SELECT 'DQ-26','Business rule','LWBS visit with consultation, or non-LWBS visit without consultation','Critical',
         (SELECT COUNT(*) FROM emergency_visits WHERE (disposition_type = 'Left Without Being Seen') <> (consultation_datetime IS NULL))
  UNION ALL SELECT 'DQ-27','Business rule','ED Admitted without admission link / link without Admitted','Critical',
         (SELECT COUNT(*) FROM emergency_visits WHERE (disposition_type = 'Admitted') <> (admission_id IS NOT NULL))
  UNION ALL SELECT 'DQ-28','Business rule','ED-linked admission: patient or admission type mismatch','Critical',
         (SELECT COUNT(*) FROM emergency_visits e JOIN admissions a USING (admission_id) WHERE e.patient_id <> a.patient_id OR a.admission_type <> 'Emergency')
  UNION ALL SELECT 'DQ-29','Business rule','doctor_activity: consultation hours exceed scheduled hours','Critical',
         (SELECT COUNT(*) FROM doctor_activity WHERE patient_consultation_hours > scheduled_hours)
  UNION ALL SELECT 'DQ-30','Business rule','admissions recorded after the patient was discharged as Deceased','Critical',
         (SELECT COUNT(*) FROM admissions a JOIN admissions d ON d.patient_id = a.patient_id AND d.discharge_type = 'Deceased'
                 WHERE a.admission_status <> 'Cancelled' AND a.admission_date > d.discharge_date)
  -- ---------------------------------------------------------------- 6. Impossible bed / patient assignments (interval overlap, half-open [admit, discharge))
  UNION ALL SELECT 'DQ-31','Impossible assignment','two stays overlapping in the same bed (double-booked bed)','Critical',
         (SELECT COUNT(*) FROM (
              SELECT admission_date, LAG(COALESCE(discharge_date, DATE '9999-12-31')) OVER (PARTITION BY bed_id ORDER BY admission_date, admission_id) AS prev_end
              FROM admissions WHERE admission_status <> 'Cancelled') x WHERE admission_date < prev_end)
  UNION ALL SELECT 'DQ-32','Impossible assignment','two stays overlapping for the same patient','Critical',
         (SELECT COUNT(*) FROM (
              SELECT admission_date, LAG(COALESCE(discharge_date, DATE '9999-12-31')) OVER (PARTITION BY patient_id ORDER BY admission_date, admission_id) AS prev_end
              FROM admissions WHERE admission_status <> 'Cancelled') x WHERE admission_date < prev_end)
  -- ---------------------------------------------------------------- 7. Readmission interval correctness
  UNION ALL SELECT 'DQ-33','Readmissions','days_between_admissions <> readmission admit date - original discharge date','Critical',
         (SELECT COUNT(*) FROM readmissions r JOIN admissions o ON o.admission_id = r.original_admission_id
                 JOIN admissions n ON n.admission_id = r.readmission_admission_id WHERE r.days_between_admissions <> n.admission_date - o.discharge_date)
  UNION ALL SELECT 'DQ-34','Readmissions','readmission whose original admission is not Discharged, or patients differ, or order is wrong','Critical',
         (SELECT COUNT(*) FROM readmissions r JOIN admissions o ON o.admission_id = r.original_admission_id
                 JOIN admissions n ON n.admission_id = r.readmission_admission_id
                 WHERE o.admission_status <> 'Discharged' OR o.patient_id <> r.patient_id OR n.patient_id <> r.patient_id OR n.admission_date < o.discharge_date)
  UNION ALL SELECT 'DQ-35','Readmissions','readmission admission is not an unplanned (Emergency) admission','Critical',
         (SELECT COUNT(*) FROM readmissions r JOIN admissions n ON n.admission_id = r.readmission_admission_id WHERE n.admission_type <> 'Emergency')
  -- ---------------------------------------------------------------- 8. Domain screens
  UNION ALL SELECT 'DQ-36','Domain','patients with age outside 0-110 or unknown gender code','Critical',
         (SELECT COUNT(*) FROM patients WHERE age NOT BETWEEN 0 AND 110 OR gender NOT IN ('Male','Female','Other'))
  UNION ALL SELECT 'DQ-37','Domain','patients.city with leading/trailing spaces or inconsistent case','Warning',
         (SELECT COUNT(*) FROM patients WHERE city <> INITCAP(TRIM(city)))
)
SELECT id AS check_id, cat AS category, nm AS check_name, 0 AS expected, actual,
       CASE WHEN actual = 0 THEN 'PASS' WHEN sev = 'Warning' THEN 'WARN' ELSE 'FAIL' END AS status, sev AS severity
FROM checks ORDER BY id;
