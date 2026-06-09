"""성적표 파싱 및 학생 DB 적재 모듈 (이슈 #16).

추천 파이프라인 앞단: 성적표 -> 파싱 -> SQLite 적재. 두 트랙을 둔다.

- parse_text.parse_transcript_text(text, dept_id, admission_year): 전체성적조회 복붙 (트랙 2)
- parse.parse_transcript_pdf(pdf, dept_id, admission_year): 성적표 PDF (트랙 1, 보수적 골격)
- load.load_transcript(result, conn): TranscriptResult -> DB (student/student_course/student_input)
- mappings: 등급->평점, 이수구분->area, 학과명->dept_id, input_hash
"""

from .load import load_transcript
from .models import StudentMeta, TakenCourse, TranscriptResult
from .parse import parse_transcript_pdf
from .parse_text import parse_transcript_text

__all__ = [
    "StudentMeta",
    "TakenCourse",
    "TranscriptResult",
    "parse_transcript_text",
    "parse_transcript_pdf",
    "load_transcript",
]
