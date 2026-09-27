"""데모 샘플 성적표 — 학과·학번마다 그 학생의 성적표인지 (#41, #51).

경영학과 성적표 하나를 모든 학과 샘플로 쓰면, 산업데이터공학과를 골랐을 때
「2026학번인데 3학년까지 경영 전공을 들은 학생」이 된다. 화면 첫 줄에 학번과 과목 수가
나란히 떠서 시연에서 바로 보인다. 학번이 다르면 학년이 다르므로(#42) 샘플도 학번마다 둔다.
샘플은 web/lib/sample.ts 에 있고 여기서 그 파일을 직접 읽는다.
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
KNOWN_RETIRED = {("BIZ", 2022): {"007001"}}
# (학과, 학번) → 이 샘플로 추천할 때의 학년. 성적표 마지막 정규학기의 다음 학기다.
EXPECTED_GRADE = {("IDE", 2026): 1, ("BIZ", 2026): 1, ("BIZ", 2025): 2, ("BIZ", 2024): 3,
                  ("BIZ", 2022): 4}


def _samples() -> dict[tuple[str, int], str]:
    src = SAMPLE_TS.read_text(encoding="utf-8")
    consts = dict(re.findall(r"const (\w+) = `(.*?)`;", src, re.S))
    table = re.search(r"SAMPLE_TRANSCRIPTS[^=]*=\s*\{(.*?)\};", src, re.S).group(1)
    out = {}
    for dept, inner in re.findall(r"(\w+):\s*\{(.*?)\}", table, re.S):
        for year, name in re.findall(r"(\d{4}):\s*(\w+)", inner):
            out[(dept, int(year))] = consts[name]
    return out


SAMPLES = _samples()
KEYS = sorted(SAMPLES)


def test_every_sample_has_an_expected_grade():
    assert set(SAMPLES) == set(EXPECTED_GRADE)


def test_every_supported_department_has_a_sample():
    conn = sqlite3.connect(ROOT / "db" / "app.db")
    depts = {r[0] for r in conn.execute("SELECT DISTINCT dept_id FROM graduation_requirement")}
    assert depts <= {d for d, _ in SAMPLES}, f"샘플이 없는 학과: {depts - {d for d, _ in SAMPLES}}"


@pytest.mark.parametrize("key", KEYS)
def test_sample_courses_belong_to_that_department(key):
    """샘플의 과목은 카탈로그에 있고, 그 학과 또는 공통 과목이다."""
    dept, _ = key
    res = parse_transcript_text(SAMPLES[key], dept_id=dept)
    assert res.courses, "샘플에서 과목을 못 읽었다"
    conn = sqlite3.connect(ROOT / "db" / "app.db")
    catalog = dict(conn.execute("SELECT course_id, dept_id FROM course"))
    ids = {c.course_id for c in res.courses}
    assert ids - set(catalog) == KNOWN_RETIRED.get(key, set())
    foreign = {cid: catalog[cid] for cid in ids & set(catalog) if catalog[cid] not in (dept, "COMMON")}
    assert not foreign, f"{key} 샘플에 다른 학과 과목: {foreign}"


@pytest.mark.parametrize("key", KEYS)
def test_sample_admission_year_matches_its_key(key):
    """성적표의 입학년도가 버튼의 학번과 같고, 그 학번을 화면에서 고를 수 있어야 한다."""
    dept, year = key
    assert parse_transcript_text(SAMPLES[key]).meta.admission_year == year
    conn = sqlite3.connect(ROOT / "db" / "app.db")
    assert data.effective_year(conn, dept, year) is not None, f"{dept} {year}학번은 지원 밖"


@pytest.mark.parametrize("key", KEYS)
def test_sample_runs_end_to_end_at_its_grade(tmp_path, key):
    """배포 경로 그대로 돌려, 샘플 학생의 학년으로 걸러진 시간표가 나오는지."""
    dept, year = key
    grade = EXPECTED_GRADE[key]
    db = tmp_path / "app.db"
    shutil.copyfile(ROOT / "db" / "app.db", db)
    text = SAMPLES[key]
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
