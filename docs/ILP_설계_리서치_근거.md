# ILP 추천 엔진 설계 — 리서치 근거 (인용 문헌)

> **이 문서의 목적**
> `docs/ILP_추천_설계.md`의 각 설계 선택(ILP 정식화, 캡 기반 목적함수, 시간충돌 제약,
> 역량 taxonomy)을 **peer-reviewed 논문·표준 교과서·공식 표준 문서의 1차 출처**로 뒷받침한다.
> 모든 출처는 WebFetch로 원문/초록/권위 메타데이터를 직접 열어 검증했으며, 각 항목에
> **검증 상태**를 표기했다. 발표·논문 작성 시 이 문서의 서지정보를 그대로 인용 가능.

## 검증 상태 범례

| 표기 | 의미 |
|------|------|
| ✅ **원문확인** | 논문 본문/초록 또는 공식 페이지를 WebFetch로 직접 열어 내용 확인 |
| 🟡 **서지확인** | 저자·연도·게재처·DOI 등 서지정보는 다중 독립 출처로 교차검증, 본문은 페이월/렌더링으로 글자단위 미확인 |
| ⚠️ **부분/주의** | 메타데이터만 확인했거나, 출처는 실재하나 우리 주장과의 적합도에 단서가 필요 |
| ❌ **검증실패** | 1차 출처로 확인 불가 — 인용 전 추가 확인 필요 |

**§6 매핑표의 '강도' 정의** (검증상태와 1:1 동기화):

| 강도 | 의미 |
|------|------|
| **강** | 근거가 ✅원문확인 + peer-reviewed/공식이며 우리 주장과 직접 정렬 |
| **중** | 근거가 🟡서지확인(본문 미대조)이거나 보조성격(강의자료·survey) |
| **공식확인(정정 필요)** | 공식 1차 출처 확인했으나 우리 측 인용에 정정이 선행돼야 함 |

> ⚠️ **2025–2026년 arXiv preprint 주의**: 최신 preprint([Soni 2025] arXiv:2511.09819, [Musazade
> 2026] arXiv:2603.03134)는 게재 전 단계로 **정식 인용 전 peer-review 게재 여부 재확인** 권장.
> ✅ 검증 루프에서 두 arXiv ID·제목·저자 모두 실재·일치 확인됨(날조 아님).

---

## 1. ILP/MILP 기반 교과목·커리큘럼 추천 (학생 과목 선택 최적화)

> **뒷받침 대상**: "졸업요건을 제약, 학생 목표를 목적함수로 두고 ILP로 과목 묶음을 최적화한다"
> (`ILP_추천_설계.md` §1, §6, §7).

- ✅ **[Shakhsi-Niaei & Abuei-Mehrizi 2020]** *An optimization-based decision support system for
  students' personalized long-term course planning.* **Computer Applications in Engineering
  Education** 28(5):1247–1264. DOI [10.1002/cae.22299](https://doi.org/10.1002/cae.22299).
  — **우리 설계와 1:1 대응**: 코스 관계·규정을 제약으로, 학생 선호(학기당 학점, 난이도, 졸업
  목표학기, 선택과목 우선순위, 목적 가중치)를 목적함수로 둔 다목적 최적화 DSS를 산업공학과에
  실제 구현. **최우선 인용.**
- ✅ **[Christou, Vagianou & Vardoulias 2022]** *Planning Courses for Student Success at the
  American College of Greece.* arXiv [2207.02659](https://arxiv.org/abs/2207.02659). — 학생
  이수계획을 **MILP**로 정식화(선수·학기 상한 제약), 목적함수에 기대 GPA 최대화 결합, **GUROBI로
  10초 이내** 해결. → "추천을 최적화로, 학생 성과를 목적함수로" + 실시간 풀이 가능성의 실증.
- ✅ **[Slim, Abdallah, Allen, Hickman & Slim 2025]** *An Efficient Linearized Optimization
  Framework for Designing Balanced and Efficient Degree Plans.* **EDM 2025**. DOI
  [10.5281/zenodo.15870189](https://doi.org/10.5281/zenodo.15870189). — 2단계 MILP로 선수·병행·
  계층적 졸업요건을 선형 제약화, 학기별 부하 균형을 절댓값 선형화로 처리. **최신 방법론 근거.**
- ✅ **[Xu, Xing & van der Schaar 2016]** *Personalized Course Sequence Recommendations.* **IEEE
  Transactions on Signal Processing.** DOI [10.1109/TSP.2016.2595495](https://doi.org/10.1109/TSP.2016.2595495);
  arXiv [1512.09176](https://arxiv.org/abs/1512.09176). — ILP는 아니나(DP+밴딧), 선수·개설시점
  제약 하 학생 성과 최적화. **추천=최적화 문제정의의 근거 + 대안 방법론 비교용.**
- ✅ **[Heileman, Abdallah, Slim & Hickman 2018]** *Curricular Analytics: A Framework for
  Quantifying the Impact of Curricular Reforms and Pedagogical Innovations.* arXiv
  [1811.09676](https://arxiv.org/abs/1811.09676). — curricular complexity(blocking/delay factor)
  메트릭의 정초 문헌. 선수관계 그래프를 제약·보조목적으로 통합할 근거.
- ⚠️ **[Charoenruengkit 2018]** *Course Planning Optimization with Conditional Constraints using
  ILP.* ICDTE 2018, ACM. DOI [10.1145/3284497.3284506](https://doi.org/10.1145/3284497.3284506).
  — 서지 확정, **초록 본문 미확인**(publisher가 가림). 관점이 "기관의 과목 개설 계획"이라 우리
  "학생 선택"과 결이 다름 → **보조 인용.**
- ❌ **[Dechter, A. 2009]** *Facilitating Timely Completion of a College Degree With Optimization
  Technology.* — 선구적 정식화로 다수 후속논문이 인용하나, **게재처·권·페이지·DOI 1차 확인 실패**
  (Semantic Scholar에도 venue/DOI 누락). **정식 인용 전 도서관 DB로 게재처 확인 필수.**

---

## 2. 직무/스킬 갭 기반 과목 추천 · 채용공고 스킬 추출

> **뒷받침 대상**: "직무가 요구하는 역량(직무 기준, 채용공고에서 도출) ↔ 학생 보유 역량의 갭을
> 메우는 과목 추천" (`ILP_추천_설계.md` §4 `ρ`, 부록 A).

- ✅ **[Frej, Dai, Montariol, Bosselut & Käser 2024]** *Course Recommender Systems Need to
  Consider the Job Market.* **ACM SIGIR 2024**. arXiv [2404.10876](https://arxiv.org/abs/2404.10876);
  DOI [10.1145/3626772.3657847](https://doi.org/10.1145/3626772.3657847). — 과목 추천이 직무시장
  수요를 반영해야 한다는 관점 정립(P1 직무정렬, P4 사용자목표 정렬). **우리 문제정의의 직접 근거.**
- ✅ **[Ahadi, Kitto, Rizoiu & Musial 2022]** *Skills Taught vs Skills Sought: Using Skills
  Analytics to Identify the Gaps between Curriculum and Job Markets.* **EDM 2022**. DOI
  [10.5281/zenodo.6853121](https://doi.org/10.5281/zenodo.6853121). — 2,747개 과목 × 144,000개
  채용공고를 NLP로 분석, 교육과정–직무 스킬 갭 정량화. **갭 측정 방법론의 직접 선례.**
- ✅ **[Zhu, Kopalle, Wang, Liu, Jona & Börner 2020]** *Community-Based Data Integration of Course
  and Job Data in Support of Personalized Career-Education Recommendations.* arXiv
  [2006.13864](https://arxiv.org/abs/2006.13864). — 과목 설명·채용공고를 이종 그래프로 통합,
  스킬 용어 불일치/갭을 명시적으로 문제정의. **데이터 통합·매핑 파이프라인 근거.**
- ✅ **[Aljohani, Aslam, Khadidos & Hassan 2022]** *Bridging the skill gap between the acquired
  university curriculum and the requirements of the job market.* **Journal of Innovation &
  Knowledge** 7(3):100190. DOI [10.1016/j.jik.2022.100190](https://doi.org/10.1016/j.jik.2022.100190).
  — 서지계량 분석으로 교육–고용 스킬 불일치 실증. **문제 동기의 근거.**
- ✅ **[Zhang, Jensen, Sonniks & Plank 2022]** *SkillSpan: Hard and Soft Skill Extraction from
  English Job Postings.* **NAACL 2022**. arXiv [2204.12811](https://arxiv.org/abs/2204.12811).
  — 채용공고 스킬 span 추출 데이터셋/모델. **채용공고→요구역량 추출 근거.**
- ✅ **[Zhang, Jensen, van der Goot & Plank 2022]** *Skill Extraction from Job Postings using Weak
  Supervision.* RecSys-in-HR'22 (ACM RecSys 2022 workshop). arXiv [2209.08071](https://arxiv.org/abs/2209.08071).
  — ESCO 기반 약지도 스킬 추출. **저비용 대량 추출 방법.**
- ✅ **[Pérez Zúñiga, Martínez García & Oliva Ibarra 2025]** *Employability and its relationship
  with the competency-based approach...: a systematic review.* **Frontiers in Education.** DOI
  [10.3389/feduc.2025.1703144](https://doi.org/10.3389/feduc.2025.1703144). — 역량기반 접근이
  취업가능성과 유의한 관계. **역량 중심 추천의 교육학적 타당성.**
- ⚠️ **[Musazade, Mezei & Zhang 2026]** *UniSkill: A Dataset for Matching University Curricula to
  Professional Competencies.* LREC 2026. arXiv [2603.03134](https://arxiv.org/abs/2603.03134).
  — 과목–ESCO 역량 매핑 데이터셋(BERT F1 87%). **과목–역량 매핑 컴포넌트 근거.** *(2026 preprint —
  재확인 대상)*
- ⚠️ **[Soni, Suleiman & Singh 2025]** *Improving Graduate Outcomes by Identifying Skills Gaps and
  Recommending Courses Based on Career Interests.* arXiv [2511.09819](https://arxiv.org/abs/2511.09819).
  — 이력서·수강이력→스킬 추출→직무 요구와 비교→누락 스킬 과목 추천. **우리 파이프라인과 동일
  구조.** *(2025 preprint — 재확인 대상)*

---

## 3. 캡(cap) 기반 coverage 목적함수의 OR/CS 이론 근거 ★핵심

> **뒷받침 대상**: 목적함수 `max Σ_k ρ_{J,k}·cov_k`, `cov_k ≤ min(attained_k, ρ_{J,k})`
> — "요구수준에서 캡을 둬 한 역량 몰빵을 막고 여러 요구역량에 분산" (`ILP_추천_설계.md` §6, §7 C4).

- 🟡 **[Nemhauser, Wolsey & Fisher 1978]** *An analysis of approximations for maximizing submodular
  set functions—I.* **Mathematical Programming** 14:265–294. DOI
  [10.1007/BF01588971](https://doi.org/10.1007/BF01588971). — **한계효용 체감(submodularity)**
  정의와 greedy `1−1/e` 보장의 정전. 우리 캡 모델은 "캡 도달 후 한계기여=0" → 명시적 한계효용
  체감 구조. *(서지 다중 교차검증; Springer 본문은 로그인 리다이렉트로 정리 글자단위 미확인)*
- 🟡 **[Nemhauser & Wolsey 1988]** *Integer and Combinatorial Optimization.* Wiley. ISBN
  0-471-82819-X. 전자판 DOI [10.1002/9781118627372](https://onlinelibrary.wiley.com/doi/book/10.1002/9781118627372)
  (Ch.16 Matroid and Submodular Function Optimization). — Set Cover/Max Coverage ILP·부분모듈
  최적화 **교과서 정전 레퍼런스**. *(Ch.16 본문 페이월 402)*
- 🟡 **[Krause, McMahan, Guestrin & Gupta 2008]** *Robust Submodular Observation Selection.*
  **JMLR** 9:2761–2801. [jmlr.org/papers/v9/krause08b.html](https://jmlr.org/papers/v9/krause08b.html).
  — 목적을 임계치에서 **절단(truncation)** 하면 submodularity가 보존되며 다목적을 고르게 채움
  (Saturate). **"캡=truncation이 균형 분산을 유도한다"는 우리 주장의 가장 직접적 학술 근거.**
- ✅ **[Maximum Coverage Problem — 표준 ILP 정식화]** (정전: NWF 1978 / N&W 1988).
  `max Σ_j y_j  s.t.  Σ_i x_i ≤ k,  Σ_{i: e_j∈S_i} x_i ≥ y_j,  x,y∈{0,1}`. — 우리 골격(과목
  선택변수 + 역량 coverage 변수 + "역량이 커버되려면 해당 과목 중 하나 선택")과 동형. 우리는
  binary `y_j` 대신 캡된 `cov_k`를 얹은 **가중·포화(saturated) 변형.**
- ✅ **[Max-min 선형화 — hypograph trick]** Lessard, *Introduction to Optimization* (CS/ECE/ISyE
  524), UW–Madison 강의자료; 개념근거 **[Stein 2024/25]** *A tutorial on properties of the epigraph
  reformulation*, **EURO Journal on Computational Optimization** ([S2192440625000061](https://www.sciencedirect.com/science/article/pii/S2192440625000061)).
  — 목적에서 최소값을 **최대화**할 때는 `t ≤ aᵢ` 제약만으로 `min`을 구현(이진변수·big-M 불필요).
  → 우리 `cov_k ≤ attained_k`, `cov_k ≤ ρ_k` 두 선형 제약이 정확히 그 케이스.
- ❌ **"coverage 최대화 = gap 최소화 동치"의 전용 출처**: 미발견. 자명한 항등식이므로 **부록 보조정리로
  직접 증명**한다. 단, **단순 동치가 아니라 가중 동치임에 주의**:
  - 일반식: `max Σ_k w_k·cov_k  ⇔  min Σ_k w_k·gap_k` (`gap_k = ρ_k − cov_k`, 상수 `Σ_k w_k·ρ_k`).
  - **본 설계는 `w_k = ρ_k`** 이므로, 동치되는 것은 단순 부족분 `Σ(ρ_k−cov_k)`가 아니라
    **ρ-가중 부족분 `Σ_k ρ_k·(ρ_k − cov_k)`**, 상수는 **`Σ_k ρ_k²`**. 발표 시 "어떤 가중치의 갭이냐"는
    질문에 "ρ-가중 갭, 상수 Σρ²"로 답할 것. (설계문서 §6·§11과 표현 일치시킴)

---

## 4. 시간충돌 제약의 UCTP(University Course Timetabling) ILP 근거

> **뒷받침 대상**: 분반 변수 `y_{c,s}∈{0,1}`, 슬롯당 `Σ y ≤ 1`(시간충돌), 과목당 분반 택1
> `Σ_s y_{c,s} ≤ 1` (`ILP_추천_설계.md` §5, §7 C1·C3, §8).

- ✅ **[Daskalaki, Birbas & Housos 2004]** *An integer programming formulation for a case study in
  university timetabling.* **EJOR** 153(1):117–135. DOI
  [10.1016/S0377-2217(03)00103-6](https://doi.org/10.1016/S0377-2217(03)00103-6). — 0–1 IP
  정식화. **Constraint 1·2**: 각 교시 교수/학생그룹당 `Σ x ≤ 1`. **우리 슬롯충돌 제약의 표준 원형.
  최우선 인용.**
- ✅ **[Bettinelli, Cacchiani, Roberti & Toth 2015]** *An overview of curriculum-based course
  timetabling.* **TOP** 23:313–349. DOI [10.1007/s11750-015-0366-z](https://doi.org/10.1007/s11750-015-0366-z).
  — ITC-2007 CB-CTT 표준 변수 `x_{chr}`, 충돌제약 Eq.5·6 `Σ x ≤ 1`. **국제표준 survey 인용.**
- ✅ **[Prabodanie 2017]** *An Integer Programming Model for a Complex University Timetabling
  Problem.* **IEMS** 16(1):141–153. DOI [10.7232/IEMS.2017.16.1.141](https://doi.org/10.7232/IEMS.2017.16.1.141).
  — 학생그룹 `Σ Y_{gc}·x ≤ 1`(슬롯당 한 과목). **enrollment 행렬 모델링 참고.**
- ✅ **[Di Gaspero & Schaerf 2007]** *Curriculum-based Course Timetabling* (ITC-2007 Track 3 공식
  기술보고서, Univ. of Udine). [PDF](https://www.eeecs.qub.ac.uk/itc2007/curriculmcourse/report/curriculumtechreport.pdf).
  — 하드제약 H2(강의실)·H3(충돌) `Σ x_{c,r,p} ≤ 1`. **국제경쟁 표준 정식화.**
- 🟡 **[Schaerf 1999]** *A Survey of Automated Timetabling.* **AI Review** 13:87–127. DOI
  [10.1023/A:1006576209967](https://doi.org/10.1023/A:1006576209967). — UCTP 표준 survey, 후속
  모든 ILP 논문의 기초. **배경 기술 인용.** *(전문 구독 필요, 서지 다중확인)*
- 🟡 **[MirHassani 2006]** *A computational approach to enhancing course timetabling with integer
  programming.* **Applied Math. and Computation** 175:814–822. DOI
  [10.1016/j.amc.2005.07.039](https://doi.org/10.1016/j.amc.2005.07.039). — "novel 0–1 IP
  formulation". *(서지·초록 확인, 전문 페이월)*
- ✅ **[Talmor 2024]** *Optimizing Academic Timetables Using ILP: A Case Study.* **Education Science
  and Management** 2(3):176–187. DOI [10.56578/esm020305](https://doi.org/10.56578/esm020305).
  — CBC 엔진, 이진+보조연속변수. **PuLP 기본 솔버(CBC) 실증 사례로 유용.**
- 🟡 **[Burke & Petrovic 2002]** *Recent research directions in automated timetabling.* **EJOR**
  140(2):266–280. — 충돌(clash) 제약을 핵심 하드제약으로 분류한 컨센서스 문헌. *(서지확인)*
- ✅ **[Wasfy & Aloul 2007]** *Solving the University Class Scheduling Problem Using Advanced ILP
  Techniques.* IEEE GCC 2007. — 0-1 ILP가 "tractable for reasonable-sized" 실증. *(초록 확인)*

> **주의(혼동 방지)**: Daskalaki et al. **2004**(EJOR 153, 정식화)과 Daskalaki & Birbas **2005**(EJOR
> 160, 효율적 해법)은 다른 논문. 또한 UCTP는 본래 "기관이 강의를 시간에 배치"하는 문제 — 우리는
> 이를 "학생이 개설 분반 중 충돌 없이 선택"으로 변용한 것이므로, 충돌제약 형태(`Σ y ≤ 1`)는 동일하나
> 문제 주체가 다름을 명시할 것.

---

## 5. 역량 taxonomy 출처: NCS·O*NET (공식 1차 검증)

> **뒷받침 대상**: `docs/역량_taxonomy_근거.md`의 10개 역량 분류 출처.

### 5-1. 공식 출처 (인용 가능)

| 출처 | 발행기관 | 버전/근거 | URL |
|------|---------|----------|-----|
| NCS 공식 포털 | 한국산업인력공단 / 고용노동부 | 세분류 1,096개(2025.12 기준), 대분류 24개 | https://www.ncs.go.kr |
| 자격기본법 제2조 제2호 | 대한민국 (법률 제19095호) | NCS 법적 정의 | https://www.law.go.kr |
| O*NET OnLine | USDOL/ETA · National Center for O*NET Development | **O*NET 30.3** (2026.5), 2018 SOC 기반 | https://www.onetonline.org |
| O*NET Content Model | USDOL/ETA | Skills/Abilities/Knowledge/Work Activities | https://www.onetcenter.org/content.html |

> ✅ 자격기본법 제2조2호 원문, NCS 대분류 24개 통계, O*NET Content Model·Essential Skills·Knowledge
> 구조를 모두 공식 페이지 WebFetch로 직접 확인함.

### 5-2. ★정오표 — `역량_taxonomy_근거.md` 수정 필요 (O*NET 직접 대조)

> ✅ **반영 완료(본 브랜치).** 아래 ❌ 2건은 `docs/역량_taxonomy_근거.md`에 **정정 적용됨**:
> VIZ `15-1199.08`→`15-2051.01`, FIN NCS `02`→`03 재무·회계`. 나머지 ⚠️(정보통신 중분류 표기,
> DATA/ML/COMM 코드 뉘앙스, 병기 권장 코드)는 담당자 합의가 필요한 사안이라 본 표에 정리만 하고
> **원본은 미변경** — 팀 논의 후 반영.

| 역량 | 문서 기재 SOC | O*NET 직접 확인 | 판정 |
|------|-------------|----------------|------|
| PROG | 15-1252.00 | Software Developers | ✅ 정확 |
| DB | 15-1242.00 | Database Administrators | ✅ 정확 |
| BIZ | 11-1021.00 | General and Operations Managers | ✅ 정확 |
| MKT | 11-2021.00 | Marketing Managers | ✅ 정확 |
| OR | 15-2031.00 | Operations Research Analysts | ✅ 정확 |
| FIN | 13-2011.00 | Accountants and Auditors | ✅ 정확 (재무분석 맥락엔 **13-2051.00 Financial and Investment Analysts** 병기 권장) |
| DATA | 15-2041.00 | **Statisticians** | ⚠️ 코드 실재하나 "통계학자". 데이터분석가는 **15-2051.01 BI Analysts** 더 근접 — 발표 시 명시 |
| ML | 15-1221.00 | Computer and Information Research Scientists | ⚠️ AI연구자. 실무 ML엔 **15-2051.00 Data Scientists** 병기 권장 |
| COMM | 27-3031.00 | Public Relations Specialists | ⚠️ 범위 좁음. 협업 일반엔 부분적합 |
| **VIZ** | **15-1199.08** | **폐지 코드 → 15-2051.01 Business Intelligence Analysts로 리다이렉트** | ❌ **오류 — 15-2051.01로 정정 필요** |

| 역량 | 문서 기재 NCS | 공식 NCS | 판정 |
|------|-------------|---------|------|
| **FIN** | 02 경영·회계·사무 → **02 재무·회계** | 02 경영·회계·사무 → **03 재무·회계** | ❌ **중분류 번호 오류 — 03으로 정정** |
| BIZ | …→ 01 기획 | …→ 01 기획**사무** → 경영기획 | ⚠️ 명칭 정밀화 |
| MKT | …→ 03 마케팅 | …→ 01 기획사무 → **02 마케팅·홍보·조사** | ⚠️ 경로 정정 |
| COMM | …→ 04 사무 | …→ 02 총무·인사 → 일반사무 → 사무행정 | ⚠️ 경로 정정 |
| PROG/DATA/ML/DB/VIZ | 20 정보통신 → "02 SW개발·구축 / 03 데이터분석 / 04 DB·빅데이터" | 20 정보통신 → 01 정보기술 → 02 정보기술개발 → (응용SW/DB엔지니어링 등 세분류) | ⚠️ 중분류 표기가 공식 명칭 아님 |

> **NCS 세분류 페이지는 JS 동적 렌더링**이라 일부는 공식 채용 직무기술서로 교차확인. 완전 목록은
> [NCS 검색](https://www.ncs.go.kr/unity/th03/ncsSearchMain.do) 또는 공공데이터포털 NCS Open API 권장.

---

## 6. 설계 선택 ↔ 근거 매핑 (요약)

| 설계 선택 (`ILP_추천_설계.md`) | 핵심 근거 | 강도 |
|---|---|---|
| ILP로 과목 선택 최적화, 졸업요건=제약·목표=목적 | Shakhsi-Niaei 2020, Christou 2022, Slim 2025 | **강(원문확인)** |
| 직무 요구역량↔학생 보유역량 갭 메우기 | Frej 2024(SIGIR), Ahadi 2022, Zhu 2020 | **강(원문확인)** |
| 채용공고에서 직무 요구역량 추출(직무 기준) | Zhang 2022 ×2(NAACL/RecSys) | 강 |
| 캡 기반 coverage = 한계효용 체감·균형분산 | NWF 1978, Krause 2008, N&W 1988 | **중(서지확인, 본문 미대조)** |
| `cov ≤ min(a,b)` 두 선형제약 선형화 | Stein 2024(원문확인), Lessard 강의자료(보조) | **강(개념 원문확인)** |
| 슬롯당 분반 ≤1 시간충돌 제약 | Daskalaki 2004, Bettinelli 2015, Di Gaspero 2007 | **강(원문확인)** |
| PuLP 기본 솔버(CBC)로 합리적 시간 내 풀림 | Talmor 2024(CBC 실증), Christou 2022(GUROBI 10초) | **중(원문확인, 솔버 상이)** |
| 역량 taxonomy NCS+O*NET | ncs.go.kr, onetonline.org (단, §5-2 정오 반영) | 공식확인(정정 필요) |

---

## 7. 인용 시 주의사항 (과장 방지 — 반드시 준수)

1. **(1−1/e) greedy 보장은 우리 솔버의 보장이 아니다.** 우리는 ILP로 **정확해**를 구하므로,
   NWF 1978은 "한계효용 체감 구조가 분산을 유도한다"는 *구조적 성질*의 근거로만 인용하고, "우리
   해가 (1−1/e)-근사"라고 쓰면 안 된다.
2. **min 선형화의 'big-M 불필요'는 조건부.** 목적이 `cov_k`에 대해 **단조 증가(최대화)** 일 때만
   두 상한 제약으로 충분하다. 등식 `cov=min(a,b)`를 부호 무관하게 강제하면 이진변수 필요. 논문에
   이 단조성 조건을 명시할 것.
3. **"coverage=gap 동치"는 자체 증명으로** 처리(전용 출처 없음, §3 마지막).
4. **Dechter 2009는 게재처 미확정([검증실패])** — 도서관 DB로 1차 확인 전 인용 보류.
5. **2025–2026 arXiv preprint**(Soni 2025, Musazade 2026): 실재·서지 검증 루프에서 확인됨. peer-review
   정식 게재 여부만 추가 확인 후 인용.
6. **UCTP 문헌은 problem 주체가 다름**(기관 배치 vs 학생 선택) — 충돌제약 형태만 차용함을 명시.
7. **PuLP를 직접 쓴 코스추천 peer-reviewed 논문은 미발견** — 선행연구는 GUROBI/CPLEX 사용. PuLP는
   구현도구로서 공식 문서를 별도 인용. (단 PuLP 기본 솔버 CBC의 이 규모 적용 가능성은 Talmor 2024가
   CBC로 실증.)
8. **`λ`(졸업 보너스)·`μ`(소프트 제약 페널티)는 학술 근거가 아닌 운영 파라미터다.** 가중합 다목적
   스칼라화 자체는 표준 기법이나(Shakhsi-Niaei 2020의 "목적 가중치"와 정렬), 구체적 값은 인용으로
   정당화하지 않고 **정규화(§설계 §6) 후 실측 튜닝**(설계문서 부록 A)으로 정한다 — 의도된 운영 결정.
9. **목적함수 두 항의 스케일을 반드시 정규화**할 것: 직무 항은 `[0,1]` 스케일이나 졸업 학점은 단위가
   커서, 정규화 없이는 `λ`가 작아도 졸업 항이 직무 항을 압도할 수 있다(설계문서 §6에서 `grad_g/need_g`로
   정규화 반영).

---

## 8. 본 리서치의 차별점 (선행연구 공백 → 발표 강조점)

선행연구(Frej 2024, Soni 2025 등)는 과목 추천까지는 하지만, **① 한 학기 시간표 제약(분반 시간충돌·
학점상한)을 ILP로 동시에 풀고 ② 채용공고 기반 직무 요구역량과 ③ 졸업요건을 한 모델에 통합**한 사례는
확인되지 않았다. 특히 **한국 대학 학점규정·한국어 채용공고** 맥락의 연구는 부재. 이 통합이 course-fit의
핵심 기여다.

---

## 부록. 검증 방법 메모

- 5개 주제를 병렬 리서치 에이전트가 분담, 각 출처를 WebSearch 후 **WebFetch로 원문/공식 페이지를
  직접 열어** 서지·내용을 대조(스니펫 비의존).
- 페이월(402/403)·동적 렌더링으로 본문 글자단위 확인이 막힌 경우 서지정보를 다중 독립 출처(Springer/
  ACM DL/RePEc/Semantic Scholar 등)로 교차검증하고 🟡로 표기.
- 검증 상태가 ❌/⚠️인 항목은 §7에 인용 제약을 명시. 본 문서는 §6 검증 루프에서 재대조됨.
