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

## 배포

프로덕션: **https://course-fit-seven.vercel.app**

GitHub Actions로 **자동 배포**됩니다. `main` 브랜치에 `web/**` 코드가 푸시되거나 PR이 머지되면 워크플로우가 돌아 1분 내에 Vercel 프로덕션에 자동 배포됩니다.
(수동 배포 필요 시: GitHub Actions 탭에서 `Deploy Frontend to Vercel` 수동 실행 or 로컬에서 `cd web && npx vercel --prod`)


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

- **백엔드는 무료 호스팅이라 콜드스타트가 있다.** 한동안 요청이 없으면 잠들고 첫 호출이
  20~30초 걸린다(실측 23.6초, 502 한 번). 랜딩에서 미리 깨우고 `/start` 는 로딩 상태를
  보여 주지만, 랜딩을 건너뛰고 들어오면 그 대기를 그대로 만난다.
- **로컬에서 실 API 를 직접 못 친다.** 배포 백엔드가 vercel 도메인만 CORS 허용이라
  `NEXT_PUBLIC_API_BASE` 에 Render 주소를 넣어도 브라우저가 막는다. 코드 기본값에는
  localhost 가 있으니 서버 쪽 `COURSE_FIT_CORS_ORIGINS` 를 고치거나 프록시로 우회한다.
- `NEXT_PUBLIC_*` 은 빌드 타임에 인라인된다. 값을 바꿨으면 **반드시 다시 빌드**해야 한다.
- 모바일에서 시간표 그리드가 좁다. 데스크톱 우선.
- 다크모드 없음 (의도).
