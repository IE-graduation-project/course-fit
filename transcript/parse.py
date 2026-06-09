"""홍익대 성적표 PDF 파서 (이슈 #16, 트랙 1, 미정).

pdfplumber로 텍스트/표를 추출해 TranscriptResult로 변환한다.
레이아웃 의존 부분(_extract_meta, _extract_rows)은 샘플 PDF 확정 후 채운다.
매핑 적용(_row_to_course)과 오케스트레이션은 레이아웃과 무관하게 완성돼 있다.
복붙(전체성적조회) 트랙은 parse_text.py 참고.
"""

from __future__ import annotations

from pathlib import Path

from . import mappings
from .models import StudentMeta, TakenCourse, TranscriptResult


def parse_transcript_pdf(pdf_path) -> TranscriptResult:
    """성적표 PDF -> TranscriptResult."""
    import pdfplumber  # 지연 import: 모듈 import 시 의존성 강제 안 함

    pdf_path = Path(pdf_path)
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        tables = [t for page in pdf.pages for t in (page.extract_tables() or [])]

    meta = _extract_meta(text)
    raw_rows = _extract_rows(tables, text)
    courses = [_row_to_course(r) for r in raw_rows]

    input_hash = mappings.compute_input_hash(meta, courses)
    return TranscriptResult(input_hash=input_hash, meta=meta, courses=courses)


def _row_to_course(row: dict) -> TakenCourse:
    """공통 행 dict -> TakenCourse. 매핑 규칙만 적용(레이아웃 무관)."""
    letter = row.get("grade_letter")
    return TakenCourse(
        course_name=row.get("course_name") or "",
        credit=int(row.get("credit") or 0),
        course_id=(row.get("course_id") or None),
        category_raw=row.get("category_raw"),
        area=mappings.category_to_area(row.get("category_raw")),
        grade_letter=letter,
        grade=mappings.grade_to_gpa(letter),
        is_pn=mappings.is_pn(letter),
        passed=mappings.is_passed(letter),
        term=row.get("term"),
    )


# --- 레이아웃 의존: 샘플 PDF 확인 후 구현 (이슈 #16) -------------------------


def _extract_meta(text: str) -> StudentMeta:
    """성적표 텍스트 -> StudentMeta (학번/성명/학과/입학년도/총취득학점/평점평균).

    dept_id는 mappings.normalize_dept(dept_name_raw)로 채운다.
    """
    raise NotImplementedError(
        "성적표 레이아웃 의존: 샘플 PDF 확인 후 구현 (이슈 #16)."
    )


def _extract_rows(tables, text) -> list[dict]:
    """성적표 표/텍스트 -> 과목 행 리스트.

    각 행: {course_id, course_name, category_raw, credit, grade_letter, term}
    """
    raise NotImplementedError(
        "성적표 레이아웃 의존: 샘플 PDF 확인 후 구현 (이슈 #16)."
    )
