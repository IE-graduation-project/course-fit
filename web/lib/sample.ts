/**
 * 데모용 샘플 성적표 — 실제 학생 성적이 아니다.
 *
 * 학수번호·과목명은 홍익대 공개 강의목록(data/catalog_crawl_raw.csv)에서 가져온
 * 공개 정보이고, 성적은 데모를 위해 임의로 채웠다. 개인정보 없음.
 *
 * 학과·학번마다 따로 둔다(#41, #51). 경영학과 성적표를 산업데이터공학과로 돌리면 학번·학년·과목이
 * 전부 어긋난다 — 「2026학번인데 3학년까지 경영 전공을 들은 학생」이 된다. 학번이 다르면 학년이
 * 다르고(#42), 학년이 다르면 추천 후보가 다르다.
 * tests/test_samples.py 가 샘플마다 과목이 카탈로그에 있는지, 학과·입학년도·학년이 맞는지 본다.
 */

/** 경영학과 22학번, 3학년 2학기까지 (휴학 1년). 007001 은 폐지 과목이라 카탈로그에 없다 — 실제 성적표에도 이런 과목이 섞인다. */
const BIZ_2022 = `전체성적조회<
2022학년도 1학년 1학기
학수번호	과목명	영문과목명	학점	성적	재수강
033102	경제학원론	PRINCIPLES OF ECONOMICS	3	B+
033103	경영경제수학	MATHEMATICS FOR BUSINESS	3	C0
033104	회계원리	PRINCIPLES OF ACCOUNTING	3	B+
311103	경영과비젼	MANAGEMENT & VISION	3	B+
007001	교양영어(1)	ENGLISH FOR GENERAL STUDIES(1)	1	P
신청학점 13 신청평점 3.10
취득학점 13 증명평점 3.10
2022학년도 1학년 2학기
학수번호	과목명	영문과목명	학점	성적	재수강
033203	기업과경영	INTRODUCTION TO BUSINESS ADMINISTRATION	3	C+
311203	재무회계	FINANCIAL ACCOUNTING	3	B0
311204	경영통계학	BUSINESS STATISTICS	3	C+
311206	비즈니스프로그래밍Ⅰ	BUSINESS PROGRAMMING Ⅰ	3	B0
신청학점 12 신청평점 2.80
취득학점 12 증명평점 2.80
2024학년도 2학년 2학기
학수번호	과목명	영문과목명	학점	성적	재수강
311318	FinanceⅠ(*)	FINANCEⅠ	3	A0
311406	생산과경영	PRODUCTION AND OPERATIONS MANAGEMENT	3	C+
311407	투자론	INVESTMENTS	3	B+
313101	마케팅(*)	MARKETING	3	A0
002019	인간관계론(C)	HUMAN RELATIONSHIP	3	B+
신청학점 15 신청평점 3.50
취득학점 15 증명평점 3.50
2025학년도 3학년 1학기
학수번호	과목명	영문과목명	학점	성적	재수강
008750	컴퓨터프로그래밍(COMP. THINKING)(C)	COMPUTATIONAL THINKING	3	A+
311309	조직행동(*)	ORGANIZATIONAL BEHAVIOR	3	A+
001009	영어	ENGLISH	3	B+
002604	교양중국어(2)	BASIC CHINESE(2)	2	B+
신청학점 11 신청평점 3.95
취득학점 11 증명평점 3.95
2025학년도 3학년 2학기
학수번호	과목명	영문과목명	학점	성적	재수강
311707	전략경영(*)	STRATEGIC MANAGEMENT	3	A0
311822	디지털마케팅애널리틱스(*)	DIGITAL MARKETING ANALYTICS	3	B+
311623	AI를활용한스타트업	AI-POWERED STARTUP	3	B+
002059	현대생활과디자인	MODERN LIFE & DESIGN	3	B+
신청학점 12 신청평점 3.55
취득학점 12 증명평점 3.55
전체성적
총 취득학점	63 학점
총 증명평점	3.38 점
`;

/** 경영학과 26학번, 1학년 1학기까지. */
const BIZ_2026 = `전체성적조회<
2026학년도 1학년 1학기
학수번호	과목명	영문과목명	학점	성적	재수강
033102	경제학원론	PRINCIPLES OF ECONOMICS	3	B+
033103	경영경제수학	MATHEMATICS FOR BUSINESS	3	B0
033104	회계원리	PRINCIPLES OF ACCOUNTING	3	A0
311103	경영과비젼	MANAGEMENT & VISION	3	A0
001009	영어	ENGLISH	3	B+
신청학점 15 신청평점 3.60
취득학점 15 증명평점 3.60
전체성적
총 취득학점	15 학점
총 증명평점	3.60 점
`;

/** 경영학과 25학번, 2학년 1학기까지. */
const BIZ_2025 = `전체성적조회<
2025학년도 1학년 1학기
학수번호	과목명	영문과목명	학점	성적	재수강
033102	경제학원론	PRINCIPLES OF ECONOMICS	3	B+
033103	경영경제수학	MATHEMATICS FOR BUSINESS	3	B0
033104	회계원리	PRINCIPLES OF ACCOUNTING	3	A0
311103	경영과비젼	MANAGEMENT & VISION	3	A0
001009	영어	ENGLISH	3	B+
신청학점 15 신청평점 3.60
취득학점 15 증명평점 3.60
2025학년도 1학년 2학기
학수번호	과목명	영문과목명	학점	성적	재수강
033203	기업과경영	INTRODUCTION TO BUSINESS ADMINISTRATION	3	B+
311203	재무회계	FINANCIAL ACCOUNTING	3	B0
311204	경영통계학	BUSINESS STATISTICS	3	C+
311206	비즈니스프로그래밍Ⅰ	BUSINESS PROGRAMMING Ⅰ	3	A0
008750	컴퓨터프로그래밍(COMP. THINKING)(C)	COMPUTATIONAL THINKING	3	A+
신청학점 15 신청평점 3.50
취득학점 15 증명평점 3.50
2026학년도 2학년 1학기
학수번호	과목명	영문과목명	학점	성적	재수강
311318	FinanceⅠ(*)	FINANCEⅠ	3	A0
311406	생산과경영	PRODUCTION AND OPERATIONS MANAGEMENT	3	B+
313101	마케팅(*)	MARKETING	3	A+
002019	인간관계론(C)	HUMAN RELATIONSHIP	3	B+
311309	조직행동(*)	ORGANIZATIONAL BEHAVIOR	3	A0
신청학점 15 신청평점 3.90
취득학점 15 증명평점 3.90
전체성적
총 취득학점	45 학점
총 증명평점	3.67 점
`;

/** 경영학과 24학번, 3학년 1학기까지. */
const BIZ_2024 = `전체성적조회<
2024학년도 1학년 1학기
학수번호	과목명	영문과목명	학점	성적	재수강
033102	경제학원론	PRINCIPLES OF ECONOMICS	3	B+
033103	경영경제수학	MATHEMATICS FOR BUSINESS	3	B0
033104	회계원리	PRINCIPLES OF ACCOUNTING	3	A0
311103	경영과비젼	MANAGEMENT & VISION	3	A0
001009	영어	ENGLISH	3	B+
신청학점 15 신청평점 3.60
취득학점 15 증명평점 3.60
2024학년도 1학년 2학기
학수번호	과목명	영문과목명	학점	성적	재수강
033203	기업과경영	INTRODUCTION TO BUSINESS ADMINISTRATION	3	B+
311203	재무회계	FINANCIAL ACCOUNTING	3	B0
311204	경영통계학	BUSINESS STATISTICS	3	C+
311206	비즈니스프로그래밍Ⅰ	BUSINESS PROGRAMMING Ⅰ	3	A0
008750	컴퓨터프로그래밍(COMP. THINKING)(C)	COMPUTATIONAL THINKING	3	A+
신청학점 15 신청평점 3.50
취득학점 15 증명평점 3.50
2025학년도 2학년 1학기
학수번호	과목명	영문과목명	학점	성적	재수강
311318	FinanceⅠ(*)	FINANCEⅠ	3	A0
311406	생산과경영	PRODUCTION AND OPERATIONS MANAGEMENT	3	B+
313101	마케팅(*)	MARKETING	3	A+
002019	인간관계론(C)	HUMAN RELATIONSHIP	3	B+
신청학점 12 신청평점 3.88
취득학점 12 증명평점 3.88
2025학년도 2학년 2학기
학수번호	과목명	영문과목명	학점	성적	재수강
311309	조직행동(*)	ORGANIZATIONAL BEHAVIOR	3	A+
311707	전략경영(*)	STRATEGIC MANAGEMENT	3	A0
002604	교양중국어(2)	BASIC CHINESE(2)	2	B+
신청학점 8 신청평점 4.06
취득학점 8 증명평점 4.06
2026학년도 3학년 1학기
학수번호	과목명	영문과목명	학점	성적	재수강
311407	투자론	INVESTMENTS	3	B+
311623	AI를활용한스타트업	AI-POWERED STARTUP	3	A0
002059	현대생활과디자인	MODERN LIFE & DESIGN	3	B+
신청학점 9 신청평점 3.67
취득학점 9 증명평점 3.67
전체성적
총 취득학점	59 학점
총 증명평점	3.70 점
`;

/** 산업데이터공학과 26학번, 1학년 1학기까지. 2026-1 에 1학년 대상으로 실제 개설된 과목이다. */
const IDE_2026 = `전체성적조회<
2026학년도 1학년 1학기
학수번호	과목명	영문과목명	학점	성적	재수강
012201	대학수학(1)	CALCULUS(1)	3	B+
012101	대학물리(1)	PHYSICS(1)	3	B0
012103	대학물리실험(1)	PHYSICS LABORATORY(1)	1	A0
012321	프로그래밍기초	FUNDAMENTALS OF PROGRAMMING	3	A+
001012	논리적사고와글쓰기(공학)	LOGICAL THINKING AND WRITING(ENGINEERING)	3	A0
001023	대학영어	COLLEGE ENGLISH	3	B+
004189	산업·데이터공학의이해	UNDERSTANDING INDUSTRIAL AND DATA ENGINEERING	3	A+
신청학점 19 신청평점 3.84
취득학점 19 증명평점 3.84
전체성적
총 취득학점	19 학점
총 증명평점	3.84 점
`;

/** 학과 코드 → 학번 → 샘플. 없는 조합은 「샘플로 먼저 볼래요」를 띄우지 않는다.
 * 산업데이터공학과는 2026학년도 교육과정만 넣어 두어 1학년 샘플 하나뿐이다. */
export const SAMPLE_TRANSCRIPTS: Readonly<Record<string, Readonly<Record<number, string>>>> = {
  BIZ: { 2022: BIZ_2022, 2024: BIZ_2024, 2025: BIZ_2025, 2026: BIZ_2026 },
  IDE: { 2026: IDE_2026 },
};
