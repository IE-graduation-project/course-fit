"""이번 학기 수강가능 최대학점 — 클래스넷 「개인별 수강가능학점 조회」와 같은 식.

    금학기 신청가능 최대학점 = 금학기 이수한계 최대학점
                            + 직전학기 평점우수자 추가학점 (직전학기 평점 3.5(B+) 이상이면 3)
                            + 직전학기 이월학점 (직전학기 이수한계 − 직전학기 신청학점, 최대 2)

- 근거: 학사내규 제4조 ①(B+ 이상 3학점 초과), ⑦(부족분 최대 2학점 이월), 학칙 제49조(성적경고 =
  직전학기 평점 1.75 미만 또는 F 2과목 이상). 이월은 직전학기가 성적경고이거나 정규학기를 8학기
  이상 이수했으면 없다(클래스넷 화면의 산정 기준). 직전학기는 계절학기가 아닌 최근 정규학기다.
- 확인: 클래스넷이 경영 4학년 2학기 학생에게 18 + 3 + 2 = 23 을 보였고(직전 4-1 이수한계 19,
  신청 15, 평점 3.70), 이 식이 그 학생의 성적표만으로 같은 23 을 낸다(2026-09-30).
- 성적경고 학생은 대학장이 학점을 더 줄일 수 있다(내규 제4조 ⑤). 정해진 수가 없어 계산하지 않는다.
"""
from __future__ import annotations

from .models import StudentMeta

# 이수학점 한계 — 학과 교과과정표 맨 아래 「이수학점한계」 행, 학년별 (1학기, 2학기).
# 2026 교과과정 책자 경영-1·2(115~116쪽), 공-12·13(100~101쪽). 2022 책자도 같은 값이다.
SEMESTER_LIMIT = {
    "BIZ": {1: (18, 19), 2: (19, 19), 3: (19, 19), 4: (19, 18)},
    "IDE": {1: (19, 19), 2: (19, 19), 3: (19, 19), 4: (19, 19)},
}
DEFAULT_LIMIT = 18     # 표에 없는 학과
GPA_BONUS_MIN = 3.5
GPA_BONUS = 3
CARRY_MAX = 2
WARNING_F = 2          # 직전학기 F 가 이만큼이면 성적경고
WARNING_GPA = 1.75     # 직전학기 평점이 이보다 낮으면 성적경고
CARRY_MAX_TERMS = 8    # 4년제 8학기 이상 이수하면 이월 없음
MAX_LEVEL = 4


def semester_limit(dept_id: str | None, level: int, semester: int) -> int:
    table = SEMESTER_LIMIT.get(dept_id or "")
    if table is None:
        return DEFAULT_LIMIT
    return table[min(max(level, 1), MAX_LEVEL)][semester - 1]


def next_semester(level: int | None, semester: int | None) -> tuple[int, int]:
    """직전학기 (학년, 학기) → 이번 학기. 성적이 나온 학기가 없으면 1학년 1학기.
    4학년 2학기 다음(초과학기)은 표에 없어 4학년 2학기로 본다."""
    if level is None or semester is None:
        return 1, 1
    if semester == 1:
        return level, 2
    return (level + 1, 1) if level < MAX_LEVEL else (MAX_LEVEL, 2)


def credit_limit(meta: StudentMeta) -> dict:
    """성적표 메타 → {max, base, gpaBonus, carry, lastTerm, lastRegistered, lastGpa}.

    직전학기 요약(신청학점·신청평점)이 성적표에 없으면 가산 없이 이번 학기 이수한계만 준다.
    """
    last_sem = int(meta.last_term.split("-")[1]) if meta.last_term else None
    level, sem = next_semester(meta.last_term_level, last_sem)
    base = semester_limit(meta.dept_id, level, sem)

    gpa, registered = meta.last_term_gpa, meta.last_term_registered
    bonus = GPA_BONUS if gpa is not None and gpa >= GPA_BONUS_MIN else 0
    warned = meta.last_term_f_count >= WARNING_F or (gpa is not None and gpa < WARNING_GPA)
    carry = 0
    if registered is not None and not warned and meta.regular_term_count < CARRY_MAX_TERMS:
        prev = semester_limit(meta.dept_id, meta.last_term_level, last_sem)
        carry = max(0, min(CARRY_MAX, prev - registered))
    return {"max": base + bonus + carry, "base": base, "gpaBonus": bonus, "carry": carry,
            "lastTerm": meta.last_term, "lastRegistered": registered, "lastGpa": gpa}
