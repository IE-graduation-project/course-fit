"""데모 샘플 성적표 — 학과마다 그 학과 학생의 성적표인지 (#41).

경영학과 성적표 하나를 모든 학과 샘플로 쓰면, 산업데이터공학과를 골랐을 때
「2026학번인데 3학년까지 경영 전공을 들은 학생」이 된다. 화면 첫 줄에 학번과 과목 수가
나란히 떠서 시연에서 바로 보인다. 샘플은 web/lib/sample.ts 에 있고 여기서 그 파일을 직접 읽는다.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path

import pytest

from recommender import data
from recommender.recommend import recommend
from transcript.load import load_transcript
from transcript.parse_text import parse_transcript_text

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_TS = ROOT / "web" / "lib" / "sample.ts"

# 카탈로그에 없어도 되는 과목 — 폐지 과목도 실제 성적표엔 섞인다는 걸 보여 주려고 일부러 둔 것
KNOWN_RETIRED = {"BIZ": {"007001"}}


def _samples() -> dict[str, str]:
    src = SAMPLE_TS.read_text(encoding="utf-8")
    consts = dict(re.findall(r"const (\w+) = `(.*?)`;", src, re.S))
    table = re.search(r"SAMPLE_TRANSCRIPTS[^=]*=\s*\{(.*?)\};", src, re.S).group(1)
    mapping = dict(re.findall(r"(\w+):\s*(\w+)", table))
    return {dept: consts[name] for dept, name in mapping.items()}


SAMPLES = _samples()


def test_every_supported_department_has_a_sample():
    conn = sqlite3.connect(ROOT / "db" / "app.db")
    depts = {r[0] for r in conn.execute("SELECT DISTINCT dept_id FROM graduation_requirement")}
    assert depts <= set(SAMPLES), f"샘플이 없는 학과: {depts - set(SAMPLES)}"


@pytest.mark.parametrize("dept", sorted(SAMPLES))
def test_sample_courses_belong_to_that_department(dept):
    """샘플의 과목은 카탈로그에 있고, 그 학과 또는 공통 과목이다."""
    res = parse_transcript_text(SAMPLES[dept], dept_id=dept)
    assert res.courses, "샘플에서 과목을 못 읽었다"
    conn = sqlite3.connect(ROOT / "db" / "app.db")
    catalog = dict(conn.execute("SELECT course_id, dept_id FROM course"))
    ids = {c.course_id for c in res.courses}
    assert ids - set(catalog) == KNOWN_RETIRED.get(dept, set())
    foreign = {cid: catalog[cid] for cid in ids & set(catalog) if catalog[cid] not in (dept, "COMMON")}
    assert not foreign, f"{dept} 샘플에 다른 학과 과목: {foreign}"


@pytest.mark.parametrize("dept", sorted(SAMPLES))
def test_sample_admission_year_is_selectable(dept):
    """성적표의 입학년도를 화면에서 고를 수 있어야 한다 — 교육과정이 없으면 추천이 안 된다."""
    year = parse_transcript_text(SAMPLES[dept]).meta.admission_year
    conn = sqlite3.connect(ROOT / "db" / "app.db")
    assert data.effective_year(conn, dept, year) is not None, f"{dept} {year}학번은 지원 밖"


@pytest.mark.parametrize("dept, grade", [("IDE", 1), ("BIZ", 4)])
def test_sample_runs_end_to_end_at_its_grade(tmp_path, dept, grade):
    """배포 경로 그대로 돌려, 샘플 학생의 학년으로 걸러진 시간표가 나오는지."""
    db = tmp_path / "app.db"
    shutil.copyfile(ROOT / "db" / "app.db", db)
    text = SAMPLES[dept]
    year = parse_transcript_text(text).meta.admission_year
    conn = sqlite3.connect(db)
    h = load_transcript(parse_transcript_text(text, dept_id=dept, admission_year=year), conn)
    rec = recommend(h, "DA", db_path=str(db), k=1)
    assert rec.grade_level == grade
    assert rec.results[0].selected, "시간표가 비었다"
    for c in rec.results[0].selected:
        (g,) = conn.execute("SELECT grade FROM course_section WHERE course_id=? AND section=?",
                            (c.course_id, c.section)).fetchone()
        assert g <= grade, f"{c.course_name} 지정 학년 {g} > {grade}"
    conn.close()
