# DB 구축 계획

ILP 기반 커리큘럼 추천용 SQLite DB(`db/schema.sql` → `db/app.db`) 적재 계획·결과.
(2026-05-24 계획 확정 → **2026-05-27 실행 완료**: 7개 테이블 2222행, 검증 통과.
→ **2026-06-10 갱신**: catalog 다년도 보강(#18)으로 `course` 193→3,304, `course_section` 적재(986행) → 8개 시드 테이블 6,319행. course_competency 전체 매핑 재실행은 후속.)

## 1. 적재 대상 테이블

| 테이블 | 소스 | 적재 시점 | 비고 |
|--------|------|-----------|------|
| `department` | `data/department.csv` | CSV 직적재 | IDE/BIZ/COMMON |
| `graduation_requirement` | `data/graduation_requirement.csv` | CSV 직적재 | `req_id` autoincrement (CSV에 없음) |
| `course` | `data/course.csv` + `data/course_crawled.csv` | CSV 직적재 | 커레이트 193 + 크롤 보강 3,111 = 3,304 (전체 카탈로그) |
| `competency` | `data/competency.csv` | CSV 직적재 | taxonomy SOT, 10개 |
| `job` | `data/job.csv` | CSV 직적재 | 6개 (DA/DE/DS/FIN/MKT/PM) |
| `course_competency` | `data/course_competency.csv` | 역량 매핑 후 적재 ✅ | 매핑 산출물 **33,040행(3,304과목 × 10)**. relevance 가중 적용(합 ≤ 1) |
| `job_competency` | `data/job_competency.csv` | 역량 매핑 후 적재 ✅ | 매핑 산출물 60행 |
| `course_section` | `data/course_section.csv` | **적재 완료 ✅ (#18 후속)** | 2026-1 분반/시간표 986행. course 적재 후(FK). 16컬럼 중 11컬럼 저장 |
| `recommendation_log` | — | 런타임 생성(빈 테이블) ✅ | |
| `student` / `student_course` | 성적표(#16) | 런타임 적재 | transcript 모듈이 적재. 추천 입력원 |

> `student_input`은 제거(2026-06-10). `student_course`에서 σ입력(matched∧passed∧¬superseded)을 파생할 수 있어 중복이었음. recommender가 student_course에서 직접 도출.

**빌드 결과**: `.venv/bin/python db/ingest.py --reset`로 일괄 적재, 검증 통과(course_competency weight 합 ≤ 1, FK 위반 0).
(초기 빌드 7개 테이블 2222행 → 이후 catalog 보강·course_section·전체 매핑·relevance 반영으로 갱신. 현행 수치는 위 표 참조.)
참고: `docs/과목과직무_역량_매핑.md`, 적재 검증은 `db/ingest.py`.

**실행 중 보정:**
- `db/ingest.py`에 main/CLI 미구현 상태 → `connect/ingest/main` + `__main__` 추가(`--reset`/`--validate` 동작).
- `graduation_requirement.min_credits` NOT NULL → nullable('교양총합'은 상한만 있는 ceiling 요건이라 min 빈 값 정상).

## 2. 제외 완료: `job_posting`

raw 채용공고는 DB 테이블로 만들지 않음. **schema.sql·ingest.py에서 제거 완료.**

- 이유: 직무-역량 매핑 파이프라인이 파일 기반(`02_sample_postings.py`가 CSV를 직접 읽어 샘플링)이라 DB 테이블 불필요. 최종 적재 대상은 `job_competency.csv`뿐.
- 조치: `db/schema.sql`에서 `job_posting` 테이블 + `idx_posting_job` 인덱스 삭제, `ingest.py` LOAD_ORDER에서 제거.

## 3. course vs course_section — 별도 유지

합치지 않고 별도 테이블로 둔다.

| | `course` | `course_section` |
|---|---|---|
| 단위 | 과목 1행 (3,304개) | 분반 1행 (986개, 1:N) |
| 시간성 | 학기 무관 마스터/SOT | 2026-1 실제 개설 스냅샷 |
| 목적 | ILP 입력 (역량매핑·졸업요건·선수과목) | 실제 수강가능·시간표 충돌검사 |
| 고유 속성 | area, semester, prerequisites, is_major_required, is_pn, is_certified_sw, msc_subarea, allowed_years | section, professor, time_slots_raw, grade, category, offering_dept, source_* |

- 공통 컬럼은 course_id·course_name·credit·time_slots_raw 정도. course_section엔 ILP 핵심 속성(area·졸업요건·선수)이 없음.
- 합치면 ILP 속성이 분반 수만큼 중복됨 → 별도 테이블 유지가 정규화상 깔끔.

### 결정: `course_section` 적재 완료 (2026-06-10, #18 후속)
실측 986분반 / 고유 course_id 280개(전부 2026-1). 과거엔 **163개 course_id가 course 카탈로그(193) 밖**이라 FK가 깨져 보류했으나, catalog 다년도 보강(#18)으로 `course`가 전체 3,304가 되면서 **280개 전부 course에 존재 → FK 위반 0** 확인. 그래서 필터 없이 986분반 전체 적재.

- **PK** `(course_id, section, source_term)` (986행 유일성 검증). **FK** `course_id → course`.
- CSV 16컬럼 중 11컬럼 저장. 미저장 5개: `course_name`/`credit`(course 조인, credit 100% 일치), `dept_name`(`offering_dept`와 중복), `grade`(`allowed_years`와 중복), `source_url`(상수).
- **추천 후보 = 별도 테이블 아님, 조인으로 도출**: `course_section ⋈ course WHERE dept_id IN ('IDE','BIZ','COMMON')` → 280과목/986분반(IDE 39, BIZ 32, COMMON 209). `course`(3,304)는 성적표 역량 매칭 universe, 추천 후보는 그중 26-1 분반이 있는 부분집합.
- 컴공 전공(자료구조·알고리즘 등 21과목)도 분반이 적재됨 — 산데공과 같은 학부라 추천 scope 확장 시 활용 가능. 단 해당 과목 `area` 커레이트는 별도 과제.

> 시간표 충돌검사는 비어있는 `course.time_slots_int`가 아니라 `course_section.time_slots_int`를 참조 (28분반은 NULL=비대면/논문 등, 충돌제약 제외).

## 4. 역량 taxonomy — `data/competency.csv` 기준

SOT는 `data/competency.csv`. comp_id 10개:
```
PROG, DATA, ML, DB, VIZ, BIZ, FIN, MKT, OR, COMM
```
- `data/README.md`의 매핑 예시(MATH/STAT/DATAVIZ/DOMAIN/PM 등)는 competency.csv와 불일치 → **무시**.
- `docs/과목과직무_역량_매핑.md`(line 121)는 competency.csv와 일치함.
- 매핑 산출물의 comp_id는 반드시 위 10개만 사용 (아니면 FK→competency 위반으로 ingest 중단).
- 주의: `FIN`, `MKT`는 comp_id이자 job_id — 테이블이 달라 무해하나 매핑/조인 코드에서 혼동 주의.

## 5. 역량 매핑 입력 파일 (적용 완료)

`docs/과목과직무_역량_매핑.md` 3.2의 직무 입력 출처는 아래대로 반영됨:

- ~~`data/job_posting.csv`~~ → **`data/job_posting_filtered.csv`** (575공고, job_id 전부 채워짐) 사용
- `job_posting.csv`는 빈 job_id 다수 포함이라 직무별 샘플링 불가했음
- 직무별 확보량 (모두 20개 샘플 충분): MKT 145, DS 146, PM 139, DA 63, FIN 50, DE 32
- `posting_id`는 DB가 없으므로 sampled CSV 내 임의 식별자로 부여.

## 6. 사전 검증 완료 (이상 없음)

- `course.course_id` PK 중복 없음, NOT NULL 컬럼 빈값 없음
- 모든 `dept_id`(IDE/BIZ/COMMON) → `department`에 존재 (FK OK)
- `graduation_requirement` (dept_id, admission_year, area) UNIQUE 중복 없음
- `job_posting_filtered.csv`의 job_id 전부 `job.csv`에 존재
