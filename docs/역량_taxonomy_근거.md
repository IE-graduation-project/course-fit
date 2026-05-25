# 역량 Taxonomy 설계 근거

## 1. 출처 체계

본 시스템의 10개 핵심 역량은 다음 두 공식 표준에 기반:

- **NCS (National Competency Standards)**: 한국 고용노동부·한국산업인력공단의 국가직무능력표준
- **O*NET (Occupational Information Network)**: 미국 노동부 후원 직업정보 네트워크

NCS를 주 분류 체계로, 데이터·AI 직무의 정밀 분류는 O*NET을 보완 참조한다.

## 2. 10개 역량 분류

| ID | 역량명 | NCS 대분류·중분류 | O*NET 분류 |
|----|--------|------------------|-----------|
| PROG | Programming & Software Development | 20 정보통신 → 02 SW개발·구축 | 15-1252.00 |
| DATA | Data Analysis & Statistical Methods | 20 정보통신 → 03 데이터분석 | 15-2041.00 |
| ML | AI & Machine Learning | 20 정보통신 → 02 SW개발 → AI | 15-1221.00 |
| DB | Database & Data Engineering | 20 정보통신 → 04 DB·빅데이터 | 15-1242.00 |
| VIZ | Data Visualization & Reporting | 20 정보통신 → 03 데이터분석 → 시각화 | 15-2051.01 |
| BIZ | Business Strategy & Management | 02 경영·회계·사무 → 01 기획 | 11-1021.00 |
| FIN | Finance & Accounting | 02 경영·회계·사무 → 03 재무·회계 | 13-2011.00 |
| MKT | Marketing & Consumer Insight | 02 경영·회계·사무 → 03 마케팅 | 11-2021.00 |
| OR | Operations Research & Optimization | 20 정보통신 → 02 SW개발 → 운영연구 | 15-2031.00 |
| COMM | Communication & Collaboration | 02 경영·회계·사무 → 04 사무 | 27-3031.00 |

## 3. 설계 원칙

### (1) 두 학과 균형
- 기술 영역 5개 (PROG, DATA, ML, DB, VIZ): 산데공 강점
- 경영 영역 4개 (BIZ, FIN, MKT, COMM): 경영 강점
- 융합 영역 1개 (OR): 두 학과 모두 기여 가능

### (2) 직무 간 차별성
대상 직무 **6개(DA, DE, DS, PM, MKT, FIN)**에 대해 각 직무의 중심 역량이 명확히 구분되어야 한다. 모든 역량이 모든 직무에서 0보다 큰 required_level을 가지되, 직무별 강조 역량이 달라야 추천 차별화가 가능하다.

| 직무 | 중심 역량 | 보조 역량 |
|------|----------|----------|
| DA | DATA, VIZ | COMM, DB |
| DE | DB, PROG | DATA |
| DS | ML, DATA, PROG | OR |
| PM | BIZ, COMM | DATA, PROG |
| MKT | MKT, BIZ | COMM, DATA |
| FIN | FIN, DATA | BIZ, COMM |

→ 6개 직무 모두 서로 다른 중심 역량 셋을 가지므로 ILP 추천이 학생 역량 프로파일에 따라 차별화된다. 자세한 선정 근거는 `docs/직무_선정_근거.md`.

### (3) 학과 모든 과목 매핑 가능성
산데공 49개 + 경영 70개 전공 과목 모두 최소 1개 이상의 역량에 weight > 0을 가질 수 있어야 한다 (course-level 검증).

### (4) 입자도 균형
- 너무 추상적 ("사고력"): 모든 과목이 균등 매핑 → 차별성 0
- 너무 구체적 ("Pandas 활용"): 한 과목에만 매핑 → 매핑 sparse
- 본 10개는 NCS 중분류 수준으로 입자도 적절

## 4. 출처 인용

### NCS
- 한국산업인력공단, "국가직무능력표준 분류체계", 2024
- 웹: https://www.ncs.go.kr
- 본 시스템에서 활용한 대분류: 02 경영·회계·사무, 20 정보통신

### O*NET
- U.S. Department of Labor, "O*NET Online", https://www.onetonline.org
- 본 시스템에서 활용한 SOC 분류: 11-xxxx (Management), 13-xxxx (Business and Financial), 15-xxxx (Computer & Mathematical)

## 5. 향후 확장

- 산업·직무 도메인 확대 시 NCS 추가 대분류 참조 (예: 14 보건·의료, 16 문화·예술)
- 정밀 매핑 필요 시 O*NET의 Skills, Abilities, Knowledge, Work Activities 세부 항목 활용

## 6. 발표 방어 논리

> "본 시스템의 10개 핵심 역량은 한국 국가직무능력표준(NCS)을 주 분류 체계로 하고, 데이터·AI 직무의 정밀 분류를 위해 미국 O*NET을 보완 참조하여 설계했다. 기술 영역 5개와 경영 영역 4개, 융합 영역 1개로 두 학과(산업데이터공학과·경영학과)를 균형있게 커버하며, 대상 직무 6개(데이터 분석가, 데이터 엔지니어, 데이터 사이언티스트, 프로덕트 매니저, 마케팅 매니저, 재무 분석가)의 차별성을 보장하도록 입자도를 조정했다."