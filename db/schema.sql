-- database: :memory:
-- DB schema (SQLite)
-- 9 tables for ILP-based curriculum recommendation
--   seed(7): department, graduation_requirement, course, competency,
--            course_competency, job, job_competency
--   runtime(2, 빈 채로): recommendation_log, student_input
-- 참고: course_section.csv(2026-1 분반·시간표)는 시간표 추천 단계에서 적재 예정 — 현재 미적재.
--       job_posting 원본 크롤링은 매핑 도출에만 사용 — DB 미포함.

PRAGMA foreign_keys = ON;

-- 1. department
CREATE TABLE IF NOT EXISTS department (
    dept_id                 TEXT    PRIMARY KEY,
    dept_name               TEXT    NOT NULL,
    total_credits_required  INTEGER NOT NULL
);

-- 2. graduation_requirement
CREATE TABLE IF NOT EXISTS graduation_requirement (
    req_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    dept_id         TEXT    NOT NULL,
    admission_year  INTEGER NOT NULL,
    area            TEXT    NOT NULL,
    min_credits     INTEGER,           -- NULL = 하한 없음 (예: '교양총합'은 상한만)
    max_credits     INTEGER,           -- NULL = 상한 없음 (대부분 floor 요건)
    FOREIGN KEY (dept_id) REFERENCES department(dept_id),
    UNIQUE (dept_id, admission_year, area)
);

-- 3. course
CREATE TABLE IF NOT EXISTS course (
    course_id           TEXT    PRIMARY KEY,
    course_name         TEXT    NOT NULL,
    credit              INTEGER NOT NULL,
    dept_id             TEXT    NOT NULL,
    area                TEXT    NOT NULL,
    allowed_years       TEXT,
    prerequisites       TEXT,
    time_slots_raw      TEXT,
    time_slots_int      TEXT,
    semester            TEXT,
    is_pn               INTEGER DEFAULT 0,
    is_major_required   INTEGER DEFAULT 0,
    is_certified_sw     INTEGER DEFAULT 0,
    msc_subarea         TEXT,
    liberal_area        TEXT,
    FOREIGN KEY (dept_id) REFERENCES department(dept_id)
);

-- 4. competency
CREATE TABLE IF NOT EXISTS competency (
    comp_id     TEXT    PRIMARY KEY,
    comp_name   TEXT    NOT NULL
);

-- 5. course_competency
-- 검증: course_id별 weight 합 = 1.0 ± 0.01 (ingest.py에서 체크)
CREATE TABLE IF NOT EXISTS course_competency (
    course_id   TEXT    NOT NULL,
    comp_id     TEXT    NOT NULL,
    weight      REAL    NOT NULL CHECK (weight >= 0 AND weight <= 1),
    PRIMARY KEY (course_id, comp_id),
    FOREIGN KEY (course_id) REFERENCES course(course_id),
    FOREIGN KEY (comp_id)   REFERENCES competency(comp_id)
);

-- 6. job
CREATE TABLE IF NOT EXISTS job (
    job_id      TEXT    PRIMARY KEY,
    job_name    TEXT    NOT NULL
);

-- 7. job_competency
CREATE TABLE IF NOT EXISTS job_competency (
    job_id          TEXT    NOT NULL,
    comp_id         TEXT    NOT NULL,
    required_level  REAL    NOT NULL CHECK (required_level >= 0 AND required_level <= 1),
    PRIMARY KEY (job_id, comp_id),
    FOREIGN KEY (job_id)  REFERENCES job(job_id),
    FOREIGN KEY (comp_id) REFERENCES competency(comp_id)
);

-- 8. recommendation_log
CREATE TABLE IF NOT EXISTS recommendation_log (
    rec_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_input_hash  TEXT    NOT NULL,
    target_job_id       TEXT    NOT NULL,
    recommended_courses TEXT    NOT NULL,
    objective_value     REAL    NOT NULL,
    rank                INTEGER NOT NULL,
    created_at          TEXT    NOT NULL,
    FOREIGN KEY (target_job_id) REFERENCES job(job_id)
);

-- 9. student_input (영구 저장 시 사용)
CREATE TABLE IF NOT EXISTS student_input (
    input_hash  TEXT    NOT NULL,
    course_id   TEXT    NOT NULL,
    grade       REAL    NOT NULL CHECK (grade >= 0 AND grade <= 4.5),
    is_pn       INTEGER DEFAULT 0,
    PRIMARY KEY (input_hash, course_id),
    FOREIGN KEY (course_id) REFERENCES course(course_id)
);

-- Indexes (성능)
CREATE INDEX IF NOT EXISTS idx_course_dept    ON course(dept_id);
CREATE INDEX IF NOT EXISTS idx_course_area    ON course(area);
CREATE INDEX IF NOT EXISTS idx_course_sem     ON course(semester);
CREATE INDEX IF NOT EXISTS idx_gr_dept_year   ON graduation_requirement(dept_id, admission_year);
CREATE INDEX IF NOT EXISTS idx_cc_course      ON course_competency(course_id);
CREATE INDEX IF NOT EXISTS idx_jc_job         ON job_competency(job_id);