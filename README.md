```
course-fit/
├── README.md                    # 이 파일
├── .gitignore
├── requirements.txt
│
├── db/
│   ├── schema.sql              # CREATE TABLE 문 (10개 테이블)
│   ├── ingest.py               # CSV → SQLite 통합 스크립트
│   └── app.db                  # 생성된 DB (gitignore)
│
├── data/                       # 크롤링 산출물 (CSV, git 포함)
│   ├── README.md               # CSV 컬럼 스펙
│   ├── department.csv
│   ├── graduation_requirement.csv
│   ├── course.csv
│   ├── competency.csv
│   ├── job.csv
│   ├── job_posting.csv
│   ├── course_competency.csv
│   └── job_competency.csv
│
├── crawlers/
│   ├── grad_requirement/       # 졸업요건 책자 파싱
│   ├── courses/                # 학교 홈페이지 과목 크롤링
│   └── job_postings/           # 채용공고 크롤링
│
├── mapping/                    # LLM 매핑
│   ├── prompts/
│   ├── map_courses.py
│   └── map_postings.py
│
├── recommender/                # ILP 추천 엔진
│   ├── student_competency.py
│   ├── gap.py
│   ├── score.py
│   └── ilp_solver.py
│
├── tests/
│   └── test_ingest.py
│
└── docs/
    └── 졸업요건_파싱_노트.md
```