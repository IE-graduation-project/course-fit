"""역량별 σ 기여 과목 — 충족한 역량을 누르면 무엇을 들어서 찼는지 보여 준다.

화면의 「이 역량은 이 과목들로 쌓였다」는 σ 와 같은 원천(params.sigma_contributions)에서 나와야
한다. 따로 계산하면 σ 는 충족이라는데 목록은 비는 식으로 어긋난다.

DB는 임시 사본을 쓴다(test_api 와 같은 이유).
"""
from __future__ import annotations

import math
import os
import pathlib
import shutil
import sqlite3

import pytest
from fastapi.testclient import TestClient

from recommender import params
from tests.test_samples import SAMPLES

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPS = ["DATA", "ML", "PROG"]


# ── 단위: 기여 목록이 σ 를 그대로 재현한다 ───────────────────────────────────
def test_contributions_reproduce_sigma_exactly():
    passed = {"a": (4.5, 0), "b": (2.25, 0), "c": (None, 1), "d": (None, 0)}
    weights = {"a": {"DATA": 0.6, "PROG": 0.2}, "b": {"DATA": 0.4}, "c": {"ML": 0.5},
               "d": {"DATA": 0.3}, "unused": {"DATA": 1.0}}
    contrib = params.sigma_contributions(passed, weights, COMPS)
    sigma = params.compute_sigma(passed, weights, COMPS, alpha=1.5)
    for k in COMPS:
        assert sigma[k] == 1.0 - math.exp(-1.5 * sum(v for _, v in contrib[k]))


def test_contributions_apply_grade_factor():
    """A+ 1.0 · 2.25 는 0.5 · P/N 은 1.0 · 성적 미상은 0.67."""
    passed = {"a": (4.5, 0), "b": (2.25, 0), "c": (None, 1), "d": (None, 0)}
    weights = {c: {"DATA": 1.0} for c in passed}
    got = dict(params.sigma_contributions(passed, weights, COMPS)["DATA"])
    assert got == {"a": 1.0, "b": 0.5, "c": 1.0, "d": params.NEUTRAL_UNKNOWN}


def test_unmapped_course_contributes_nothing():
    contrib = params.sigma_contributions({"x": (4.5, 0)}, {}, COMPS)
    assert contrib == {k: [] for k in COMPS}


# ── API: diagnosis.sources ───────────────────────────────────────────────────
@pytest.fixture(scope="module")
def db_copy(tmp_path_factory):
    dst = tmp_path_factory.mktemp("srcdb") / "app.db"
    shutil.copyfile(ROOT / "db" / "app.db", dst)
    return dst


@pytest.fixture(scope="module")
def client(db_copy):
    old = os.environ.get("COURSE_FIT_DB")
    os.environ["COURSE_FIT_DB"] = str(db_copy)
    from api.main import app
    with TestClient(app) as c:
        yield c
    if old is None:
        os.environ.pop("COURSE_FIT_DB", None)
    else:
        os.environ["COURSE_FIT_DB"] = old


@pytest.fixture(scope="module")
def payload(client):
    # 데모 샘플(경영 22학번, 4학년). tests/fixtures 의 붙여넣기 예시는 가짜 학수번호라 σ 가 0 이다.
    r = client.post("/api/transcript", json={
        "text": SAMPLES[("BIZ", 2022)], "dept": "BIZ", "admissionYear": 2022})
    assert r.status_code == 200, r.text
    sid = r.json()["studentId"]
    rec = client.post("/api/recommend", json={"studentId": sid, "job": "DA", "mode": "balanced"})
    assert rec.status_code == 200, rec.text
    return sid, rec.json()


def test_every_built_up_competency_lists_its_courses(payload):
    """σ 가 0 보다 크면 목록이 있고, 0 이면 없다 — 「충족」을 눌렀는데 비어 있으면 안 된다."""
    _, rec = payload
    diag = rec["diagnosis"]
    assert diag["sources"], "sources 가 비었다"
    for k, s in diag["sigma"].items():
        assert (s > 0) == (k in diag["sources"]), k


def test_sources_are_taken_courses_ranked_by_share(payload, db_copy):
    sid, rec = payload
    conn = sqlite3.connect(db_copy)
    taken = {r[0] for r in conn.execute(
        "SELECT course_id FROM student_course WHERE input_hash = ? AND passed = 1", (sid,))}
    for k, items in rec["diagnosis"]["sources"].items():
        assert 0 < len(items) <= 6, k
        shares = [it["share"] for it in items]
        assert shares == sorted(shares, reverse=True), k
        assert all(0 < v <= 1 for v in shares), k
        assert sum(shares) <= 1 + 1e-3, k
        for it in items:
            assert it["courseId"] in taken, (k, it)
            assert it["name"] != it["courseId"], f"{it['courseId']} 이름을 못 찾았다"
