"""catalog 보강 매핑 단위테스트 (이슈 #18). 네트워크 없이 매핑 규칙만 검증."""

from __future__ import annotations

from crawlers.courses.merge_catalog import resolve_area, resolve_dept


def test_resolve_dept():
    assert resolve_dept({"B010"}, "경영학부") == "BIZ"
    assert resolve_dept(set(), "경영학전공") == "BIZ"
    assert resolve_dept({"A200"}, f"산업{chr(0xB7)}데이터공학과") == "IDE"  # 구분점 포함 공식 표기
    assert resolve_dept({"A200"}, "컴퓨터공학과") == "COMMON"
    assert resolve_dept({"GE1"}, "교양과(서울)") == "COMMON"


def test_resolve_area_major():
    assert resolve_area("전선", {"B010"}, "BIZ") == ("전공선택", None)
    assert resolve_area("전필", {"B010"}, "BIZ") == ("전공필수", None)
    assert resolve_area("전기", {"B010"}, "BIZ") == ("전공기초", None)
    # 전공이지만 소유 학부 불명(COMMON) -> 일반선택으로 환산
    assert resolve_area("전선", {"A200"}, "COMMON") == ("일반선택", None)


def test_resolve_area_liberal():
    assert resolve_area("교필/교양필수", {"GE1"}, "COMMON") == ("교양필수", None)
    assert resolve_area("교선", {"GE3"}, "COMMON") == ("공통교양", None)
    assert resolve_area("일교/언어와철학", {"GE14"}, "COMMON") == ("공통교양", None)
    assert resolve_area("핵교/공학의이해", {"GE1"}, "COMMON") == ("공통교양", None)
    assert resolve_area("일선", set(), "COMMON") == ("일반선택", None)
    assert resolve_area("교직", set(), "COMMON") == ("일반선택", None)


def test_resolve_area_msc():
    assert resolve_area("교선", {"ENG_GE14", "GE4"}, "COMMON") == ("MSC", "math")
    assert resolve_area("교선", {"ENG_GE15"}, "COMMON") == ("MSC", "science")
    assert resolve_area("전선", {"ENG_GE16"}, "COMMON") == ("MSC", "cs")


def test_resolve_area_unknown():
    assert resolve_area("이상한구분", set(), "COMMON") == (None, None)
    assert resolve_area("", set(), "COMMON") == (None, None)
