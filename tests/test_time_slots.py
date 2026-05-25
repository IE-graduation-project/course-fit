"""time_slots 전처리 파서 테스트. (crawlers/courses/preprocess_time_slots.py)"""

import csv
from pathlib import Path

import pytest

from crawlers.courses.preprocess_time_slots import (
    DAY_STRIDE,
    format_slots,
    parse_time_slots,
    slot_to_human,
    slots_conflict,
    tokenize_periods,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SECTIONS_CSV = REPO_ROOT / "data" / "course_section.csv"


# --- tokenize_periods: 한/두 자리 교시 구분의 핵심 케이스 ---
@pytest.mark.parametrize(
    "digits,expected",
    [
        ("123", [1, 2, 3]),          # 한 자리 연속
        ("234", [2, 3, 4]),
        ("12", [1, 2]),              # 1·2교시(아침) — [12] 아님
        ("13", [1, 3]),              # 비연속 한 자리
        ("89", [8, 9]),
        ("10", [10]),                # 0은 단독 불가 → 10
        ("910", [9, 10]),
        ("1011", [10, 11]),          # 10,11 (1·0·1·1 아님)
        ("91011", [9, 10, 11]),
        ("8910", [8, 9, 10]),
        ("101112", [10, 11, 12]),
        ("111213", [11, 12, 13]),    # 모두 두 자리 (단일 분해는 교시1 중복으로 무효)
        ("10111213", [10, 11, 12, 13]),
        ("1234", [1, 2, 3, 4]),
        # 의도된 동작 고정: 단독 1X(앞에 10/11 없음)는 1+X로 해석 (홍익 표기 관례)
        ("1213", [1, 2, 13]),
    ],
)
def test_tokenize_periods(digits, expected):
    assert tokenize_periods(digits) == expected


@pytest.mark.parametrize("digits", ["98", "21", "320", "140"])
def test_tokenize_invalid_raises(digits):
    # 역순/유효분해 불가 → fail-loud (조용한 오파싱 금지)
    with pytest.raises(ValueError):
        tokenize_periods(digits)


def test_max_period_failloud():
    # MAX_PERIOD(13) 초과 교시만으로 구성돼 유효 분해가 없으면 ValueError
    with pytest.raises(ValueError):
        tokenize_periods("1415")  # [14,15]는 >13, [1,4,15]도 15>13 → 분해 불가


def test_tokenize_strictly_increasing():
    # 모든 결과는 강한 증가
    for digits in ["123", "91011", "111213", "10111213"]:
        toks = tokenize_periods(digits)
        assert toks == sorted(set(toks))
        assert all(b > a for a, b in zip(toks, toks[1:]))


# --- parse_time_slots: 슬롯 인코딩 ---
def test_parse_known_samples():
    # 월(0)·9,10,11
    assert parse_time_slots("월91011") == [9, 10, 11]
    # 수(2)·8,9 + 금(4)·9 → 2*16+8, 2*16+9, 4*16+9
    assert parse_time_slots("수89,금9") == [40, 41, 73]
    # 화(1)·1,2,3
    assert parse_time_slots("화123") == [17, 18, 19]


def test_parse_multiday_and_sunday():
    # 일요일(6) 포함, 비연속 교시
    assert parse_time_slots("수89,일13") == [40, 41, 97, 99]
    # 토요일(5)
    assert parse_time_slots("토1234") == [81, 82, 83, 84]


@pytest.mark.parametrize("empty", ["", "   ", None])
def test_parse_empty(empty):
    assert parse_time_slots(empty) == []


def test_parse_dedup_and_sorted():
    # 같은 슬롯 중복은 제거되고 정렬됨
    assert parse_time_slots("월2,월2") == [2]
    assert parse_time_slots("금9,수8") == sorted([4 * 16 + 9, 2 * 16 + 8])


def test_parse_invalid_block_raises():
    with pytest.raises(ValueError):
        parse_time_slots("X12")       # 요일 아님
    with pytest.raises(ValueError):
        parse_time_slots("월")        # 교시 없음


# --- 슬롯 의미/유틸 ---
def test_slot_encoding_no_cross_day_collision():
    # 서로 다른 요일의 같은 교시는 절대 같은 슬롯이 아님 (DAY_STRIDE > 최대 교시)
    assert parse_time_slots("월9") != parse_time_slots("화9")
    assert DAY_STRIDE > 15


def test_slot_to_human_roundtrip():
    for raw, human in [("월91011", ["월9", "월10", "월11"]),
                       ("수89,금9", ["수8", "수9", "금9"])]:
        assert [slot_to_human(s) for s in parse_time_slots(raw)] == human


def test_format_slots():
    assert format_slots([9, 10, 11]) == "9,10,11"
    assert format_slots([]) == ""


def test_slots_conflict():
    a = parse_time_slots("수89,금9")   # 수8,수9,금9
    b = parse_time_slots("목789")       # 목7,8,9 — 겹침 없음
    c = parse_time_slots("금9,월1")     # 금9 겹침
    assert slots_conflict(a, b) is False
    assert slots_conflict(a, c) is True


# --- 실데이터 전수: 파싱 오류 0, 컬럼 정합성 ---
@pytest.mark.skipif(not SECTIONS_CSV.exists(), reason="course_section.csv 없음")
def test_all_sections_parse_without_error():
    with SECTIONS_CSV.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows, "데이터가 비어있음"
    for row in rows:
        # 예외 없이 파싱돼야 함
        slots = parse_time_slots(row["time_slots_raw"])
        # 저장된 time_slots_int가 있다면 파서 결과와 일치해야 함(전처리 완료 검증)
        if "time_slots_int" in row:
            assert row["time_slots_int"] == format_slots(slots)
