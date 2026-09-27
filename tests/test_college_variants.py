"""단과대별 교양필수 — 학생 학과의 변형만 후보에 남는다 (#55).

논리적사고와글쓰기는 (경영) BIZ · (공학) IDE · (인문) · (법학) · (예술) COMMON 으로 카탈로그에 있다.
걸러 주지 않으면 경영학과 학생의 졸업 우선 시간표에 (법학)이 들어갔다.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from recommender import data

ROOT = Path(__file__).resolve().parent.parent
OWN = {"BIZ": "논리적사고와글쓰기(경영)", "IDE": "논리적사고와글쓰기(공학)"}


def _conn():
    conn = sqlite3.connect(ROOT / "db" / "app.db")
    conn.row_factory = sqlite3.Row
    return conn


@pytest.mark.parametrize("dept", sorted(OWN))
def test_only_own_college_writing_course_is_a_candidate(dept):
    conn = _conn()
    names = {c.course_name for c in data.load_candidates(conn, dept, term=data.active_term(conn),
                                                         grade=None)}
    writing = {n for n in names if n.startswith("논리적사고와글쓰기")}
    assert writing <= {OWN[dept]}, writing


@pytest.mark.parametrize("dept", sorted(OWN))
def test_nothing_else_is_dropped(dept):
    """빠지는 것은 다른 단과대 논리적사고와글쓰기 분반뿐이다 — 순번 괄호(대학물리(2))는 그대로."""
    conn = _conn()
    term = data.active_term(conn)
    kept = {(c.course_id, c.section) for c in data.load_candidates(conn, dept, term=term, grade=None)}
    offered = conn.execute(
        "SELECT s.course_id, s.section, c.course_name FROM course_section s "
        "JOIN course c ON c.course_id = s.course_id "
        "WHERE s.source_term = ? AND c.dept_id IN (?, 'COMMON') AND c.area <> '일반선택'",
        (term, dept)).fetchall()
    dropped = {r["course_name"] for r in offered if (r["course_id"], r["section"]) not in kept}
    assert dropped and all(n.startswith("논리적사고와글쓰기") and n != OWN[dept] for n in dropped), dropped
