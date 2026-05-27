"""KoSBERT 임베딩 유사도 (의미 기반) — Phase 3

모델: jhgan/ko-sbert-nli (HuggingFace, 무료), sentence-transformers.
첫 실행 시 모델 자동 다운로드.

  역량 임베딩: e_c = KoSBERT(definition_c + " " + keywords_c)
  문서 임베딩: e_d = KoSBERT(text_d)
  유사도:      sim(c, d) = cos(e_c, e_d)

- 과목: 1과목 = 1문서.
- 직무: 긴 텍스트 → 공고별 임베딩·유사도 후 직무 단위 평균.

산출물
- `mapping/intermediate/embedding_scores_course.csv`
- `mapping/intermediate/embedding_scores_job.csv`
  형식(wide): id, PROG, ..., COMM  (cos 유사도, 0~1 부근)

사용법
    python mapping/04_compute_embeddings.py
    python mapping/04_compute_embeddings.py --job-only
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import maputil as mu  # noqa: E402

MODEL_NAME = "jhgan/ko-sbert-nli"


def competency_texts(kw: dict, comps: list[str]) -> list[str]:
    return [kw[c]["definition"] + " " + " ".join(kw[c]["keywords"]) for c in comps]


def write_wide(path: Path, rows: dict[str, list[float]], comps: list[str], id_col: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([id_col] + comps)
        for rid in rows:
            w.writerow([rid] + [f"{v:.6f}" for v in rows[rid]])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-only", action="store_true")
    ap.add_argument("--course-only", action="store_true")
    args = ap.parse_args()

    from sentence_transformers import SentenceTransformer
    from sentence_transformers.util import cos_sim

    kw = mu.load_keywords()
    comps = mu.comp_order()
    print(f"KoSBERT ({MODEL_NAME}) 로드 중...")
    model = SentenceTransformer(MODEL_NAME)

    comp_emb = model.encode(competency_texts(kw, comps), convert_to_tensor=True,
                            normalize_embeddings=True)

    if not args.course_only:
        docs = mu.load_job_docs()  # (job_id, pid, text)
        texts = [t for _, _, t in docs]
        emb = model.encode(texts, convert_to_tensor=True, normalize_embeddings=True,
                           show_progress_bar=True)
        sims = cos_sim(emb, comp_emb)  # (n_docs, n_comp)
        acc: dict[str, list[float]] = defaultdict(lambda: [0.0] * len(comps))
        cnt: dict[str, int] = defaultdict(int)
        for i, (job_id, _pid, _t) in enumerate(docs):
            for j in range(len(comps)):
                acc[job_id][j] += float(sims[i][j])
            cnt[job_id] += 1
        rows = {j: [acc[j][k] / cnt[j] for k in range(len(comps))] for j in acc}
        out = mu.INTERMEDIATE / "embedding_scores_job.csv"
        write_wide(out, rows, comps, "job_id")
        print(f"  job: {len(rows)}개 (공고 {len(docs)}건 평균) → {out}")

    if not args.job_only:
        if not mu.COURSE_DESC_CSV.exists():
            print(f"  course 건너뜀: {mu.COURSE_DESC_CSV} 없음 (01 미완료)")
            return 0
        docs = mu.load_course_docs()  # (course_id, text)
        texts = [t for _, t in docs]
        emb = model.encode(texts, convert_to_tensor=True, normalize_embeddings=True,
                           show_progress_bar=True)
        sims = cos_sim(emb, comp_emb)
        rows = {cid: [float(sims[i][j]) for j in range(len(comps))]
                for i, (cid, _t) in enumerate(docs)}
        out = mu.INTERMEDIATE / "embedding_scores_course.csv"
        write_wide(out, rows, comps, "course_id")
        print(f"  course: {len(rows)}개 → {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
