"""성적표 값 변환 규칙 (이슈 #16).

등급 -> 4.5 평점, 이수구분 -> area enum, 학과명 -> dept_id, input_hash 산출.
표기 변형(전각 등) 정규화 포함. 실제 표기는 샘플 PDF로 확정한다.
"""

from __future__ import annotations

import hashlib
import re

# --- 4-1. 등급 -> 4.5 평점 ---------------------------------------------------
GRADE_TO_GPA = {
    "A+": 4.5, "A0": 4.0, "A": 4.0,
    "B+": 3.5, "B0": 3.0, "B": 3.0,
    "C+": 2.5, "C0": 2.0, "C": 2.0,
    "D+": 1.5, "D0": 1.0, "D": 1.0,
    "F": 0.0,
}
PASS_LETTERS = {"P"}             # Pass (P/N 과목)
NONPASS_LETTERS = {"NP", "N"}    # Non-pass
PN_LETTERS = PASS_LETTERS | NONPASS_LETTERS
PASS_GPA_THRESHOLD = 1.0         # D0 이상이면 이수

# --- 4-2. 이수구분 -> area enum (data/README.md의 enum과 동기화) -------------
# area enum: 교양필수, 특성화교양, SW데이터활용역량, 공통교양, 전공기초영어,
#            전공필수, 전공선택, 일반선택, MSC, 전공기초
CATEGORY_TO_AREA = {
    "전공필수": "전공필수", "전필": "전공필수",
    "전공선택": "전공선택", "전선": "전공선택",
    "전공기초": "전공기초", "전기": "전공기초",
    "교양필수": "교양필수", "교필": "교양필수",
    "공통교양": "공통교양", "교양선택": "공통교양", "교선": "공통교양",
    "특성화교양": "특성화교양",
    "일반선택": "일반선택", "일선": "일반선택",
    "MSC": "MSC",
    "전공기초영어": "전공기초영어",
    "SW데이터활용역량": "SW데이터활용역량",
    "SW데이터": "SW데이터활용역량",
}


def normalize_letter(letter: str | None) -> str | None:
    """등급 표기 정규화: 공백 제거, 대문자, 전각 +/- -> 반각."""
    if letter is None:
        return None
    s = re.sub(r"\s+", "", letter).upper()
    s = s.replace("＋", "+").replace("－", "-").replace("ー", "-")
    return s or None


def grade_to_gpa(letter: str | None) -> float | None:
    """등급 -> 4.5 평점. P/N 또는 미인식이면 None."""
    s = normalize_letter(letter)
    if s is None or s in PN_LETTERS:
        return None
    return GRADE_TO_GPA.get(s)


def is_pn(letter: str | None) -> bool:
    """P/N(P/NP/N) 과목 여부."""
    return normalize_letter(letter) in PN_LETTERS


def is_passed(letter: str | None) -> bool:
    """이수(취득) 여부: P 또는 D0(1.0) 이상. F/NP/N/미인식은 미이수."""
    s = normalize_letter(letter)
    if s in PASS_LETTERS:
        return True
    if s in NONPASS_LETTERS:
        return False
    g = GRADE_TO_GPA.get(s)
    return g is not None and g >= PASS_GPA_THRESHOLD


def category_to_area(category: str | None) -> str | None:
    """이수구분 -> area enum. 미매핑이면 None."""
    if category is None:
        return None
    key = re.sub(r"\s+", "", category)
    return CATEGORY_TO_AREA.get(key)


def normalize_dept(name: str | None) -> str | None:
    """성적표 학과명 -> dept_id. 미매핑이면 None."""
    if not name:
        return None
    s = re.sub(r"\s+", "", name)
    if "산업" in s and ("데이터" in s or "데이타" in s):
        return "IDE"
    if "경영" in s:
        return "BIZ"
    return None


def compute_input_hash(meta, courses) -> str:
    """성적표 내용 기반 결정적 해시(앞 16자리).

    학생 식별자(학번 우선, 없으면 성명) + 정렬된 과목 핵심값으로 산출.
    같은 성적표 재업로드 시 동일 hash -> idempotent 적재.
    """
    ident = (
        getattr(meta, "student_no", None)
        or getattr(meta, "name", None)
        or "{}|{}".format(getattr(meta, "dept_id", None), getattr(meta, "admission_year", None))
    ).strip()
    rows = sorted(
        "{}|{}|{}|{}".format(
            c.course_id or "",
            c.term or "",
            normalize_letter(c.grade_letter) or "",
            c.credit,
        )
        for c in courses
    )
    key = ident + "\n" + "\n".join(rows)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
