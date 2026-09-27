"""졸업요건 상쇄는 과목의 개설 학과를 본다 (#40).

영역 이름이 같아도 학과가 다르면 다른 요건이다. 경영학과의 「전공필수」는 산업데이터공학과의
「전공필수」를 채우지 못한다 — 타 학과 전공 과목은 일반선택으로 인정된다. 교양 영역은 전교
공통이라 개설 학과와 무관하게 그대로 인정한다.

여기 테스트는 영역 이름만으로 합산하던 코드에서 실패한다.
"""
from __future__ import annotations

import sqlite3

from recommender import data

# (course_id, 개설 학과, 카탈로그 영역, 학점)
CATALOG = [
    ("IDE_REQ", "IDE", "전공필수", 3),
    ("IDE_MSC", "IDE", "MSC", 3),
    ("BIZ_REQ", "BIZ", "전공필수", 3),
    ("BIZ_BASE", "BIZ", "전공기초", 3),
    ("BIZ_LIB", "BIZ", "공통교양", 3),    # 경영학과가 개설한 교양 — 교양은 전교 공통
    ("COM_LIB", "COMMON", "공통교양", 2),
]
UNMATCHED = ("999999", "일반선택", 1)     # 카탈로그에 없는 과목 — 적재 시 일반선택으로 들어온다


def _conn(student_dept: str) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE course (course_id TEXT PRIMARY KEY, dept_id TEXT, area TEXT);
        CREATE TABLE course_competency (course_id TEXT, comp_id TEXT, weight REAL);
        CREATE TABLE student (input_hash TEXT PRIMARY KEY, dept_id TEXT, admission_year INTEGER,
                              current_grade INTEGER);
        CREATE TABLE student_course (
            input_hash TEXT, course_id TEXT, area TEXT, credit INTEGER, grade REAL,
            is_pn INTEGER, matched INTEGER, passed INTEGER, superseded INTEGER
        );
        """
    )
    conn.execute("INSERT INTO student VALUES ('h', ?, 2026, NULL)", (student_dept,))
    for cid, dept, area, credit in CATALOG:
        conn.execute("INSERT INTO course VALUES (?, ?, ?)", (cid, dept, area))
        # student_course.area 는 load.py 가 카탈로그 영역을 그대로 복사한 값이다
        conn.execute(
            "INSERT INTO student_course VALUES ('h', ?, ?, ?, 4.0, 0, 1, 1, 0)",
            (cid, area, credit),
        )
    cid, area, credit = UNMATCHED
    conn.execute(
        "INSERT INTO student_course VALUES ('h', ?, ?, ?, 4.0, 0, 0, 1, 0)", (cid, area, credit)
    )
    # 낙제한 시도는 어느 영역에도 들어가지 않는다 — 조인이 이 필터를 깨지 않는지 본다
    conn.execute("INSERT INTO student_course VALUES ('h', 'IDE_REQ', '전공필수', 3, NULL, 0, 1, 0, 0)")
    conn.commit()
    return conn


def test_other_dept_major_does_not_fill_ide_requirement():
    earned = data.load_student(_conn("IDE"), "h").earned_by_area
    assert earned["전공필수"] == 3          # 경영 전공필수 3학점은 빠지고 IDE 것만
    assert "전공기초" not in earned          # 경영 전공기초도 산데공 요건이 아니다


def test_other_dept_major_is_credited_as_general_elective():
    earned = data.load_student(_conn("IDE"), "h").earned_by_area
    # 경영 전공필수 3 + 경영 전공기초 3 + 미매칭 1 — 들은 학점은 버려지지 않는다
    assert earned["일반선택"] == 7


def test_liberal_arts_count_regardless_of_offering_dept():
    earned = data.load_student(_conn("IDE"), "h").earned_by_area
    assert earned["공통교양"] == 5          # 경영 개설 교양 3 + 공통 2


def test_rule_is_symmetric_for_business_students():
    earned = data.load_student(_conn("BIZ"), "h").earned_by_area
    assert earned["전공필수"] == 3          # 경영 것만
    assert earned["전공기초"] == 3
    assert "MSC" not in earned              # 산데공 MSC 는 경영 학생에게 일반선택
    assert earned["일반선택"] == 7          # 산데공 전공필수 3 + MSC 3 + 미매칭 1
    assert earned["공통교양"] == 5


def test_total_credit_is_preserved():
    """영역만 옮길 뿐 학점을 지우지 않는다 — 어느 학과로 봐도 합이 같다."""
    ide = sum(data.load_student(_conn("IDE"), "h").earned_by_area.values())
    biz = sum(data.load_student(_conn("BIZ"), "h").earned_by_area.values())
    assert ide == biz == 18
