"""졸업 우선은 필수·전공 영역을 먼저 채운다 (#53).

ε 만 다르면 균형과 졸업 우선이 같은 시간표를 냈다. 졸업 반영의 최대는 학점 상한이라, 균형에서
담은 학점 전부가 남은 요건에 들어가면 졸업 우선이 더 고를 해가 없다. 졸업 우선에는 영역 가중을
걸고(PREFERENCE_AREA_WEIGHT), 화면의 「졸업 반영」은 성향과 무관하게 학점 그대로 센다.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path

from recommender import model
from recommender.data import Candidate
from recommender.recommend import (GRADUATION_AREA_WEIGHT, PREFERENCE_AREA_WEIGHT,
                                   PREFERENCE_EPS, recommend)
from transcript.load import load_transcript
from transcript.parse_text import parse_transcript_text

ROOT = Path(__file__).resolve().parent.parent
MAJOR = {"전공필수", "전공기초", "MSC", "전공선택", "교양필수"}


def _cand(cid, area, slot):
    return Candidate(course_id=cid, section="1", course_name=cid, credit=3, area=area,
                     slots=(slot,), prereqs=(), weights={})


def test_weight_prefers_required_area_at_equal_credits():
    # 3학점 한 자리 — 교양도 전공필수도 남은 요건을 3학점 채운다. 가중이 없으면 직무 적합이 높은
    # 교양이 이기고, 졸업 우선 가중이면 전공필수가 이긴다. 두 경우 모두 졸업 반영은 3 이다.
    scores = {"LIB": 0.9, "REQ": 0.1}
    cands = [_cand("LIB", "공통교양", 0), _cand("REQ", "전공필수", 1)]
    need = {"공통교양": 3, "전공필수": 3}
    kw = dict(U=3, L=3, taken_ids=set(), passed_ids=set(), eps=1.0, k=1)
    plain = model.solve_topk(cands, scores, need, **kw)[0]
    weighted = model.solve_topk(cands, scores, need, area_weight=GRADUATION_AREA_WEIGHT, **kw)[0]
    assert [c.course_id for c in plain.selected] == ["LIB"]
    assert [c.course_id for c in weighted.selected] == ["REQ"]
    assert plain.gradprogress == weighted.gradprogress == 3


def test_only_graduation_mode_is_weighted():
    assert PREFERENCE_AREA_WEIGHT["gap"] is None
    assert PREFERENCE_AREA_WEIGHT["balanced"] is None
    assert PREFERENCE_AREA_WEIGHT["graduation"] is GRADUATION_AREA_WEIGHT
    assert all(isinstance(w, int) and w >= 1 for w in GRADUATION_AREA_WEIGHT.values())


def test_graduation_differs_from_balanced_on_the_freshman_sample(tmp_path):
    """산데공 1학년 샘플 — 가중 전에는 두 성향이 같은 시간표였다."""
    src = (ROOT / "web" / "lib" / "sample.ts").read_text(encoding="utf-8")
    text = re.search(r"const IDE_2026 = `(.*?)`;", src, re.S).group(1)
    db = tmp_path / "app.db"
    shutil.copyfile(ROOT / "db" / "app.db", db)
    conn = sqlite3.connect(db)
    h = load_transcript(parse_transcript_text(text, dept_id="IDE", admission_year=2026), conn)
    conn.close()
    out = {}
    for mode in ("balanced", "graduation"):
        r = recommend(h, "DA", db_path=str(db), eps=PREFERENCE_EPS[mode], k=1,
                      area_weight=PREFERENCE_AREA_WEIGHT[mode]).results[0]
        out[mode] = (frozenset(c.course_id for c in r.selected), r.gradprogress,
                     sum(c.credit for c in r.selected if c.area in MAJOR))
    assert out["balanced"][0] != out["graduation"][0]
    assert out["graduation"][1] >= out["balanced"][1]          # 졸업 반영은 줄지 않는다
    assert out["graduation"][2] > out["balanced"][2]           # 전공·필수 학점은 늘어난다
