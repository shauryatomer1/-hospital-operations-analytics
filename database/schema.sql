-- =====================================================================================
-- schema.sql  |  Hospital Operations & Performance Analytics  |  PostgreSQL 14+ (tested on 16)
-- Normalised relational schema (3NF) with PKs, FKs, CHECK constraints and indexes.
-- Run:  psql -d hospital -f database/schema.sql
-- =====================================================================================
DROP SCHEMA IF EXISTS hospital CASCADE;
CREATE SCHEMA hospital;
SET search_path = hospital, public;

-- ---------- reference tables -------------------------------------------------------
CREATE TABLE departments (
    department_id        CHAR(3)      PRIMARY KEY,
    department_name      VARCHAR(60)  NOT NULL UNIQUE,
    department_category  VARCHAR(30)  NOT NULL,
    department_capacity  INTEGER      NOT NULL CHECK (department_capacity >= 0)   -- physical (sanctioned) inpatient beds
);
COMMENT ON COLUMN departments.department_capacity IS 'Sanctioned physical inpatient beds. Must equal COUNT(beds) - checked in data_quality_checks.sql';

CREATE TABLE patients (
    patient_id         VARCHAR(8)  PRIMARY KEY,
    age                SMALLINT    NOT NULL CHECK (age BETWEEN 0 AND 110),         -- age (years) at first encounter in the dataset
    gender             VARCHAR(10) NOT NULL CHECK (gender IN ('Male','Female','Other')),
    city               VARCHAR(40) NOT NULL,
    patient_type       VARCHAR(30) NOT NULL CHECK (patient_type IN ('Insured','Self-Pay','Government Scheme','Corporate')),
    registration_date  DATE        NOT NULL
);

CREATE TABLE doctors (
    doctor_id        VARCHAR(8)  PRIMARY KEY,
    doctor_name      VARCHAR(60) NOT NULL,
    department_id    CHAR(3)     NOT NULL REFERENCES departments(department_id),
    specialization   VARCHAR(60) NOT NULL,
    employment_type  VARCHAR(25) NOT NULL CHECK (employment_type IN ('Full-Time','Part-Time','Visiting Consultant')),
    shift            VARCHAR(15) NOT NULL CHECK (shift IN ('Morning','Evening','Night','Rotational'))
);

CREATE TABLE beds (
    bed_id         VARCHAR(6)  PRIMARY KEY,
    department_id  CHAR(3)     NOT NULL REFERENCES departments(department_id),
    bed_type       VARCHAR(25) NOT NULL,
    bed_status     VARCHAR(15) NOT NULL CHECK (bed_status IN ('Available','Occupied','Maintenance','Closed'))
);
COMMENT ON COLUMN beds.bed_status IS 'CURRENT snapshot status (at 2025-12-31). Never use it for historical occupancy - use admission/discharge intervals.';

-- ---------- transactional tables ---------------------------------------------------
CREATE TABLE admissions (
    admission_id        VARCHAR(10) PRIMARY KEY,
    patient_id          VARCHAR(8)  NOT NULL REFERENCES patients(patient_id),
    admission_date      DATE        NOT NULL,
    discharge_date      DATE,
    admission_type      VARCHAR(10) NOT NULL CHECK (admission_type IN ('Emergency','Elective','Referral')),
    department_id       CHAR(3)     NOT NULL REFERENCES departments(department_id),
    doctor_id           VARCHAR(8)  NOT NULL REFERENCES doctors(doctor_id),
    bed_id              VARCHAR(6)  REFERENCES beds(bed_id),
    diagnosis_category  VARCHAR(40),
    admission_status    VARCHAR(12) NOT NULL CHECK (admission_status IN ('Discharged','Admitted','Cancelled')),
    discharge_type      VARCHAR(40) CHECK (discharge_type IN ('Discharged Home','Discharged Home with Follow-up',
                                  'Transferred to Another Facility','Left Against Medical Advice','Deceased')),
    CONSTRAINT ck_dates        CHECK (discharge_date IS NULL OR discharge_date >= admission_date),
    CONSTRAINT ck_status_dis   CHECK ((admission_status = 'Discharged' AND discharge_date IS NOT NULL AND discharge_type IS NOT NULL)
                                   OR (admission_status IN ('Admitted','Cancelled') AND discharge_date IS NULL AND discharge_type IS NULL)),
    CONSTRAINT ck_status_bed   CHECK ((admission_status = 'Cancelled' AND bed_id IS NULL)
                                   OR (admission_status <> 'Cancelled' AND bed_id IS NOT NULL))
);
COMMENT ON TABLE admissions IS 'One row per admission request. Discharged = completed stay; Admitted = still in-house at snapshot (open stay, excluded from completed-LOS KPIs); Cancelled = no bed ever occupied.';

CREATE TABLE emergency_visits (
    emergency_visit_id     VARCHAR(10) PRIMARY KEY,
    patient_id             VARCHAR(8)  NOT NULL REFERENCES patients(patient_id),
    arrival_datetime       TIMESTAMP   NOT NULL,
    triage_level           SMALLINT    NOT NULL CHECK (triage_level BETWEEN 1 AND 5),   -- 1 = most urgent (ESI-style)
    consultation_datetime  TIMESTAMP,                                                   -- NULL for Left-Without-Being-Seen
    disposition_datetime   TIMESTAMP   NOT NULL,
    disposition_type       VARCHAR(40) NOT NULL CHECK (disposition_type IN ('Admitted','Discharged Home',
                           'Referred for Outpatient Follow-up','Transferred','Left Against Medical Advice',
                           'Left Without Being Seen','Deceased')),
    department_id          CHAR(3)     NOT NULL REFERENCES departments(department_id),
    admission_id           VARCHAR(10) REFERENCES admissions(admission_id),             -- extension: resulting admission (if Admitted)
    CONSTRAINT ck_ed_times CHECK ((consultation_datetime IS NULL OR consultation_datetime >= arrival_datetime)
                              AND disposition_datetime >= arrival_datetime
                              AND (consultation_datetime IS NULL OR disposition_datetime >= consultation_datetime)),
    CONSTRAINT ck_ed_lwbs  CHECK ((consultation_datetime IS NULL) = (disposition_type = 'Left Without Being Seen'))
);

CREATE TABLE doctor_activity (
    activity_id                 VARCHAR(10) PRIMARY KEY,
    doctor_id                   VARCHAR(8)  NOT NULL REFERENCES doctors(doctor_id),
    activity_date               DATE        NOT NULL,
    scheduled_hours             NUMERIC(4,2) NOT NULL CHECK (scheduled_hours > 0),
    patient_consultation_hours  NUMERIC(5,2) NOT NULL CHECK (patient_consultation_hours >= 0),
    patients_attended           INTEGER      NOT NULL CHECK (patients_attended >= 0),
    CONSTRAINT ck_hours CHECK (patient_consultation_hours <= scheduled_hours),
    CONSTRAINT uq_doctor_day UNIQUE (doctor_id, activity_date)
);

CREATE TABLE readmissions (
    readmission_id            VARCHAR(8) PRIMARY KEY,
    patient_id                VARCHAR(8) NOT NULL REFERENCES patients(patient_id),
    original_admission_id     VARCHAR(10) NOT NULL REFERENCES admissions(admission_id),
    readmission_admission_id  VARCHAR(10) NOT NULL UNIQUE REFERENCES admissions(admission_id),
    days_between_admissions   INTEGER NOT NULL CHECK (days_between_admissions BETWEEN 0 AND 90),
    CONSTRAINT ck_distinct CHECK (original_admission_id <> readmission_admission_id)
);

-- ---------- indexes (foreign keys + common filter / join columns) --------------------
CREATE INDEX ix_adm_patient      ON admissions (patient_id);
CREATE INDEX ix_adm_adm_date     ON admissions (admission_date);
CREATE INDEX ix_adm_dis_date     ON admissions (discharge_date);
CREATE INDEX ix_adm_dept_date    ON admissions (department_id, admission_date);
CREATE INDEX ix_adm_bed          ON admissions (bed_id, admission_date);
CREATE INDEX ix_adm_doctor       ON admissions (doctor_id);
CREATE INDEX ix_adm_status       ON admissions (admission_status);
CREATE INDEX ix_ed_arrival       ON emergency_visits (arrival_datetime);
CREATE INDEX ix_ed_dept          ON emergency_visits (department_id);
CREATE INDEX ix_ed_triage        ON emergency_visits (triage_level);
CREATE INDEX ix_ed_patient       ON emergency_visits (patient_id);
CREATE INDEX ix_ed_admission     ON emergency_visits (admission_id);
CREATE INDEX ix_act_date         ON doctor_activity (activity_date);
CREATE INDEX ix_readm_orig       ON readmissions (original_admission_id);
CREATE INDEX ix_readm_patient    ON readmissions (patient_id);
CREATE INDEX ix_doc_dept         ON doctors (department_id);
CREATE INDEX ix_bed_dept         ON beds (department_id);
CREATE INDEX ix_pat_reg          ON patients (registration_date);

-- NOTE: a "no overlapping stay in the same bed" EXCLUDE constraint needs the btree_gist extension:
--   CREATE EXTENSION btree_gist;
--   ALTER TABLE admissions ADD CONSTRAINT ex_bed_no_overlap EXCLUDE USING gist
--     (bed_id WITH =, daterange(admission_date, COALESCE(discharge_date,'infinity'), '[)') WITH &&) WHERE (bed_id IS NOT NULL);
-- It is optional here (extension not always installed) - the same rule is verified in data_quality_checks.sql (DQ-31).
