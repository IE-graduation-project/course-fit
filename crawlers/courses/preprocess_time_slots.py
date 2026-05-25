"""time_slots_raw → time_slots_int 전처리.

홍익대 공식 시간표 표기(예: ``월91011``, ``수89,금9``)를 ILP 추천 엔진이 시간 충돌을
판정할 수 있는 **정수 슬롯 집합**으로 변환한다. (docs/ILP_추천_설계.md §3 선행작업 P1)

슬롯 인코딩
-----------
``slot = 요일_index * DAY_STRIDE + 교시``
- 요일_index: 월=0, 화=1, 수=2, 목=3, 금=4, 토=5, 일=6
- 교시: 1..15 (DAY_STRIDE=16 > 최대 교시이므로 요일 간 슬롯 충돌 없음)

예) ``월91011`` → 월(0)·9,10,11교시 → {9, 10, 11}
    ``수89,금9`` → 수(2)·8,9 + 금(4)·9 → {40, 41, 73}

교시 파싱 규칙 (중요)
---------------------
숫자열은 두 자리 교시(10~13)와 한 자리 교시가 구분 기호 없이 붙어 있다
(예: ``91011`` = 9,10,11 / ``111213`` = 11,12,13 / ``12`` = 1,2). 이를
**"각 교시 1~MAX_PERIOD·강한 증가(strictly increasing) 유효 분해 중 토큰 수가 가장 많은 분해"**
로 결정론적으로 해석한다.
- ``12`` → [1, 2]   (아침 1·2교시. [12] 단일 해석보다 토큰 많은 [1,2] 선택 — 홍익 표기 관례)
- ``1011`` → [10, 11]  (``0``은 단독 교시가 될 수 없어 ``10``으로 묶임)
- ``111213`` → [11, 12, 13]  (모두 단일로 쪼개면 교시 1이 중복되어 무효 → 유일 해)
- ``91011`` → [9, 10, 11]
한 분반의 한 요일 블록은 서로 다른 교시들이 증가 순으로 나열된다고 가정한다(실데이터 검증됨).

한계(의도된 동작)
-----------------
- ``MAX_PERIOD``는 2026-1 실데이터 관측 최대 교시(13)로 둔다. 초과 교시가 든 문자열은
  유효 분해가 없어 ``ValueError``로 **명시적 실패**한다(조용한 오파싱 방지). 미래 학기에
  야간 교시가 늘면 이 상수만 올리면 된다.
- 12~13교시는 실데이터에서 항상 ``101112``·``111213``처럼 **앞 교시(10·11)와 연속된 run**
  안에서만 등장하므로 정확히 파싱된다. 만약 어떤 학기가 "12·13교시에만 열리는 강의"를
  ``1213``으로 표기하면 본 규칙은 ``[1, 2, 13]``으로 해석한다(2026-1에는 그런 사례 없음).
  그런 표기가 도입되면 파싱 관례를 재정의해야 한다.

학기 무관: ``course_section.csv``의 ``time_slots_raw``만 입력으로 받으므로 2026-1 외 어느
학기 스냅샷에도 그대로 동작한다(하드코딩 없음).
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
from pathlib import Path

logger = logging.getLogger("preprocess_time_slots")

DAY_TO_IDX = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}
IDX_TO_DAY = {v: k for k, v in DAY_TO_IDX.items()}
DAY_STRIDE = 16
MIN_PERIOD, MAX_PERIOD = 1, 13  # 13 = 2026-1 관측 최대 교시. 초과 시 ValueError(fail-loud)

_BLOCK_RE = re.compile(r"^([월화수목금토일])(\d+)$")


def tokenize_periods(digits: str) -> list[int]:
    """연속 숫자열을 교시 리스트로 분해.

    유효(각 교시 1..15, 강한 증가) 분해 중 **토큰 수가 최대**인 것을 택한다.
    한 자리 우선(ln=1을 먼저 시도)이라 동률 시 더 잘게 쪼갠 해가 선택된다.
    """
    n = len(digits)
    best: list[int] | None = None

    def rec(i: int, prev: int, acc: list[int]) -> None:
        nonlocal best
        if i == n:
            if best is None or len(acc) > len(best):
                best = acc.copy()
            return
        for length in (1, 2):
            if i + length > n:
                continue
            tok = digits[i : i + length]
            if length == 2 and tok[0] == "0":
                continue  # 선행 0 금지 (0X는 교시 아님)
            val = int(tok)
            if val < MIN_PERIOD or val > MAX_PERIOD:
                continue
            if val <= prev:
                continue  # 같은 블록 내 교시는 강한 증가
            acc.append(val)
            rec(i + length, val, acc)
            acc.pop()

    rec(0, 0, [])
    if best is None:
        raise ValueError(
            f"교시 파싱 실패: {digits!r} — 유효한 분해(교시 {MIN_PERIOD}~{MAX_PERIOD}, "
            "강한 증가)가 없습니다. 역순 표기나 범위 초과(>MAX_PERIOD) 교시를 확인하세요."
        )
    return best


def parse_time_slots(raw: str) -> list[int]:
    """time_slots_raw 한 셀을 정렬된 정수 슬롯 리스트로 변환. 빈 값은 []."""
    raw = (raw or "").strip()
    if not raw:
        return []
    slots: set[int] = set()
    for block in raw.split(","):
        block = block.strip()
        if not block:
            continue
        m = _BLOCK_RE.match(block)
        if not m:
            raise ValueError(f"블록 형식 오류: {block!r} (원본 {raw!r})")
        day_idx = DAY_TO_IDX[m.group(1)]
        for period in tokenize_periods(m.group(2)):
            slots.add(day_idx * DAY_STRIDE + period)
    return sorted(slots)


def format_slots(slots: list[int]) -> str:
    """정수 슬롯 리스트를 CSV 셀 문자열로(콤마 구분, 공백 없음). 빈 리스트는 ''."""
    return ",".join(str(s) for s in slots)


def slot_to_human(slot: int) -> str:
    """슬롯 정수를 사람용 표기로 역변환(디버그/테스트용). 예) 73 → '금9'."""
    day_idx, period = divmod(slot, DAY_STRIDE)
    if day_idx not in IDX_TO_DAY:
        raise ValueError(f"슬롯 {slot}의 요일 인덱스 {day_idx}가 범위 밖입니다.")
    return f"{IDX_TO_DAY[day_idx]}{period}"


def slots_conflict(a: "list[int] | set[int]", b: "list[int] | set[int]") -> bool:
    """두 슬롯 집합이 시간 충돌(공유 슬롯 존재)하는지."""
    return bool(set(a) & set(b))


def process_csv(sections_path: Path, output_path: Path) -> dict:
    """course_section.csv를 읽어 time_slots_int 컬럼을 채워 output_path에 쓴다."""
    with sections_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"빈 CSV: {sections_path}")
        fieldnames = list(reader.fieldnames)
        if "time_slots_raw" not in fieldnames:
            raise ValueError("time_slots_raw 컬럼이 없습니다.")
        if "time_slots_int" not in fieldnames:
            fieldnames.insert(fieldnames.index("time_slots_raw") + 1, "time_slots_int")
        rows = list(reader)

    stats = {"total": 0, "filled": 0, "empty": 0, "errors": 0}
    error_samples: list[str] = []
    for row in rows:
        stats["total"] += 1
        raw = row.get("time_slots_raw", "")
        try:
            slots = parse_time_slots(raw)  # 이 호출만 ValueError를 던짐
        except ValueError as exc:
            stats["errors"] += 1
            row["time_slots_int"] = ""
            if len(error_samples) < 10:
                error_samples.append(str(exc))
            continue
        row["time_slots_int"] = format_slots(slots)
        if slots:
            stats["filled"] += 1
        else:
            stats["empty"] += 1

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    stats["error_samples"] = error_samples
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="time_slots_raw → time_slots_int 전처리")
    parser.add_argument("--sections", default="data/course_section.csv",
                        help="입력 course_section.csv 경로")
    parser.add_argument("--output", default=None,
                        help="출력 경로(기본: --sections와 동일, 제자리 갱신)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    sections_path = Path(args.sections)
    output_path = Path(args.output) if args.output else sections_path
    if not sections_path.exists():
        logger.error("입력 파일 없음: %s", sections_path)
        return 1

    try:
        stats = process_csv(sections_path, output_path)
    except OSError as exc:
        logger.error("파일 처리 실패: %s", exc)
        return 1
    logger.info(
        "처리 %d행 → time_slots_int 채움 %d / 빈 시간표 %d / 파싱오류 %d  (→ %s)",
        stats["total"], stats["filled"], stats["empty"], stats["errors"], output_path,
    )
    for sample in stats.get("error_samples", []):
        logger.warning("  파싱오류: %s", sample)
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
