"""공강 요일 (#77) — 학생이 비우겠다고 고른 요일의 수업은 추천하지 않는다.

요일은 0=월 … 4=금. 그 요일에 한 교시라도 걸친 분반을 후보에서 미리 뺀다(B3). ILP 식은 그대로라
동점 결정(#45, #73)에 손대지 않는다. 시간 미지정 분반(비대면·논문)은 학교에 나올 일이 없어 남긴다.
못 채우면 서버가 조건을 풀지 않고 빈 결과를 준다 — 화면이 공강을 줄여 보라고 안내한다.
"""
from __future__ import annotations

import os
import pathlib
import shutil

import pytest
from fastapi.testclient import TestClient

from recommender import model
from recommender.data import Candidate

ROOT = pathlib.Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "tests" / "fixtures" / "transcript_paste_sample.txt"
MON, TUE, WED, THU, FRI, SAT = range(6)


def _slot(day: int, period: int) -> int:
    return day * model.DAY_STRIDE + period


def _cand(cid: str, slots: tuple[int, ...]) -> Candidate:
    return Candidate(course_id=cid, section="1", course_name=cid, credit=3, area="전공선택",
                     slots=slots, prereqs=(), weights={})


def _kept(cands, free_days) -> set[str]:
    return {c.course_id for c in model.filter_candidates(cands, set(), set(), free_days)}


# ── B3 사전필터 ─────────────────────────────────────────────────────────────
def test_section_on_a_free_day_is_dropped():
    cands = [_cand("MON", (_slot(MON, 2), _slot(MON, 3))), _cand("FRI", (_slot(FRI, 5),))]
    assert _kept(cands, [FRI]) == {"MON"}


def test_section_touching_a_free_day_once_is_dropped():
    """월·금에 나뉜 분반은 금요일 하루만 걸쳐도 금공강을 깬다."""
    cands = [_cand("SPLIT", (_slot(MON, 2), _slot(FRI, 2))), _cand("TUE", (_slot(TUE, 2),))]
    assert _kept(cands, [FRI]) == {"TUE"}


def test_unscheduled_section_survives_any_free_day():
    cands = [_cand("ONLINE", ()), _cand("WED", (_slot(WED, 1),))]
    assert _kept(cands, [MON, TUE, WED, THU, FRI]) == {"ONLINE"}


def test_no_free_day_keeps_everything():
    cands = [_cand("MON", (_slot(MON, 1),)), _cand("SAT", (_slot(SAT, 1),))]
    assert _kept(cands, []) == {"MON", "SAT"}
    assert _kept(cands, ()) == {"MON", "SAT"}


def test_last_period_of_the_day_before_is_not_mistaken_for_the_free_day():
    """요일 경계 — 목요일 15교시(슬롯 63)는 금요일(64~)이 아니다."""
    cands = [_cand("THU_LATE", (_slot(THU, 15),)), _cand("FRI_FIRST", (_slot(FRI, 1),))]
    assert _kept(cands, [FRI]) == {"THU_LATE"}


# ── API ─────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def client(tmp_path_factory):
    dst = tmp_path_factory.mktemp("freedb") / "app.db"
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


@pytest.fixture(scope="module")
def student_id(client) -> str:
    r = client.post("/api/transcript", json={
        "text": SAMPLE.read_text(encoding="utf-8"), "dept": "BIZ", "admissionYear": 2022})
    assert r.status_code == 200, r.text
    return r.json()["studentId"]


@pytest.mark.parametrize("bad", [[5], [-1], [0, 7]])
def test_recommend_400_for_day_outside_mon_to_fri(client, student_id, bad):
    r = client.post("/api/recommend", json={"studentId": student_id, "job": "DA", "freeDays": bad})
    assert r.status_code == 400
    assert r.json()["error"] == "bad_free_days"


@pytest.mark.parametrize("free", [[FRI], [MON, FRI]])
def test_recommended_sections_avoid_free_days(client, student_id, free):
    d = client.post("/api/recommend", json={"studentId": student_id, "job": "DA",
                                            "freeDays": free}).json()
    assert d["params"]["freeDays"] == free
    assert d["timetables"], "시간표가 비었다"
    for tt in d["timetables"]:
        for c in tt["courses"]:
            days = {s // model.DAY_STRIDE for s in c["slots"]}
            assert not days & set(free), f"{c['name']} 이 공강 요일에 있다: {c['slotsHuman']}"


def test_free_days_are_echoed_sorted_and_deduplicated(client, student_id):
    d = client.post("/api/recommend", json={"studentId": student_id, "job": "DA",
                                            "freeDays": [FRI, MON, FRI]}).json()
    assert d["params"]["freeDays"] == [MON, FRI]


def test_no_free_days_is_the_default(client, student_id):
    base = {"studentId": student_id, "job": "DA"}
    plain = client.post("/api/recommend", json=base).json()
    empty = client.post("/api/recommend", json={**base, "freeDays": []}).json()
    assert plain["params"]["freeDays"] == []
    assert plain["timetables"] == empty["timetables"]


def test_every_weekday_free_gives_an_empty_result_not_an_error(client, student_id):
    """다섯 요일을 다 비우면 12학점을 못 채운다. 500 이 아니라 빈 결과여야 화면이 안내를 낸다."""
    r = client.post("/api/recommend", json={"studentId": student_id, "job": "DA",
                                            "freeDays": [MON, TUE, WED, THU, FRI]})
    assert r.status_code == 200, r.text
    d = r.json()
    for tt in d["timetables"]:      # 시간 미지정·토요일 분반만으로 채운 경우
        for c in tt["courses"]:
            assert all(s // model.DAY_STRIDE > FRI for s in c["slots"])
