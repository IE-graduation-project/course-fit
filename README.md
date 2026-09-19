# course-fit

성적표를 붙여넣고 목표 직무를 고르면, **부족한 역량을 채우는 다음 학기 시간표**를 추천한다.
시간 충돌·학점 상하한·기수강·선수과목을 제약으로 걸고 정수계획법(ILP)으로 풀기 때문에,
충돌하는 시간표는 애초에 후보에 오르지 않는다. 졸업요건 진척도 2순위 목적함수로 함께 본다.

- 배포본 https://course-fit-seven.vercel.app
- 역량 10축 `PROG DATA ML DB VIZ BIZ FIN MKT OR COMM` · 직무 6종 `DA DS DE PM MKT FIN`
- σ(보유) → `gap = max(0, ρ−σ)` → `Score_c = Σ gap·w` → ILP 2단계(직무적합 → 졸업진척, ε 이 조절)

## 빠르게 돌려보기

```bash
# 백엔드
pip install -r requirements-api.txt
uvicorn api.main:app --reload            # http://localhost:8000/docs

# 프론트
cd web && npm install && npm run dev     # http://localhost:3000
```

프론트는 백엔드 없이도 돈다 — `NEXT_PUBLIC_API_BASE` 가 비어 있으면 `web/public/fixtures/` 의
실제 파이프라인 산출물을 읽는다. 자세한 건 `web/README.md`.

## 구조

```
course-fit/
├── api/                  FastAPI — 추천 엔진을 HTTP 로 감싼다 (docs/API_계약.md)
├── web/                  Next.js 15 + Tailwind v4 프론트엔드 (web/README.md)
│
├── transcript/           성적표 텍스트 파싱 → 학생 DB 적재
├── recommender/          ILP 추천 엔진 (모델·점수·설명)
├── mapping/              과목·채용공고를 역량으로 매핑 (LLM)
├── crawlers/             졸업요건·과목·채용공고 수집
│
├── db/                   schema.sql · ingest.py (app.db 는 gitignore)
├── data/                 크롤링 산출물 CSV — 컬럼 스펙은 data/README.md
├── tests/
└── docs/                 설계 정본
```

## 설계 문서

구현 사실은 코드가 이기지만, **왜 그렇게 했는지는 `docs/` 가 정본**이다.

| | |
|---|---|
| `ILP_추천시스템_설계.md` | 결정변수·제약·목적함수. 왜 ILP 인지 |
| `API_계약.md` | 프론트 ↔ 엔진 인터페이스. `web/lib/types.ts` 와 1:1 |
| `UIUX_확정.md` | 화면 셋의 설계 근거 |
| `배포_설계.md` | 컨테이너·호스팅·CI/CD |
| `시스템_한계.md` | 의식적으로 자른 범위와 방어 논리 |
| `추천_근거_설명.md` | 화면의 숫자가 각각 무엇이고 어떻게 나왔나 |
| `성적표_파싱_설계.md` · `졸업요건_추출.md` | 입력 파이프라인 |
| `과목과직무_역량_매핑.md` · `역량_taxonomy_근거.md` · `직무_선정_근거.md` | 역량·직무 정의 근거 |
| `역량매핑_시행착오.md` · `직무_클러스터링_가이드.md` | 매핑 과정의 기록 |
| `데모_명령어.md` | 시연용 CLI |
