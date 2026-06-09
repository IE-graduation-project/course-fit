"""직무 입력 추출 — 공고 샘플링·핵심 섹션 추출 (Phase 2)

`data/job_posting_filtered.csv` 에서 직무별 공고를 무작위 샘플링하고,
각 공고에서 자격요건/주요업무/우대사항 섹션만 추출해 노이즈(회사 소개 등)를 줄인다.
LLM 호출 없음.

산출물
- `data/job_postings_sampled.csv`  (job_id, posting_id, extracted_text)

처리
- 직무별 최대 N개(기본 20) 무작위 샘플, random_state 고정 → 재현성.
- 섹션 헤더(한·영 변형 포함)부터 텍스트 끝까지 잘라 회사 소개 앞부분 제거.
  실패 시 raw_text 앞 MAX_FALLBACK 자 사용.

사용법
    python mapping/02_sample_postings.py
    python mapping/02_sample_postings.py --n 30 --seed 42
"""
from __future__ import annotations

import argparse
import csv
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IN_CSV = ROOT / "data" / "job_posting_filtered.csv"
OUT_CSV = ROOT / "data" / "job_postings_sampled.csv"

N_PER_JOB = 20
SEED = 42
MAX_LEN = 2000        # 추출 섹션 최대 길이
MAX_FALLBACK = 1500   # 섹션 추출 실패 시 앞부분 길이

# 핵심 섹션 시작 헤더 (한·영 변형). 회사 소개·복지 등은 보통 이 앞에 위치.
SECTION_HEADERS = [
    r"자격\s*요건", r"자격\s*조건", r"지원\s*자격",
    r"주요\s*업무", r"담당\s*업무", r"업무\s*내용", r"업무\s*소개", r"직무\s*소개",
    r"우대\s*사항", r"필수\s*요건", r"이런\s*분",
    r"qualifications", r"responsibilities", r"requirements",
    r"what\s+you('|’)?ll\s+do", r"what\s+we('|’)?re\s+looking",
]
HEADER_RE = re.compile("|".join(SECTION_HEADERS), re.IGNORECASE)


def extract_core(raw_text: str) -> str:
    """첫 핵심 섹션 헤더부터 끝까지 추출(앞 회사 소개 제거). 실패 시 앞부분."""
    m = HEADER_RE.search(raw_text)
    if m:
        core = raw_text[m.start():]
        return core[:MAX_LEN].strip()
    return raw_text[:MAX_FALLBACK].strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=N_PER_JOB, help="직무별 샘플 수")
    ap.add_argument("--seed", type=int, default=SEED, help="random_state")
    args = ap.parse_args()

    with IN_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # 직무별 그룹
    by_job: dict[str, list[dict]] = {}
    for r in rows:
        by_job.setdefault(r["job_id"], []).append(r)

    rng = random.Random(args.seed)
    out_rows: list[tuple[str, int, str]] = []
    for job_id in sorted(by_job):
        postings = by_job[job_id]
        k = min(args.n, len(postings))
        sample = rng.sample(postings, k)
        for pid, p in enumerate(sample, 1):
            text = extract_core(p["raw_text"])
            out_rows.append((job_id, pid, text))
        print(f"  {job_id}: {len(postings)}개 중 {k}개 샘플")

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["job_id", "posting_id", "extracted_text"])
        writer.writerows(out_rows)

    print(f"완료 → {OUT_CSV} (총 {len(out_rows)}행, seed={args.seed})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
