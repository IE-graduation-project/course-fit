"""추천 근거 생성 — "왜 이 시간표인가".

Recommendation을 받아 사용자에게 보일 구조화된 설명을 만든다(데모 + 서비스 공용).
근거의 원천은 전부 모델 내부값이라 사후 합리화가 아니다:
- 진단: gap_k = ρ_k − σ_k (직무 요구 대비 부족 역량)
- 과목 추천 이유: Score_c = Σ_k gap_k · w_{c,k} 의 축별 분해 (어느 역량 갭을 채우나)
- 졸업 기여: need_g (그 과목 영역의 남은 졸업 부족분)
"""
from __future__ import annotations

from .recommend import Recommendation

# 역량 taxonomy 한글 라벨 (competency.csv 10개 고정)
COMP_KR = {
    "PROG": "프로그래밍", "DATA": "데이터분석", "ML": "머신러닝", "DB": "데이터베이스",
    "VIZ": "데이터시각화", "BIZ": "비즈니스", "FIN": "재무", "MKT": "마케팅",
    "OR": "최적화", "COMM": "커뮤니케이션",
}


def build_explanation(rec: Recommendation, job_name: str, *, gap_threshold: float = 0.03) -> dict:
    """Recommendation → 구조화된 설명 dict (JSON 직렬화 가능, 서비스에서 그대로 사용)."""
    sigma, gap, need = rec.sigma, rec.gap, rec.need
    comps = list(sigma.keys())

    gaps = sorted(((k, gap[k]) for k in comps if gap[k] > gap_threshold), key=lambda x: -x[1])
    strengths = sorted(((k, sigma[k]) for k in comps if gap[k] <= gap_threshold and sigma[k] >= 0.5),
                       key=lambda x: -x[1])

    res = rec.results[0]
    courses = []
    for c in sorted(res.selected,
                    key=lambda c: -sum(gap[k] * c.weights.get(k, 0) for k in comps)):
        contrib = sorted(((gap[k] * c.weights.get(k, 0), k) for k in comps), reverse=True)
        score = sum(v for v, _ in contrib)
        career = [(COMP_KR[k], v, (v / score if score > 0 else 0))
                  for v, k in contrib if v > 0][:2]
        courses.append({
            "course_id": c.course_id, "section": c.section, "name": c.course_name,
            "credit": c.credit, "area": c.area, "slots": c.slots,
            "score": round(score, 4),
            "career_reason": career,                       # [(역량, 기여값, 비중), ...]
            "grad_reason": (c.area, need.get(c.area, 0)),   # (영역, 남은 부족학점)
        })

    return {
        "job": job_name, "dept": rec.dept_id, "admission_year": rec.admission_year,
        "diagnosis": {
            "strengths": [(COMP_KR[k], round(v, 2)) for k, v in strengths],
            "gaps": [(COMP_KR[k], round(v, 2)) for k, v in gaps],
        },
        "timetable": courses,
        "summary": {"careerfit": round(res.careerfit, 4),
                    "gradprogress": res.gradprogress, "total_credit": res.total_credit},
        "n_alternatives": len(rec.results),
    }


def _bar(v: float, scale: float = 25) -> str:
    return "█" * max(1, int(v * scale))


def format_card(expl: dict) -> str:
    """설명 dict → 사람이 읽는 텍스트 카드 (CLI 데모용)."""
    L = []
    L.append("═" * 60)
    L.append(f" {expl['dept']} {expl['admission_year']}학번 · 목표 직무: {expl['job']}")
    L.append("═" * 60)

    L.append("\n[1] 역량 진단 (직무 요구 대비)")
    if expl["diagnosis"]["strengths"]:
        s = ", ".join(f"{n}({v})" for n, v in expl["diagnosis"]["strengths"][:4])
        L.append(f"  ✓ 이미 갖춘 역량: {s}")
    if expl["diagnosis"]["gaps"]:
        L.append("  ▲ 채워야 할 역량(부족):")
        for n, v in expl["diagnosis"]["gaps"]:
            L.append(f"      {n:8} {_bar(v)} {v}")
    else:
        L.append("  (직무 요구를 이미 대부분 충족 — 졸업요건 위주로 추천)")

    L.append(f"\n[2] 추천 시간표 ({expl['summary']['total_credit']}학점) — 과목별 추천 이유")
    for c in expl["timetable"]:
        slots = ",".join(map(str, c["slots"])) or "시간미지정"
        L.append(f"  ▸ {c['name']} ({c['credit']}학점 · {c['area']} · 슬롯 {slots})")
        if c["career_reason"]:
            parts = " / ".join(f"{n} 갭 {int(share*100)}%" for n, _v, share in c["career_reason"])
            L.append(f"      · 직무: {parts} 보완")
        else:
            L.append("      · 직무: 직접 보완 역량 없음 (졸업요건 목적)")
        area, nd = c["grad_reason"]
        if nd > 0:
            L.append(f"      · 졸업: '{area}' 요건 진전 (남은 부족 {nd}학점)")

    L.append("\n[3] 제약 충족: ✓ 시간충돌 없음  ✓ 학점 상·하한  ✓ 기수강 제외  ✓ 선수과목 충족")
    if expl["n_alternatives"] > 1:
        L.append(f"     (동급 대안 시간표 {expl['n_alternatives']}개 중 1순위)")
    return "\n".join(L)
