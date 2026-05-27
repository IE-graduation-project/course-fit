"""과목 입력 풍부화 — LLM 과목 설명 생성 (Phase 2)

`data/course.csv` 의 과목명·학과·이수구분을 입력으로 LLM 을 호출해
과목별 학습 내용 설명(키워드 + 200~300자)을 생성한다.

매핑 점수 산출에는 쓰지 않고, TF-IDF·KoSBERT 의 **입력 텍스트**로만 사용한다
(docs/과목과직무_역량_매핑.md 0·3.3 절).

산출물
- `data/course_descriptions.csv`  (course_id, description)

특징
- 이미 생성된 course_id 는 건너뛴다(캐싱) → 중단·재실행·비용 방어.
- 프롬프트는 `mapping/prompts/course_description.txt`.

사용법
    python mapping/01_generate_descriptions.py            # 미생성분만 생성
    python mapping/01_generate_descriptions.py --limit 5  # 앞 5개만 (시범)
    python mapping/01_generate_descriptions.py --force    # 전체 재생성
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import os

ROOT = Path(__file__).resolve().parent.parent
COURSE_CSV = ROOT / "data" / "course.csv"
DEPT_CSV = ROOT / "data" / "department.csv"
OUT_CSV = ROOT / "data" / "course_descriptions.csv"
PROMPT_FILE = ROOT / "mapping" / "prompts" / "course_description.txt"

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-nano")


def load_dept_names() -> dict[str, str]:
    with DEPT_CSV.open(encoding="utf-8") as f:
        return {r["dept_id"]: r["dept_name"] for r in csv.DictReader(f)}


def load_courses() -> list[dict]:
    with COURSE_CSV.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_done() -> set[str]:
    """이미 생성된 course_id 집합 (캐싱)."""
    if not OUT_CSV.exists():
        return set()
    with OUT_CSV.open(encoding="utf-8") as f:
        return {r["course_id"] for r in csv.DictReader(f) if r.get("description", "").strip()}


def build_prompt(template: str, course: dict, dept_names: dict[str, str]) -> str:
    return template.format(
        course_name=course["course_name"],
        dept_name=dept_names.get(course["dept_id"], course["dept_id"]),
        area=course.get("area", ""),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="앞 N개만 처리 (시범)")
    ap.add_argument("--force", action="store_true", help="이미 생성된 것도 재생성")
    args = ap.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY 미설정. .env 확인.", file=sys.stderr)
        return 1

    from openai import OpenAI

    client = OpenAI()
    template = PROMPT_FILE.read_text(encoding="utf-8")
    dept_names = load_dept_names()
    courses = load_courses()
    done = set() if args.force else load_done()

    todo = [c for c in courses if c["course_id"] not in done]
    if args.limit:
        todo = todo[: args.limit]

    print(f"전체 {len(courses)}개 · 기생성 {len(done)}개 · 이번 생성 {len(todo)}개 (model={MODEL})")
    if not todo:
        print("생성할 과목 없음.")
        return 0

    # append 모드: 헤더는 파일 없을 때만
    new_file = not OUT_CSV.exists()
    with OUT_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["course_id", "description"])

        for i, course in enumerate(todo, 1):
            prompt = build_prompt(template, course, dept_names)
            try:
                resp = client.chat.completions.create(
                    model=MODEL,
                    messages=[{"role": "user", "content": prompt}],
                )
                desc = resp.choices[0].message.content.strip().replace("\n", " ")
            except Exception as e:  # noqa: BLE001
                print(f"  [{i}/{len(todo)}] {course['course_id']} {course['course_name']} 실패: {e}",
                      file=sys.stderr)
                continue
            writer.writerow([course["course_id"], desc])
            f.flush()  # 중단 대비 즉시 저장
            print(f"  [{i}/{len(todo)}] {course['course_id']} {course['course_name']} ✓")

    print(f"완료 → {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
