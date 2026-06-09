"""홍익대 성적표/성적증명서 PDF 파서 (이슈 #16, 트랙 1).

보수적 골격(frame). 실제 PDF 양식이 아직 확정되지 않았으므로, 본 적 없는 표
레이아웃을 추측해 틀린 데이터를 만들지 않는다. 대신:

1. pdfplumber로 PDF 전체 텍스트를 추출하고,
2. 이미 검증된 텍스트 파서(parse_text)에 위임한다 (성적표 텍스트가 전체성적조회
   복붙과 유사한 행 구조라는 보수적 가정).
3. 과목을 하나도 못 뽑으면 조용히 빈 결과를 내지 않고 명확히 실패한다.

실제 샘플 확보 후 보강 포인트(여기만 손대면 됨):
- PDF가 표 형태면 `extract_pdf_rows()`를 pdfplumber `extract_tables` 기반으로 구현해
  `_row_to_course()`에 dict를 넘기면 된다(이수구분 컬럼 포함 시 area 정밀화).
- 학번/성명/학과/입학년도/총취득/평점 메타 추출 위치 확정.
"""

from __future__ import annotations

from pathlib import Path

from . import mappings
from .models import TakenCourse, TranscriptResult
from .parse_text import parse_transcript_text


class TranscriptParseError(RuntimeError):
    """PDF에서 성적표 구조를 해석하지 못할 때."""


def extract_pdf_text(pdf_path) -> str:
    """pdfplumber로 PDF 전체 텍스트 추출 (페이지 줄바꿈 연결). 지연 import."""
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def parse_transcript_pdf(
    pdf_path,
    *,
    dept_id: str | None = None,
    admission_year: int | None = None,
    student_no: str | None = None,
    name: str | None = None,
) -> TranscriptResult:
    """성적표 PDF -> TranscriptResult (보수적 골격).

    현재는 텍스트 추출 후 검증된 텍스트 파서에 위임한다. 실제 양식 확정 시
    표/이수구분 기반 추출로 보강한다. 시그니처는 트랙 2와 동일하게 맞춘다.
    """
    text = extract_pdf_text(pdf_path)
    result = parse_transcript_text(
        text,
        dept_id=dept_id,
        admission_year=admission_year,
        student_no=student_no,
        name=name,
    )
    if not result.courses:
        raise TranscriptParseError(
            f"PDF에서 과목 행을 찾지 못했습니다: {Path(pdf_path).name}. "
            "PDF 레이아웃 확인 후 extract_pdf_rows 보강 필요 (이슈 #16 트랙1)."
        )
    return result


def _row_to_course(row: dict) -> TakenCourse:
    """공통 행 dict -> TakenCourse. 매핑 규칙만 적용(레이아웃 무관).

    표 기반 추출 보강 시(이수구분 컬럼 포함 PDF) 이 헬퍼로 행을 변환한다.
    row 키: course_id, course_name, category_raw, credit, grade_letter, term, retake
    """
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
        superseded=bool(row.get("retake")),
        term=row.get("term"),
    )
