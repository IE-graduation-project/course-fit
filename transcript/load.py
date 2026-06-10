"""성적표 파싱 결과를 SQLite에 적재 (이슈 #16).

- student:        학생 메타 1행
- student_course: 성적표 전 과목 원본 (catalog 미매칭 포함). σ·need_g·B1의 단일 진실원천.
  · σ 입력  = matched ∧ passed ∧ ¬superseded
  · need_g  = area별 passed ∧ ¬superseded 학점 집계
  · B1      = 전체 course_id

input_hash 기준 idempotent: 같은 해시의 기존 row를 삭제 후 재적재한다.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import TranscriptResult

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "app.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"

# catalog/이수구분 어디에도 영역이 없으면 졸업규칙상 일반선택(catch-all)으로 환산.
# 어떤 학생 성적표든 robust하게 적재되게 하는 일반화 장치 (catalog 완전성과 무관).
FALLBACK_AREA = "일반선택"


def connect(db_path=DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """schema.sql 실행 (테이블 없으면 생성). 테스트/단독 실행용."""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _catalog_areas(conn: sqlite3.Connection) -> dict[str, str]:
    """course_id -> area (catalog가 권위 있는 영역 소스)."""
    return {cid: area for cid, area in conn.execute("SELECT course_id, area FROM course")}


def _delete_existing(conn: sqlite3.Connection, input_hash: str) -> None:
    conn.execute("DELETE FROM student_course WHERE input_hash = ?", (input_hash,))
    conn.execute("DELETE FROM student        WHERE input_hash = ?", (input_hash,))


def load_transcript(
    result: TranscriptResult,
    conn: sqlite3.Connection,
    *,
    created_at: str | None = None,
    source_file: str | None = None,
) -> str:
    """TranscriptResult를 student/student_course에 적재하고 input_hash를 반환한다."""
    catalog = _catalog_areas(conn)
    h = result.input_hash
    created_at = created_at or datetime.now(timezone.utc).isoformat()

    _delete_existing(conn, h)

    m = result.meta
    conn.execute(
        """INSERT INTO student
               (input_hash, student_no, name, dept_id, dept_name_raw,
                admission_year, current_grade, total_earned, gpa, source_file, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (h, m.student_no, m.name, m.dept_id, m.dept_name_raw,
         m.admission_year, m.current_grade, m.total_earned, m.gpa, source_file, created_at),
    )

    # student_course: 전 과목 원본. σ/need_g/B1은 소비자(recommender)가 이 테이블에서 필터로 도출.
    for c in result.courses:
        matched = bool(c.course_id and c.course_id in catalog)
        # 매칭 과목 영역은 catalog가 권위(이수구분보다 세분). 미매칭은 파서 제공값,
        # 그것도 없으면 일반선택 fallback (졸업 catch-all, 어떤 성적표든 영역 결측 없이 적재).
        area = catalog[c.course_id] if matched else (c.area or FALLBACK_AREA)
        conn.execute(
            """INSERT INTO student_course
                   (input_hash, course_id, course_name, category_raw, area,
                    credit, grade_letter, grade, is_pn, passed, superseded, term, matched)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (h, c.course_id, c.course_name, c.category_raw, area,
             c.credit, c.grade_letter, c.grade, int(c.is_pn), int(c.passed),
             int(c.superseded), c.term, int(matched)),
        )

    conn.commit()
    return h
