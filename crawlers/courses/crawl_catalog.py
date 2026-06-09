#!/usr/bin/env python3
"""다년도 + 전체 학과 시간표 크롤로 과목 카탈로그 보강 (이슈 #18).

hongik_timetable.py의 상세조회/파싱 함수를 재사용하되, 학과 스코프를 하드코딩하지
않고 hak03.jsp 선택 학기 페이지의 goDetail01(...) 호출에서 전체 학과/교양 스코프를
자동 추출한다(self-discovering). 비공학(abeek=0)/공학(abeek=1) 교양을 모두 포함한다.

학수번호 단위로 dedup한 원천 CSV(data/catalog_crawl_raw.csv)를 만들고,
category(이수구분)와 source scope를 보존해 merge_catalog.py가 area로 매핑한다.

Usage:
    python crawlers/courses/crawl_catalog.py --from 2020 --to 2026 --output data/catalog_crawl_raw.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path

import requests

from . import hongik_timetable as ht

CSV_FIELDS = [
    "course_id", "course_name", "credit", "offering_dept",
    "category", "categories_seen", "scopes_seen", "latest_term", "terms_seen",
]
REGULAR_SEMESTERS = ["1학기", "2학기"]

# goDetail01('ibhak','campus','gubun','dept','grade')>학과명<
_GODETAIL_RE = re.compile(
    r"goDetail01\('([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)'\)[^>]*>([^<]+)<"
)


def build_terms(year_from: int, year_to: int) -> list[str]:
    return [f"{y}학년도 {s}" for y in range(year_from, year_to + 1) for s in REGULAR_SEMESTERS]


def _new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "course-fit catalog crawler (+https://cn.hongik.ac.kr/app/timetable/)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    s.get(ht.BASE_URL, timeout=30)
    return s


def fetch_term_page(session, term_label, ibhak="2022", abeek="0"):
    """선택 학기 페이지 + hidden (p_yy, p_hakgi). abeek로 비공학/공학 교양 뷰 전환."""
    url = ht.BASE_URL + "hak03.jsp"
    yyhakgi = ht._extract_option_value(session.get(url, timeout=30).text, term_label)
    payload = {
        "yyhakgi": yyhakgi, "ibhak": ibhak, "abeek": abeek, "p_type": "2",
        "p_search_haksu": "", "p_search_prof": "", "p_search_week": "0", "btn_search": "조회",
    }
    sel = session.post(url, data=payload, headers={"Referer": url}, timeout=30)
    sel.encoding = "utf-8"
    ht._raise_if_alert(sel.text, f"term {term_label} abeek={abeek}")
    return sel.text, ht._extract_hidden(sel.text, "p_yy"), ht._extract_hidden(sel.text, "p_hakgi")


def extract_scopes(page: str, abeek: str) -> list[ht.DepartmentRequest]:
    """페이지의 goDetail01 호출에서 전체 학과/교양 스코프 추출."""
    scopes = []
    for ibhak, campus, gubun, dept, grade, name in _GODETAIL_RE.findall(page):
        name = re.sub(r"\s+", " ", name).strip()
        # 교양(gubun=1)은 GE{grade}/ENG_GE{grade}, 전공(gubun=2)은 학과코드를 scope 코드로
        code = dept if gubun == "2" else (("ENG_GE" if abeek == "1" else "GE") + grade)
        scopes.append(
            ht.DepartmentRequest(
                source_dept_code=code, source_dept_name=name,
                p_campus=campus, p_gubun=gubun, p_dept=dept,
                p_ibhak=ibhak, p_type="1", p_grade=grade, p_abeek=abeek,
            )
        )
    return scopes


def _term_scopes(session, term: str) -> list[ht.DepartmentRequest]:
    """한 학기의 전체 스코프: 전공(1회) + 비공학 교양 + 공학 교양(MSC 포함)."""
    page0, p_yy, p_hakgi = fetch_term_page(session, term, abeek="0")
    scopes = extract_scopes(page0, "0")
    # 공학 교양/MSC(gubun=1)만 abeek=1에서 추가 (전공은 abeek 무관이라 중복 크롤 방지)
    try:
        page1, _, _ = fetch_term_page(session, term, abeek="1")
        scopes += [s for s in extract_scopes(page1, "1") if s.p_gubun == "1"]
    except (requests.RequestException, ht.TimetableCrawlerError) as exc:
        print(f"  [skip abeek=1] {term}: {str(exc)[:60]}", file=sys.stderr)
    return scopes, p_yy, p_hakgi


def crawl(year_from: int, year_to: int, delay: float = 0.2) -> dict[str, dict]:
    session = _new_session()
    catalog: dict[str, dict] = {}

    for term in build_terms(year_from, year_to):
        try:
            scopes, p_yy, p_hakgi = _term_scopes(session, term)
        except (requests.RequestException, ht.TimetableCrawlerError) as exc:
            print(f"[SKIP term] {term}: {type(exc).__name__} {str(exc)[:80]}", file=sys.stderr)
            continue

        term_total = 0
        for dept in scopes:
            try:
                detail = ht.fetch_department_detail(session, dept, p_yy=p_yy, p_hakgi=p_hakgi)
                rows = ht.parse_detail_rows(detail, dept)
            except (requests.RequestException, ht.TimetableCrawlerError) as exc:
                print(f"  [skip scope] {term}/{dept.source_dept_code}: {str(exc)[:50]}", file=sys.stderr)
                time.sleep(delay)
                continue

            for r in rows:
                cid = r["course_id"]
                cat = (r.get("category") or "").replace("\n", "/").strip()
                e = catalog.get(cid)
                if e is None:
                    e = {
                        "course_id": cid, "course_name": r["course_name"], "credit": r["credit"],
                        "offering_dept": r["offering_dept"], "category": cat,
                        "categories_seen": set(), "scopes_seen": set(),
                        "latest_term": term, "terms_seen": set(),
                    }
                    catalog[cid] = e
                e["course_name"] = r["course_name"] or e["course_name"]
                e["credit"] = r["credit"] or e["credit"]
                e["offering_dept"] = r["offering_dept"] or e["offering_dept"]
                e["category"] = cat or e["category"]
                e["latest_term"] = term
                if cat:
                    e["categories_seen"].add(cat)
                for sc in r.get("source_dept_code", "").split(";"):
                    if sc:
                        e["scopes_seen"].add(sc)
                e["terms_seen"].add(term)
                term_total += 1
            time.sleep(delay)
        print(f"[term done] {term}: scopes={len(scopes)} rows={term_total} 누적={len(catalog)}", file=sys.stderr)

    return catalog


def write_csv(catalog: dict[str, dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for cid in sorted(catalog):
            e = catalog[cid]
            writer.writerow({
                "course_id": e["course_id"], "course_name": e["course_name"], "credit": e["credit"],
                "offering_dept": e["offering_dept"], "category": e["category"],
                "categories_seen": ";".join(sorted(e["categories_seen"])),
                "scopes_seen": ";".join(sorted(e["scopes_seen"])),
                "latest_term": e["latest_term"], "terms_seen": ";".join(sorted(e["terms_seen"])),
            })


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="year_from", type=int, default=2020)
    ap.add_argument("--to", dest="year_to", type=int, default=2026)
    ap.add_argument("--delay", type=float, default=0.2)
    ap.add_argument("--output", type=Path, default=Path("data/catalog_crawl_raw.csv"))
    args = ap.parse_args(argv)

    catalog = crawl(args.year_from, args.year_to, delay=args.delay)
    if not catalog:
        print("ERROR: 크롤 결과 없음", file=sys.stderr)
        return 1
    write_csv(catalog, args.output)
    print(f"Wrote {len(catalog)} courses to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
