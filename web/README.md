# web — course-fit 프론트엔드

Next.js 15 (App Router) + Tailwind v4 + TypeScript. 화면 설계 근거는 `docs/UIUX_확정.md`,
백엔드가 맞춰야 할 인터페이스는 `docs/API_계약.md`.

## 실행

```bash
cd web
npm install
npm run dev        # http://localhost:3000
```

백엔드 없이 그냥 돈다. `public/fixtures/` 의 JSON 을 읽기 때문이다.

## 실 API 붙이기

```bash
# web/.env.local
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

이 값이 비어 있으면 픽스처, 채워져 있으면 실 API 를 친다 (`lib/api.ts`).
**프론트 코드는 안 고쳐도 된다.**

## 구조

```
app/
  page.tsx              랜딩
  start/page.tsx        입력 — 대화형 3단계 (성적표 · 직무 · 성향)
  result/ResultClient.tsx  결과 — 시간표 · 역량 진단 · 졸업 진척 · 추천 근거
components/
  TimetableGrid.tsx     월~금 × 교시 그리드. 연강 병합, 과목별 고정 색
  CompetencyChart.tsx   σ(막대) vs ρ(눈금) vs gap(빗금)
  CourseCard.tsx        과목 하나의 추천 근거 — Score 축별 분해
lib/
  types.ts              API 계약 타입 (정본)
  api.ts                mock ↔ 실 API 어댑터
  slots.ts              슬롯 정수 ↔ 요일·교시 (preprocess_time_slots.py 와 동일 규약)
  competency.ts         역량 10축 고정 색 · 직무 표시 순서
  sample.ts             데모용 샘플 성적표 (실제 학생 성적 아님)
public/fixtures/        실제 파이프라인으로 뽑은 응답 예시 18종 + reference.json
scripts/dump_fixtures.py  픽스처 재생성
```

## 픽스처 재생성

DB·성적표가 이미 적재된 상태에서:

```bash
python -m transcript --text <성적표.txt> --dept BIZ --year 2022   # input_hash 확보
python web/scripts/dump_fixtures.py <input_hash> web/public/fixtures
```

직무 6 × 성향 3 = 18개 + `reference.json` 이 나온다.
이 스크립트가 만드는 JSON 모양이 곧 `POST /api/recommend` 응답 스펙이라,
백엔드 직렬화 코드를 짤 때 참조 구현으로 쓰면 된다.

## 알려진 제약

- 아무 성적표를 넣어도 결과는 고정이다 (백엔드 없음).
- 모바일에서 시간표 그리드가 좁다. 데스크톱 우선.
- 다크모드 없음 (의도).
