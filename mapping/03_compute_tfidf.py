"""TF-IDF 점수 (키워드 빈도 기반) — Phase 3

키워드 직접 매칭 + IDF 가중 방식. 복합 키워드("데이터 분석")를 안전히 다루기 위해
TfidfVectorizer 기본 토큰화 대신 사전 키워드를 문서에서 직접 카운트한다
(docs/과목과직무_역량_매핑.md 5.1·10 절).

  TF(k, d)  : 문서 d 내 키워드 k 출현 횟수
  IDF(k)    : log((1+N)/(1+DF(k))) + 1   (sklearn smooth_idf 방식, 항상 양수)
  tfidf_score(c, d) = Σ_{k ∈ keywords(c)} TF(k,d) · IDF(k)

- 과목: 1과목 = 1문서.
- 직무: 공고별로 점수 계산 후 직무 단위 평균.

산출물
- `mapping/intermediate/tfidf_scores_course.csv`
- `mapping/intermediate/tfidf_scores_job.csv`
  형식(wide): id, PROG, DATA, ..., COMM  (raw 점수, 미정규화)

사용법
    python mapping/03_compute_tfidf.py            # 둘 다 (course 입력 있을 때)
    python mapping/03_compute_tfidf.py --job-only
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import maputil as mu  # noqa: E402


def all_keywords(kw: dict) -> list[str]:
    seen, out = set(), []
    for v in kw.values():
        for k in v["keywords"]:
            kl = k.lower()
            if kl not in seen:
                seen.add(kl)
                out.append(k)
    return out


def _is_ascii(k: str) -> bool:
    return all(ord(c) < 128 for c in k)


@lru_cache(maxsize=2048)
def _pattern(keyword: str) -> re.Pattern:
    """ASCII 키워드는 단어 경계 매칭(앞뒤가 영문·숫자가 아닐 때만).
    'or'가 work/for 안에, 'ai'가 training 안에 거짓 매칭되는 것을 방지."""
    return re.compile(r"(?<![a-z0-9])" + re.escape(keyword.lower()) + r"(?![a-z0-9])")


def match_count(text_lower: str, keyword: str) -> int:
    """키워드 출현 횟수. ASCII는 단어 경계, 한국어는 부분문자열."""
    if _is_ascii(keyword):
        return len(_pattern(keyword).findall(text_lower))
    return text_lower.count(keyword.lower())


def compute_idf(docs: list[str], keywords: list[str]) -> dict[str, float]:
    """smooth IDF. 매칭 규칙은 match_count 와 동일."""
    n = len(docs)
    docs_l = [d.lower() for d in docs]
    idf = {}
    for k in keywords:
        df = sum(1 for d in docs_l if match_count(d, k) > 0)
        idf[k] = math.log((1 + n) / (1 + df)) + 1.0
    return idf


def score_doc(text: str, kw: dict, idf: dict[str, float], comps: list[str]) -> dict[str, float]:
    """문서 1개의 역량별 TF-IDF 합."""
    tl = text.lower()
    out = {c: 0.0 for c in comps}
    for c in comps:
        for k in kw[c]["keywords"]:
            cnt = match_count(tl, k)
            if cnt:
                out[c] += cnt * idf[k]
    return out


def write_wide(path: Path, rows: dict[str, dict[str, float]], comps: list[str], id_col: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([id_col] + comps)
        for rid in rows:
            w.writerow([rid] + [f"{rows[rid][c]:.6f}" for c in comps])


def run_course(kw: dict, comps: list[str]):
    docs = mu.load_course_docs()  # (course_id, text)
    texts = [t for _, t in docs]
    idf = compute_idf(texts, all_keywords(kw))
    rows = {cid: score_doc(text, kw, idf, comps) for cid, text in docs}
    out = mu.INTERMEDIATE / "tfidf_scores_course.csv"
    write_wide(out, rows, comps, "course_id")
    print(f"  course: {len(rows)}개 → {out}")


def run_job(kw: dict, comps: list[str]):
    docs = mu.load_job_docs()  # (job_id, posting_id, text)
    texts = [t for _, _, t in docs]
    idf = compute_idf(texts, all_keywords(kw))  # 공고 단위 IDF
    # 공고별 점수 후 직무 평균
    acc: dict[str, dict[str, float]] = defaultdict(lambda: {c: 0.0 for c in comps})
    cnt: dict[str, int] = defaultdict(int)
    for job_id, _pid, text in docs:
        s = score_doc(text, kw, idf, comps)
        for c in comps:
            acc[job_id][c] += s[c]
        cnt[job_id] += 1
    rows = {j: {c: acc[j][c] / cnt[j] for c in comps} for j in acc}
    out = mu.INTERMEDIATE / "tfidf_scores_job.csv"
    write_wide(out, rows, comps, "job_id")
    print(f"  job: {len(rows)}개 (공고 {len(docs)}건 평균) → {out}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-only", action="store_true")
    ap.add_argument("--course-only", action="store_true")
    args = ap.parse_args()

    kw = mu.load_keywords()
    comps = mu.comp_order()
    print(f"TF-IDF (역량 {len(comps)}개, 키워드 {len(all_keywords(kw))}개)")

    if not args.course_only:
        run_job(kw, comps)
    if not args.job_only:
        if mu.COURSE_DESC_CSV.exists():
            run_course(kw, comps)
        else:
            print(f"  course 건너뜀: {mu.COURSE_DESC_CSV} 없음 (01 미완료)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
