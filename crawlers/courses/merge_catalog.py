#!/usr/bin/env python3
"""크롤 원천(catalog_crawl_raw.csv) -> course_crawled.csv 보강 (이슈 #18).

이수구분(category)과 source scope를 area enum/dept_id로 매핑해, 기존 course.csv에
없는 과목만 골라 data/course_crawled.csv로 출력한다. 커레이트된 course.csv는
건드리지 않고, ingest가 보강분을 함께 적재한다.

매핑 주의:
- 시간표 이수구분은 '개설 학부 관점'이다. B010(경영)의 전선 = 경영 학생 기준 전공선택.
  타 학부 학생에겐 일반선택이므로, 전공 area는 소유 학부(BIZ/IDE)인 과목에만 부여하고
  소유 학부가 불명(COMMON)이면 일반선택으로 환산한다. 학생 관점 환산은 추천(need_g)이 담당.
- MSC는 공학계열 교양 scope(ENG_GE14/15/16)로 판별, dept_id=IDE로 둔다(산데공 요건).
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

COURSE_FIELDS = [
    "course_id", "course_name", "credit", "dept_id", "area",
    "allowed_years", "prerequisites", "time_slots_raw", "time_slots_int",
    "semester", "is_pn", "is_major_required", "is_certified_sw",
    "msc_subarea", "liberal_area",
]

MSC_SCOPE_SUBAREA = {"ENG_GE14": "math", "ENG_GE15": "science", "ENG_GE16": "cs"}
MAJOR_AREAS = {"전공필수", "전공선택", "전공기초"}


def resolve_dept(scopes: set[str], offering: str) -> str:
    if "B010" in scopes or "경영" in offering:
        return "BIZ"
    if "산업" in offering and ("데이터" in offering or "데이타" in offering):
        return "IDE"
    if "산업공학" in offering:
        return "IDE"
    return "COMMON"


def resolve_area(category: str, scopes: set[str], dept: str) -> tuple[str | None, str | None]:
    """(area, msc_subarea) 반환. 매핑 불가 시 (None, None)."""
    for scope, sub in MSC_SCOPE_SUBAREA.items():
        if scope in scopes:
            return "MSC", sub

    c = category or ""
    if c.startswith("전필"):
        area = "전공필수"
    elif c.startswith("전선"):
        area = "전공선택"
    elif c.startswith("전기"):
        area = "전공기초"
    elif c.startswith("교필"):
        area = "교양필수"
    elif c.startswith("교선") or c.startswith("일교") or c.startswith("핵교"):
        area = "공통교양"
    elif c.startswith("일선"):
        area = "일반선택"
    elif c.startswith("교직"):
        area = "일반선택"
    else:
        return None, None

    # 전공 area인데 소유 학부가 우리 코호트가 아니면(COMMON) 일반선택으로 환산
    if area in MAJOR_AREAS and dept == "COMMON":
        area = "일반선택"
    return area, None


def load_existing_ids(course_csv: Path) -> set[str]:
    if not course_csv.exists():
        return set()
    with course_csv.open(encoding="utf-8") as f:
        return {row["course_id"] for row in csv.DictReader(f)}


def build(raw_csv: Path, course_csv: Path) -> tuple[list[dict], dict]:
    existing = load_existing_ids(course_csv)
    out: list[dict] = []
    stats = {"added": 0, "skip_existing": 0, "skip_no_area": 0, "skip_no_credit": 0, "by_area": {}}

    with raw_csv.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            cid = r["course_id"]
            if cid in existing:
                stats["skip_existing"] += 1
                continue
            credit = r["credit"].strip()
            if not credit.isdigit():
                stats["skip_no_credit"] += 1
                continue
            scopes = {s for s in r.get("scopes_seen", "").split(";") if s}
            dept = resolve_dept(scopes, r.get("offering_dept", ""))
            area, msc = resolve_area(r.get("category", ""), scopes, dept)
            if area is None:
                stats["skip_no_area"] += 1
                continue
            if area == "MSC":
                dept = "IDE"
            out.append({
                "course_id": cid,
                "course_name": r["course_name"],
                "credit": credit,
                "dept_id": dept,
                "area": area,
                "allowed_years": "",
                "prerequisites": "",
                "time_slots_raw": "",
                "time_slots_int": "",
                "semester": "",
                "is_pn": "0",
                "is_major_required": "0",
                "is_certified_sw": "0",
                "msc_subarea": msc or "",
                "liberal_area": "",
            })
            stats["added"] += 1
            stats["by_area"][area] = stats["by_area"].get(area, 0) + 1
    return out, stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", type=Path, default=Path("data/catalog_crawl_raw.csv"))
    ap.add_argument("--course", type=Path, default=Path("data/course.csv"))
    ap.add_argument("--output", type=Path, default=Path("data/course_crawled.csv"))
    args = ap.parse_args(argv)

    rows, stats = build(args.raw, args.course)
    rows.sort(key=lambda r: r["course_id"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COURSE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {stats['added']} courses to {args.output}")
    print(f"  skip(existing)={stats['skip_existing']} skip(no_area)={stats['skip_no_area']} skip(no_credit)={stats['skip_no_credit']}")
    print(f"  area 분포: {stats['by_area']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
