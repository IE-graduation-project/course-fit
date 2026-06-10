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


def solve_topk(candidates, score_by_course, need, *, U=18, L=12,
               taken_ids, passed_ids, eps=0.0, k=3, msg=False) -> list[Result]:
    """상위 k개 시간표를 반환 (1등이 [0]). k-best via no-good cut.

    1순위(CareerFit)로 V*를 고정한 뒤, 2순위(GradProgress)를 풀고 → 그 해를 배제하는
    no-good cut을 추가 → 재풀이를 k번 반복한다. 재풀이도 전체 ILP라 모든 hard 제약
    (시간충돌·분반·학점)을 다시 만족하므로 나오는 대안은 전부 유효한 시간표다.
    """
    cands = filter_candidates(candidates, taken_ids, passed_ids)
    if not cands:
        return [Result([], 0.0, 0.0, 0, "no_candidates")]

    x = {i: pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(len(cands))}
    careerfit = pulp.lpSum(c.credit * score_by_course[c.course_id] * x[i]
                           for i, c in enumerate(cands))
    solver = pulp.PULP_CBC_CMD(msg=msg)

    # ── 1순위: 직무적합 최대화 → V*
    p1 = pulp.LpProblem("careerfit", pulp.LpMaximize)
    p1 += careerfit
    _add_base_constraints(p1, x, cands, U, L)
    p1.solve(solver)
    if pulp.LpStatus[p1.status] != "Optimal":
        return [Result([], 0.0, 0.0, 0, pulp.LpStatus[p1.status])]
    vstar = pulp.value(careerfit)

    # ── 2순위: 졸업진척(need-cap) 최대화 (직무적합 ≥ (1−ε)V* 유지) + k-best 루프
    # GradProgress = Σ_g min(need_g, 영역 g에 담은 학점). min은 보조변수 f_g로 선형화:
    # f_g ≤ need_g, f_g ≤ 담은학점_g, 목적함수에 +f_g → 솔버가 f_g=min(...)으로 맞춤.
    p2 = pulp.LpProblem("gradprogress", pulp.LpMaximize)
    need_areas = [a for a in {c.area for c in cands} if need.get(a, 0) > 0]
    fvars = []
    for j, a in enumerate(need_areas):
        placed = pulp.lpSum(c.credit * x[i] for i, c in enumerate(cands) if c.area == a)
        f = pulp.LpVariable(f"f_{j}", lowBound=0, upBound=need[a])  # f_g ≤ need_g
        p2 += f <= placed, f"needcap_{j}"                          # f_g ≤ 담은학점_g
        fvars.append(f)
    gradprog = pulp.lpSum(fvars)
    p2 += gradprog
    _add_base_constraints(p2, x, cands, U, L)
    p2 += careerfit >= (1.0 - eps) * vstar - 1e-6, "careerfit_floor"  # 부동소수 여유

    results: list[Result] = []
    for it in range(k):
        p2.solve(solver)
        if pulp.LpStatus[p2.status] != "Optimal":
            break
        sel_idx = [i for i in range(len(cands)) if (x[i].value() or 0) > 0.5]
        selected = [cands[i] for i in sel_idx]
        results.append(Result(
            selected=selected,
            careerfit=pulp.value(careerfit),
            gradprogress=pulp.value(gradprog),
            total_credit=sum(c.credit for c in selected),
            status="Optimal",
        ))
        # no-good cut: 이 분반 조합 그대로는 다시 못 고르게 (최소 1개는 달라야 함)
        p2 += pulp.lpSum(x[i] for i in sel_idx) <= len(sel_idx) - 1, f"nogood_{it}"

    return results or [Result([], 0.0, 0.0, 0, "Infeasible")]


def solve(candidates, score_by_course, need, *, U=18, L=12,
          taken_ids, passed_ids, eps=0.0, msg=False) -> Result:
    """단일 최적 시간표 (solve_topk k=1의 첫 해)."""
    return solve_topk(
        candidates, score_by_course, need, U=U, L=L,
        taken_ids=taken_ids, passed_ids=passed_ids, eps=eps, k=1, msg=msg,
    )[0]
