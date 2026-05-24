#!/usr/bin/env python3
"""Validate `data/course_section.csv` against course-level `data/course.csv`."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REQUIRED_SECTION_FIELDS = {
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
}

SAMPLE_EXPECTATIONS = [
    ("140715", "시스템분석", "하정훈", "월91011"),
    ("140524", "경제성분석", "옥창수", "화123"),
    ("140316", "데이터사이언스", "박희석", "수89,금9"),
]
MULTI_SECTION_EXPECTATIONS = ["033102", "033103"]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp))


def validate(sections_path: Path, courses_path: Path) -> dict[str, object]:
    sections = read_csv(sections_path)
    courses = read_csv(courses_path)
    if not sections:
        raise AssertionError(f"No section rows found in {sections_path}")

    missing_fields = REQUIRED_SECTION_FIELDS - set(sections[0].keys())
    if missing_fields:
        raise AssertionError(f"Missing course_section fields: {sorted(missing_fields)}")

    section_course_ids = {row["course_id"] for row in sections}
    course_ids = {row["course_id"] for row in courses}
    unmatched = sorted(section_course_ids - course_ids)
    matched_course_ids = sorted(course_ids & section_course_ids)

    section_counts = Counter(row["course_id"] for row in sections)
    source_counts = Counter(row.get("source_dept_code", "") for row in sections)
    source_scope_counts = Counter(
        scope
        for row in sections
        for scope in row.get("source_dept_code", "").split(";")
        if scope
    )
    matched_by_course_dept = Counter(
        row.get("dept_id", "") for row in courses if row["course_id"] in section_course_ids
    )
    course_unmatched_by_dept: dict[str, list[str]] = defaultdict(list)
    for row in courses:
        if row["course_id"] not in section_course_ids and len(course_unmatched_by_dept[row.get("dept_id", "")]) < 12:
            course_unmatched_by_dept[row.get("dept_id", "")].append(
                f"{row['course_id']} {row['course_name']}"
            )

    sample_results = []
    for course_id, name, professor, time_slots in SAMPLE_EXPECTATIONS:
        matches = [
            row
            for row in sections
            if row["course_id"] == course_id
            and row["course_name"] == name
            and row["professor"] == professor
            and row["time_slots_raw"] == time_slots
        ]
        sample_results.append(
            {
                "course_id": course_id,
                "expected": {"course_name": name, "professor": professor, "time_slots_raw": time_slots},
                "pass": bool(matches),
                "sections": [row["section"] for row in matches],
            }
        )
        if not matches:
            observed = [
                {
                    "section": row["section"],
                    "course_name": row["course_name"],
                    "professor": row["professor"],
                    "time_slots_raw": row["time_slots_raw"],
                }
                for row in sections
                if row["course_id"] == course_id
            ]
            raise AssertionError(f"Sample check failed for {course_id}; observed={observed}")

    multi_section_results = []
    for course_id in MULTI_SECTION_EXPECTATIONS:
        count = section_counts[course_id]
        multi_section_results.append({"course_id": course_id, "section_count": count, "pass": count >= 2})
        if count < 2:
            raise AssertionError(f"Expected multiple sections for {course_id}, found {count}")

    by_dept_unmatched: dict[str, list[str]] = defaultdict(list)
    for row in sections:
        if row["course_id"] in unmatched and len(by_dept_unmatched[row.get("source_dept_code", "")]) < 12:
            by_dept_unmatched[row.get("source_dept_code", "")].append(
                f"{row['course_id']}-{row['section']} {row['course_name']}"
            )

    return {
        "section_rows": len(sections),
        "unique_section_course_ids": len(section_course_ids),
        "course_rows": len(courses),
        "matched_unique_course_ids": len(matched_course_ids),
        "unmatched_unique_course_ids": len(unmatched),
        "matched_rate_vs_section_course_ids": round(len(matched_course_ids) / len(section_course_ids), 4),
        "course_csv_rows_with_2026_1_sections": len(matched_course_ids),
        "course_csv_match_rate": round(len(matched_course_ids) / len(course_ids), 4) if course_ids else 0,
        "unmatched_examples": unmatched[:20],
        "unmatched_examples_by_source_dept": dict(by_dept_unmatched),
        "section_rows_by_source_dept": dict(source_counts),
        "section_rows_by_individual_source_scope": dict(source_scope_counts),
        "course_csv_matched_by_dept": dict(matched_by_course_dept),
        "course_csv_unmatched_examples_by_dept": dict(course_unmatched_by_dept),
        "sample_results": sample_results,
        "multi_section_results": multi_section_results,
    }


def print_summary(result: dict[str, object]) -> None:
    print(f"course_section rows: {result['section_rows']}")
    print(f"unique course_section.course_id: {result['unique_section_course_ids']}")
    print(f"course.csv rows: {result['course_rows']}")
    print(
        "matched unique section course_ids in course.csv: "
        f"{result['matched_unique_course_ids']} / {result['unique_section_course_ids']} "
        f"({result['matched_rate_vs_section_course_ids']})"
    )
    print(
        "course.csv target courses with 2026-1 sections: "
        f"{result['course_csv_rows_with_2026_1_sections']} / {result['course_rows']} "
        f"({result['course_csv_match_rate']})"
    )
    print(f"unmatched unique course_ids: {result['unmatched_unique_course_ids']}")
    print(f"unmatched examples: {', '.join(result['unmatched_examples'])}")
    print("section rows by source dept:", result["section_rows_by_source_dept"])
    print("section rows by individual source scope:", result["section_rows_by_individual_source_scope"])
    print("course.csv matched by dept:", result["course_csv_matched_by_dept"])
    print("course.csv unmatched examples by dept:", result["course_csv_unmatched_examples_by_dept"])
    print("sample checks:")
    for item in result["sample_results"]:
        print(f"- {item['course_id']}: PASS sections={item['sections']}")
    print("multi-section checks:")
    for item in result["multi_section_results"]:
        print(f"- {item['course_id']}: PASS count={item['section_count']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sections", type=Path, default=Path("data/course_section.csv"))
    parser.add_argument("--courses", type=Path, default=Path("data/course.csv"))
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary")
    args = parser.parse_args(argv)

    try:
        result = validate(args.sections, args.courses)
    except (OSError, AssertionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
