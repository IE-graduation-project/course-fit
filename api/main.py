"""course-fit HTTP API.

계산 로직은 recommender/transcript에 있다. 이 모듈은 그것들을 계약(docs/API_계약.md) 모양으로
감싸기만 한다. 배포 설계: docs/배포_설계.md
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from recommender import data as rdata, params as rparams
from recommender.recommend import DEFAULT_PREFERENCE, PREFERENCE_EPS, recommend
from transcript.load import load_transcript
from transcript.parse_text import parse_transcript_text

from . import db
from .errors import ApiError, api_error_handler
from .schemas import RecommendRequest, TranscriptRequest
from .serialize import build_payload, build_reference, load_ref_data

DEFAULT_ORIGINS = "https://course-fit-seven.vercel.app,http://localhost:3000"

# CBC 1회 풀이 상한(초). 로컬 실측 0.6초라 여유가 크지만, 탐색이 폭발하는 입력에
# 워커가 영구히 물리는 것만 막으면 된다(결정 ⑤).
SOLVE_TIME_LIMIT = 30.0


def cors_origins() -> list[str]:
    raw = os.environ.get("COURSE_FIT_CORS_ORIGINS") or DEFAULT_ORIGINS
    return [o.strip() for o in raw.split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """기동 시 1회 — 시드 DB를 쓰기 가능한 곳으로 복사하고 참조 데이터를 캐시한다.

    참조 데이터(역량·직무·학과·분반 메타)는 런타임에 바뀌지 않는다. 요청마다 다시 읽을
    이유가 없어 한 번만 로드해 재사용한다.
    """
    db.ensure_db()
    conn = db.connect()
    try:
        app.state.ref = load_ref_data(conn)
    finally:
        conn.close()
    yield


app = FastAPI(title="course-fit API", version="0.1.0", lifespan=lifespan)
app.add_exception_handler(ApiError, api_error_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict:
    """배포 확인용. DB가 열리고 시드가 들어 있는지까지 본다 — 200만으로는 부족하다."""
    conn = db.connect()
    try:
        n = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
             for t in ("course", "course_section", "course_competency", "job", "student")}
    finally:
        conn.close()
    return {
        "status": "ok",
        "db": str(db.db_path()),
        "courses": n["course"],
        "sections": n["course_section"],
        "competencyMappings": n["course_competency"],
        "jobs": n["job"],
        "students": n["student"],
        "ttlHours": db.ttl_hours(),
    }


@app.get("/api/reference")
def reference() -> dict:
    """드롭다운·라벨용 참조 데이터. 정적이라 캐시 가능."""
    return build_reference(app.state.ref)


def _check_program(conn, dept: str, admission_year: int) -> int:
    """이 학과·입학년도에 적용할 졸업요건이 있는지 확인하고 적용 연도를 돌려준다(결정 ③·⑨).

    추천 단계까지 미루면 사용자가 성적표를 다 붙여넣은 다음 화면에서 에러를 만난다.
    실패를 입력 시점으로 당긴다.
    """
    year = rdata.effective_year(conn, dept, admission_year)
    if year is not None:
        return year
    earliest = rdata.earliest_year(conn, dept)
    if earliest is None:
        raise ApiError(400, "unsupported_dept", f"지원하지 않는 학과입니다: {dept}")
    raise ApiError(400, "unsupported_year",
                   f"{_dept_name(conn, dept)}는 {earliest}학번부터 지원합니다 "
                   f"(입력: {admission_year}학번).")


def _dept_name(conn, dept: str) -> str:
    r = conn.execute("SELECT dept_name FROM department WHERE dept_id=?", (dept,)).fetchone()
    return r[0] if r else dept


@app.post("/api/transcript")
def transcript(req: TranscriptRequest) -> dict:
    """성적표 텍스트를 파싱해 적재하고 studentId(=input_hash)를 돌려준다.

    같은 입력은 같은 해시 → 덮어쓰기(idempotent). 로그인이 없어 이 해시가 곧 학생 식별자다.
    """
    conn = db.connect()
    try:
        _check_program(conn, req.dept, req.admissionYear)
        db.purge_expired(conn)          # 결정 ⑧ — TTL 지난 성적표 정리

        result = parse_transcript_text(req.text, dept_id=req.dept,
                                       admission_year=req.admissionYear)
        if not result.courses:
            raise ApiError(400, "empty_transcript",
                           "성적표에서 과목을 찾지 못했습니다. 클래스넷 '전체성적조회' 화면을 "
                           "그대로 복사해 붙여넣어 주세요.")
        load_transcript(result, conn)
        matched = conn.execute(
            "SELECT COUNT(*) FROM student_course WHERE input_hash=? AND matched=1",
            (result.input_hash,)).fetchone()[0]
    finally:
        conn.close()

    return {
        "studentId": result.input_hash,
        "deptId": req.dept,
        "admissionYear": req.admissionYear,
        "courseCount": len(result.courses),
        "matchedCount": matched,
        "semesters": [],            # 파싱 결과 확인 화면용. 현재 프론트는 쓰지 않는다
    }


@app.post("/api/recommend")
def recommend_endpoint(req: RecommendRequest) -> dict:
    """학생 × 직무 × 성향으로 ILP를 풀어 시간표와 근거를 돌려준다.

    요청마다 실제로 최적화를 수행한다 — 미리 계산해 둔 답을 꺼내오는 것이 아니다.
    """
    if req.eps is None and req.mode is not None and req.mode not in PREFERENCE_EPS:
        raise ApiError(400, "unknown_mode",
                       f"성향은 {', '.join(PREFERENCE_EPS)} 중 하나여야 합니다: {req.mode}")
    if req.minCredits > req.maxCredits:
        raise ApiError(400, "bad_credit_bounds",
                       f"최소학점({req.minCredits})이 최대학점({req.maxCredits})보다 큽니다.")

    mode = req.mode or DEFAULT_PREFERENCE
    eps = req.eps if req.eps is not None else PREFERENCE_EPS[mode]

    conn = db.connect()
    try:
        db.purge_expired(conn)          # 결정 ⑧
        # 존재 확인을 먼저 한다 — recommend() 내부 ValueError를 문자열로 분류하면
        # 메시지가 바뀔 때마다 조용히 깨진다.
        if conn.execute("SELECT 1 FROM student WHERE input_hash=?",
                        (req.studentId,)).fetchone() is None:
            raise ApiError(404, "student_not_found",
                           "성적표를 찾을 수 없습니다. 다시 붙여넣어 주세요. "
                           "(보관 기간이 지나 삭제되었을 수 있습니다.)")
        if conn.execute("SELECT 1 FROM job WHERE job_id=?", (req.job,)).fetchone() is None:
            raise ApiError(400, "unknown_job", f"없는 직무입니다: {req.job}")

        rec = recommend(req.studentId, req.job, db_path=str(db.db_path()),
                        U=req.maxCredits, L=req.minCredits, alpha=rparams.ALPHA_DEFAULT,
                        eps=eps, k=req.topK, time_limit=SOLVE_TIME_LIMIT)
        return build_payload(conn, rec, app.state.ref, job_id=req.job, mode=mode, eps=eps,
                             alpha=rparams.ALPHA_DEFAULT, max_credits=req.maxCredits,
                             min_credits=req.minCredits, top_k=req.topK)
    finally:
        conn.close()
