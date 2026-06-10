"""recommender 실험용 CLI 래퍼 — 추천 로직은 recommend.recommend()에 있다.

    python -m recommender --student <input_hash> --job DA --max-credits 18

CLI는 실험·데모용 앞문일 뿐이며, 프로토타입(웹/API)은 recommend.recommend()를 직접 호출한다.
"""
from __future__ import annotations

import argparse
import sys

from . import data, params
from .recommend import DEFAULT_PREFERENCE, PREFERENCE_EPS, recommend


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ILP 직무역량 과목 추천 (실험용 CLI)")
    ap.add_argument("--student", required=True, help="학생 input_hash")
    ap.add_argument("--job", required=True, help="목표 직무 job_id (예: DA)")
    ap.add_argument("--db", default=str(data.DB_PATH))
    ap.add_argument("--max-credits", type=int, default=18, help="학점 상한 U (기본 18)")
    ap.add_argument("--min-credits", type=int, default=12, help="학점 하한 L (기본 12)")
    ap.add_argument("--alpha", type=float, default=params.ALPHA_DEFAULT, help="σ 포화곡선 α")
    ap.add_argument("--mode", choices=list(PREFERENCE_EPS), default=DEFAULT_PREFERENCE,
                    help="추천 성향: gap(역량충실)/balanced(균형)/graduation(졸업·전공우선)")
    ap.add_argument("--eps", type=float, default=None, help="ε 직접 지정 (지정 시 --mode 무시)")
    args = ap.parse_args(argv)

    eps = args.eps if args.eps is not None else PREFERENCE_EPS[args.mode]
    try:
        rec = recommend(
            args.student, args.job, db_path=args.db,
            U=args.max_credits, L=args.min_credits, alpha=args.alpha, eps=eps,
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    res = rec.result
    mode_label = "직접지정" if args.eps is not None else args.mode
    print(f"[학생] {rec.dept_id} {rec.admission_year}학번   [성향] {mode_label}(ε={eps})   [상태] {res.status}")
    if res.status != "Optimal":
        print("추천 시간표를 찾지 못했습니다 (제약 충돌 또는 후보 없음).")
        return 0

    print(f"[직무적합 V*] {res.careerfit:.4f}   "
          f"[졸업진척] {res.gradprogress:.0f}학점   [총학점] {res.total_credit}")
    print(f"[추천 {len(res.selected)}개 분반]")
    for c in sorted(res.selected, key=lambda c: (c.area, c.course_id)):
        slots = ",".join(map(str, c.slots)) or "시간미지정"
        print(f"  {c.course_id}-{c.section}  {c.course_name}  "
              f"({c.credit}학점 · {c.area} · 슬롯 {slots})")
    return 0
