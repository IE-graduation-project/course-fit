"""매핑 파이프라인 공통 유틸 (03·04·05 공유).

키워드 사전 로드, 역량 순서, 입력 텍스트 로더를 제공한다.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
KEYWORDS_JSON = ROOT / "mapping" / "competency_keywords.json"
INTERMEDIATE = ROOT / "mapping" / "intermediate"

COURSE_DESC_CSV = DATA / "course_descriptions.csv"
JOB_SAMPLED_CSV = DATA / "job_postings_sampled.csv"


def load_keywords() -> dict:
    """competency_keywords.json 로드. competency.csv 의 10개가 SOT."""
    with KEYWORDS_JSON.open(encoding="utf-8") as f:
        return json.load(f)


def comp_order() -> list[str]:
    """data/competency.csv 순서대로 comp_id 목록 (출력 컬럼 순서 기준)."""
    with (DATA / "competency.csv").open(encoding="utf-8") as f:
        return [r["comp_id"] for r in csv.DictReader(f)]


def load_course_docs() -> list[tuple[str, str]]:
    """(course_id, description) 목록. 과목은 1과목=1문서."""
    with COURSE_DESC_CSV.open(encoding="utf-8") as f:
        return [(r["course_id"], r["description"]) for r in csv.DictReader(f)]


def load_job_docs() -> list[tuple[str, str, str]]:
    """(job_id, posting_id, extracted_text) 목록. 직무는 공고별 문서 후 직무 평균."""
    with JOB_SAMPLED_CSV.open(encoding="utf-8") as f:
        return [(r["job_id"], r["posting_id"], r["extracted_text"]) for r in csv.DictReader(f)]
