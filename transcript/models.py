"""성적표 파싱 결과 데이터 모델 (이슈 #16).

parse.py(PDF 추출)와 load.py(DB 적재)가 공유하는 구조체.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StudentMeta:
    """학생 메타데이터 (성적표 상단 정보)."""

    student_no: str | None = None       # 학번
    name: str | None = None             # 성명
    dept_id: str | None = None          # 매핑된 학과 (IDE/BIZ), 실패 시 None
    dept_name_raw: str | None = None    # 성적표 원문 학과명
    admission_year: int | None = None   # 입학년도
    current_grade: int | None = None    # 이번 학기 학년 (마지막 확정 학기의 다음 학기, #42)
    total_earned: int | None = None     # 총 취득학점
    gpa: float | None = None            # 전체 평점평균
    # 직전학기 = 성적이 나온 마지막 정규학기(계절학기 제외). 수강가능학점 계산용(transcript.credit_limit)
    last_term: str | None = None            # 예: 2026-1
    last_term_level: int | None = None       # 그 학기의 학년
    last_term_registered: int | None = None  # 그 학기 신청학점 (성적표 「신청학점」 줄)
    last_term_gpa: float | None = None       # 그 학기 신청평점 (성적표 「신청평점」 줄)
    last_term_f_count: int = 0               # 그 학기 F 과목 수 (2과목 이상이면 학사경고)
    regular_term_count: int = 0              # 이수한 정규학기 수


@dataclass
class TakenCourse:
    """성적표 과목 한 줄."""

    course_name: str
    credit: int
    course_id: str | None = None        # 학수번호 (없을 수 있음)
    category_raw: str | None = None     # 이수구분 원문 (전필/전선/교양 등)
    area: str | None = None             # area enum 매핑값 (실패 시 None)
    grade_letter: str | None = None     # 등급 원문 (A+, B0, P, F, NP)
    grade: float | None = None          # 4.5 환산 (P/N/F 등 비해당 시 None)
    is_pn: bool = False                 # P/N 과목 여부
    passed: bool = False                # 이수(취득) 여부
    superseded: bool = False            # 재수강으로 대체된 이전 시도 (집계 제외, 이력 보존)
    term: str | None = None             # 수강 학기 (예: 2023-1, 2025-S)
    matched: bool = False               # course 카탈로그 매칭 여부 (적재 시 확정)


@dataclass
class TranscriptResult:
    """성적표 1건의 파싱 결과."""

    input_hash: str
    meta: StudentMeta
    courses: list[TakenCourse] = field(default_factory=list)
