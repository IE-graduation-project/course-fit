"""모든 fetcher 호출 → data/job_posting.csv 생성.

사용법:
    python -m crawlers.job_postings.run_all
    python -m crawlers.job_postings.run_all --only greenhouse,naver
    python -m crawlers.job_postings.run_all --out data/job_posting.csv
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_CSV = REPO_ROOT / "data" / "job_posting.csv"

# 등록된 fetcher 모듈 (모두 crawlers.job_postings.{name})
FETCHERS = [
    # 라운드 1: 표준 ATS / 자체 JSON / sitemap
    "greenhouse",
    "naver",
    "kakao",
    "greetinghr",   # 라운드 5에서 11사로 확장됨
    "toss",
    "jumpit",
    "korean_tech",  # 무신사·두나무 best-effort
    # 라운드 5: ATS 어댑터 + 자체 SSR 추가
    "ashby",        # 42dot, furiosa-ai, twelve-labs
    "channelio",    # 채널톡
    "ncsoft",       # NCSOFT 자체 Spring SSR
    "lunit",        # Lunit Greenhouse 신도메인
]


def run_one(name: str) -> list[dict]:
    mod_path = f"crawlers.job_postings.{name}"
    try:
        mod = importlib.import_module(mod_path)
    except Exception as exc:
        print(f"[SKIP] {name}: import 실패 — {exc}", file=sys.stderr)
        return []
    if not hasattr(mod, "fetch"):
        print(f"[SKIP] {name}: fetch() 함수 없음", file=sys.stderr)
        return []
    try:
        records = list(mod.fetch())
    except Exception as exc:
        print(
            f"[FAIL] {name}: fetch() 예외 {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return []
    print(f"[OK]   {name}: {len(records)} records", file=sys.stderr)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(
        description="채용공고 크롤러 일괄 실행",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--only", help="콤마구분 fetcher 이름 (예: greenhouse,naver)")
    parser.add_argument("--out", type=Path, default=OUTPUT_CSV)
    args = parser.parse_args()

    targets = (
        [t.strip() for t in args.only.split(",") if t.strip()]
        if args.only
        else FETCHERS
    )

    all_records: list[dict] = []
    for name in targets:
        all_records.extend(run_one(name))

    if not all_records:
        print("ERROR: 수집된 레코드 없음", file=sys.stderr)
        return 1

    df = pd.DataFrame(
        all_records,
        columns=["job_id", "source", "posting_url", "raw_text", "crawled_at"],
    )
    before = len(df)
    df = df.drop_duplicates(subset=["posting_url"], keep="first")
    print(f"[DEDUPE] {before} → {len(df)}", file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False, encoding="utf-8")
    print(f"[WROTE] {args.out} ({len(df)} rows)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
