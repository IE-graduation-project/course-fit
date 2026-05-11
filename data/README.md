# Data CSV Specs

크롤러가 생성해야 할 CSV 파일의 컬럼 스펙. **컬럼명/순서/타입을 정확히 맞출 것.**

- 모든 CSV: UTF-8 (BOM 없음), 헤더 1행 포함
- BOOL 필드: `0` / `1` (true/false 금지)
- NULL 필드: 빈 문자열
- 콤마구분 필드: 공백 없이 `1,2,3`

---

## 1. `department.csv`
```
dept_id,dept_name,total_credits_required
IDE,산업데이터공학과,132
BIZ,경영학과,132
```

## 2. `graduation_requirement.csv`
영역별 최소·최대 학점. `req_id`는 ingest 시 자동 생성하므로 CSV에 없음.

```
dept_id,admission_year,area,min_credits,max_credits
IDE,2026,교양필수,6,
IDE,2026,특성화교양,3,
IDE,2026,SW데이터활용역량,9,
IDE,2026,MSC,30,
IDE,2026,전공기초영어,2,
IDE,2026,전공필수,30,
IDE,2026,전공선택,24,
IDE,2026,교양총합,,40
BIZ,2022,교양필수,6,
BIZ,2022,특성화교양,3,
```

**area enum (정확히 이 문자열만 사용)**
- `교양필수`
- `특성화교양`
- `SW데이터활용역량`
- `공통교양`
- `전공기초영어`
- `전공필수`
- `전공선택`
- `일반선택`
- `MSC` (산데공만)
- `전공기초` (경영만)
- `교양총합` (상한 표현용 가상 area, min_credits 빈 값 + max_credits만 채움)

## 3. `course.csv`
과목 정보. 가장 중요한 테이블.

**필드 설명**
- `course_id`: 학수번호 (문자열, leading zero 유지)
- `credit`: 정수
- `area`: graduation_requirement.area의 enum과 정확히 일치
- `allowed_years`: 콤마구분 학년 (예: `2,3,4`). 제한 없으면 `1,2,3,4`
- `prerequisites`: 선수과목 course_id 콤마구분. 없으면 빈 문자열
- `time_slots_raw`: 사람용 표기 (`월3-4,수3-4`). 없으면 빈 문자열
- `time_slots_int`: 정수 슬롯 (전처리 후 채움. 크롤링 단계에선 빈 값 OK)
- `semester`: 학년-학기 형식, 다중 학기 가능 시 콤마 구분
  - 예: `1-2` (1학년 2학기), `1-2,2-1` (1학년 2학기 또는 2학년 1학기 부학기 개설)
  - 본학기 + 부학기 모두 표기 (학생이 둘 중 하나에 수강 가능)
- `is_pn`: P/N 과목이면 1
- `is_major_required`: 전공필수면 1
- `is_certified_sw`: SW/데이터활용역량 인증과목이면 1
- `msc_subarea`: MSC 과목만 `math` / `science` / `cs` 중 하나, 그 외 빈 문자열

**CSV 작성 팁**
- 콤마가 들어가는 필드(`allowed_years`, `prerequisites`, `time_slots_raw`)는 **반드시 큰따옴표로 감쌀 것**. 예: `"2,3,4"`
- pandas로 저장 시 `df.to_csv(path, index=False, encoding='utf-8')` 사용

## 4. `competency.csv`
역량 taxonomy 10개 -- 한국 NCS 기반 + 약간 변형

```
comp_id,comp_name
PROG,Programming & Software Development
DATA,Data Analysis & Statistics
ML,AI/Machine Learning
DB,Database & Data Engineering
VIZ,Data Visualization & Reporting
BIZ,Business Analysis & Strategy
FIN,Finance & Accounting
COMM,Communication & Presentation
PM,roject Management
DOMAIN,Industry Domain Knowledge
```

(comp_id, comp_name 최종 확정은 별도 논의 — 위는 placeholder)

## 5. `job.csv`
```
job_id,job_name
DA,데이터 분석가
DS,데이터 사이언티스트
PM,프로덕트 매니저
```

## 6. `job_posting.csv`
채용공고 원본. `posting_id`는 ingest 시 자동 생성.

```
job_id,source,posting_url,raw_text,crawled_at
DA,잡코리아,https://...,공고 본문 전체...,2026-05-09T14:00:00
DA,사람인,https://...,공고 본문 전체...,2026-05-09T14:30:00
```

- `crawled_at`: ISO 8601 형식
- `raw_text`: 줄바꿈 포함 가능 → CSV 저장 시 quote 처리 필수 (`csv.QUOTE_ALL` 또는 pandas 기본)

## 7. `course_competency.csv`
LLM 매핑 결과. **course_id별 weight 합 = 1.0 ± 0.01** 검증.

```
course_id,comp_id,weight
101503,PROG,0.6
101503,MATH,0.4
013312,PROG,0.8
013312,MATH,0.2
```

## 8. `job_competency.csv`
LLM 매핑 결과. 0~1 스케일 (합 = 1 제약 없음, 직무별 독립).

```
job_id,comp_id,required_level
DA,PROG,0.7
DA,STAT,0.9
DA,ML,0.5
DA,DB,0.6
DA,COMM,0.7
DA,DATAVIZ,0.8
```

---

## 검증 규칙 (ingest.py가 자동 체크)

1. 모든 FK가 부모 테이블에 존재
2. `course_competency.weight`: course_id별 합 = 1.0 ± 0.01
3. `job_competency.required_level`: 0~1 범위
4. `course.area` ∈ enum
5. `course.area`가 해당 dept의 `graduation_requirement.area`에 존재 (없으면 warning)
6. `course.allowed_years`: 1~4 범위
7. `course.msc_subarea` not null ⟹ `area = 'MSC'`

검증 실패 시 ingest 중단. 에러 메시지로 수정 위치 표시.