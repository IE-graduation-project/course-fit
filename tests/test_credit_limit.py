"""이번 학기 수강가능 최대학점 — 클래스넷 「개인별 수강가능학점 조회」와 같은 식인가.

클래스넷이 경영 4학년 2학기 학생에게 보인 값: 이수한계 18 + 평점우수 3 + 이월 2 = 23
(직전학기 4학년 1학기, 이수한계 19, 신청 15학점, 평점 3.70). 아래 첫 테스트가 그 학생의 성적표
모양을 그대로 옮긴 것이다.
"""
from __future__ import annotations

import os
import pathlib
import shutil

import pytest
from fastapi.testclient import TestClient

from tests.test_samples import SAMPLES
from transcript.credit_limit import credit_limit
from transcript.parse_text import parse_transcript_text

ROOT = pathlib.Path(__file__).resolve().parent.parent
HEAD = "학수번호\t과목명\t영문과목명\t학점\t성적\t재수강"


def _term(header: str, grades: list[str], registered: int, gpa: str) -> str:
    rows = [f"{311100 + i}\t과목{i}\tCOURSE {i}\t3\t{g}" for i, g in enumerate(grades)]
    return "\n".join([header, HEAD, *rows, f"신청학점 {registered} 신청평점 {gpa}",
                      f"취득학점 {registered} 증명평점 {gpa}"])


def _limit(dept: str, *terms: str) -> dict:
    return credit_limit(parse_transcript_text("\n".join(["전체성적조회<", *terms]), dept_id=dept).meta)


def test_matches_classnet_example():
    got = _limit("BIZ",
                 _term("2025학년도 3학년 2학기", ["A0"] * 6, 18, "4.00"),
                 _term("2026학년도 4학년 1학기", ["B+"] * 5, 15, "3.70"),
                 _term("2026학년도 4학년 하계계절학기", ["A+"], 3, "4.50"))
    assert got["lastTerm"] == "2026-1", "계절학기는 직전학기가 아니다"
    assert (got["base"], got["gpaBonus"], got["carry"], got["max"]) == (18, 3, 2, 23)


def test_summary_split_across_lines_is_read():
    """라벨과 값이 줄을 나눠 붙여넣어져도 같은 값을 읽는다."""
    text = "\n".join(["2026학년도 1학년 1학기", HEAD, "311100\t과목\tC\t3\tA0",
                      "신청학점", "15", "신청평점", "3.70", "취득학점", "15", "증명평점", "3.70"])
    meta = parse_transcript_text(text, dept_id="BIZ").meta
    assert (meta.last_term_registered, meta.last_term_gpa) == (15, 3.7)


def test_gpa_just_below_b_plus_gets_no_bonus():
    got = _limit("BIZ", _term("2026학년도 2학년 1학기", ["B+"] * 6, 18, "3.49"))
    assert got["gpaBonus"] == 0


@pytest.mark.parametrize("grades,gpa", [
    (["", "", "A0", "A0", "A0"], "2.40"),   # 공란 = 일반과목 F, 2과목
    (["D0"] * 5, "1.00"),                    # 평점 1.75 미만
])
def test_academic_warning_cancels_carry(grades, gpa):
    got = _limit("BIZ", _term("2026학년도 2학년 1학기", grades, 15, gpa))
    assert got["carry"] == 0


def test_no_carry_after_eight_semesters():
    terms = [_term(f"{2021 + i // 2}학년도 {min(i // 2 + 1, 4)}학년 {i % 2 + 1}학기", ["A0"] * 4, 12, "4.00")
             for i in range(8)]
    got = _limit("IDE", *terms)
    assert got["carry"] == 0 and got["gpaBonus"] == 3


def test_semester_limit_follows_the_department_table():
    """경영은 1학년 1학기와 4학년 2학기가 18, 나머지 19. 산데공은 전부 19."""
    assert _limit("BIZ", _term("2026학년도 3학년 2학기", ["C0"] * 6, 19, "2.00"))["base"] == 19
    assert _limit("BIZ", _term("2026학년도 4학년 1학기", ["C0"] * 6, 19, "2.00"))["base"] == 18
    assert _limit("IDE", _term("2026학년도 4학년 1학기", ["C0"] * 6, 19, "2.00"))["base"] == 19


def test_carry_uses_last_semesters_own_limit():
    """직전 4학년 1학기 이수한계는 19 — 18학점 신청이면 1학점이 넘어간다."""
    got = _limit("BIZ", _term("2026학년도 4학년 1학기", ["C0"] * 6, 18, "2.00"))
    assert got["carry"] == 1


def test_freshman_without_grades_gets_first_semester_limit():
    meta = parse_transcript_text("전체성적조회<", dept_id="IDE").meta
    assert credit_limit(meta)["max"] == 19


# ── API ─────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def client(tmp_path_factory):
    dst = tmp_path_factory.mktemp("cldb") / "app.db"
    shutil.copyfile(ROOT / "db" / "app.db", dst)
    old = os.environ.get("COURSE_FIT_DB")
    os.environ["COURSE_FIT_DB"] = str(dst)
    from api.main import app
    with TestClient(app) as c:
        yield c
    if old is None:
        os.environ.pop("COURSE_FIT_DB", None)
    else:
        os.environ["COURSE_FIT_DB"] = old


@pytest.mark.parametrize("dept,year", sorted(SAMPLES))
def test_transcript_returns_credit_limit_and_recommend_honors_it(client, dept, year):
    r = client.post("/api/transcript", json={"text": SAMPLES[(dept, year)], "dept": dept,
                                             "admissionYear": year}).json()
    lim = r["creditLimit"]
    assert lim["max"] == lim["base"] + lim["gpaBonus"] + lim["carry"]
    assert 18 <= lim["base"] <= 19 and lim["gpaBonus"] in (0, 3) and 0 <= lim["carry"] <= 2
    rec = client.post("/api/recommend", json={"studentId": r["studentId"], "job": "DA",
                                              "maxCredits": lim["max"]}).json()
    assert rec["timetables"] and all(t["totalCredit"] <= lim["max"] for t in rec["timetables"])
