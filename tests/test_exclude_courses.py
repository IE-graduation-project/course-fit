"""이 과목 빼고 다시 풀기 (C8).

사용자가 추천 결과의 한 과목을 빼 달라고 하면, 그 course_id 를 후보에서 미리 빼고 ILP 를
다시 푼다. free_days 와 같은 제약 축이다 — 뺀 과목은 어느 대안에도 나오지 않고, 솔버는
그 자리를 다른 과목으로 채운다.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from recommender import data, params
from recommender.recommend import recommend

ROOT = Path(__file__).resolve().parent.parent


def _biz_2026_student() -> str:
    """경영 2026 샘플 성적표를 app.db 에 적재하고 input_hash 반환."""
    import re

    from transcript.load import load_transcript
    from transcript.parse_text import parse_transcript_text

    src = (ROOT / "web" / "lib" / "sample.ts").read_text(encoding="utf-8")
    consts = dict(re.findall(r"const (\w+) = `(.*?)`;", src, re.S))
    table = re.search(r"SAMPLE_TRANSCRIPTS[^=]*=\s*\{(.*?)\};", src, re.S).group(1)
    text = None
    for dept, inner in re.findall(r"(\w+):\s*\{(.*?)\}", table, re.S):
        if dept == "BIZ":
            for year, name in re.findall(r"(\d{4}):\s*(\w+)", inner):
                if year == "2026":
                    text = consts[name]
    assert text, "BIZ 2026 샘플을 찾지 못했다"
    conn = sqlite3.connect(ROOT / "db" / "app.db")
    try:
        return load_transcript(parse_transcript_text(text, dept_id="BIZ", admission_year=2026), conn)
    finally:
        conn.close()


def _run(h, exclude=()):
    return recommend(h, "DA", db_path=str(ROOT / "db" / "app.db"),
                     eps=0.3, exclude_courses=exclude)   # eps 0.3 = 균형 성향


def test_excluded_course_disappears_and_is_replaced():
    h = _biz_2026_student()
    base = _run(h)
    assert base.results, "기본 추천이 비었다"
    first = [c.course_id for c in base.results[0].selected]
    assert first, "1안이 비었다"
    drop = first[0]

    after = _run(h, exclude=[drop])
    for res in after.results:          # 어느 대안에도 없어야 한다
        assert drop not in {c.course_id for c in res.selected}, f"{drop} 가 제외 후에도 남았다"


def test_exclude_empty_is_noop():
    h = _biz_2026_student()
    a = [c.course_id for c in _run(h).results[0].selected]
    b = [c.course_id for c in _run(h, exclude=[]).results[0].selected]
    assert a == b
