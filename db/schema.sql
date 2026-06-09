-- database: :memory:
-- DB schema (SQLite)
-- 12 tables for ILP-based curriculum recommendation
--   seed(8): department, graduation_requirement, course, competency,
--            course_competency, job, job_competency, course_section
--   runtime(4, 빈 채로): recommendation_log, student_input, student, student_course
-- 참고: course_section(2026-1 분반/시간표)은 ILP 시간표 추천 후보의 시간정보. course 전체 적재 후 적재.
--       job_posting 원본 크롤링은 매핑 도출에만 사용, DB 미포함.
--       student/student_course/student_input은 성적표 적재(이슈 #16)로 채워진다.

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

-- 10. student: 성적표 1건 = 학생 1명 (이슈 #16)
CREATE TABLE IF NOT EXISTS student (
    input_hash      TEXT    PRIMARY KEY,   -- 성적표 내용 기반 결정적 해시
    student_no      TEXT,                  -- 학번 (성적표에 있으면)
    name            TEXT,                  -- 성명 (있으면)
    dept_id         TEXT,                  -- 매핑된 학과(IDE/BIZ), 매핑 실패 시 NULL
    dept_name_raw   TEXT,                  -- 성적표 원문 학과명
    admission_year  INTEGER,               -- 입학년도
    current_grade   INTEGER,               -- 현재 학년 (성적표 기준/추정)
    total_earned    INTEGER,               -- 총 취득학점 (성적표 합계)
    gpa             REAL,                  -- 전체 평점평균 (성적표 표기)
    source_file     TEXT,                  -- 원본 PDF 파일명
    created_at      TEXT,
    FOREIGN KEY (dept_id) REFERENCES department(dept_id)
);

-- 11. student_course: 성적표 전 과목 원본 (이슈 #16)
-- catalog 미매칭(교양/타과/폐지) 과목까지 포함해 영역별 기수강학점(need_g) 산출에 사용.
CREATE TABLE IF NOT EXISTS student_course (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    input_hash      TEXT    NOT NULL,
    course_id       TEXT,                  -- 학수번호 (없을 수 있음)
    course_name     TEXT    NOT NULL,
    category_raw    TEXT,                  -- 성적표 이수구분 원문 (전필/전선/교양 등)
    area            TEXT,                  -- area enum 매핑값 (실패 시 NULL)
    credit          INTEGER NOT NULL,
    grade_letter    TEXT,                  -- 등급 원문 (A+, B0, P, F, NP 등)
    grade           REAL,                  -- 4.5 환산 (P/N/F 등 비해당 시 NULL)
    is_pn           INTEGER DEFAULT 0,     -- P/N 과목이면 1
    passed          INTEGER DEFAULT 0,     -- 이수(취득) 여부
    superseded      INTEGER DEFAULT 0,     -- 재수강으로 대체된 이전 시도 (집계 제외)
    term            TEXT,                  -- 수강 학기 (예: 2023-1, 2025-S)
    matched         INTEGER DEFAULT 0,     -- course 카탈로그 매칭 여부
    FOREIGN KEY (input_hash) REFERENCES student(input_hash)
);

-- 12. course_section: 2026-1 분반/시간표 (ILP 시간표 추천 후보의 시간정보)
-- grain: 과목 × 분반 × 학기. (course_id, section, source_term) 유일성 검증됨(986행 중복 0).
-- course 전체 적재 후 적재(FK 의존). credit/course_name은 course에서 조인(중복 저장 안 함).
-- time_slots_int NULL = 비대면/논문/실습 등 고정 시간 미지정(28행) → 추천 시 시간충돌 제약 제외.
CREATE TABLE IF NOT EXISTS course_section (
    course_id        TEXT    NOT NULL,   -- FK → course
    section          TEXT    NOT NULL,   -- 분반 번호 ('1','2'...)
    source_term      TEXT    NOT NULL,   -- 개설 학기 ('2026-1')
    time_slots_int   TEXT,               -- ILP 충돌제약용 교시 인덱스 ('34,35,50,51')
    time_slots_raw   TEXT,               -- 사람 읽기용 ('수23,목23')
    professor        TEXT,
    category         TEXT,               -- 개설시점 이수구분('전필' 등, 개설학부 관점)
    offering_dept    TEXT,               -- 실제 개설학과
    source_dept_code TEXT,               -- 크롤 스코프 코드('A200')
    source_dept_name TEXT,               -- 크롤 스코프명
    notes            TEXT,               -- 수강제한/비고
    PRIMARY KEY (course_id, section, source_term),
    FOREIGN KEY (course_id) REFERENCES course(course_id)
);

-- Indexes (성능)
CREATE INDEX IF NOT EXISTS idx_course_dept    ON course(dept_id);
CREATE INDEX IF NOT EXISTS idx_course_area    ON course(area);
CREATE INDEX IF NOT EXISTS idx_course_sem     ON course(semester);
CREATE INDEX IF NOT EXISTS idx_gr_dept_year   ON graduation_requirement(dept_id, admission_year);
CREATE INDEX IF NOT EXISTS idx_cc_course      ON course_competency(course_id);
CREATE INDEX IF NOT EXISTS idx_jc_job         ON job_competency(job_id);
CREATE INDEX IF NOT EXISTS idx_sc_hash        ON student_course(input_hash);
CREATE INDEX IF NOT EXISTS idx_si_hash        ON student_input(input_hash);
CREATE INDEX IF NOT EXISTS idx_section_course ON course_section(course_id);
CREATE INDEX IF NOT EXISTS idx_section_term   ON course_section(source_term);