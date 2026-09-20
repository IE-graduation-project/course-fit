"""목적함수가 비었을 때 — PuLP 의 `value()` 는 0.0 이 아니라 None 을 돌려준다.

PuLP 는 계수 0 인 항을 식에서 버린다. 그래서 모든 계수가 0 이면 식 자체가 비고,
`pulp.value()` 가 `None` 을 낸다. 이때 `LpStatus` 는 `'Optimal'` 이라 상태 가드로는 걸리지 않는다.

두 경로 모두 실제 학생 상태에서 도달한다:
  A) 어떤 직무의 gap 이 10개 역량 전부에서 0  → 모든 과목 Score 0
  B) 후보 area 의 need 가 전부 0(졸업 임박) → f_g 변수가 하나도 안 만들어짐

A 는 `TypeError` 로 죽고, B 는 죽지 않고 `None` 을 Result 에 담아 API·화면까지 흘려보낸다.
DB 를 타지 않고 solve_topk 를 직접 부른다 — 이 결함은 데이터가 아니라 식의 모양에서 온다.
"""
from __future__ import annotations

from recommender.data import Candidate
from recommender.model import solve_topk

COMMON = dict(taken_ids=set(), passed_ids=set(), U=18, L=12, k=1)


def _candidates(n: int = 6, credit: int = 3, area: str = "전공선택") -> list[Candidate]:
    """시간이 겹치지 않는 n개 분반. L=12 를 넘기려면 최소 4과목이 필요하다."""
    return [
        Candidate(course_id=f"C{i}", section="1", course_name=f"과목{i}",
                  credit=credit, area=area,
                  slots=(i * 3, i * 3 + 1, i * 3 + 2), prereqs=(), weights={})
        for i in range(n)
    ]


def test_all_scores_zero_does_not_crash():
    """전 후보 Score 0 — 직무적합이 빈 식이 되어도 시간표는 나와야 한다."""
    cands = _candidates()
    results = solve_topk(cands, {c.course_id: 0.0 for c in cands},
                         {"전공선택": 30}, **COMMON)
    assert results, "결과가 비었다"
    r = results[0]
    assert r.careerfit == 0.0, f"careerfit={r.careerfit!r} (기대 0.0)"
    assert r.selected, "고를 것이 없다고 판단해버렸다"
    # 직무적합이 0 이어도 졸업 진척으로는 최적화할 수 있어야 한다
    assert r.gradprogress > 0


def test_no_need_areas_returns_zero_not_none():
    """졸업요건이 전부 충족 — GradProgress 가 빈 식이어도 None 이 아니라 0.0 이어야 한다."""
    cands = _candidates()
    r = solve_topk(cands, {c.course_id: 0.5 for c in cands}, {}, **COMMON)[0]
    assert r.gradprogress is not None, "None 이 Result 에 들어갔다 — API·화면까지 흘러간다"
    assert r.gradprogress == 0.0, f"gradprogress={r.gradprogress!r} (기대 0.0)"
    assert r.careerfit > 0


def test_need_areas_not_matching_candidates():
    """need 는 있는데 후보 area 와 겹치지 않는 경우도 같은 경로다."""
    cands = _candidates(area="전공선택")
    r = solve_topk(cands, {c.course_id: 0.5 for c in cands},
                   {"교양필수": 9}, **COMMON)[0]
    assert r.gradprogress == 0.0, f"gradprogress={r.gradprogress!r} (기대 0.0)"


def test_result_fields_are_always_float():
    """선언이 float 이면 실제로도 float 이어야 한다 — 프론트 타입이 이 약속에 기대고 있다."""
    cands = _candidates()
    for scores, need in (
        ({c.course_id: 0.0 for c in cands}, {"전공선택": 30}),
        ({c.course_id: 0.5 for c in cands}, {}),
        ({c.course_id: 0.0 for c in cands}, {}),
        ({c.course_id: 0.5 for c in cands}, {"전공선택": 30}),
    ):
        for r in solve_topk(cands, scores, need, **COMMON):
            assert isinstance(r.careerfit, float), f"careerfit={r.careerfit!r}"
            assert isinstance(r.gradprogress, float), f"gradprogress={r.gradprogress!r}"


def test_normal_input_unchanged():
    """방어를 넣어도 정상 입력의 값은 그대로여야 한다."""
    cands = _candidates()
    r = solve_topk(cands, {c.course_id: 0.5 for c in cands},
                   {"전공선택": 30}, **COMMON)[0]
    assert r.careerfit == 9.0      # 6과목 × 3학점 × 0.5, 18학점 상한
    assert r.gradprogress == 18.0  # min(need 30, 담은 18)
    assert r.total_credit == 18
