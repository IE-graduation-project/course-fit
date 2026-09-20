#!/usr/bin/env python3
"""Crawl Hongik University undergraduate timetable sections.

Source of truth: https://cn.hongik.ac.kr/app/timetable/

The public timetable UI works as a small JSP workflow:
1. GET `hak03.jsp` to receive the term selector.
2. POST the selected `yyhakgi` value back to `hak03.jsp`.
3. Extract hidden `p_yy` and `p_hakgi` from the selected-term page.
4. POST department parameters to `hak03_detail01.jsp`.

This script writes section-level rows to `data/course_section.csv`; it does not
modify the course-level `data/course.csv`.
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests

BASE_URL = "https://cn.hongik.ac.kr/app/timetable/"
SOURCE_TERM = "2026-1"
TERM_LABEL = "2026학년도 1학기"

CSV_FIELDS = [
    "course_id",
    "section",
    "course_name",
    "dept_name",
    "offering_dept",
    "professor",
    "time_slots_raw",
    "credit",
    "grade",
    "category",
    "source_term",
    "source_url",
    "source_dept_code",
    "source_dept_name",
    "notes",
]


@dataclass(frozen=True)
class DepartmentRequest:
    source_dept_code: str
    source_dept_name: str
    p_campus: str
    p_gubun: str
    p_dept: str
    p_ibhak: str = "2022"
    p_type: str = "1"
    p_grade: str = "0"
    p_abeek: str = "0"


MAJOR_DEPARTMENT_SCOPES = [
    DepartmentRequest(
        source_dept_code="A200",
        source_dept_name="컴퓨터·데이터공학부(컴퓨터공학과, 산업·데이터공학과)",
        p_campus="1",
        p_gubun="2",
        p_dept="A200",
    ),
    DepartmentRequest(
        source_dept_code="B010",
        source_dept_name="경영학부",
        p_campus="1",
        p_gubun="2",
        p_dept="B010",
    ),
]

# Official Seoul-campus liberal-arts scopes exposed by `hak03.jsp` for
# 2022+ entrants in the 2026-1 selected-term page. These are `goDetail01`
# parameter tuples with `p_gubun=1`, `p_dept=0001`, and grade-like category
# codes. The labels intentionally preserve the official timetable grouping.
LIBERAL_ARTS_SCOPES = [
    DepartmentRequest("GE1", "교양필수", "1", "1", "0001", p_grade="1"),
    DepartmentRequest("GE2", "인문계열", "1", "1", "0001", p_grade="2"),
    DepartmentRequest("GE3", "사회계열", "1", "1", "0001", p_grade="3"),
    DepartmentRequest("GE4", "자연계열", "1", "1", "0001", p_grade="4"),
    DepartmentRequest("GE5", "예체능계열", "1", "1", "0001", p_grade="5"),
    DepartmentRequest("GE6", "영어계열", "1", "1", "0001", p_grade="6"),
    DepartmentRequest("GE7", "제2외국어계열", "1", "1", "0001", p_grade="7"),
    DepartmentRequest("GE8", "교직과목", "1", "1", "0001", p_grade="8"),
    DepartmentRequest("GE11", "예술과디자인", "1", "1", "0001", p_grade="11"),
    DepartmentRequest("GE12", "제2외국어와한문", "1", "1", "0001", p_grade="12"),
    DepartmentRequest("GE13", "과학과컴퓨터", "1", "1", "0001", p_grade="13"),
    DepartmentRequest("GE14", "언어와철학", "1", "1", "0001", p_grade="14"),
    DepartmentRequest("GE15", "법과생활", "1", "1", "0001", p_grade="15"),
    DepartmentRequest("GE16", "사회와경제", "1", "1", "0001", p_grade="16"),
    DepartmentRequest("GE17", "역사와문화", "1", "1", "0001", p_grade="17"),
]

ENGINEERING_LIBERAL_ARTS_SCOPES = [
    DepartmentRequest("ENG_GE11", "기초교양", "1", "1", "0001", p_grade="11", p_abeek="1"),
    DepartmentRequest("ENG_GE12", "일반교양", "1", "1", "0001", p_grade="12", p_abeek="1"),
    DepartmentRequest("ENG_GE13", "핵심교양", "1", "1", "0001", p_grade="13", p_abeek="1"),
    DepartmentRequest("ENG_GE14", "MSC수학", "1", "1", "0001", p_grade="14", p_abeek="1"),
    DepartmentRequest("ENG_GE15", "MSC과학", "1", "1", "0001", p_grade="15", p_abeek="1"),
    DepartmentRequest("ENG_GE16", "MSC전산", "1", "1", "0001", p_grade="16", p_abeek="1"),
    DepartmentRequest("ENG_GE1", "인문계열(공학)", "1", "1", "0001", p_grade="1", p_abeek="1"),
    DepartmentRequest("ENG_GE2", "사회계열(공학)", "1", "1", "0001", p_grade="2", p_abeek="1"),
    DepartmentRequest("ENG_GE3", "자연계열(공학)", "1", "1", "0001", p_grade="3", p_abeek="1"),
    DepartmentRequest("ENG_GE4", "예체능계열(공학)", "1", "1", "0001", p_grade="4", p_abeek="1"),
    DepartmentRequest("ENG_GE5", "영어계열(공학)", "1", "1", "0001", p_grade="5", p_abeek="1"),
    DepartmentRequest("ENG_GE6", "제2외국어계열(공학)", "1", "1", "0001", p_grade="6", p_abeek="1"),
    DepartmentRequest("ENG_GE7", "교직(공학)", "1", "1", "0001", p_grade="7", p_abeek="1"),
]

TARGET_DEPARTMENTS = MAJOR_DEPARTMENT_SCOPES + LIBERAL_ARTS_SCOPES + ENGINEERING_LIBERAL_ARTS_SCOPES


class TimetableCrawlerError(RuntimeError):
    """Raised when the official timetable workflow cannot be parsed."""


_TERM_RE = re.compile(r"^(\d{4})-([12])$")


def term_label_of(term: str) -> str:
    """`"2026-2"` -> `"2026학년도 2학기"`.

    정규학기(1·2)만 받는다. 드롭다운에는 계절학기도 있지만(`2026학년도 하계계절학기`)
    라벨 규칙이 달라 이 규칙으로는 만들 수 없고 추천 대상도 아니다. 여기서 막지 않으면
    `2026-3` 이 `2026학년도 3학기` 라는 없는 라벨이 되어 `_extract_option_value` 에서
    "Could not find term option label" 로 죽는다 — 입력 오류가 크롤 실패로 위장된다.

    crawl_catalog.build_terms 의 f"{y}학년도 {s}" 와 같은 규칙이다.
    """
    match = _TERM_RE.match(term)
    if not match:
        raise ValueError(f"학기 형식이 잘못됐습니다: {term!r} (예: 2026-2 — 정규학기 1·2만)")
    year, semester = match.groups()
    return f"{year}학년도 {semester}학기"


def _normalize_text(value: str) -> str:
    value = html.unescape(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"[ \t\r\f\v]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    return value.strip()


def _cell_text(cell_html: str) -> str:
    cell_html = re.sub(r"<br\s*/?>", "\n", cell_html, flags=re.IGNORECASE)
    cell_html = re.sub(r"<script\b.*?</script>", " ", cell_html, flags=re.IGNORECASE | re.DOTALL)
    cell_html = re.sub(r"<style\b.*?</style>", " ", cell_html, flags=re.IGNORECASE | re.DOTALL)
    cell_html = re.sub(r"<[^>]+>", " ", cell_html)
    return _normalize_text(cell_html)


def _course_name(cell_html: str) -> str:
    text = _cell_text(cell_html)
    for line in (part.strip() for part in text.splitlines()):
        if not line:
            continue
        # The second line is usually the English title in parentheses.
        if line.startswith("(") and line.endswith(")"):
            continue
        return line
    return text


def _extract_option_value(page: str, label: str) -> str:
    option_re = re.compile(r"<option\b[^>]*value=[\"']([^\"']+)[\"'][^>]*>(.*?)</option>", re.I | re.S)
    for value, raw_label in option_re.findall(page):
        if _normalize_text(re.sub(r"<[^>]+>", " ", raw_label)) == label:
            return html.unescape(value)
    raise TimetableCrawlerError(f"Could not find term option label: {label}")


def _extract_hidden(page: str, name: str) -> str:
    pattern = re.compile(
        rf"<input\b(?=[^>]*\bname\s*=\s*[\"']{re.escape(name)}[\"'])(?=[^>]*\bvalue\s*=\s*[\"']([^\"']*)[\"'])[^>]*>",
        re.I | re.S,
    )
    match = pattern.search(page)
    if not match:
        raise TimetableCrawlerError(f"Could not find hidden input: {name}")
    return html.unescape(match.group(1))


def _raise_if_alert(page: str, context: str) -> None:
    match = re.search(r"alert\(['\"](.*?)['\"]\)", page, re.S)
    if match:
        message = _normalize_text(match.group(1))
        raise TimetableCrawlerError(f"Official timetable returned alert during {context}: {message}")


def fetch_selected_term_page(session: requests.Session, term_label: str = TERM_LABEL) -> tuple[str, str, str]:
    """Return selected-term page plus hidden `(p_yy, p_hakgi)` values."""
    hak03_url = BASE_URL + "hak03.jsp"
    response = session.get(hak03_url, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    _raise_if_alert(response.text, "initial hak03.jsp load")

    yyhakgi = _extract_option_value(response.text, term_label)
    payload = {
        "yyhakgi": yyhakgi,
        "ibhak": "2022",
        "abeek": "0",
        "p_type": "2",
        "p_search_haksu": "",
        "p_search_prof": "",
        "p_search_week": "0",
        "btn_search": "조회",
    }
    selected = session.post(hak03_url, data=payload, headers={"Referer": hak03_url}, timeout=30)
    selected.raise_for_status()
    selected.encoding = "utf-8"
    _raise_if_alert(selected.text, f"selecting term {term_label}")
    return selected.text, _extract_hidden(selected.text, "p_yy"), _extract_hidden(selected.text, "p_hakgi")


def fetch_department_detail(
    session: requests.Session,
    department: DepartmentRequest,
    p_yy: str,
    p_hakgi: str,
) -> str:
    payload = {
        "p_yy": p_yy,
        "p_hakgi": p_hakgi,
        "p_campus": department.p_campus,
        "p_gubun": department.p_gubun,
        "p_dept": department.p_dept,
        "p_grade": department.p_grade,
        "p_abeek": department.p_abeek,
        "p_ibhak": department.p_ibhak,
        "p_search_haksu": "",
        "p_search_prof": "",
        "p_search_week": "0",
        "p_type": department.p_type,
    }
    detail_url = BASE_URL + "hak03_detail01.jsp"
    response = session.post(detail_url, data=payload, headers={"Referer": BASE_URL + "hak03.jsp"}, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    _raise_if_alert(response.text, f"fetching department {department.p_dept}")
    return response.text


def parse_detail_rows(
    page: str,
    department: DepartmentRequest,
    source_term: str = SOURCE_TERM,
) -> list[dict[str, str]]:
    """상세 페이지 한 장을 행으로 판다.

    `source_term` 은 반드시 인자로 받는다. 모듈 전역을 읽으면 `--term` 을 다른 지점에만
    배선했을 때 2026-2 실데이터에 `2026-1` 이 찍히고, 행수도 과목명도 정상이라
    예외 없이 통과한다. 기본값을 남기는 이유는 crawl_catalog 가 2인자로 부르기 때문이다.
    """
    rows: list[dict[str, str]] = []
    tr_blocks = re.findall(r"<tr\b[^>]*>(.*?)</tr>", page, flags=re.I | re.S)
    for tr in tr_blocks:
        td_blocks = re.findall(r"<td\b[^>]*>(.*?)</td>", tr, flags=re.I | re.S)
        if len(td_blocks) < 14:
            continue

        haksu = _cell_text(td_blocks[4])
        if not re.match(r"^\d{6}-[^\s]+$", haksu):
            continue
        course_id, section = haksu.rsplit("-", 1)

        row = {
            "course_id": course_id,
            "section": section,
            "course_name": _course_name(td_blocks[5]),
            "dept_name": _cell_text(td_blocks[1]),
            "offering_dept": _cell_text(td_blocks[2]),
            "professor": _cell_text(td_blocks[11]),
            "time_slots_raw": _cell_text(td_blocks[12]),
            "credit": _cell_text(td_blocks[6]),
            "grade": _cell_text(td_blocks[0]),
            "category": _cell_text(td_blocks[3]),
            "source_term": source_term,
            "source_url": BASE_URL,
            "source_dept_code": department.source_dept_code,
            "source_dept_name": department.source_dept_name,
            "notes": _cell_text(td_blocks[13]),
        }
        rows.append(row)
    return rows


def section_sort_key(row: dict[str, str]) -> tuple[str, str, int, str]:
    section = row["section"]
    section_num = int(section) if section.isdigit() else 10_000
    return (row["source_dept_code"], row["course_id"], section_num, section)


def _merge_duplicate_sections(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Merge duplicate rows exposed under both non-engineering and engineering liberal scopes.

    Hongik's 2022+ non-engineering and engineering menus repeat many identical
    liberal-arts rows under different grouping labels. Keep one section row and
    preserve all official source scopes in semicolon-delimited source fields.
    """
    merged: dict[tuple[str, str, str, str, str], dict[str, str]] = {}
    scope_codes: dict[tuple[str, str, str, str, str], set[str]] = {}
    scope_names: dict[tuple[str, str, str, str, str], set[str]] = {}
    for row in rows:
        key = (
            row["course_id"],
            row["section"],
            row["course_name"],
            row["professor"],
            row["time_slots_raw"],
        )
        if key not in merged:
            merged[key] = dict(row)
            scope_codes[key] = set()
            scope_names[key] = set()
        scope_codes[key].update(part for part in row["source_dept_code"].split(";") if part)
        scope_names[key].update(part for part in row["source_dept_name"].split(";") if part)
    out = []
    for key, row in merged.items():
        row["source_dept_code"] = ";".join(sorted(scope_codes[key]))
        row["source_dept_name"] = ";".join(sorted(scope_names[key]))
        out.append(row)
    return out


def crawl_sections(
    departments: Iterable[DepartmentRequest] = TARGET_DEPARTMENTS,
    term: str = SOURCE_TERM,
) -> list[dict[str, str]]:
    """한 학기의 분반·시간표를 전부 긁는다. **단일 학기 전제**다.

    `_merge_duplicate_sections` 의 병합 키에 source_term 이 없어서, 두 학기를 한 번에
    모으면 과목명·교수·시간이 같은 분반이 한 행으로 합쳐진다. 다학기를 지원하려면
    병합 키부터 고쳐야 한다.
    """
    term_label = term_label_of(term)
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "course-fit timetable crawler (+https://cn.hongik.ac.kr/app/timetable/)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    # Establish cookies/session state from the frame page before using hak03.jsp.
    index = session.get(BASE_URL, timeout=30)
    index.raise_for_status()

    _term_page, p_yy, p_hakgi = fetch_selected_term_page(session, term_label)
    all_rows: list[dict[str, str]] = []
    for department in departments:
        detail = fetch_department_detail(session, department, p_yy=p_yy, p_hakgi=p_hakgi)
        rows = parse_detail_rows(detail, department, source_term=term)
        if not rows:
            raise TimetableCrawlerError(f"No timetable rows parsed for {department.p_dept}")
        all_rows.extend(rows)
    return sorted(_merge_duplicate_sections(all_rows), key=section_sort_key)


def write_csv(rows: list[dict[str, str]], output: Path, term: str | None = None) -> None:
    """CSV 로 쓴다. `term` 을 주면 모든 행이 그 학기인지 먼저 단언한다.

    배선을 한 지점이라도 빠뜨리면 2026-2 실데이터에 `2026-1` 이 찍힌 CSV 가 나온다.
    행수도 과목명도 교수도 전부 정상이라 눈으로는 안 잡히고, 그대로 적재되면
    DB 에 틀린 학기가 굳는다. 여기서 막으면 다음 학기에 같은 실수가 불가능하다.
    """
    if term is not None:
        found = {row["source_term"] for row in rows}
        if found != {term}:
            raise TimetableCrawlerError(
                f"source_term 이 요청한 학기와 다릅니다: 기대 {{{term!r}}}, 실제 {found!r}. "
                "--term 배선이 빠진 지점이 있습니다 (parse_detail_rows 확인)."
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _term_arg(value: str) -> str:
    """argparse 용 — 형식 오류를 크롤 실패가 아니라 CLI 오류로 돌려준다."""
    try:
        term_label_of(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/course_section.csv"))
    parser.add_argument(
        "--term",
        type=_term_arg,
        default=SOURCE_TERM,
        help="크롤할 학기 (예: 2026-2). 정규학기 1·2만 받는다.",
    )
    args = parser.parse_args(argv)

    try:
        rows = crawl_sections(term=args.term)
        write_csv(rows, args.output, term=args.term)
    except (requests.RequestException, TimetableCrawlerError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["source_dept_code"]] = counts.get(row["source_dept_code"], 0) + 1
    print(f"Wrote {len(rows)} rows to {args.output}")
    for code, count in sorted(counts.items()):
        print(f"- {code}: {count} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
