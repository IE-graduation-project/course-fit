"""성적표 파싱 결과를 SQLite에 적재 (이슈 #16).

- student:        학생 메타 1행
- student_course: 성적표 전 과목 원본 (catalog 미매칭 포함 -> need_g 산출용)
- student_input:  catalog 매칭 + 이수 과목만 (추천 엔진 σ_k / 이미수강 필터용)

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


def connect(db_path=DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """schema.sql 실행 (테이블 없으면 생성). 테스트/단독 실행용."""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _catalog_course_ids(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT course_id FROM course")}


def _delete_existing(conn: sqlite3.Connection, input_hash: str) -> None:
    conn.execute("DELETE FROM student_course WHERE input_hash = ?", (input_hash,))
    conn.execute("DELETE FROM student_input  WHERE input_hash = ?", (input_hash,))
    conn.execute("DELETE FROM student        WHERE input_hash = ?", (input_hash,))


def load_transcript(
    result: TranscriptResult,
    conn: sqlite3.Connection,
    *,
    created_at: str | None = None,
    source_file: str | None = None,
) -> str:
    """TranscriptResult를 3개 테이블에 적재하고 input_hash를 반환한다."""
    catalog = _catalog_course_ids(conn)
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

    # student_course: 전 과목 / student_input 후보: 매칭 + 이수 과목 중 최고 성적
    best_input: dict[str, tuple[float, int]] = {}
    for c in result.courses:
        matched = bool(c.course_id and c.course_id in catalog)
        conn.execute(
            """INSERT INTO student_course
                   (input_hash, course_id, course_name, category_raw, area,
                    credit, grade_letter, grade, is_pn, passed, term, matched)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (h, c.course_id, c.course_name, c.category_raw, c.area,
             c.credit, c.grade_letter, c.grade, int(c.is_pn), int(c.passed),
             c.term, int(matched)),
        )
        if matched and c.passed:
            # P/N은 평점이 없으므로 0.0으로 저장(소비자는 is_pn=1이면 grade 무시)
            g = 0.0 if (c.is_pn or c.grade is None) else c.grade
            prev = best_input.get(c.course_id)
            if prev is None or g > prev[0]:
                best_input[c.course_id] = (g, int(c.is_pn))

    for course_id, (g, pn) in best_input.items():
        conn.execute(
            "INSERT INTO student_input (input_hash, course_id, grade, is_pn) VALUES (?, ?, ?, ?)",
            (h, course_id, g, pn),
        )

    conn.commit()
    return h
