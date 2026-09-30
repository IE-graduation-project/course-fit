"""API 계약·불변식 테스트.

**무엇을 보장하려는 건가**
1. 스키마 대조 — 실 응답이 프론트가 기대하는 모양인가 (`web/public/fixtures/*.json`이 기준).
   픽스처를 만든 학생이 DB에 없어 값 대조는 불가능하다(배포 설계 §3.1). 모양만 본다.
   단 `/api/reference`는 학생과 무관해 값까지 대조한다.
2. 불변식 — 응답 JSON만 보고 ILP hard 제약 위반을 잡아낸다.
3. 결정성 — 같은 입력이면 같은 시간표. 2026-09-13에 깨져 있던 성질이라 회귀 테스트로 고정한다.

DB는 임시 사본을 쓴다. 테스트가 개발자의 db/app.db에 학생을 적재하면 안 된다.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil

import pytest
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "tests" / "fixtures" / "transcript_paste_sample.txt"
FIXTURES = ROOT / "web" / "public" / "fixtures"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    dst = tmp_path_factory.mktemp("apidb") / "app.db"
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


# ── /health ────────────────────────────────────────────────────────────────
def test_health_reports_seeded_db(client):
    d = client.get("/health").json()
    assert d["status"] == "ok"
    assert d["courses"] > 3000 and d["sections"] > 900


# ── /api/reference — 학생 무관이라 값까지 대조 ──────────────────────────────
def test_reference_matches_fixture_exactly(client):
    """픽스처는 이제 api/serialize.py 가 만든다(결정 ①). 그래서 값까지 완전히 같아야 한다.

    이게 깨지면 둘 중 하나다 — 직렬화를 고치고 픽스처를 재생성하지 않았거나(dump_fixtures.py),
    참조 데이터(역량·직무·학과)가 DB에서 바뀌었거나.
    """
    got = client.get("/api/reference").json()
    want = json.loads((FIXTURES / "reference.json").read_text(encoding="utf-8"))
    assert got == want, "픽스처 재생성이 필요하다: python web/scripts/dump_fixtures.py <hash> web/public/fixtures"


def test_reference_programs_expose_supported_years(client):
    programs = {p["dept"]: p["fromYear"] for p in client.get("/api/reference").json()["programs"]}
    assert programs == {"BIZ": 2022, "IDE": 2026}


# ── /api/transcript ────────────────────────────────────────────────────────
def test_transcript_is_idempotent(client):
    body = {"text": SAMPLE.read_text(encoding="utf-8"), "dept": "BIZ", "admissionYear": 2022}
    a = client.post("/api/transcript", json=body).json()
    b = client.post("/api/transcript", json=body).json()
    assert a["studentId"] == b["studentId"]
    assert a["courseCount"] == b["courseCount"] > 0


@pytest.mark.parametrize("dept,year,ok", [
    ("BIZ", 2022, True),    # 개정 연도 당해
    ("BIZ", 2025, True),    # 결정 ⑨ — 2022 교육과정이 계속 적용된다
    ("BIZ", 2021, False),   # 2022 개정 이전
    ("IDE", 2026, True),
    ("IDE", 2025, False),   # 산데공은 26학번부터
    ("ZZZ", 2022, False),   # 없는 학과
])
def test_transcript_validates_program_up_front(client, dept, year, ok):
    """추천 단계가 아니라 입력 시점에 거른다(결정 ③)."""
    r = client.post("/api/transcript", json={
        "text": SAMPLE.read_text(encoding="utf-8"), "dept": dept, "admissionYear": year})
    assert (r.status_code == 200) is ok, r.text
    if not ok:
        assert r.json()["error"] in {"unsupported_year", "unsupported_dept"}
        assert "지원" in r.json()["detail"]


def test_transcript_rejects_unparseable_text(client):
    r = client.post("/api/transcript",
                    json={"text": "안녕하세요", "dept": "BIZ", "admissionYear": 2022})
    assert r.status_code == 400
    assert r.json()["error"] == "empty_transcript"


# ── /api/recommend — 스키마 대조 ────────────────────────────────────────────
def _assert_shape(got, want, path="") -> None:
    """want(픽스처)의 모든 키가 got에 있고 타입이 호환되는지. got의 추가 키는 허용한다.

    null은 와일드카드다 — professor 등은 계약상 nullable이라 학생이 다르면 한쪽만 null일 수 있다.
    """
    if want is None or got is None:
        return
    if isinstance(want, dict):
        assert isinstance(got, dict), f"{path}: dict 여야 하는데 {type(got).__name__}"
        for k in want:
            assert k in got, f"{path}.{k} 가 응답에 없다 — 프론트가 깨진다"
            _assert_shape(got[k], want[k], f"{path}.{k}")
    elif isinstance(want, list):
        assert isinstance(got, list), f"{path}: list 여야 하는데 {type(got).__name__}"
        if want and got:
            _assert_shape(got[0], want[0], f"{path}[0]")
    elif isinstance(want, bool):
        assert isinstance(got, bool), f"{path}: bool 여야 한다"
    elif isinstance(want, (int, float)):
        assert isinstance(got, (int, float)) and not isinstance(got, bool), f"{path}: 수 여야 한다"
    else:
        assert isinstance(got, str), f"{path}: 문자열이어야 한다"


def test_recommend_shape_matches_fixture(client, student_id):
    got = client.post("/api/recommend", json={
        "studentId": student_id, "job": "DA", "mode": "balanced"}).json()
    want = json.loads((FIXTURES / "DA_balanced.json").read_text(encoding="utf-8"))
    _assert_shape(got, want, "recommend")


def test_recommend_has_all_ten_competency_axes(client, student_id):
    d = client.post("/api/recommend", json={"studentId": student_id, "job": "DA"}).json()
    for axis in ("sigma", "rho", "gap"):
        assert len(d["diagnosis"][axis]) == 10, f"{axis} 가 10축이 아니다 — 진단 막대가 깨진다"


def test_recommend_reports_applied_requirement_year(client):
    """결정 ⑨ — 2025학번에게 2022 교육과정이 적용됐음을 화면에 고지할 수 있어야 한다."""
    sid = client.post("/api/transcript", json={
        "text": SAMPLE.read_text(encoding="utf-8"), "dept": "BIZ",
        "admissionYear": 2025}).json()["studentId"]
    d = client.post("/api/recommend", json={"studentId": sid, "job": "DA"}).json()
    assert d["student"]["admissionYear"] == 2025
    assert d["student"]["requirementYear"] == 2022


# ── /api/recommend — ILP 불변식 ─────────────────────────────────────────────
@pytest.mark.parametrize("u", [15, 21])
def test_recommend_fills_up_to_chosen_credits(client, student_id, u):
    """결과 화면의 학점 선택(15·18·21)이 시간표 학점 상한으로 그대로 간다 — 21 을 골랐는데
    18 짜리가 오거나 15 를 골랐는데 넘치면 선택지가 거짓말이다."""
    d = client.post("/api/recommend", json={"studentId": student_id, "job": "DA",
                                            "maxCredits": u}).json()
    assert d["params"]["maxCredits"] == u
    assert d["timetables"], "시간표가 비었다"
    for tt in d["timetables"]:
        assert u - 3 < tt["totalCredit"] <= u, tt["totalCredit"]


@pytest.mark.parametrize("job", ["DA", "MKT"])
def test_recommend_respects_hard_constraints(client, student_id, job):
    """응답 JSON만 보고 A1·A2·A3·B1 위반을 잡는다."""
    req = {"studentId": student_id, "job": job, "maxCredits": 18, "minCredits": 12}
    d = client.post("/api/recommend", json=req).json()
    assert d["timetables"], "시간표가 비었다"
    for tt in d["timetables"]:
        credits = sum(c["credit"] for c in tt["courses"])
        assert credits == tt["totalCredit"]
        assert 12 <= credits <= 18, f"A3 위반: {credits}학점"

        slots = [s for c in tt["courses"] for s in c["slots"]]
        assert len(slots) == len(set(slots)), "A1 위반: 같은 교시에 두 과목"

        ids = [c["courseId"] for c in tt["courses"]]
        assert len(ids) == len(set(ids)), "A2 위반: 한 과목의 분반이 둘"

        for c in tt["courses"]:
            if c["careerReason"]:
                total = sum(r["share"] for r in c["careerReason"])
                assert 0 < total <= 1.0001, f"share 합이 이상하다: {total}"


def test_recommend_excludes_already_taken(client, student_id):
    """B1 — 기수강 과목은 후보에서 빠져야 한다."""
    from api import db
    conn = db.connect()
    taken = {r[0] for r in conn.execute(
        "SELECT course_id FROM student_course WHERE input_hash=? AND course_id IS NOT NULL",
        (student_id,))}
    conn.close()
    d = client.post("/api/recommend", json={"studentId": student_id, "job": "DA"}).json()
    for tt in d["timetables"]:
        for c in tt["courses"]:
            assert c["courseId"] not in taken, f"기수강인데 추천됨: {c['courseId']}"


def test_recommend_actually_solves_per_job(client, student_id):
    """룩업이 아니라 매 요청 ILP를 푸는 중임의 증명 — 직무가 다르면 시간표가 달라야 한다."""
    def courses(job):
        d = client.post("/api/recommend", json={"studentId": student_id, "job": job}).json()
        return {c["courseId"] for c in d["timetables"][0]["courses"]}
    assert courses("DA") != courses("MKT")


def test_recommend_is_deterministic(client, student_id):
    """2026-09-13 회귀 — set 순회 순서가 흔들려 같은 입력에 다른 시간표가 나왔다."""
    req = {"studentId": student_id, "job": "DA", "mode": "balanced"}
    a = client.post("/api/recommend", json=req).json()
    b = client.post("/api/recommend", json=req).json()
    assert a == b


def test_recommend_mode_changes_result_shape(client, student_id):
    """성향(ε)이 실제로 목적함수에 반영되는지."""
    got = {m: client.post("/api/recommend",
                          json={"studentId": student_id, "job": "DA", "mode": m}).json()
           for m in ("gap", "balanced", "graduation")}
    assert [got[m]["params"]["eps"] for m in ("gap", "balanced", "graduation")] == [0.0, 0.3, 0.6]


# ── /api/recommend — 에러 ───────────────────────────────────────────────────
def test_recommend_404_for_unknown_student(client):
    r = client.post("/api/recommend", json={"studentId": "deadbeefdeadbeef", "job": "DA"})
    assert r.status_code == 404
    assert r.json()["error"] == "student_not_found"


def test_recommend_400_for_unknown_job(client, student_id):
    r = client.post("/api/recommend", json={"studentId": student_id, "job": "NOPE"})
    assert r.status_code == 400
    assert r.json()["error"] == "unknown_job"


def test_recommend_400_for_bad_mode(client, student_id):
    r = client.post("/api/recommend", json={"studentId": student_id, "job": "DA", "mode": "fast"})
    assert r.status_code == 400
    assert r.json()["error"] == "unknown_mode"


def test_recommend_400_when_credit_bounds_inverted(client, student_id):
    r = client.post("/api/recommend", json={
        "studentId": student_id, "job": "DA", "minCredits": 18, "maxCredits": 12})
    assert r.status_code == 400
    assert r.json()["error"] == "bad_credit_bounds"
