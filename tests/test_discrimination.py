"""직무 간 변별력 — 과목을 쌓아도 「어느 직무가 맞나」가 무너지지 않는지 (#31).

매핑 벡터는 과목마다 10역량 전부에 가중치가 있고, 4위 아래는 KoSBERT 가 고르게 까는 바닥이다.
그 바닥까지 σ 에 누적하면 과목 수가 늘수록 모든 역량 σ 가 같이 올라, 경영학과 3학년이 데이터
사이언티스트 적합도 94 로 나왔다. 과목별 상위 역량만 기여하게 한 뒤(params.COURSE_TOP_K)의
격차를 배포 경로(data.load_weights → params.compute_sigma → api.serialize.job_fit)로 잰다.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path

from api.serialize import job_fit
from recommender import data, diagnose, params
from recommender.recommend import recommend
from transcript.load import load_transcript
from transcript.parse_text import parse_transcript_text

ROOT = Path(__file__).resolve().parent.parent
JOBS = ("DA", "DS", "DE", "PM", "MKT", "FIN")
DATA_JOBS = ("DA", "DS", "DE")
BIZ_JOBS = ("PM", "MKT", "FIN")


def test_top_k_keeps_the_largest_and_breaks_ties_by_id():
    w = {"ML": 0.30, "DATA": 0.10, "PROG": 0.10, "DB": 0.10, "VIZ": 0.02, "OR": 0.0}
    assert params.top_k_weights(w, 3) == {"ML": 0.30, "DATA": 0.10, "DB": 0.10}
    assert params.top_k_weights({"ML": 0.0, "OR": 0.0}, 3) == {}


def test_every_loaded_course_contributes_at_most_top_k():
    conn = sqlite3.connect(ROOT / "db" / "app.db")
    conn.row_factory = sqlite3.Row
    ids = [r[0] for r in conn.execute("SELECT DISTINCT course_id FROM course_competency")]
    assert max(len(w) for w in data.load_weights(conn, ids).values()) <= params.COURSE_TOP_K


def test_spread_holds_as_courses_accumulate():
    """산데공 1학년 샘플 → 전공·MSC 를 지정 학년 순으로 28과목까지. 절단 전엔 17 까지 무너졌다."""
    conn = sqlite3.connect(ROOT / "db" / "app.db")
    conn.row_factory = sqlite3.Row
    comps = data.comp_ids(conn)
    rhos = {j: data.load_rho(conn, j) for j in JOBS}
    path = diagnose.curriculum(conn)[:28]
    sigma = params.compute_sigma({c: (4.0, 0) for c in path}, data.load_weights(conn, path), comps)
    fits = {j: job_fit(sigma, rhos[j], comps) for j in JOBS}
    assert max(fits, key=fits.get) == "DS"
    assert max(fits.values()) - min(fits.values()) >= 30


def test_business_senior_is_not_a_data_scientist(tmp_path):
    """경영 샘플(3학년 2학기까지)의 데이터 직무 적합도가 경영 직무보다 뚜렷이 낮다.

    절단 전: DS 93.9 · PM 99.7 (5.8 차이). 화면의 「직무별 적합도」가 사실상 같은 값이었다.
    """
    src = (ROOT / "web" / "lib" / "sample.ts").read_text(encoding="utf-8")
    text = re.search(r"const BIZ_2022 = `(.*?)`;", src, re.S).group(1)
    db = tmp_path / "app.db"
    shutil.copyfile(ROOT / "db" / "app.db", db)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    h = load_transcript(parse_transcript_text(text, dept_id="BIZ", admission_year=2022), conn)
    rec = recommend(h, "PM", db_path=str(db), k=1)
    comps = data.comp_ids(conn)
    fits = {j: job_fit(rec.sigma, data.load_rho(conn, j), comps) for j in JOBS}
    conn.close()
    assert min(fits[j] for j in BIZ_JOBS) - max(fits[j] for j in DATA_JOBS) >= 15, fits
