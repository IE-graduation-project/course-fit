"""추천 서비스 계층 — 재사용 가능한 진입점.

CLI·웹·API·노트북 어디서든 `recommend(...)`만 호출하면 된다. UI에 독립적이며,
DB(app.db)와 transcript가 적재한 student* 테이블만 읽는다.

    from recommender.recommend import recommend
    rec = recommend(input_hash, "DA", U=18)
    rec.result.selected  # 추천 분반 목록
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import data, params
from .model import Result, solve_topk

# 사용자 취향 → ε 프리셋 (설계 4.4). 낮을수록 부족역량 우선(교양 OK),
# 높을수록 졸업·전공 비중. 포화 학생이 많은 3~4학년 타깃이라 balanced를 기본값으로.
PREFERENCE_EPS = {
    "gap": 0.0,          # 부족 역량 충실 — 교양이어도 갭 보완 우선
    "balanced": 0.3,     # 균형 (기본)
    "graduation": 0.6,   # 졸업·전공 우선
}
DEFAULT_PREFERENCE = "balanced"

# 성향별 2순위 영역 가중 (#53). ε 만으로는 졸업 우선이 균형과 같은 시간표를 냈다 — 균형에서
# 이미 담은 학점 전부가 남은 요건에 들어가면(졸업 반영 = 학점 상한) 더 고를 해가 없다.
# 졸업 우선은 화면 설명(「졸업요건·전공 학점을 먼저 채움」)대로 필수 → 전공 → 나머지 순으로 채운다.
GRADUATION_AREA_WEIGHT = {"전공필수": 3, "교양필수": 3,
                          "전공기초": 2, "MSC": 2, "전공선택": 2}
PREFERENCE_AREA_WEIGHT: dict[str, dict[str, int] | None] = {
    "gap": None,
    "balanced": None,
    "graduation": GRADUATION_AREA_WEIGHT,
}


@dataclass
class Recommendation:
    """추천 산출물 (직렬화·표시용). σ/gap/need는 시간표와 무관해 공통, 시간표만 top-k."""
    results: list[Result]           # 상위 k개 시간표 (1등이 [0])
    sigma: dict[str, float]         # 학생 현재 역량 (10차원)
    gap: dict[str, float]           # 직무 대비 부족 방향
    need: dict[str, int]            # 영역별 졸업 부족학점
    dept_id: str
    admission_year: int
    requirement_year: int           # 실제 적용된 교육과정 개정 연도 (결정 ⑨). 화면 고지용
    grade_level: int                # 후보를 거른 학년 (#42). 화면 고지용
    # 역량별 σ 기여 과목 [(course_id, grade_factor·w)]. 화면의 「무엇으로 쌓였나」용
    contributions: dict[str, list[tuple[str, float]]] = field(default_factory=dict)

    @property
    def result(self) -> Result:
        """1등 시간표 (하위호환)."""
        return self.results[0]


def recommend(input_hash, job_id, *, db_path=data.DB_PATH, U=18, L=12,
              alpha=params.ALPHA_DEFAULT, eps=0.0, k=3,
              time_limit: float | None = None,
              area_weight: dict[str, int] | None = None,
              free_days=()) -> Recommendation:
    """파라미터 사전계산(σ/gap/Score/need) → 2단계 ILP(top-k) → Recommendation.

    dept/입학년도는 student 테이블에서 읽으므로 인자로 받지 않는다.
    """
    conn = data.connect(db_path)
    try:
        comp = data.comp_ids(conn)
        student = data.load_student(conn, input_hash)
        rho = data.load_rho(conn, job_id)
        term = data.active_term(conn)
        grade = data.grade_for_term(student.current_grade, student.admission_year, term)
        candidates = data.load_candidates(conn, student.dept_id, term=term, grade=grade)
        min_credits = data.load_min_credits(conn, student.dept_id, student.admission_year)
        # 입학년도와 다를 수 있다 — 2025학번 경영은 2022 교육과정을 따른다(결정 ⑨).
        req_year = data.effective_year(conn, student.dept_id, student.admission_year)
    finally:
        conn.close()

    sigma = params.compute_sigma(student.passed, student.weights, comp, alpha=alpha)
    contributions = params.sigma_contributions(student.passed, student.weights, comp)
    gap = params.compute_gap(sigma, rho, comp)
    need = params.compute_need(student.earned_by_area, min_credits)

    score_by_course: dict[str, float] = {}
    for c in candidates:
        if c.course_id not in score_by_course:
            score_by_course[c.course_id] = params.score_of(c.weights, gap, comp)

    results = solve_topk(
        candidates, score_by_course, need,
        U=U, L=L,
        taken_ids=student.taken_ids,
        passed_ids=set(student.passed.keys()),
        eps=eps, k=k, time_limit=time_limit, area_weight=area_weight, free_days=free_days,
    )
    return Recommendation(
        results=results, sigma=sigma, gap=gap, need=need,
        dept_id=student.dept_id, admission_year=student.admission_year,
        requirement_year=req_year, grade_level=grade, contributions=contributions,
    )
