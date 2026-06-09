# DB 구축 계획

ILP 기반 커리큘럼 추천용 SQLite DB(`db/schema.sql` → `db/app.db`) 적재 계획·결과.
(2026-05-24 계획 확정 → **2026-05-27 실행 완료**: 7개 테이블 2222행, 검증 통과.)

## 1. 적재 대상 테이블

| 테이블 | 소스 | 적재 시점 | 비고 |
|--------|------|-----------|------|
| `department` | `data/department.csv` | CSV 직적재 | IDE/BIZ/COMMON |
| `graduation_requirement` | `data/graduation_requirement.csv` | CSV 직적재 | `req_id` autoincrement (CSV에 없음) |
| `course` | `data/course.csv` | CSV 직적재 | 과목 단위 SOT |
| `competency` | `data/competency.csv` | CSV 직적재 | taxonomy SOT, 10개 |
| `job` | `data/job.csv` | CSV 직적재 | 6개 (DA/DE/DS/FIN/MKT/PM) |
| `course_competency` | `data/course_competency.csv` | 역량 매핑 후 적재 ✅ | 매핑 산출물 1930행 |
| `job_competency` | `data/job_competency.csv` | 역량 매핑 후 적재 ✅ | 매핑 산출물 60행 |
| `course_section` | `data/course_section.csv` | **현재 미적재 (보류)** | 시간표 추천 단계로 미룸. CSV로만 보유 |
| `recommendation_log` | — | 런타임 생성(빈 테이블) ✅ | |
| `student_input` | — | 런타임 생성(빈 테이블) ✅ | |

**빌드 결과**: 역량 매핑 완료 후 `.venv/bin/python db/ingest.py --reset`로 7개 테이블 일괄 적재(2222행), 검증 통과(weight 합=1, FK 위반 0).
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
| 단위 | 과목 1행 (193개) | 분반 1행 (986개, 1:N) |
| 시간성 | 학기 무관 마스터/SOT | 2026-1 실제 개설 스냅샷 |
| 목적 | ILP 입력 (역량매핑·졸업요건·선수과목) | 실제 수강가능·시간표 충돌검사 |
| 고유 속성 | area, semester, prerequisites, is_major_required, is_pn, is_certified_sw, msc_subarea, allowed_years | section, professor, time_slots_raw, grade, category, offering_dept, source_* |

- 공통 컬럼은 4개뿐(course_id, course_name, credit, time_slots_raw). course_section엔 ILP 핵심 속성이 없음.
- 합치면 ILP 속성이 분반 수만큼 중복되고, 매칭률 42%(section 280개 course_id 중 117개만 course에 존재) 탓에 NULL/손실 발생.

### 결정: `course_section`은 시간표 추천 단계에서 적재 (현재 보류)
실측 986분반 / 고유 course_id 280개(전부 2026-1). 그중 **163개 course_id가 course 카탈로그(193) 밖**(타과·교양 등) → 역량 매핑이 없어 추천에 사용 불가.

- **현재**: 미적재. `course_section.csv` 파일로만 보유.
- **적재 시(시간표 추천 단계)**: course 카탈로그(193) 기준 필터 후 적재 → FK 깔끔. ILP 결정 단위가 분반이므로 그때 테이블 신설.

> 실제 시간표 충돌검사는 비어있는 `course.time_slots_int`가 아니라 `course_section`을 참조해야 정확함 (별도 설계 결정).

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
