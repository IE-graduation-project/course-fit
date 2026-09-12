# API 계약 — 웹 프론트 ↔ 추천 엔진

프론트(`web/`)가 기대하는 HTTP 인터페이스. **계산 로직은 새로 짤 것이 없다** —
이미 있는 `recommender.recommend()` 와 `transcript.load` 를 이 모양으로 감싸기만 하면 된다.

- 타입 정본: `web/lib/types.ts` (TypeScript). 이 문서와 1:1.
- 실제 응답 예시: `web/public/fixtures/*.json` — 실제 파이프라인을 돌려 뽑은 진짜 값이다.
- 프론트는 `NEXT_PUBLIC_API_BASE` 가 비어 있으면 픽스처를, 채워져 있으면 이 API 를 쓴다.
  즉 **백엔드가 뜨면 프론트 코드 수정 없이 환경변수만 바꾸면 된다.**

---

## 0. 공통

- 인코딩 `application/json; charset=utf-8`
- 에러 `{ "error": "...", "detail": "..." }` + 적절한 4xx/5xx
- 인증 없음 (프로토타입). 학생 식별은 `studentId` = `transcript` 의 `input_hash`.

---

## 1. `GET /api/reference`

드롭다운·라벨용 참조 데이터. 정적이라 캐시 가능.

```json
{
  "jobs": [{ "id": "DA", "name": "데이터 분석가" }],
  "competencies": [
    { "id": "DB", "nameKo": "데이터베이스", "nameEn": "Database & Data Engineering" }
  ],
  "modes": [
    { "id": "balanced", "eps": 0.3, "label": "균형", "desc": "역량과 졸업 진척을 함께. 기본값." }
  ],
  "areas": ["교양필수", "전공선택", "..."]
}
```

| 필드 | 출처 |
|---|---|
| `jobs` | `SELECT job_id, job_name FROM job` |
| `competencies` | `competency` 테이블 + `recommender.explain.COMP_KR` |
| `modes` | `recommender.recommend.PREFERENCE_EPS` (gap 0.0 / balanced 0.3 / graduation 0.6) |
| `areas` | `db/ingest.VALID_AREAS` |

---

## 2. `POST /api/transcript`

클래스넷 「성적정보 → 전체성적조회」 복붙 텍스트를 적재한다.

**요청**
```json
{ "text": "전체성적조회<\n2022학년도 1학년 1학기\n학수번호\t과목명\t...", "dept": "BIZ", "admissionYear": 2022 }
```

- `dept` 는 `IDE` 또는 `BIZ` 만 (department 테이블).
- `admissionYear` 는 졸업요건이 정의된 조합만 유효 — 현재 **IDE→2026, BIZ→2022**.

**응답**
```json
{
  "studentId": "746696b793744f17",
  "deptId": "BIZ",
  "admissionYear": 2022,
  "courseCount": 45,
  "matchedCount": 41,
  "semesters": []
}
```

- `studentId` = `transcript.load` 가 뱉는 `input_hash`. 같은 입력은 같은 해시로 **덮어쓰기**(idempotent).
- `matchedCount` = catalog 매칭에 성공한 과목 수. 화면에서 "N과목 중 M과목 인식" 으로 쓸 수 있다.
- `semesters` 는 사용자가 파싱 결과를 확인·수정하는 화면용. **지금 프론트는 안 쓰므로 `[]` 로 둬도 된다.**

**PDF 트랙**: `transcript/parse.py` 에 골격만 있다. 지금 UI 는 텍스트 복붙만 노출한다
(5월 합의: "구현은 텍스트 복붙 중심, PDF 는 인터페이스만").

---

## 3. `POST /api/recommend`

**요청**
```json
{ "studentId": "746696b793744f17", "job": "DA", "mode": "balanced" }
```

| 필드 | 필수 | 기본 | 대응 |
|---|---|---|---|
| `studentId` | ✓ | | `recommend(input_hash=...)` |
| `job` | ✓ | | `job_id` |
| `mode` | | `balanced` | ε 프리셋 |
| `eps` | | | 주면 `mode` 무시 |
| `maxCredits` / `minCredits` | | 18 / 12 | `U` / `L` |
| `topK` | | 3 | `k` |

**응답** — `recommender.explain.build_explanation()` 의 확장판.
전체 예시는 `web/public/fixtures/DA_balanced.json`.

```jsonc
{
  "student": { "deptId": "BIZ", "admissionYear": 2022 },
  "job": { "id": "DA", "name": "데이터 분석가" },

  // 직무 6종 적합도 — σ 는 직무 무관이라 한 번에 다 낸다. ε 에 안 흔들린다.
  // fit = 1 − Σ_k ρ_k·gap_k / Σ_k ρ_k  (0~100)
  "fitByJob": [{ "job": "DA", "name": "데이터 분석가", "fit": 93.7 }],

  "params": { "mode": "balanced", "eps": 0.3, "alpha": 1.5,
              "maxCredits": 18, "minCredits": 12, "topK": 3 },

  "diagnosis": {
    "sigma": { "DB": 0.675, "VIZ": 0.8468, "...": 0 },   // 학생 보유
    "rho":   { "DB": 0.8329, "VIZ": 1.0,    "...": 0 },   // 직무 요구
    "gap":   { "DB": 0.1579, "VIZ": 0.1532, "...": 0 },   // max(0, ρ−σ)
    "strengths": [{ "comp": "BIZ", "compKo": "비즈니스", "sigma": 0.9971 }],
    "gaps":      [{ "comp": "DB",  "compKo": "데이터베이스", "gap": 0.1579 }]
  },

  "need": { "전공선택": 12, "SW데이터활용역량": 9, "특성화교양": 3 },

  "timetables": [{
    "rank": 1, "careerfit": 0.5368, "gradProgress": 12, "totalCredit": 18,
    "status": "Optimal",
    "courses": [{
      "courseId": "311317", "section": "1", "name": "IT와경영",
      "credit": 3, "area": "전공선택",
      "slots": [18, 19, 20],            // 요일idx(월0..일6) × 16 + 교시
      "slotsHuman": ["화2", "화3", "화4"],
      "professor": "안형준", "timeRaw": "화234",
      "offeringDept": "경영학부", "category": "전선",
      "score": 0.0462,                  // Score_c = Σ_k gap_k · w_{c,k}
      "careerReason": [                 // Score 의 축별 분해, 상위 3
        { "comp": "DB", "compKo": "데이터베이스", "value": 0.0401, "share": 0.8673 }
      ],
      "gradReason": { "area": "전공선택", "remaining": 12 }
    }]
  }],

  "constraints": { "noTimeConflict": true, "creditBounds": true,
                   "excludeTaken": true, "prereqSatisfied": true }
}
```

### 프론트가 실제로 쓰는 필드

화면에 안 나오는 필드는 빼도 되지만, 아래는 **빠지면 화면이 깨진다**:

| 화면 | 필요한 필드 |
|---|---|
| 시간표 그리드 | `timetables[].courses[].slots` · `name` · `professor` |
| 성향 토글 | `params.eps` |
| 역량 진단 막대 | `diagnosis.sigma` · `rho` · `gap` (10축 전부) |
| 졸업 진척 | `need` |
| 과목 근거 막대 | `careerReason[].share` · `compKo` · `comp` |
| 제약 배지 | `constraints` |
| 대안 탭 | `timetables[].rank` · `totalCredit` |
| 직무 비교 바 | `fitByJob[].fit` · `name` |

`slots` 가 비면(`[]`) 프론트는 그리드 밖 "시간 미지정" 으로 뺀다 — 500 내지 말고 빈 배열로 주면 된다.

### infeasible 일 때

ILP 가 못 풀면 `timetables: []` 에 `status` 를 담아 **200 으로** 준다.
(학생 입장에서 500 은 "서비스 고장", 빈 결과는 "조건이 빡세다" 라 메시지가 달라야 한다.)

---

## 4. 구현 메모

`recommender/recommend.py` 모듈 독스트링에 이미 이렇게 적혀 있다 —
> CLI·웹·API·노트북 어디서든 `recommend(...)` 만 호출하면 된다.

그래서 서버는 얇아도 된다. 대략:

```python
from fastapi import FastAPI
from recommender.recommend import recommend, PREFERENCE_EPS
from recommender.explain import build_explanation

app = FastAPI()

@app.post("/api/recommend")
def api_recommend(req: RecommendRequest):
    eps = req.eps if req.eps is not None else PREFERENCE_EPS[req.mode or "balanced"]
    rec = recommend(req.studentId, req.job, U=req.maxCredits, L=req.minCredits,
                    eps=eps, k=req.topK)
    return to_payload(rec, ...)   # 위 스키마로 직렬화
```

`to_payload` 의 참조 구현은 이 저장소의 픽스처 생성 스크립트에 이미 있다 —
`web/public/fixtures/*.json` 을 만든 로직을 그대로 옮기면 된다.

**CORS**: 프론트가 Vercel 에 뜨면 도메인 허용 필요.

### 실제로 돌려봤습니다 (2026-08-31)

이 계약대로 FastAPI 스켈레톤을 짜서 프론트를 붙여봤습니다.
**엔드포인트 3개 전부 동작했고 프론트 코드는 한 줄도 안 고쳤습니다** —
`NEXT_PUBLIC_API_BASE` 만 채웠습니다. 직무를 바꾸면 ILP 가 실제로 다시 풀려서
완전히 다른 시간표가 나옵니다.

확인된 것:

- `/api/transcript` 는 두 줄입니다.
  ```python
  result = parse_transcript_text(text, dept_id=dept, admission_year=year)
  h = load_transcript(result, conn); conn.commit()
  ```
  ⚠️ `transcript/__init__.py` 독스트링에는 `parse_transcript_text(text, dept_id, admission_year)`
  로 적혀 있는데 실제 시그니처는 **키워드 전용**입니다(`text` 만 위치인자).
  독스트링이 낡았습니다 — 고쳐두시면 좋을 것 같습니다.
- `/api/recommend` 는 `recommend.recommend()` 호출 + 직렬화가 전부입니다.
  직렬화는 `web/scripts/dump_fixtures.py` 를 그대로 옮기면 됩니다.
- `/api/reference` 는 job/competency 테이블 읽기 + `PREFERENCE_EPS`.

스켈레톤 자체는 검증용이라 저장소에 넣지 않았습니다(백엔드는 소연님 레인).
필요하시면 드리겠습니다.
