"""성적표 파싱/적재 단위테스트 (이슈 #16).

PDF 레이아웃과 무관한 매핑 규칙과 DB 적재 로직을 검증한다.
(레이아웃 의존 parse._extract_* 는 샘플 PDF 확정 후 별도 테스트.)
"""

from __future__ import annotations

import pathlib
import sqlite3

import pytest

from transcript import mappings
from transcript.load import ensure_schema, load_transcript
from transcript.models import StudentMeta, TakenCourse, TranscriptResult
from transcript.parse import _row_to_course
from transcript.parse_text import parse_transcript_text

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "transcript_paste_sample.txt"


# --- 등급 매핑 ---------------------------------------------------------------
def test_grade_to_gpa():
    assert mappings.grade_to_gpa("A+") == 4.5
    assert mappings.grade_to_gpa("A0") == 4.0
    assert mappings.grade_to_gpa("A") == 4.0
    assert mappings.grade_to_gpa("B0") == 3.0
    assert mappings.grade_to_gpa("F") == 0.0
    assert mappings.grade_to_gpa("P") is None      # P/N은 평점 없음
    assert mappings.grade_to_gpa("A＋") == 4.5      # 전각 +
    assert mappings.grade_to_gpa("a+") == 4.5       # 소문자
    assert mappings.grade_to_gpa("없음") is None


def test_pass_and_pn():
    assert mappings.is_pn("P") and mappings.is_pn("NP") and mappings.is_pn("N")
    assert not mappings.is_pn("A+")
    assert mappings.is_passed("D0") is True
    assert mappings.is_passed("F") is False
    assert mappings.is_passed("P") is True
    assert mappings.is_passed("NP") is False


def test_category_to_area():
    assert mappings.category_to_area("전필") == "전공필수"
    assert mappings.category_to_area("전공 선택") == "전공선택"
    assert mappings.category_to_area("교양선택") == "공통교양"
    assert mappings.category_to_area("MSC") == "MSC"
    assert mappings.category_to_area("없는구분") is None
    assert mappings.category_to_area(None) is None


def test_normalize_dept():
    # 공식 학과명은 구분점(chr 0xB7) 포함 -> 런타임에 실제 글자로 매칭
    sep = chr(0xB7)
    assert mappings.normalize_dept(f"산업{sep}데이터공학과") == "IDE"
    assert mappings.normalize_dept("산업데이터공학과") == "IDE"
    assert mappings.normalize_dept("경영학과") == "BIZ"
    assert mappings.normalize_dept("물리학과") is None
    assert mappings.normalize_dept(None) is None


def test_input_hash_deterministic():
    meta = StudentMeta(student_no="C012345")
    courses = [
        TakenCourse(course_name="데이터사이언스", credit=3, course_id="140316",
                    term="2025-1", grade_letter="A+"),
    ]
    h1 = mappings.compute_input_hash(meta, courses)
    h2 = mappings.compute_input_hash(meta, courses)
    assert h1 == h2
    assert len(h1) == 16
    # 내용이 바뀌면 hash도 바뀐다
    courses2 = courses + [TakenCourse(course_name="x", credit=3, course_id="000001",
                                      term="2025-1", grade_letter="B+")]
    assert mappings.compute_input_hash(meta, courses2) != h1


def test_row_to_course_mapping():
    course = _row_to_course({
        "course_id": "140316", "course_name": "데이터사이언스",
        "category_raw": "전필", "credit": "3", "grade_letter": "A+", "term": "2025-1",
    })
    assert course.area == "전공필수"
    assert course.grade == 4.5
    assert course.passed and not course.is_pn
    assert course.credit == 3


# --- DB 적재 -----------------------------------------------------------------
@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON")
    ensure_schema(c)
    c.execute("INSERT INTO department VALUES ('IDE', '산업데이터공학과', 132)")
    c.execute(
        "INSERT INTO course (course_id, course_name, credit, dept_id, area) "
        "VALUES ('140316', '데이터사이언스', 3, 'IDE', '전공필수')"
    )
    c.commit()
    yield c
    c.close()


def _sample_result() -> TranscriptResult:
    meta = StudentMeta(student_no="C012345", dept_id="IDE", admission_year=2023, total_earned=12)
    courses = [
        # 매칭 + 이수 -> σ 입력(matched∧passed∧¬superseded) 포함
        TakenCourse(course_id="140316", course_name="데이터사이언스", category_raw="전공필수",
                    area="전공필수", credit=3, grade_letter="A+", grade=4.5, passed=True, term="2025-1"),
        # 미매칭 교양 -> matched=0 (need_g엔 fallback area로 집계, σ엔 제외)
        TakenCourse(course_id="990001", course_name="대학글쓰기", category_raw="교양필수",
                    area="교양필수", credit=2, grade_letter="B+", grade=3.5, passed=True, term="2023-1"),
        # 낙제(재수강 전 시도) -> passed=0이라 σ 입력 제외
        TakenCourse(course_id="140316", course_name="데이터사이언스", category_raw="전공필수",
                    area="전공필수", credit=3, grade_letter="F", grade=0.0, passed=False, term="2024-1"),
    ]
    return TranscriptResult(input_hash="testhash00000001", meta=meta, courses=courses)


def test_load_writes_tables(conn):
    load_transcript(_sample_result(), conn, source_file="t.pdf")
    assert conn.execute("SELECT COUNT(*) FROM student").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM student_course").fetchone()[0] == 3
    # σ 입력 = matched ∧ passed ∧ ¬superseded (140316 A+ 1건; F 제외, 미매칭 990001 제외)
    rows = conn.execute(
        "SELECT course_id, grade FROM student_course "
        "WHERE matched=1 AND passed=1 AND superseded=0"
    ).fetchall()
    assert rows == [("140316", 4.5)]


def test_load_matched_flag(conn):
    load_transcript(_sample_result(), conn)
    m = dict(conn.execute("SELECT course_id, matched FROM student_course").fetchall())
    assert m["140316"] == 1   # catalog 존재
    assert m["990001"] == 0   # catalog 미존재


def test_load_idempotent(conn):
    load_transcript(_sample_result(), conn)
    load_transcript(_sample_result(), conn)  # 같은 성적표 재적재
    assert conn.execute("SELECT COUNT(*) FROM student").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM student_course").fetchone()[0] == 3
    assert conn.execute(
        "SELECT COUNT(*) FROM student_course WHERE matched=1 AND passed=1 AND superseded=0"
    ).fetchone()[0] == 1


def test_load_pn_course(conn):
    conn.execute(
        "INSERT INTO course (course_id, course_name, credit, dept_id, area) "
        "VALUES ('140999', '세미나', 1, 'IDE', '전공선택')"
    )
    conn.commit()
    meta = StudentMeta(student_no="C0001")
    courses = [
        TakenCourse(course_id="140999", course_name="세미나", category_raw="전선",
                    area="전공선택", credit=1, grade_letter="P", grade=None,
                    is_pn=True, passed=True, term="2025-1"),
    ]
    load_transcript(TranscriptResult("h_pn_000000001", meta, courses), conn)
    # P/N 과목: student_course에 grade NULL + is_pn=1 원본 보존, σ 입력에도 포함(passed)
    row = conn.execute(
        "SELECT grade, is_pn, matched, passed, superseded FROM student_course WHERE course_id='140999'"
    ).fetchone()
    assert row == (None, 1, 1, 1, 0)


# --- 전체성적조회 복붙 파서 (트랙 2) ----------------------------------------
def test_text_parse_basic():
    r = parse_transcript_text(FIXTURE.read_text(encoding="utf-8"), dept_id="BIZ", admission_year=2021)
    assert r.meta.dept_id == "BIZ"
    assert r.meta.admission_year == 2021
    assert r.meta.current_grade == 2
    assert r.meta.total_earned == 15
    assert r.meta.gpa == 3.10
    assert len(r.courses) == 8
    assert sum(1 for c in r.courses if c.superseded) == 1          # 재수강 1건
    blanks = [c for c in r.courses if c.grade_letter is None]       # 공란 = 미이수
    assert blanks and all(not c.passed for c in blanks)
    ps = [c for c in r.courses if c.grade_letter == "P"]            # P = pn + 이수
    assert ps and all(c.is_pn and c.passed for c in ps)


def test_text_parse_infer_admission_year():
    r = parse_transcript_text(FIXTURE.read_text(encoding="utf-8"))  # year 미지정 -> 추론
    assert r.meta.admission_year == 2021   # 최초 1학년 학년도


def test_text_load_end_to_end(conn):
    conn.execute("INSERT INTO department VALUES ('BIZ', '경영학과', 132)")
    for cid, area in [("311001", "전공필수"), ("311002", "전공기초"), ("311003", "전공선택"),
                      ("311004", "전공기초"), ("900001", "공통교양")]:
        conn.execute(
            "INSERT INTO course (course_id, course_name, credit, dept_id, area) VALUES (?, ?, 3, 'BIZ', ?)",
            (cid, cid, area),
        )
    conn.commit()

    r = parse_transcript_text(FIXTURE.read_text(encoding="utf-8"), dept_id="BIZ", admission_year=2021)
    load_transcript(r, conn)

    assert conn.execute("SELECT COUNT(*) FROM student_course").fetchone()[0] == 8
    # σ 입력 = matched ∧ passed ∧ ¬superseded (student_course에서 도출)
    si = dict(conn.execute(
        "SELECT course_id, grade FROM student_course "
        "WHERE matched=1 AND passed=1 AND superseded=0"
    ).fetchall())
    assert set(si) == {"311001", "311002", "311003", "311004", "900001"}
    assert si["311003"] == 3.0       # 재수강 최종 B0이 유효본
    assert si["900001"] is None      # P/N은 grade NULL (원본 보존)
    # 311003: 공란/재수강/B0 = student_course 3행
    assert conn.execute("SELECT COUNT(*) FROM student_course WHERE course_id='311003'").fetchone()[0] == 3
    # 007777 미매칭 -> σ 입력 제외, student_course엔 matched=0 + 일반선택 fallback
    assert conn.execute("SELECT matched, area FROM student_course WHERE course_id='007777'").fetchone() == (0, "일반선택")
    # 영역별 기수강학점 (need_g 산출분): 매칭+이수+비대체만
    area_credits = dict(conn.execute(
        "SELECT area, SUM(credit) FROM student_course "
        "WHERE matched=1 AND passed=1 AND superseded=0 GROUP BY area"
    ).fetchall())
    assert area_credits == {"전공필수": 3, "전공기초": 6, "전공선택": 3, "공통교양": 2}


# --- PDF 트랙(트랙 1) 보수적 골격 -------------------------------------------
def test_pdf_delegates_to_text(monkeypatch):
    # 실제 PDF 없이: 텍스트 추출만 모킹 -> 검증된 텍스트 파서에 위임됨을 확인
    from transcript import parse as pdfmod

    monkeypatch.setattr(pdfmod, "extract_pdf_text", lambda p: FIXTURE.read_text(encoding="utf-8"))
    r = pdfmod.parse_transcript_pdf("dummy.pdf", dept_id="BIZ", admission_year=2021)
    assert r.meta.dept_id == "BIZ"
    assert len(r.courses) == 8


def test_pdf_empty_raises(monkeypatch):
    # 과목을 못 뽑으면 조용히 빈 결과 대신 명확히 실패 (보수적)
    from transcript import parse as pdfmod

    monkeypatch.setattr(pdfmod, "extract_pdf_text", lambda p: "헤더만 있고 과목 없음")
    with pytest.raises(pdfmod.TranscriptParseError):
        pdfmod.parse_transcript_pdf("dummy.pdf", dept_id="BIZ", admission_year=2021)
