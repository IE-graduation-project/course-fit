"""ILP 사전계산 파라미터 — grade_factor, σ, gap, Score, need.

솔버·DB에 독립이라 단독 단위테스트가 가능하다. 설계: docs/ILP_추천시스템_설계.md 4절.
"""
from __future__ import annotations

import math

ALPHA_DEFAULT = 1.5
NEUTRAL_UNKNOWN = 0.67   # 미상(파싱실패, passed)의 grade_factor — P/N과 분리 (설계 2.3)

# 과목 하나가 σ·Score 에 기여하는 역량 수 (#31, 설계 2.1). 매핑 벡터의 4위 아래는 KoSBERT
# 유사도가 모든 역량에 고르게 까는 바닥(역량매핑_시행착오 2절)이라, 과목을 쌓을수록 그 바닥이
# 전 역량 σ 를 같이 밀어 올려 고학년의 직무 간 적합도 차이가 무너졌다.
COURSE_TOP_K = 3


def top_k_weights(weights: dict[str, float], k: int = COURSE_TOP_K) -> dict[str, float]:
    """가중치가 큰 역량 k개만 남긴다. 0 은 버리고, 동점은 comp_id 순이라 결과가 고정된다."""
    ranked = sorted(((w, cid) for cid, w in weights.items() if w > 0), key=lambda t: (-t[0], t[1]))
    return {cid: w for w, cid in ranked[:k]}


def grade_factor(grade: float | None, is_pn: int) -> float:
    """성적 → [0,1] 계수. grade/4.5 (학칙 평점 정규화, 설계 2.3).

    - is_pn=1 → 1.0 (P/N은 A+ 취급, 결정사항)
    - grade None 또는 0 & is_pn=0 → 0.67 (미상). F는 passed=0이라 σ 입력에 없으므로,
      이수 과목의 grade None/0은 파싱실패(미상)뿐. (student_course는 P/N grade를 NULL로 저장)
    - 그 외 → grade/4.5
    """
    if is_pn:
        return 1.0
    if grade is None or grade == 0.0:
        return NEUTRAL_UNKNOWN
    return grade / 4.5


def sigma_contributions(
    passed: dict[str, tuple[float, int]],
    weights: dict[str, dict[str, float]],
    comp_ids: list[str],
) -> dict[str, list[tuple[str, float]]]:
    """σ_k 의 지수 안 합을 과목별로 쪼갠 것 — 역량마다 [(course_id, grade_factor(c)·w_{c,k})].

    compute_sigma 가 이 목록을 그대로 더하므로 화면의 「이 역량은 어느 과목으로 쌓였나」가
    σ 와 어긋날 수 없다. 순서는 passed 순서(합산 순서를 바꾸지 않으려고 정렬하지 않는다).
    """
    contrib: dict[str, list[tuple[str, float]]] = {k: [] for k in comp_ids}
    for cid, (grade, is_pn) in passed.items():
        gf = grade_factor(grade, is_pn)
        for k, w in weights.get(cid, {}).items():
            if k in contrib:
                contrib[k].append((cid, gf * w))
    return contrib


def compute_sigma(
    passed: dict[str, tuple[float, int]],
    weights: dict[str, dict[str, float]],
    comp_ids: list[str],
    alpha: float = ALPHA_DEFAULT,
) -> dict[str, float]:
    """σ_k = 1 − exp(−α · Σ_{기수강 c} grade_factor(c)·w_{c,k}).

    매핑(weights)이 없는 기수강 과목은 0 기여(설계 8절 한계).
    """
    contrib = sigma_contributions(passed, weights, comp_ids)
    return {k: 1.0 - math.exp(-alpha * sum(v for _, v in contrib[k])) for k in comp_ids}


def compute_gap(sigma: dict[str, float], rho: dict[str, float], comp_ids: list[str]) -> dict[str, float]:
    """gap_k = max(0, ρ_k − σ_k)."""
    return {k: max(0.0, rho.get(k, 0.0) - sigma[k]) for k in comp_ids}


def score_of(weights: dict[str, float], gap: dict[str, float], comp_ids: list[str]) -> float:
    """Score_c = Σ_k gap_k · w_{c,k} (과목 1개의 직무적합도)."""
    return sum(gap[k] * weights.get(k, 0.0) for k in comp_ids)


def compute_need(earned_by_area: dict[str, int], min_credits: dict[str, int]) -> dict[str, int]:
    """need_g = max(0, min_credits_g − 기이수학점_g)."""
    return {area: max(0, mc - earned_by_area.get(area, 0)) for area, mc in min_credits.items()}
