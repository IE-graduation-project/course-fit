"""2순위 동점 가르기 — 졸업 반영이 같으면 직무 적합이 높은 시간표 (#45).

2순위는 졸업 반영만 최대화하고 직무 적합은 하한으로만 건다. 하한 위에서 졸업 반영이 같은
해는 목적함수 값이 똑같아서, 무엇이 나올지는 CBC 의 탐색 순서가 정했다. 같은 입력이
로컬(Windows)과 배포 서버(Linux)에서 다른 시간표를 냈고, 배포 쪽이 직무 적합이 더 낮았다.

동점 가르기는 졸업 반영을 한 학점도 내주면 안 된다 — 그건 1·2순위를 뒤집는 것이다.
"""
from __future__ import annotations

from recommender import model
from recommender.data import Candidate


def _cand(cid, area, credit, slot):
    return Candidate(course_id=cid, section="1", course_name=cid, credit=credit, area=area,
                     slots=(slot,), prereqs=(), weights={})


def _solve(cands, scores, need, *, U, L, eps=1.0, k=1):
    return model.solve_topk(cands, scores, need, U=U, L=L, taken_ids=set(), passed_ids=set(),
                            eps=eps, k=k)


def test_ties_on_graduation_go_to_the_higher_career_fit():
    # 공통교양 3학점 한 자리를 두고 다섯 과목이 경쟁 — 졸업 반영은 누굴 골라도 3 이다.
    # 낮은 점수를 변수 순서 앞에 둬서, 순서대로 고르는 솔버라면 틀린 쪽을 잡게 한다.
    scores = {"A": 0.05, "B": 0.10, "C": 0.20, "D": 0.40, "E": 0.90}
    cands = [_cand(cid, "공통교양", 3, i) for i, cid in enumerate(scores)]
    r = _solve(cands, scores, {"공통교양": 3}, U=3, L=3)[0]
    assert r.gradprogress == 3
    assert [c.course_id for c in r.selected] == ["E"]


def test_tie_break_never_costs_a_graduation_credit():
    # 직무 적합이 20배 높은 과목이 있어도, 졸업 반영 1학점을 잃는다면 고르지 않는다.
    scores = {"MSC1": 0.05, "LIB1": 1.00}
    cands = [_cand("MSC1", "MSC", 3, 0), _cand("LIB1", "공통교양", 3, 1)]
    r = _solve(cands, scores, {"MSC": 3}, U=3, L=3)[0]
    assert r.gradprogress == 3
    assert [c.course_id for c in r.selected] == ["MSC1"]


def test_alternatives_stay_in_lexicographic_order():
    """안 2·3 은 안 1 보다 (졸업 반영, 직무 적합) 사전순으로 나쁘거나 같다."""
    scores = {f"C{i}": s for i, s in enumerate([0.9, 0.7, 0.5, 0.3, 0.1, 0.8])}
    areas = ["공통교양", "공통교양", "MSC", "MSC", "공통교양", "전공선택"]
    cands = [_cand(cid, a, 3, i) for (cid, a), i in zip(zip(scores, areas), range(6))]
    rs = _solve(cands, scores, {"공통교양": 3, "MSC": 3}, U=6, L=6, k=3)
    keys = [(round(r.gradprogress, 6), round(r.careerfit, 6)) for r in rs]
    assert keys == sorted(keys, reverse=True), keys


def test_full_ties_pick_the_same_timetable_whatever_the_order():
    """점수까지 같은 해가 여럿이면 후보 순서와 무관하게 같은 안이 나온다 (#73).

    CBC 는 동점 최적해 중 무엇을 낼지 변수 순서와 실행 환경에 따라 달리 골랐다. 순서를 섞어
    그 차이를 흉내 낸다 — 같은 과목의 분반 다섯, 점수·영역·학점이 같은 다른 과목 넷.
    """
    import random

    sections = [Candidate(course_id="A", section=str(s), course_name="A", credit=3, area="전공선택",
                          slots=(s,), prereqs=(), weights={}) for s in range(1, 6)]
    others = [_cand(f"B{i}", "공통교양", 3, 10 + i) for i in range(4)]
    scores = {"A": 0.5, **{f"B{i}": 0.2 for i in range(4)}}
    need = {"전공선택": 3, "공통교양": 3}
    picks = set()
    for seed in range(8):
        cands = sections + others
        random.Random(seed).shuffle(cands)
        rs = _solve(cands, scores, need, U=6, L=6, k=3)
        picks.add(tuple(tuple(sorted(f"{c.course_id}-{c.section}" for c in r.selected)) for r in rs))
    assert len(picks) == 1, picks
