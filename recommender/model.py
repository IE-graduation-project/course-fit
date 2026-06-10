"""PuLP 2단계 우선순위형(lexicographic) ILP. 설계 6절.

[1순위] max CareerFit → V*
[2순위] max GradProgress  s.t. CareerFit ≥ (1−ε)·V*
hard 제약 A1(시간충돌)·A2(분반택1)·A3/A3'(학점상한/하한). B1·B2는 후보 사전필터로 처리.
"""
from __future__ import annotations

from dataclasses import dataclass

import pulp


@dataclass
class Result:
    selected: list          # list[Candidate]
    careerfit: float
    gradprogress: float
    total_credit: int
    status: str             # PuLP 상태 문자열 또는 'no_candidates'


def filter_candidates(candidates, taken_ids, passed_ids):
    """B1(기수강 제외)·B2(선수 미충족 제외) 사전필터."""
    out = []
    for c in candidates:
        if c.course_id in taken_ids:                                  # B1
            continue
        if c.prereqs and not all(p in passed_ids for p in c.prereqs):  # B2
            continue
        out.append(c)
    return out


def _add_base_constraints(prob, x, cands, U, L):
    """hard 제약 A1·A2·A3·A3'를 prob에 추가 (매 problem마다 새 제약 객체로)."""
    # A1 시간충돌: 슬롯별 ≤1. NULL 슬롯은 c.slots=()이라 어디에도 안 들어가 자동 제외.
    slot_map: dict[int, list[int]] = {}
    for i, c in enumerate(cands):
        for s in c.slots:
            slot_map.setdefault(s, []).append(i)
    for s, idxs in slot_map.items():
        if len(idxs) > 1:
            prob += pulp.lpSum(x[i] for i in idxs) <= 1, f"slot_{s}"

    # A2 한 과목당 분반 하나
    by_course: dict[str, list[int]] = {}
    for i, c in enumerate(cands):
        by_course.setdefault(c.course_id, []).append(i)
    for cid, idxs in by_course.items():
        if len(idxs) > 1:
            prob += pulp.lpSum(x[i] for i in idxs) <= 1, f"course_{cid}"

    # A3 / A3' 학점 상·하한
    total = pulp.lpSum(c.credit * x[i] for i, c in enumerate(cands))
    prob += total <= U, "credit_upper"
    prob += total >= L, "credit_lower"


def solve(candidates, score_by_course, need, *, U=18, L=12,
          taken_ids, passed_ids, eps=0.0, msg=False) -> Result:
    cands = filter_candidates(candidates, taken_ids, passed_ids)
    if not cands:
        return Result([], 0.0, 0.0, 0, "no_candidates")

    x = {i: pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(len(cands))}
    careerfit = pulp.lpSum(c.credit * score_by_course[c.course_id] * x[i]
                           for i, c in enumerate(cands))
    gradprog = pulp.lpSum((1 if need.get(c.area, 0) > 0 else 0) * c.credit * x[i]
                          for i, c in enumerate(cands))
    solver = pulp.PULP_CBC_CMD(msg=msg)

    # ── 1순위: 직무적합 최대화 → V*
    p1 = pulp.LpProblem("careerfit", pulp.LpMaximize)
    p1 += careerfit
    _add_base_constraints(p1, x, cands, U, L)
    p1.solve(solver)
    if pulp.LpStatus[p1.status] != "Optimal":
        return Result([], 0.0, 0.0, 0, pulp.LpStatus[p1.status])
    vstar = pulp.value(careerfit)

    # ── 2순위: 졸업진척 최대화, 직무적합 ≥ (1−ε)V* 유지
    p2 = pulp.LpProblem("gradprogress", pulp.LpMaximize)
    p2 += gradprog
    _add_base_constraints(p2, x, cands, U, L)
    p2 += careerfit >= (1.0 - eps) * vstar - 1e-6, "careerfit_floor"  # 부동소수 여유
    p2.solve(solver)
    status = pulp.LpStatus[p2.status]
    if status != "Optimal":
        return Result([], 0.0, 0.0, 0, status)

    selected = [c for i, c in enumerate(cands) if (x[i].value() or 0) > 0.5]
    return Result(
        selected=selected,
        careerfit=pulp.value(careerfit),
        gradprogress=pulp.value(gradprog),
        total_credit=sum(c.credit for c in selected),
        status=status,
    )
