"""PuLP 2단계 우선순위형(lexicographic) ILP. 설계 6절.

[1순위] max CareerFit → V*
[2순위] max GradProgress  s.t. CareerFit ≥ (1−ε)·V*
[3순위] 2순위가 같으면 CareerFit 이 높은 쪽 — 목적에 δ·CareerFit 을 섞는다 (#45)
[4순위] 그래도 같으면 분반별 고정 가중의 합이 가장 작은 쪽 — 실행 환경과 무관하게 같은 안 (#73)
hard 제약 A1(시간충돌)·A2(분반택1)·A3/A3'(학점상한/하한). B1·B2는 후보 사전필터로 처리.
"""
from __future__ import annotations

import hashlib
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


def _objective_value(expr) -> float:
    """PuLP 목적값을 float 로 읽는다. 빈 식이면 None 이 오는데 그건 0.0 이라는 뜻이다.

    PuLP 는 계수 0 인 항을 식에서 버린다. 그래서 모든 계수가 0 이거나(전 후보 Score 0)
    항이 하나도 안 만들어지면(need 가 비어 f_g 가 없음) 식 자체가 비고 `value()` 가
    None 을 낸다. 풀이가 실패한 것이 아니라 더할 것이 없었던 것이라 LpStatus 는
    'Optimal' 이고, 그래서 상태 가드로는 걸리지 않는다.

    None 을 그대로 흘리면 두 가지로 터진다: 산술에 쓰이면 TypeError 이고,
    Result 에 담기면 float 로 선언된 필드에 None 이 들어가 API·프론트까지 샌다.
    접는 자리를 한 곳으로 모아, 호출부마다 `or 0.0` 을 반복하지 않는다.
    """
    return float(pulp.value(expr) or 0.0)


def _tie_weight(c) -> float:
    """분반마다 정해진 [1, 2) 의 가중. 학수번호와 분반만으로 정해져 실행 환경·후보 순서와 무관하다."""
    h = hashlib.sha256(f"{c.course_id}-{c.section}".encode()).digest()
    return 1.0 + int.from_bytes(h[:4], "big") / 2**32


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
               taken_ids, passed_ids, eps=0.0, k=3, msg=False,
               time_limit: float | None = None,
               area_weight: dict[str, int] | None = None) -> list[Result]:
    """상위 k개 시간표를 반환 (1등이 [0]). k-best via no-good cut.

    1순위(CareerFit)로 V*를 고정한 뒤, 2순위(GradProgress)를 풀고 → 그 해를 배제하는
    no-good cut을 추가 → 재풀이를 k번 반복한다. 재풀이도 전체 ILP라 모든 hard 제약
    (시간충돌·분반·학점)을 다시 만족하므로 나오는 대안은 전부 유효한 시간표다.

    area_weight 는 2순위에서 영역별 졸업 반영 학점에 곱할 정수 가중이다(없는 영역 1). None 이면
    모든 영역을 같은 무게로 센다. 가중은 목적식에만 걸고, Result.gradprogress 는 가중 없이
    학점 그대로 센다 — 화면의 「졸업 반영」은 성향과 무관하게 같은 단위여야 한다(#53).

    time_limit(초)은 CBC 1회 풀이의 상한이다. None이면 무제한(CLI·테스트 기본). 웹 서버는
    반드시 지정해야 한다 — 탐색이 폭발하는 입력이 오면 요청이 무한정 물린다. 상한에 걸리면
    CBC가 그때까지의 최선해를 반환하므로 status가 Optimal이 아닐 수 있다.
    """
    cands = filter_candidates(candidates, taken_ids, passed_ids)
    if not cands:
        return [Result([], 0.0, 0.0, 0, "no_candidates")]

    x = {i: pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(len(cands))}
    careerfit = pulp.lpSum(c.credit * score_by_course[c.course_id] * x[i]
                           for i, c in enumerate(cands))
    # 전 후보 Score 가 0 이면 PuLP 가 계수 0 인 항을 버려 이 식이 빈다. 그 사실은
    # **p1 을 풀기 전에** 기록해야 한다 — solve() 가 변수 없는 목적식에 `__dummy` 를
    # 끼워 넣으면서 이 식 객체를 제자리에서 바꾸기 때문에, 나중에 len() 을 재면 1 이 나온다.
    careerfit_is_empty = len(careerfit) == 0
    solver = pulp.PULP_CBC_CMD(msg=msg, timeLimit=time_limit)

    # ── 1순위: 직무적합 최대화 → V*
    p1 = pulp.LpProblem("careerfit", pulp.LpMaximize)
    p1 += careerfit
    _add_base_constraints(p1, x, cands, U, L)
    p1.solve(solver)
    if pulp.LpStatus[p1.status] != "Optimal":
        return [Result([], 0.0, 0.0, 0, pulp.LpStatus[p1.status])]
    vstar = _objective_value(careerfit)

    # ── 2순위: 졸업진척(need-cap) 최대화 (직무적합 ≥ (1−ε)V* 유지) + k-best 루프
    # GradProgress = Σ_g min(need_g, 영역 g에 담은 학점). min은 보조변수 f_g로 선형화:
    # f_g ≤ need_g, f_g ≤ 담은학점_g, 목적함수에 +f_g → 솔버가 f_g=min(...)으로 맞춤.
    p2 = pulp.LpProblem("gradprogress", pulp.LpMaximize)
    # sorted 필수 — set 순회 순서는 PYTHONHASHSEED에 따라 프로세스마다 달라진다.
    # f_g 변수 순서가 흔들리면 동점 최적해 중 CBC가 고르는 해가 바뀌어, 같은 입력에
    # 매 실행 다른 시간표가 나온다(2026-09-13 확인). 정렬로 변수 순서를 고정한다.
    need_areas = sorted(a for a in {c.area for c in cands} if need.get(a, 0) > 0)
    fvars = []
    for j, a in enumerate(need_areas):
        placed = pulp.lpSum(c.credit * x[i] for i, c in enumerate(cands) if c.area == a)
        f = pulp.LpVariable(f"f_{j}", lowBound=0, upBound=need[a])  # f_g ≤ need_g
        p2 += f <= placed, f"needcap_{j}"                          # f_g ≤ 담은학점_g
        fvars.append(f)
    gradprog = pulp.lpSum(fvars)
    # 졸업 우선은 같은 학점이라도 필수·전공 영역을 먼저 채운다(#53). 가중이 정수라 서로 다른
    # 해의 가중 합 차이도 0 이 아니면 최소 1 — 아래 δ 논증이 그대로 선다.
    objective = (pulp.lpSum(area_weight.get(a, 1) * f for a, f in zip(need_areas, fvars))
                 if area_weight else gradprog)
    # 3순위 — 졸업 반영이 같은 해가 여럿이면 CBC 탐색 순서가 해를 골라, 같은 입력이 로컬과
    # 배포 서버에서 다른 시간표를 냈고 배포 쪽 직무 적합이 더 낮았다(#45). δ·CareerFit 을
    # 목적에 섞어 동점 안에서 직무 적합이 높은 해를 고른다. 졸업 반영은 학점 단위라 해 사이
    # 차이가 0 이 아니면 최소 1 이고, CareerFit ≤ U·max Score 이므로 δ = 0.5/(U·max Score)
    # 면 δ·CareerFit 의 폭이 0.5 를 넘지 않아 졸업 반영을 한 학점도 내주지 않는다.
    max_score = max((score_by_course[c.course_id] for c in cands), default=0.0)
    if not (careerfit_is_empty or max_score <= 0):
        objective = objective + (0.5 / (U * max_score)) * careerfit
    total = pulp.lpSum(c.credit * x[i] for i, c in enumerate(cands))
    tie = pulp.lpSum(_tie_weight(c) * x[i] for i, c in enumerate(cands))
    # 목적이 비면(전 후보 Score 0, need 없음) 어떤 해든 최적이라 4순위가 곧 목적이다. 빈 목적을
    # 그대로 두면 solve() 가 끼운 `__dummy` 가 문제에 남아 다음 풀이의 LP 파일을 깨뜨린다.
    objective_is_empty = len(objective) == 0
    p2 += -tie if objective_is_empty else objective
    _add_base_constraints(p2, x, cands, U, L)
    # careerfit 이 빈 식이면(전 후보 Score 0) 이 제약은 0 >= -1e-6 이라 항상 참이다.
    # 그런데 PuLP 는 변수가 없는 제약·목적에 `__dummy` 를 끼워 넣는다. 목적식(gradprog)도
    # 비어 있으면 `__dummy` 가 두 번 들어가 LP 파일이 깨지고(Repeated variable names)
    # CBC 가 통째로 실패한다. 뜻이 없는 제약은 아예 걸지 않는다.
    if not careerfit_is_empty:
        p2 += careerfit >= (1.0 - eps) * vstar - 1e-6, "careerfit_floor"  # 부동소수 여유

    results: list[Result] = []
    for it in range(k):
        p2.solve(solver)
        if pulp.LpStatus[p2.status] != "Optimal":
            break
        sel_idx = [i for i in range(len(cands)) if (x[i].value() or 0) > 0.5]
        # 4순위 — 목적값이 같은 해가 여럿이면 CBC 가 어느 것을 내는지는 실행 환경마다 달라,
        # 같은 입력이 로컬과 배포 서버에서 다른 시간표를 냈다(#73, 36가지 중 33가지). 목적값과
        # 총 학점을 방금 찾은 값에 묶고 고정 가중 합이 가장 작은 해로 고른다. 점수는 그대로다.
        if not objective_is_empty:
            sel_idx = _break_tie(p2, solver, x, sel_idx, objective, total, tie,
                                 credit=sum(cands[i].credit for i in sel_idx), it=it)
        selected = [cands[i] for i in sel_idx]
        # 값은 고른 분반에서 바로 센다. 4순위 풀이가 Optimal 이 아니면 변수 값은 그 풀이의
        # 것이라 sel_idx 와 맞지 않고, 4순위에선 f_g 가 목적에 없어 min(need, 담은 학점)까지 안 올라간다.
        results.append(Result(
            selected=selected,
            careerfit=float(sum(c.credit * score_by_course[c.course_id] for c in selected)),
            gradprogress=float(sum(min(need[a], sum(c.credit for c in selected if c.area == a))
                                   for a in need_areas)),
            total_credit=sum(c.credit for c in selected),
            status="Optimal",
        ))
        # no-good cut: 이 분반 조합 그대로는 다시 못 고르게 (최소 1개는 달라야 함)
        p2 += pulp.lpSum(x[i] for i in sel_idx) <= len(sel_idx) - 1, f"nogood_{it}"

    return results or [Result([], 0.0, 0.0, 0, "Infeasible")]


def _break_tie(prob, solver, x, sel_idx, objective, total, tie, *, credit, it):
    """목적값·총 학점을 지금 해에 묶고 tie 를 최소화해 고른 해의 인덱스. prob 는 원래대로 돌려 놓는다.

    상한 시간에 걸리는 등 Optimal 이 아니면 2순위가 낸 해(sel_idx)를 그대로 쓴다.
    """
    floor, cap = f"tie_floor_{it}", f"tie_credit_{it}"
    prob += objective >= _objective_value(objective) - 1e-6, floor  # 부동소수 여유
    prob += total == credit, cap
    prob.sense = pulp.LpMinimize
    prob.setObjective(tie)
    prob.solve(solver)
    if pulp.LpStatus[prob.status] == "Optimal":
        sel_idx = [i for i in range(len(x)) if (x[i].value() or 0) > 0.5]
    for name in (floor, cap):
        del prob.constraints[name]
    prob.sense = pulp.LpMaximize
    prob.setObjective(objective)
    return sel_idx


def solve(candidates, score_by_course, need, *, U=18, L=12,
          taken_ids, passed_ids, eps=0.0, msg=False, time_limit: float | None = None) -> Result:
    """단일 최적 시간표 (solve_topk k=1의 첫 해)."""
    return solve_topk(
        candidates, score_by_course, need, U=U, L=L,
        taken_ids=taken_ids, passed_ids=passed_ids, eps=eps, k=1, msg=msg,
        time_limit=time_limit,
    )[0]
