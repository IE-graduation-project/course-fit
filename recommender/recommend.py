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
    # 졸업까지 남은 학점 표시용. 영역별 need 합이 아니라 총학점−취득학점으로 센다.
    total_earned: int | None = None     # 성적표 총 취득학점 (영역 매핑과 무관)
    total_required: int | None = None   # 학과 졸업 총학점 (department.total_credits_required, 132)
    # 시간 충돌로 1등 시간표에서 빠진 고가치 후보 [(Candidate, score, 겹친_선택과목명)].
    # "정말 중요한 수업이 겹쳐 하나가 떨어졌을 때 그것도 옵션으로"(발표 피드백)를 위해 화면에 띄운다.
    dropped_conflicts: list = field(default_factory=list)

    @property
    def result(self) -> Result:
        """1등 시간표 (하위호환)."""
        return self.results[0]


def _dropped_by_conflict(results, candidates, score_by_course, *, top_n: int = 3):
    """1등 시간표에 들었어도 좋았을 만큼 점수가 높은데, 선택된 과목과 시간이 겹쳐 빠진 후보.

    발표 피드백: "정말 중요한 수업 2개가 겹쳐 하나가 떨어지면, 그걸 듣고 싶은 학생도 있으니
    옵션으로 보여 달라." 1등 해의 선택 과목과 슬롯이 겹치고, 점수가 선택된 과목 중 가장 낮은
    것 이상인 비선택 후보만 고른다(겹치지 않았으면 들어올 값어치였다는 뜻). 과목 단위로 묶어
    최고점 분반만, 점수 내림차순 top_n.
    """
    solved = [r for r in results if r.status == "Optimal"]
    if not solved:
        return []
    selected = solved[0].selected
    if not selected:
        return []
    sel_ids = {c.course_id for c in selected}
    owner = {}  # slot → 겹친 선택 과목 (course_id, name)
    for c in selected:
        for s in c.slots:
            owner.setdefault(s, (c.course_id, c.course_name))
    floor = min(score_by_course.get(c.course_id, 0.0) for c in selected)
    best: dict[str, tuple] = {}
    for c in candidates:
        if c.course_id in sel_ids:
            continue
        sc = score_by_course.get(c.course_id, 0.0)
        if sc <= 0 or sc < floor:
            continue
        clash = next((owner[s] for s in c.slots if s in owner), None)
        if clash is None:
            continue
        prev = best.get(c.course_id)
        if prev is None or sc > prev[1]:
            best[c.course_id] = (c, sc, clash[0], clash[1])
    return sorted(best.values(), key=lambda t: -t[1])[:top_n]


def recommend(input_hash, job_id, *, db_path=data.DB_PATH, U=18, L=12,
              alpha=params.ALPHA_DEFAULT, eps=0.0, k=3,
              time_limit: float | None = None,
              area_weight: dict[str, int] | None = None,
              free_days=(), exclude_courses=()) -> Recommendation:
    """파라미터 사전계산(σ/gap/Score/need) → 2단계 ILP(top-k) → Recommendation.

    dept/입학년도는 student 테이블에서 읽으므로 인자로 받지 않는다.

    `exclude_courses` 는 사용자가 "이 과목 빼고 다시"로 지정한 course_id 집합이다. 후보에서
    미리 빼고 다시 푼다 — free_days 와 같은 제약 축이라 식은 그대로고, ILP 가 그 과목 없이
    다음 최적 조합을 찾는다.
    """
    exclude_courses = set(exclude_courses)
    conn = data.connect(db_path)
    try:
        comp = data.comp_ids(conn)
        student = data.load_student(conn, input_hash)
        # job_id 는 하나(str)일 수도 여럿(list)일 수도 있다. 여럿이면 요구 역량의 합집합(역량별 max).
        rho = data.load_rho_union(conn, job_id)
        term = data.active_term(conn)
        grade = data.grade_for_term(student.current_grade, student.admission_year, term)
        candidates = data.load_candidates(conn, student.dept_id, term=term, grade=grade)
        if exclude_courses:
            candidates = [c for c in candidates if c.course_id not in exclude_courses]
        min_credits = data.load_min_credits(conn, student.dept_id, student.admission_year)
        # 입학년도와 다를 수 있다 — 2025학번 경영은 2022 교육과정을 따른다(결정 ⑨).
        req_year = data.effective_year(conn, student.dept_id, student.admission_year)
        total_required = data.total_credits_required(conn, student.dept_id)
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
    dropped = _dropped_by_conflict(results, candidates, score_by_course)
    return Recommendation(
        results=results, sigma=sigma, gap=gap, need=need,
        dropped_conflicts=dropped,
        dept_id=student.dept_id, admission_year=student.admission_year,
        requirement_year=req_year, grade_level=grade, contributions=contributions,
        total_earned=student.total_earned, total_required=total_required,
    )
