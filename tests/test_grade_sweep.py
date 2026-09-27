"""학년을 바꿔 가며 추천이 그 학년에 맞는지 (#36).

경영 샘플(web/lib/sample.ts 의 BIZ_2022)은 3학년 2학기까지 다섯 학기다. 앞에서부터 학기 단위로
잘라 같은 학생의 1·2·3·3·4학년 시점을 만들고, 배포 경로(parse → load → recommend)로 돌린다.
산업데이터공학과는 교육과정이 2026학년도 하나라 학번 대신 이수 학기로 학년을 바꾼다.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path

import pytest

from api.serialize import job_fit
from recommender import data
from recommender.recommend import recommend
from transcript.load import load_transcript
from transcript.parse_text import _SEM_RE, parse_transcript_text

ROOT = Path(__file__).resolve().parent.parent
JOBS = ("DA", "DS", "DE", "PM", "MKT", "FIN")
# 이수한 학기 수 → 다음 학기 학년. 2학년 1학기는 성적표에 없어(휴학) 2학년 2학기 뒤가 곧 3학년이다.
EXPECTED_GRADE = {1: 1, 2: 2, 3: 3, 4: 3, 5: 4}


def _biz_sample() -> str:
    src = (ROOT / "web" / "lib" / "sample.ts").read_text(encoding="utf-8")
    return re.search(r"const BIZ_2022 = `(.*?)`;", src, re.S).group(1)


def _first_semesters(text: str, n: int) -> str:
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if _SEM_RE.match(line)]
    return text if n >= len(starts) else "\n".join(lines[:starts[n]])


@pytest.fixture(scope="module")
def sweep(tmp_path_factory):
    """학기 수별 (추천 결과, 직무별 적합도, 지정 학년 조회용 연결)."""
    db = tmp_path_factory.mktemp("sweep") / "app.db"
    shutil.copyfile(ROOT / "db" / "app.db", db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    comps = data.comp_ids(conn)
    rhos = {j: data.load_rho(conn, j) for j in JOBS}
    text = _biz_sample()
    out = {}
    for n in EXPECTED_GRADE:
        parsed = parse_transcript_text(_first_semesters(text, n), dept_id="BIZ", admission_year=2022)
        h = load_transcript(parsed, conn)
        rec = recommend(h, "DA", db_path=str(db), k=1)
        out[n] = (rec, {j: job_fit(rec.sigma, rhos[j], comps) for j in JOBS})
    yield out, conn
    conn.close()


def test_sample_really_has_five_semesters():
    assert len([l for l in _biz_sample().splitlines() if _SEM_RE.match(l)]) == max(EXPECTED_GRADE)


@pytest.mark.parametrize("n", sorted(EXPECTED_GRADE))
def test_grade_follows_the_last_semester(sweep, n):
    rec, _ = sweep[0][n]
    assert rec.grade_level == EXPECTED_GRADE[n]


@pytest.mark.parametrize("n", sorted(EXPECTED_GRADE))
def test_recommended_sections_are_open_to_that_grade(sweep, n):
    (rec, _), conn = sweep[0][n], sweep[1]
    assert rec.results[0].selected, "시간표가 비었다"
    for c in rec.results[0].selected:
        (g,) = conn.execute("SELECT grade FROM course_section WHERE course_id=? AND section=?",
                            (c.course_id, c.section)).fetchone()
        assert g <= rec.grade_level, f"{c.course_name} 지정 학년 {g} > {rec.grade_level}"


def test_candidate_pool_widens_with_grade(sweep):
    conn = sweep[1]
    term = data.active_term(conn)
    sizes = [len(data.load_candidates(conn, "BIZ", term=term, grade=g)) for g in (1, 2, 3, 4)]
    assert sizes == sorted(sizes) and sizes[0] < sizes[-1], sizes


def test_fit_never_drops_as_semesters_accumulate(sweep):
    """학기를 더하면 σ 는 줄지 않으므로 어느 직무든 적합도가 떨어지면 안 된다."""
    results = sweep[0]
    for j in JOBS:
        fits = [results[n][1][j] for n in sorted(results)]
        assert all(a <= b + 1e-9 for a, b in zip(fits, fits[1:])), (j, fits)


def test_taken_courses_are_never_recommended(sweep):
    results = sweep[0]
    text = _biz_sample()
    for n, (rec, _) in results.items():
        taken = set(re.findall(r"^(\d{6})\t", _first_semesters(text, n), re.M))
        picked = {c.course_id for c in rec.results[0].selected}
        assert not taken & picked, (n, taken & picked)
