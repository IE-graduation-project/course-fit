"""학기 스코프 — 두 학기가 함께 적재돼도 지난 학기가 새지 않는지.

course_section 의 PK 는 (course_id, section, source_term) 3축인데 후보집합과 분반 메타는
(course_id, section) 2축으로 다룬다. 학기 필터가 없으면 이 차이가 조용한 버그가 된다:
후보집합은 같은 분반을 학기 수만큼 중복으로 담고, 분반 메타 dict 는 마지막에 읽힌 행으로
덮어써서 지난 학기 교수·강의실을 이번 학기 화면에 그린다.

여기 테스트는 학기 필터가 빠진 코드에서 전부 실패한다 — 그게 이 파일이 있는 이유다.
"""
from __future__ import annotations

import sqlite3

import pytest

from api.serialize import load_section_meta
from recommender import data

TERM_OLD = "2026-1"
TERM_NEW = "2026-2"


def _conn(terms: tuple[str, ...]) -> sqlite3.Connection:
    """같은 (course_id, section) 을 여러 학기로 넣은 최소 DB.

    교수 이름을 학기별로 다르게 둬서, 메타가 어느 학기를 읽었는지 값으로 판별한다.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE course (
            course_id TEXT PRIMARY KEY, course_name TEXT, credit INTEGER,
            dept_id TEXT, area TEXT, prerequisites TEXT
        );
        CREATE TABLE course_section (
            course_id TEXT, section TEXT, source_term TEXT,
            time_slots_int TEXT, time_slots_raw TEXT, professor TEXT,
            category TEXT, offering_dept TEXT, grade INTEGER,
            PRIMARY KEY (course_id, section, source_term)
        );
        CREATE TABLE course_competency (course_id TEXT, comp_id TEXT, weight REAL);
        """
    )
    conn.execute(
        "INSERT INTO course VALUES ('C1','데이터분석',3,'IDE','전공선택','')"
    )
    for term in terms:
        conn.execute(
            "INSERT INTO course_section "
            "(course_id, section, source_term, time_slots_int, time_slots_raw, "
            " professor, category, offering_dept) "
            "VALUES ('C1','01',?,'1,2','월12',?,'전선','산업데이터공학과')",
            (term, f"교수-{term}"),
        )
    conn.commit()
    return conn


def test_active_term_reads_the_loaded_term():
    with _conn((TERM_NEW,)) as conn:
        assert data.active_term(conn) == TERM_NEW


def test_active_term_refuses_two_terms():
    """두 학기가 섞이면 조용히 고르지 말고 멈춘다."""
    with _conn((TERM_OLD, TERM_NEW)) as conn:
        with pytest.raises(ValueError, match="학기가 2개"):
            data.active_term(conn)


def test_candidates_do_not_duplicate_across_terms():
    """학기 필터가 없으면 같은 분반이 학기 수만큼 후보에 들어간다."""
    with _conn((TERM_OLD, TERM_NEW)) as conn:
        cands = data.load_candidates(conn, "IDE", term=TERM_NEW, grade=None)
    assert len(cands) == 1, "같은 분반이 학기별로 중복되면 ILP 가 같은 과목을 두 번 고를 수 있다"
    assert cands[0].course_id == "C1"


def test_candidates_exclude_other_terms():
    with _conn((TERM_OLD, TERM_NEW)) as conn:
        assert data.load_candidates(conn, "IDE", term=TERM_OLD, grade=None) != []
        # 적재되지 않은 학기를 물으면 조용히 이번 학기로 넘어가지 않고 비어야 한다
        assert data.load_candidates(conn, "IDE", term="2027-1", grade=None) == []


def test_candidates_require_explicit_term():
    """기본값이 없어야 한다 — 빠뜨린 호출은 지난 학기를 추천하는 대신 죽어야 한다."""
    with _conn((TERM_NEW,)) as conn:
        with pytest.raises(TypeError):
            data.load_candidates(conn, "IDE")


def test_section_meta_picks_the_requested_term():
    """(course_id, section) 2축 dict 가 다른 학기 행으로 덮어써지지 않는다."""
    with _conn((TERM_OLD, TERM_NEW)) as conn:
        meta = load_section_meta(conn, term=TERM_NEW)
    assert len(meta) == 1
    assert meta[("C1", "01")]["professor"] == f"교수-{TERM_NEW}"


def test_section_meta_requires_explicit_term():
    with _conn((TERM_NEW,)) as conn:
        with pytest.raises(TypeError):
            load_section_meta(conn)
