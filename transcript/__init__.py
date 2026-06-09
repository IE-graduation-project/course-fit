"""성적표 파싱 및 학생 DB 적재 모듈 (이슈 #16).

추천 파이프라인 앞단: 성적표 PDF -> 파싱 -> SQLite 적재.

- parse.parse_transcript(pdf): PDF -> TranscriptResult
- load.load_transcript(result, conn): TranscriptResult -> DB (student/student_course/student_input)
- mappings: 등급->평점, 이수구분->area, 학과명->dept_id, input_hash
"""

from .models import StudentMeta, TakenCourse, TranscriptResult

__all__ = ["StudentMeta", "TakenCourse", "TranscriptResult"]
