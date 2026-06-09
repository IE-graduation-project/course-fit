"""결합 + 정규화 → 최종 long CSV — Phase 3 / 6 / 7

TF-IDF·KoSBERT 점수를 min-max 로 스케일 통일 후 가중합하고,
과목(합=1)·직무(직무별 0~1)로 정규화해 DB 적재용 long 형식으로 저장한다
(docs/과목과직무_역량_매핑.md 5.3·6·7 절).

  결합:   combined(c,d) = α · tfidf_norm + (1−α) · sim_norm     (α 기본 0.5)
  과목:   weight(c,d)        = combined / Σ_c' combined          (합 = 1)
  직무:   required_level(c,j) = (combined − min_c') / (max_c' − min_c')  (직무별 0~1)

산출물
- `data/course_competency.csv`  (course_id, comp_id, weight)
- `data/job_competency.csv`     (job_id, comp_id, required_level)

사용법
    python mapping/05_combine_normalize.py            # 둘 다
    python mapping/05_combine_normalize.py --job-only
    python mapping/05_combine_normalize.py --alpha 0.4
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import maputil as mu  # noqa: E402

ALPHA = 0.7  # TF-IDF 가중치. 낮출수록 의미(KoSBERT)에 더 의존. 0.5→0.7: 임베딩 평탄화 억제.
EPS = 1e-12


def read_wide(path: Path, comps: list[str]) -> tuple[list[str], dict[str, list[float]]]:
    with path.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        rows = {}
        ids = []
        for row in r:
            rid = row[r.fieldnames[0]]
            ids.append(rid)
            rows[rid] = [float(row[c]) for c in comps]
    return ids, rows


def row_minmax(rows: dict[str, list[float]]) -> dict[str, list[float]]:
    """행(문서) 단위 min-max → 각 문서를 0~1로. 분모 0 방어.

    전역 min-max 는 극단 문서가 스케일을 독점해 나머지 문서의 역량 간
    차이를 눌러버린다(특히 코사인 유사도처럼 분산이 작은 KoSBERT 점수).
    행 단위 정규화는 각 문서 내부의 '어느 역량 선호' 구조를 보존한다.
    """
    out = {}
    for k, v in rows.items():
        lo, hi = min(v), max(v)
        span = hi - lo
        out[k] = [0.0 for _ in v] if span < EPS else [(x - lo) / span for x in v]
    return out


def combine(tfidf: dict, emb: dict, alpha: float) -> dict[str, list[float]]:
    tn = row_minmax(tfidf)
    en = row_minmax(emb)
    out = {}
    for rid in tfidf:
        out[rid] = [alpha * tn[rid][i] + (1 - alpha) * en[rid][i] for i in range(len(tfidf[rid]))]
    return out


def normalize_course(combined: dict[str, list[float]], comps: list[str]) -> list[tuple]:
    """역량 weight 합 = 1. 합이 0이면 균등 분배."""
    out = []
    for cid, vec in combined.items():
        s = sum(vec)
        w = [1.0 / len(comps)] * len(comps) if s < EPS else [v / s for v in vec]
        for i, c in enumerate(comps):
            out.append((cid, c, round(w[i], 6)))
    return out


def normalize_job(combined: dict[str, list[float]], comps: list[str]) -> list[tuple]:
    """직무별 min-max → 0~1. 분모 0이면 모두 0."""
    out = []
    for jid, vec in combined.items():
        lo, hi = min(vec), max(vec)
        span = hi - lo
        norm = [0.0] * len(vec) if span < EPS else [(v - lo) / span for v in vec]
        for i, c in enumerate(comps):
            out.append((jid, c, round(norm[i], 6)))
    return out


def write_long(path: Path, rows: list[tuple], header: list[str]):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-only", action="store_true")
    ap.add_argument("--course-only", action="store_true")
    ap.add_argument("--alpha", type=float, default=ALPHA)
    args = ap.parse_args()

    comps = mu.comp_order()
    inter = mu.INTERMEDIATE
    print(f"결합·정규화 (α={args.alpha}, 역량 {len(comps)}개)")

    if not args.course_only:
        _, tfidf = read_wide(inter / "tfidf_scores_job.csv", comps)
        _, emb = read_wide(inter / "embedding_scores_job.csv", comps)
        combined = combine(tfidf, emb, args.alpha)
        rows = normalize_job(combined, comps)
        out = mu.DATA / "job_competency.csv"
        write_long(out, rows, ["job_id", "comp_id", "required_level"])
        print(f"  job: {len(rows)}행 → {out}")

    if not args.job_only:
        cpath = inter / "tfidf_scores_course.csv"
        if not cpath.exists():
            print("  course 건너뜀: tfidf_scores_course.csv 없음 (03 course 미실행)")
            return 0
        _, tfidf = read_wide(cpath, comps)
        _, emb = read_wide(inter / "embedding_scores_course.csv", comps)
        combined = combine(tfidf, emb, args.alpha)
        rows = normalize_course(combined, comps)
        out = mu.DATA / "course_competency.csv"
        write_long(out, rows, ["course_id", "comp_id", "weight"])
        print(f"  course: {len(rows)}행 (과목 {len(rows)//len(comps)}개) → {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
