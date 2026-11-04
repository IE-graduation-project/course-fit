"""job_posting.csv → web/public/job_postings.json (직무별 대표 공고 몇 건).

결과 화면에서 "이 직무 실제 채용공고" 링크로 쓴다(C12). 역량 요구의 출처를 보여줘
추천 근거의 설득력을 높인다. raw_text 는 넣지 않는다 — 제목(첫 의미 있는 줄)과 URL 만.
"""
from __future__ import annotations
import csv, json, re, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
# 분류(job_id)가 든 커밋본을 읽는다. 작업트리의 재크롤본은 분류 전 원본이라 job_id 가 비어 있다.
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "job_posting.csv"
OUT = ROOT / "web" / "public" / "job_postings.json"
PER_JOB = 4

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

def title_of(raw: str) -> str:
    for line in (raw or "").splitlines():
        t = line.strip()
        # 위치/날짜/머리말 줄은 건너뛴다
        if len(t) >= 4 and not re.match(r"^(위치|Location|근무|Seoul|대한민국)\b", t):
            return re.sub(r"\s+", " ", t)[:80]
    return ""

def company_of(source: str) -> str:
    # "Greenhouse:coupang" → "coupang"
    return (source or "").split(":")[-1].strip()

def main() -> int:
    # 2패스: 회사 다양성을 위해 먼저 회사당 1건씩 채우고(1패스), 모자라면 2건까지 채운다(2패스).
    cand: dict[str, list[dict]] = defaultdict(list)
    seen: dict[str, set] = defaultdict(set)
    with SRC.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            jid = (row.get("job_id") or "").strip()
            url = (row.get("posting_url") or "").strip()
            if not jid or not url.startswith("http"):
                continue
            title = title_of(row.get("raw_text", ""))
            if not title:
                continue
            key = title.lower()
            if key in seen[jid]:
                continue
            seen[jid].add(key)
            cand[jid].append({"title": title, "url": url, "company": company_of(row.get("source", ""))})

    by_job: dict[str, list[dict]] = {}
    for jid, items in cand.items():
        picked: list[dict] = []
        for cap in (1, 2):  # 회사당 1건 → 부족하면 2건
            for it in items:
                if len(picked) >= PER_JOB:
                    break
                if sum(1 for p in picked if p["company"] == it["company"]) >= cap:
                    continue
                if it in picked:
                    continue
                picked.append(it)
        by_job[jid] = picked[:PER_JOB]
    OUT.write_text(json.dumps(by_job, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"wrote {OUT} jobs={list(by_job)} counts={ {k: len(v) for k, v in by_job.items()} }")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
