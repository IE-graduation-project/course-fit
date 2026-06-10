"""ILP 추천 단위테스트 (설계: docs/ILP_추천시스템_설계.md).

params(σ/gap/Score/need)와 model(2단계 ILP)을 DB·매핑 없이 검증한다.
DB 의존 로직(data.py)·end-to-end는 매핑 적재 후 별도 통합테스트.
"""
from __future__ import annotations

import math

from recommender import params, model
from recommender.data import Candidate


# --- grade_factor ------------------------------------------------------------
def test_grade_factor_normalized():
    assert params.grade_factor(4.5, 0) == 1.0
    assert math.isclose(params.grade_factor(3.0, 0), 3.0 / 4.5)
    assert math.isclose(params.grade_factor(1.0, 0), 1.0 / 4.5)  # D0 = 0.22


def test_grade_factor_pn_is_aplus():
    assert params.grade_factor(0.0, 1) == 1.0  # P/N → A+ (결정사항)


def test_grade_factor_unknown_neutral():
    # 이수 과목의 grade 0/None & is_pn 0 = 미상(F는 passed=0이라 σ 입력에 없음)
    assert params.grade_factor(0.0, 0) == params.NEUTRAL_UNKNOWN
    assert params.grade_factor(None, 0) == params.NEUTRAL_UNKNOWN  # student_course는 NULL 저장


# --- σ / gap / Score ---------------------------------------------------------
def test_sigma_saturation():
    comp = ["PROG", "DATA"]
    sigma = params.compute_sigma({"a": (4.5, 0)}, {"a": {"PROG": 0.5}}, comp, alpha=1.5)
    assert math.isclose(sigma["PROG"], 1 - math.exp(-1.5 * 0.5))
    assert sigma["DATA"] == 0.0  # 기여 없는 역량은 0


def test_sigma_unmatched_contributes_zero():
    comp = ["PROG"]
    # weights에 없는 기수강 과목은 σ에 0 기여 (설계 8절 한계)
    sigma = params.compute_sigma({"unknown": (4.5, 0)}, {}, comp)
    assert sigma["PROG"] == 0.0


def test_gap_clamped_at_zero():
    comp = ["PROG", "DATA"]
    gap = params.compute_gap({"PROG": 0.9, "DATA": 0.1}, {"PROG": 0.5, "DATA": 0.8}, comp)
    assert gap["PROG"] == 0.0          # 이미 충족 → 0
    assert math.isclose(gap["DATA"], 0.7)


def test_score_is_dot_product():
    comp = ["PROG", "DATA"]
    sc = params.score_of({"PROG": 0.5, "DATA": 0.5}, {"PROG": 0.2, "DATA": 0.4}, comp)
    assert math.isclose(sc, 0.5 * 0.2 + 0.5 * 0.4)


def test_need_floor():
    need = params.compute_need({"전공선택": 30, "공통교양": 5}, {"전공선택": 24, "공통교양": 17})
    assert need["전공선택"] == 0       # 이미 초과
    assert need["공통교양"] == 12


# --- ILP model ---------------------------------------------------------------
def _cand(cid, sec, credit, area, slots, prereqs=()):
    return Candidate(cid, sec, f"과목{cid}", credit, area, slots, prereqs, {})


def test_time_conflict_picks_one():
    # A·B 슬롯 충돌 → 둘 중 점수 높은 하나만
    A = _cand("a", "1", 3, "전공선택", (1, 2))
    B = _cand("b", "1", 3, "전공선택", (1, 2))
    C = _cand("c", "1", 3, "공통교양", (3, 4))
    res = model.solve([A, B, C], {"a": 0.3, "b": 0.1, "c": 0.05},
                      {"전공선택": 6, "공통교양": 3},
                      U=9, L=3, taken_ids=set(), passed_ids=set())
    assert res.status == "Optimal"
    sel = sorted(c.course_id for c in res.selected)
    assert sel == ["a", "c"]           # A(0.3)가 B(0.1)보다 우선, C는 충돌 없음
    assert res.total_credit == 6


def test_prereq_hard_blocks():
    # 선수 'x' 미이수 → 후보에서 제외(B2)
    D = _cand("d", "1", 3, "전공선택", (5,), prereqs=("x",))
    E = _cand("e", "1", 3, "전공선택", (6,))
    res = model.solve([D, E], {"d": 0.9, "e": 0.1}, {"전공선택": 6},
                      U=9, L=3, taken_ids=set(), passed_ids=set())
    sel = [c.course_id for c in res.selected]
    assert "d" not in sel and "e" in sel


def test_prereq_satisfied_allows():
    D = _cand("d", "1", 3, "전공선택", (5,), prereqs=("x",))
    res = model.solve([D], {"d": 0.9}, {"전공선택": 6},
                      U=9, L=3, taken_ids=set(), passed_ids={"x"})
    assert [c.course_id for c in res.selected] == ["d"]


def test_already_taken_excluded():
    A = _cand("a", "1", 3, "전공선택", (1,))
    res = model.solve([A], {"a": 0.9}, {"전공선택": 6},
                      U=9, L=3, taken_ids={"a"}, passed_ids=set())
    assert res.status == "no_candidates"


def test_topk_returns_distinct_alternatives():
    # 같은 과목 두 분반(시간만 다름) = 동등한 대안. k-best가 둘 다 반환해야.
    A1 = _cand("a", "1", 3, "전공선택", (1,))
    A2 = _cand("a", "2", 3, "전공선택", (2,))
    res = model.solve_topk([A1, A2], {"a": 0.2}, {"전공선택": 6},
                           U=3, L=3, taken_ids=set(), passed_ids=set(), k=3)
    assert len(res) == 2                              # 분반택1이라 1·2분반 두 대안
    assert {r.selected[0].section for r in res} == {"1", "2"}
    assert all(r.gradprogress == 3 for r in res)      # 둘 다 동등 점수


def test_topk_k1_equals_solve():
    A = _cand("a", "1", 3, "전공선택", (1,))
    one = model.solve([A], {"a": 0.2}, {"전공선택": 6}, U=3, L=3,
                      taken_ids=set(), passed_ids=set())
    topk = model.solve_topk([A], {"a": 0.2}, {"전공선택": 6}, U=3, L=3,
                            taken_ids=set(), passed_ids=set(), k=1)
    assert len(topk) == 1 and topk[0].selected[0].course_id == one.selected[0].course_id


def test_lexicographic_gradprogress_breaks_tie():
    # 직무적합 동점일 때 졸업진척(need>0 영역)이 우선되는지
    # A·B 점수 동일, 슬롯 무충돌. credit 상한이 둘 다는 못 담게 → 졸업진척 큰 쪽
    A = _cand("a", "1", 3, "전공선택", (1,))     # need 있음
    B = _cand("b", "1", 3, "교양필수", (2,))     # need 없음(0)
    res = model.solve([A, B], {"a": 0.2, "b": 0.2},
                      {"전공선택": 6, "교양필수": 0},
                      U=3, L=3, taken_ids=set(), passed_ids=set())
    assert [c.course_id for c in res.selected] == ["a"]   # 동점 → 졸업진척 큰 A
