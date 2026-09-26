"""수강 가능 학년 — 1학년에게 4학년 전공이 추천되지 않는지 (#42).

시간표의 분반마다 지정 학년(1~4, 0=무관)이 있고 「지정 학년 이상이면 수강 가능」이 규칙이다.
이 값이 적재 때 버려지고 후보 쿼리에도 없어서, 학년이 추천을 전혀 바꾸지 못했다.

학생 학년은 성적표에서 센다. 전체성적조회엔 성적이 확정된 학기만 나오므로 지금 학기는
마지막 학기의 다음이다 — 3학년 2학기까지 나온 학생은 이번 학기 4학년이다.

여기 테스트는 학년을 보지 않던 코드(분반 학년 미적재, 최고 학년을 그대로 쓰던 파서)에서 실패한다.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from db.ingest import validate
from recommender import data
from transcript.parse_text import grade_in_next_semester, parse_transcript_text

ROOT = Path(__file__).resolve().parent.parent


# ── 이번 학기 학년 ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("terms, want", [
    ([], None),                                      # 신입생 — 정규학기 없음
    ([(2026, 1, 1)], 1),                             # 1학년 1학기 뒤는 1학년 2학기
    ([(2025, 1, 3), (2025, 2, 3)], 4),              # 3학년 2학기 뒤는 4학년
    ([(2025, 2, 3), (2025, 1, 3)], 4),              # 입력 순서와 무관
    ([(2022, 1, 1), (2024, 2, 2), (2025, 1, 3)], 3),  # 휴학 공백이 있어도 마지막 학기 기준
    ([(2026, 2, 4)], 4),                             # 4학년 2학기 뒤도 4학년 (초과학기)
])
def test_grade_in_next_semester(terms, want):
    assert grade_in_next_semester(terms) == want


def _transcript(*headers: str) -> str:
    lines = ["전체성적조회"]
    for i, h in enumerate(headers):
        lines += [h, "학수번호\t과목명\t영문과목명\t학점\t성적\t재수강",
                  f"00710{i}\t과목{i}\tSUBJECT\t3\tA0"]
    return "\n".join(lines)


def test_parser_reports_this_semesters_grade_not_the_last_one():
    text = _transcript("2024학년도 3학년 1학기", "2024학년도 3학년 2학기")
    assert parse_transcript_text(text).meta.current_grade == 4


def test_parser_ignores_seasonal_terms():
    # 계절학기가 마지막이어도 학년 진급과 무관하다
    text = _transcript("2025학년도 1학년 1학기", "2025학년도 1학년 하계계절학기")
    assert parse_transcript_text(text).meta.current_grade == 1


# ── 입학년도 폴백 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("current, admission, term, want", [
    (3, 2026, "2026-2", 3),       # 성적표가 알려주면 그걸 쓴다 (입학년도와 어긋나도)
    (None, 2026, "2026-2", 1),    # 신입생
    (None, 2024, "2026-2", 3),
    (None, 2019, "2026-2", 4),    # 상한
    (None, 2027, "2026-2", 1),    # 하한
])
def test_grade_for_term(current, admission, term, want):
    assert data.grade_for_term(current, admission, term) == want


# ── 후보 필터 ────────────────────────────────────────────────────────────────
def _conn() -> sqlite3.Connection:
    """지정 학년 0~4 분반을 하나씩 둔 최소 DB."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE course (
            course_id TEXT PRIMARY KEY, course_name TEXT, credit INTEGER,
            dept_id TEXT, area TEXT, prerequisites TEXT
        );
        CREATE TABLE course_section (
            course_id TEXT, section TEXT, source_term TEXT, grade INTEGER,
            time_slots_int TEXT, PRIMARY KEY (course_id, section, source_term)
        );
        CREATE TABLE course_competency (course_id TEXT, comp_id TEXT, weight REAL);
        """
    )
    for g in range(5):
        area = "공통교양" if g == 0 else "전공선택"
        conn.execute("INSERT INTO course VALUES (?, ?, 3, 'IDE', ?, '')", (f"G{g}", f"학년{g}", area))
        conn.execute("INSERT INTO course_section VALUES (?, '1', '2026-2', ?, '')", (f"G{g}", g))
    conn.commit()
    return conn


def _ids(grade):
    return [c.course_id for c in data.load_candidates(_conn(), "IDE", term="2026-2", grade=grade)]


def test_first_year_sees_only_first_year_and_unrestricted():
    assert _ids(1) == ["G0", "G1"]


def test_third_year_sees_up_to_third():
    assert _ids(3) == ["G0", "G1", "G2", "G3"]


def test_none_means_no_restriction():
    assert _ids(None) == ["G0", "G1", "G2", "G3", "G4"]


def test_grade_has_no_default():
    # 빠뜨리면 조용히 제약이 풀리는 대신 즉시 죽는다
    with pytest.raises(TypeError):
        data.load_candidates(_conn(), "IDE", term="2026-2")


# ── 적재 검증 ────────────────────────────────────────────────────────────────
def test_validate_rejects_missing_section_grade():
    conn = sqlite3.connect(":memory:")
    conn.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    conn.execute("INSERT INTO department VALUES ('IDE', '산업데이터공학과', 132)")
    conn.execute("INSERT INTO course (course_id, course_name, credit, dept_id, area) "
                 "VALUES ('C1', '과목', 3, 'IDE', '전공선택')")
    conn.execute("INSERT INTO course_section (course_id, section, source_term, grade) "
                 "VALUES ('C1', '1', '2026-2', NULL)")
    errors = validate(conn)
    assert any("지정 학년" in e for e in errors), errors


# ── 종단 — 배포 DB 로 실제 추천을 돌렸을 때 ───────────────────────────────────
def test_recommendation_never_exceeds_students_grade(tmp_path):
    """픽스처 성적표는 2학년 1학기까지라 이번 학기 2학년이다. 3·4학년 전공이 나오면 안 된다."""
    import shutil

    from recommender.recommend import recommend
    from transcript.load import load_transcript

    db = tmp_path / "app.db"
    shutil.copyfile(ROOT / "db" / "app.db", db)
    text = (ROOT / "tests" / "fixtures" / "transcript_paste_sample.txt").read_text(encoding="utf-8")
    res = parse_transcript_text(text, dept_id="BIZ", admission_year=2022)  # test_api 와 같은 입력
    conn = sqlite3.connect(db)
    h = load_transcript(res, conn)

    rec = recommend(h, "DA", db_path=str(db), k=3)
    assert rec.grade_level == 2
    picked = [(c.course_id, c.section) for r in rec.results for c in r.selected]
    assert picked, "추천이 비었다"
    for cid, sec in picked:
        (g,) = conn.execute(
            "SELECT grade FROM course_section WHERE course_id=? AND section=?", (cid, sec)
        ).fetchone()
        assert g in (0, 1, 2), f"{cid}-{sec} 지정 학년 {g} > 2"
    conn.close()
