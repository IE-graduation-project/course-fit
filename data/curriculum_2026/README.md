# 전학과 교육과정 데이터 (서울캠 2026) — 출처와 재현

course-fit 을 산업데이터공학과(IDE)·경영(BIZ) 파일럿에서 **홍익대 서울캠 전 학과**로 넓힐 때
쓴 교육과정 데이터의 1차 소스와 생성 스크립트다 (이슈 #57). 라이브 데이터는 `../*.csv` 이고,
이 디렉터리는 그걸 어떻게 만들었는지(출처·방법·한계)를 남겨 재현과 검증이 가능하게 한다.

## 구성
- `parsed/<CODE>.json` — 서울캠 50학과 교육과정 판독 결과. 학과별 과목 목록(학수번호·과목명·학점·
  학년·학기·이수구분 raw·전공필수 여부). 2026 교과과정 책자 e-book 판독본.
- `grad_requirements.json` — 단과대별 졸업 요건 추출본. 책자 「교과과정 개편에 따른 졸업학점 현황」
  표에서 영역별 최소학점·총 졸업학점을 읽고, 각 값에 **출처 페이지**를 붙였다. 인쇄된 숫자만 기록,
  미인쇄는 null + 사유.
- `grad_requirements_6.json` — 앞 표에 없던 융합전공 6개의 섹션 판독 결과.
- `load_all_departments.py` — 위 두 소스를 읽어 `../department.csv`·`graduation_requirement.csv`·
  `course.csv`·`course_dept.csv` 로 병합하는 로더(재현용).
- `load_report.txt` — 학과별 적재 로그(전공 학점 분해, 소속 단과대).

## 출처와 방법 (1차 소스)
- 교육과정·졸업요건: 홍익대 2026 교과과정 책자 e-book(`ibookcontents.hongik.ac.kr`). 교내망 전용.
- 시간표: `cn.hongik.ac.kr/app/timetable` 의 학부 스코프(서울 45개, 세종 제외) 크롤 → 교시 전처리.
- **전공 학점 분해**: 책자는 전공을 "전공 N학점(전공필수 포함)" 합계로만 준다. 이를
  전공필수 = 판독 전공필수 과목 학점 합, 전공선택 = N − 전공필수 로 나눴다(전 학과 정합 확인).
- **이수구분(area) 매핑**: IDE/BIZ 실측(raw_area→DB area)을 지상진실로, 타 단과대 전용 area
  (교직·교양선택·기본소양 계열)만 규칙으로 확장. 상세는 `load_all_departments.py` 의 `norm_area`.
- 교양필수·공통교양·특성화교양·SW데이터활용역량·전공기초영어 = 전교/단과대 공통 → `COMMON`.
  전공필수·전공선택·전공기초·MSC = 학과 고유. 일반선택 = 후보 제외.

## 융합전공 6학과(ASA·ELA·BDB·FMB·MAI·HCS) — 선택지에서 제외
재조사(`grad_requirements_6_research.json`) 결과, 이 6개는 모두 **다전공형 융합전공**이다.
독립 졸업학점이 없고, 주전공(소속 학과) 졸업요건을 채우면서 융합전공 교과목 36학점(중복 최대
12)을 더 듣는 구조다(책자 융합전공 섹션 머리말 "36학점 이상", 정본 『융합전공 이수내규』
제2장9조4항). 따라서 "내 학과 졸업요건"을 묻는 course-fit 의 **주전공 선택지가 될 수 없어 제외**한다.
- 과목(course/course_dept)은 카탈로그에 남겨 공유 후보로 쓰되, graduation_requirement 를 만들지
  않아 학과 드롭다운(department ⋈ graduation_requirement)에서 자연히 빠진다.
- ELA·BDB·FMB 는 세종캠 전공이기도 하다(goDetail01 p_campus=2, BDB 상경·광홍, FMB AID융합과기대).
- 각 전공별 총 졸업학점은 비공개 『융합전공 이수내규』에 있고 한국망 밖에서 접근이 막혀 확정 못 했다.
  한국 IP(포털 로그인·VPN)에서 이수내규 원문을 받으면 채울 수 있다.
- **구분**: DEN·IOT·IRB·SCD·DSC 는 책자 page-26~28 이 자율전공 "주전공" 졸업요건(전공50·MSC24·
  총132)을 명시해, 정당한 주전공 경로가 있어 포함한다. 위 6개는 그 명시가 없다.

## 알려진 한계
- 건축학전공(ARCH)은 5년제라 5학년 지정 과목(grade=5)이 있다. 적재는 허용하나, 추천 엔진의
  학년 상한은 4년제 기준이라 5학년 과목 추천은 미지원(학과별 수업연한 모델이 후속 과제).
- 일부 신설·융합 전공(DEN·IOT 등)은 판독 전공필수 플래그가 없어 전공필수 하한이 0으로 적재된다
  (전공선택 하한은 정상).

## 재현
```
python data/curriculum_2026/load_all_departments.py   # parsed + grad_requirements → data/*.csv 병합
python db/ingest.py --reset                            # DB 재빌드 + 무결성 검증
python -m pytest                                       # 회귀
```
