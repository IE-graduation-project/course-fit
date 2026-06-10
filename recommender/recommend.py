"""추천 서비스 계층 — 재사용 가능한 진입점.

CLI·웹·API·노트북 어디서든 `recommend(...)`만 호출하면 된다. UI에 독립적이며,
DB(app.db)와 transcript가 적재한 student* 테이블만 읽는다.

    from recommender.recommend import recommend
    rec = recommend(input_hash, "DA", U=18)
    rec.result.selected  # 추천 분반 목록
"""
from __future__ import annotations

from dataclasses import dataclass

from . import data, params
from .model import Result, solve

# 사용자 취향 → ε 프리셋 (설계 4.4). 낮을수록 부족역량 우선(교양 OK),
# 높을수록 졸업·전공 비중. 포화 학생이 많은 3~4학년 타깃이라 balanced를 기본값으로.
PREFERENCE_EPS = {
    "gap": 0.0,          # 부족 역량 충실 — 교양이어도 갭 보완 우선
    "balanced": 0.3,     # 균형 (기본)
    "graduation": 0.6,   # 졸업·전공 우선
}
DEFAULT_PREFERENCE = "balanced"


@dataclass
class Recommendation:
    """추천 1건의 전체 산출물 (직렬화·표시용)."""
    result: Result                  # 선택 분반·V*·졸업진척·총학점·상태
    sigma: dict[str, float]         # 학생 현재 역량 (10차원)
    gap: dict[str, float]           # 직무 대비 부족 방향
    need: dict[str, int]            # 영역별 졸업 부족학점
    dept_id: str
    admission_year: int


def recommend(input_hash, job_id, *, db_path=data.DB_PATH, U=18, L=12,
              alpha=params.ALPHA_DEFAULT, eps=0.0) -> Recommendation:
    """파라미터 사전계산(σ/gap/Score/need) → 2단계 ILP → Recommendation.

    dept/입학년도는 student 테이블에서 읽으므로 인자로 받지 않는다.
    """
    conn = data.connect(db_path)
    try:
        comp = data.comp_ids(conn)
        student = data.load_student(conn, input_hash)
        rho = data.load_rho(conn, job_id)
        candidates = data.load_candidates(conn, student.dept_id)
        min_credits = data.load_min_credits(conn, student.dept_id, student.admission_year)
    finally:
        conn.close()

    sigma = params.compute_sigma(student.passed, student.weights, comp, alpha=alpha)
    gap = params.compute_gap(sigma, rho, comp)
    need = params.compute_need(student.earned_by_area, min_credits)

    score_by_course: dict[str, float] = {}
    for c in candidates:
        if c.course_id not in score_by_course:
            score_by_course[c.course_id] = params.score_of(c.weights, gap, comp)

    result = solve(
        candidates, score_by_course, need,
        U=U, L=L,
        taken_ids=student.taken_ids,
        passed_ids=set(student.passed.keys()),
        eps=eps,
    )
    return Recommendation(
        result=result, sigma=sigma, gap=gap, need=need,
        dept_id=student.dept_id, admission_year=student.admission_year,
    )
