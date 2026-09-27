"""클래스넷 전체성적조회 복붙 텍스트 파서 (이슈 #16, 트랙 2).

학생이 클래스넷 좌측 '성적정보 > 전체성적조회' 화면을 Ctrl+A/C/V 한 텍스트를 파싱한다.

이 포맷의 특징(샘플 분석):
- 학기 헤더: `2022학년도 1학년 1학기` (학년은 0/N 가능, 학기는 1/2학기, 하계/동계계절학기)
- 컬럼: 학수번호, 과목명, 영문과목명, 학점, 성적, 재수강  (이수구분 컬럼 없음)
- 성적: A+ ~ D0, P, F, 또는 공란
- 공란 = 일반과목 F(미이수), 'F' 표기 = P/N과목 F (footer 규칙)
- '재수강' 표시 행 = 재수강으로 대체된 이전 시도 -> 성적증명서 미포함 (집계 제외, 이력 보존)
- 학번/성명/학과/입학년도는 화면에 없음 -> dept_id/admission_year는 학생이 입력(인자로 받음)
- 전체성적조회엔 성적 확정 학기만 나옴 -> 공란을 F로 처리해도 진행중 과목 오인 없음
"""

from __future__ import annotations

import re

from . import mappings
from .models import StudentMeta, TakenCourse, TranscriptResult

_SEM_RE = re.compile(r"^\s*(\d{4})학년도\s+(\d+)학년\s+(\S+?)\s*$")
_COURSE_ID_RE = re.compile(r"^\d{6}$")
_CREDIT_RE = re.compile(r"^\d{1,2}$")
_GRADE_TOKENS = {"A+", "A0", "B+", "B0", "C+", "C0", "D+", "D0", "F", "P", "NP", "N"}
_RETAKE_TOKEN = "재수강"
_SKIP_PREFIX = ("학수번호", "신청학점", "취득학점", "전체성적조회")
_TERM_CODE = {"1학기": "1", "2학기": "2", "하계계절학기": "S", "동계계절학기": "W"}
_REGULAR_SEMESTER = {"1학기": 1, "2학기": 2}
MAX_GRADE = 4


def grade_in_next_semester(regular_terms: list[tuple[int, int, int]]) -> int | None:
    """(학년도, 학기, 학년) 목록에서 성적이 확정된 마지막 정규학기의 **다음 학기** 학년.

    전체성적조회엔 성적이 확정된 학기만 나온다. 그래서 학생이 지금 다니는 학기는
    마지막 학기의 다음이다 — 3학년 2학기까지 나온 학생은 이번 학기 4학년이고,
    3학년 1학기까지 나온 학생은 아직 3학년이다. 추천은 이번 학기 수강신청용이라
    이 값을 써야 한다(#42). 계절학기와 0학년 표기는 학년 진급과 무관해 뺀다.
    """
    if not regular_terms:
        return None
    _, semester, level = max(regular_terms)
    return min(level + 1 if semester == 2 else level, MAX_GRADE)


def _split_fields(line: str) -> list[str]:
    """탭 우선 분리, 없으면 2칸 이상 공백으로 분리(웹 복붙 대응)."""
    if "\t" in line:
        return [f.strip() for f in line.split("\t")]
    return [f.strip() for f in re.split(r"\s{2,}", line.strip())]


def _parse_course_line(line: str):
    """과목 행 -> (course_id, name, credit, grade_letter|None, retake). 아니면 None."""
    fields = _split_fields(line)
    if not fields or not _COURSE_ID_RE.match(fields[0]):
        return None
    course_id = fields[0]
    name = fields[1] if len(fields) > 1 else ""
    credit = 0
    grade = None
    retake = False
    for f in fields[2:]:
        if f == _RETAKE_TOKEN:
            retake = True
        elif f in _GRADE_TOKENS:
            grade = f
        elif _CREDIT_RE.match(f):
            credit = int(f)
    return course_id, name, credit, grade, retake


def _term_label(year: int, term_raw: str) -> str:
    return f"{year}-{_TERM_CODE.get(term_raw, term_raw)}"


def infer_admission_year(courses_meta: list[tuple[int, int]]) -> int | None:
    """(학년도, 학년) 목록에서 입학년도 추론: 최초 1학년의 학년도, 없으면 최소 학년도."""
    firsts = [year for year, lvl in courses_meta if lvl == 1]
    if firsts:
        return min(firsts)
    years = [year for year, _ in courses_meta]
    return min(years) if years else None


def parse_transcript_text(
    text: str,
    *,
    dept_id: str | None = None,
    admission_year: int | None = None,
    student_no: str | None = None,
    name: str | None = None,
) -> TranscriptResult:
    """전체성적조회 복붙 텍스트 -> TranscriptResult.

    dept_id/admission_year는 화면에 없으므로 학생 입력값을 받는다.
    admission_year 미지정 시 학기 헤더에서 추론한다.
    """
    cur_year: int | None = None
    cur_term: str | None = None
    grade_levels: list[tuple[int, int]] = []   # (학년도, 학년) 입학년도 추론용
    regular_terms: list[tuple[int, int, int]] = []   # (학년도, 학기, 학년) 현재 학년 계산용
    total_earned: int | None = None
    gpa: float | None = None
    in_overall = False

    courses: list[TakenCourse] = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue

        m = _SEM_RE.match(s)
        if m:
            cur_year = int(m.group(1))
            cur_term = m.group(3)
            level = int(m.group(2))
            grade_levels.append((cur_year, level))
            if cur_term in _REGULAR_SEMESTER and level > 0:
                regular_terms.append((cur_year, _REGULAR_SEMESTER[cur_term], level))
            in_overall = False
            continue

        if s.startswith("전체성적") and not s.startswith("전체성적조회"):
            in_overall = True
            continue

        if in_overall:
            mm = re.search(r"총\s*취득학점\s*([\d,]+)", s)
            if mm:
                total_earned = int(mm.group(1).replace(",", ""))
            mm = re.search(r"총\s*증명평점\s*([\d.]+)", s)
            if mm:
                gpa = float(mm.group(1))
            continue

        if s.startswith(_SKIP_PREFIX) or s == "성적경고":
            continue

        parsed = _parse_course_line(s)
        if parsed is None or cur_year is None:
            continue
        course_id, cname, credit, grade_letter, retake = parsed
        courses.append(
            TakenCourse(
                course_name=cname,
                credit=credit,
                course_id=course_id,
                category_raw=None,          # 전체성적조회엔 이수구분 없음
                area=None,                  # 적재 시 catalog로 채움
                grade_letter=grade_letter,  # 공란이면 None -> 미이수(F)로 처리됨
                grade=mappings.grade_to_gpa(grade_letter),
                is_pn=mappings.is_pn(grade_letter),
                passed=(not retake) and mappings.is_passed(grade_letter),
                superseded=retake,
                term=_term_label(cur_year, cur_term) if cur_term else None,
            )
        )

    if admission_year is None:
        admission_year = infer_admission_year(grade_levels)
    current_grade = grade_in_next_semester(regular_terms)

    meta = StudentMeta(
        student_no=student_no,
        name=name,
        dept_id=dept_id,
        admission_year=admission_year,
        current_grade=current_grade,
        total_earned=total_earned,
        gpa=gpa,
    )
    input_hash = mappings.compute_input_hash(meta, courses)
    return TranscriptResult(input_hash=input_hash, meta=meta, courses=courses)
