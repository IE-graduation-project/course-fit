"""recommender 데이터 접근 계층 — DB(app.db)에서 ILP 입력을 읽어 메모리 구조체로.

transcript 모듈을 import 하지 않으며, student/student_course 테이블을 통해서만 연결된다
(접점=DB). 읽는 것:
- 후보집합 C: course_section ⋈ course (dept∈{학생dept, COMMON} ∧ area≠일반선택)
- w_{c,k}: course_competency 의 과목별 상위 3역량 (#31),  ρ_k: job_competency
- 학생 기수강: student_course 단일 원천
    · σ·선수충족 = matched ∧ passed ∧ ¬superseded
    · 기이수학점(need) = area별 passed ∧ ¬superseded 합. 타 학과 전공 영역은 일반선택으로 (#40)
    · B1 = 전체 course_id
- min_credits_g: graduation_requirement,  선수: course.prerequisites,  시간슬롯: course_section
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from . import params

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "app.db"

EXCLUDED_CAND_AREAS = ("일반선택",)   # 후보집합 제외 (설계 1절)

# 학과마다 따로 정의되는 영역. 이름이 같아도 경영학과 「전공필수」와 산업데이터공학과
# 「전공필수」는 다른 요건이다 — 타 학과 과목이면 일반선택으로 인정한다(#40). 교양 영역
# (공통교양·교양필수·특성화교양 등)은 전교 공통이라 여기 넣지 않는다.
DEPT_SCOPED_AREAS = frozenset({"전공필수", "전공선택", "전공기초", "MSC"})
CROSS_DEPT_AREA = "일반선택"

# 단과대마다 따로 여는 교양필수 — 논리적사고와글쓰기(경영)·(공학)·(인문)·(법학)·(예술). 카탈로그에서
# 학과 것은 그 학과, 나머지는 COMMON 이라 걸러 주지 않으면 경영학과 학생에게 (법학)이 추천된다(#55).
# 괄호 안에 숫자가 있는 것(대학물리(2))은 순번이라 변형으로 보지 않는다.
_VARIANT_SUFFIX = re.compile(r"\([^()\d]+\)$")


def _variant_base(name: str) -> str | None:
    m = _VARIANT_SUFFIX.search(name)
    return name[:m.start()] if m else None


def active_term(conn) -> str:
    """DB 에 적재된 개설 학기. 둘 이상이면 즉시 실패한다.

    course_section 의 PK 는 (course_id, section, source_term) 3축인데 후보집합과 분반
    메타는 (course_id, section) 2축으로만 다룬다. 두 학기가 함께 적재되면 같은 키가
    겹쳐 조용히 덮어써지고 지난 학기 분반이 후보에 섞인다. 섞인 뒤에는 증상이
    "추천이 좀 이상하다"로만 보여서 추적이 어렵다 — 적재 단계에서 멈춘다.

    학기를 환경변수로 받지 않는 이유: 설정이 데이터와 어긋나면 후보가 0건이 되는데
    그 0건은 오류가 아니라 "이번 학기엔 들을 게 없다"처럼 보인다. 데이터에서 유도하면
    어긋날 자리가 없다.
    """
    terms = [r[0] for r in conn.execute(
        "SELECT DISTINCT source_term FROM course_section ORDER BY source_term")]
    if len(terms) != 1:
        raise ValueError(
            f"course_section 의 학기가 {len(terms)}개입니다: {terms}. "
            "이 파이프라인은 한 학기만 적재한다고 가정합니다 — 여러 학기를 함께 쓰려면 "
            "load_candidates·load_section_meta 에 term 을 명시해 호출하세요."
        )
    return terms[0]


@dataclass
class Candidate:
    course_id: str
    section: str
    course_name: str
    credit: int
    area: str
    slots: tuple[int, ...]        # 교시 인덱스. () = 시간 미지정(비대면/논문) → 충돌제약 자동 제외
    prereqs: tuple[str, ...]      # 선수 course_id들 (AND). () = 선수 없음
    weights: dict[str, float]     # comp_id -> weight (course_competency)


@dataclass
class Student:
    input_hash: str
    dept_id: str
    admission_year: int
    passed: dict[str, tuple[float | None, int]]  # course_id -> (grade, is_pn)  σ·선수충족 (student_course 필터)
    taken_ids: set[str]                     # 성적표 전체 course_id  B1 제외용 (student_course)
    earned_by_area: dict[str, int]          # area -> 기이수학점  need용 (student_course)
    weights: dict[str, dict[str, float]]    # passed course_id -> {comp_id: weight}  σ용
    current_grade: int | None = None        # 이번 학기 학년 (성적표 기준). None = 성적표에 정규학기 없음


def connect(db_path=DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _parse_slots(s: str | None) -> tuple[int, ...]:
    if not s:
        return ()
    return tuple(int(x) for x in s.split(",") if x.strip())


def _parse_prereqs(s: str | None) -> tuple[str, ...]:
    if not s:
        return ()
    return tuple(x.strip() for x in s.split(",") if x.strip())


def comp_ids(conn) -> list[str]:
    """역량 taxonomy 순서대로 comp_id."""
    return [r["comp_id"] for r in conn.execute("SELECT comp_id FROM competency")]


def load_weights(conn, course_ids, *, top_k: int | None = params.COURSE_TOP_K
                 ) -> dict[str, dict[str, float]]:
    """course_competency에서 주어진 과목들의 역량 가중치 (없으면 빈 dict → σ에 0 기여).

    σ(기수강)와 Score(후보) 모두 여기를 지나므로 상위 top_k 역량 절단(#31)도 여기서 한 번만
    건다. top_k=None 은 매핑 원본 그대로 — 전후 비교(recommender.diagnose)용.
    """
    out: dict[str, dict[str, float]] = {}
    ids = list(course_ids)
    if not ids:
        return out
    qmarks = ",".join("?" * len(ids))
    for r in conn.execute(
        f"SELECT course_id, comp_id, weight FROM course_competency WHERE course_id IN ({qmarks})",
        ids,
    ):
        out.setdefault(r["course_id"], {})[r["comp_id"]] = r["weight"]
    if top_k is None:
        return out
    return {cid: params.top_k_weights(w, top_k) for cid, w in out.items()}


def load_candidates(conn, dept_id: str, *, term: str, grade: int | None) -> list[Candidate]:
    """후보집합 C. 학생 dept 전공 + COMMON 교양, 일반선택 제외, 해당 학기 개설분, 수강 가능 학년만.

    ORDER BY 필수 — 이 순서가 ILP 결정변수 x_0..x_N의 번호를 정한다. 순서가 흔들리면
    동점 최적해 중 CBC가 고르는 해가 바뀌어 같은 입력에 다른 시간표가 나온다.
    ORDER BY 없는 SQL 결과 순서는 표준상 미보장이고, 인덱스 추가·VACUUM·DB 재생성으로
    실제로 바뀔 수 있다(컨테이너는 빌드마다 DB를 새로 만든다).

    `term` 은 기본값이 없다. 빠뜨리면 TypeError 로 즉시 죽는다 — 지난 학기 분반을
    추천하는 것보다 안 뜨는 편이 낫다. 값은 보통 `active_term(conn)` 으로 얻는다.

    `grade` 도 같은 이유로 기본값이 없다(#42). 분반의 지정 학년이 이 값 이하이거나 0(학년
    무관)인 분반만 남긴다 — 지정 학년 이상이면 수강 가능하다는 규칙이고, 카탈로그의
    allowed_years("3,4" 등)도 같은 규칙으로 만들어져 있다. 제약 없이 부르려면 None 을 명시한다.
    """
    depts = ["COMMON"] if dept_id == "COMMON" else [dept_id, "COMMON"]
    dep_q = ",".join("?" * len(depts))
    excl_q = ",".join("?" * len(EXCLUDED_CAND_AREAS))
    rows = conn.execute(
        f"""
        SELECT s.course_id, s.section, c.course_name, c.credit, c.area, c.dept_id,
               s.time_slots_int, c.prerequisites
        FROM course_section s
        JOIN course c ON c.course_id = s.course_id
        WHERE s.source_term = ?
          AND c.dept_id IN ({dep_q}) AND c.area NOT IN ({excl_q})
          AND (? IS NULL OR COALESCE(s.grade, 0) = 0 OR s.grade <= ?)
        ORDER BY s.course_id, s.section
        """,
        (term, *depts, *EXCLUDED_CAND_AREAS, grade, grade),
    ).fetchall()

    # 학생 학과에 같은 이름의 교양필수 변형이 있으면 다른 단과대 변형(COMMON)은 뺀다(#55).
    own = {_variant_base(n) for (n,) in conn.execute(
        "SELECT course_name FROM course WHERE dept_id = ? AND area = '교양필수'", (dept_id,))}
    own.discard(None)
    rows = [r for r in rows
            if not (r["area"] == "교양필수" and r["dept_id"] == "COMMON"
                    and _variant_base(r["course_name"]) in own)]

    weights = load_weights(conn, {r["course_id"] for r in rows})
    return [
        Candidate(
            course_id=r["course_id"],
            section=r["section"],
            course_name=r["course_name"],
            credit=r["credit"],
            area=r["area"],
            slots=_parse_slots(r["time_slots_int"]),
            prereqs=_parse_prereqs(r["prerequisites"]),
            weights=weights.get(r["course_id"], {}),
        )
        for r in rows
    ]


def _credited_area(area: str, course_dept: str | None, student_dept: str) -> str:
    """이 학생의 졸업요건에서 그 과목이 채우는 영역.

    student_course.area 는 카탈로그 영역을 그대로 복사한 값이라 개설 학과 기준이다.
    학생 학과 기준으로 옮기는 건 여기 한 곳에서만 한다. 카탈로그에 없는 과목
    (course_dept=None)은 적재 때 이미 일반선택 등으로 들어왔으니 그대로 둔다.
    """
    if course_dept in (None, student_dept, "COMMON"):
        return area
    return CROSS_DEPT_AREA if area in DEPT_SCOPED_AREAS else area


MAX_GRADE = 4   # transcript.parse_text.MAX_GRADE 와 같은 값 (이 모듈은 transcript 를 import 하지 않는다)


def grade_for_term(current_grade: int | None, admission_year: int, term: str) -> int:
    """추천 학기(`term`, 예: '2026-2')의 학년.

    성적표가 알려주는 학년(마지막 확정 학기의 다음 학기)을 우선한다 — 학생이 고른 입학년도는
    교육과정을 고르는 값이고, 휴학하면 학년과 어긋난다. 성적표에 정규학기가 하나도 없으면
    (신입생) 입학년도에서 센다.
    """
    if current_grade is not None:
        return current_grade
    year = int(term.split("-")[0])
    return max(1, min(MAX_GRADE, year - admission_year + 1))


def load_student(conn, input_hash: str) -> Student:
    srow = conn.execute(
        "SELECT input_hash, dept_id, admission_year, current_grade FROM student WHERE input_hash=?",
        (input_hash,),
    ).fetchone()
    if srow is None:
        raise ValueError(f"student 없음: input_hash={input_hash}")
    if srow["dept_id"] is None or srow["admission_year"] is None:
        raise ValueError(f"학생 dept/입학년도 미상 (성적표 매핑 실패): {input_hash}")

    # student_course 단일 원천에서 σ입력·기이수학점·B1을 한 번에 도출.
    passed: dict[str, tuple[float | None, int]] = {}
    best_cmp: dict[str, float] = {}     # 재시도 중 최고 성적 선택용 (P/N·None은 0으로 비교)
    taken_ids: set[str] = set()
    earned_by_area: dict[str, int] = {}
    for r in conn.execute(
        """SELECT sc.course_id, sc.area, sc.credit, sc.grade, sc.is_pn, sc.matched,
                  sc.passed, sc.superseded, c.dept_id AS course_dept
           FROM student_course sc LEFT JOIN course c ON c.course_id = sc.course_id
           WHERE sc.input_hash=?""",
        (input_hash,),
    ):
        cid = r["course_id"]
        if cid:
            taken_ids.add(cid)                         # B1: 성적표 전 과목 제외
        active = r["passed"] and not r["superseded"]
        if active and r["area"]:                       # need_g: area별 기이수학점
            area = _credited_area(r["area"], r["course_dept"], srow["dept_id"])
            earned_by_area[area] = earned_by_area.get(area, 0) + (r["credit"] or 0)
        if cid and r["matched"] and active:            # σ·선수충족: 매칭+이수+비대체
            cmp_g = 0.0 if (r["is_pn"] or r["grade"] is None) else r["grade"]
            if cid not in best_cmp or cmp_g > best_cmp[cid]:
                best_cmp[cid] = cmp_g
                passed[cid] = (r["grade"], r["is_pn"])

    return Student(
        input_hash=input_hash,
        dept_id=srow["dept_id"],
        admission_year=srow["admission_year"],
        passed=passed,
        taken_ids=taken_ids,
        earned_by_area=earned_by_area,
        weights=load_weights(conn, passed.keys()),
        current_grade=srow["current_grade"],
    )


def load_job_name(conn, job_id: str) -> str:
    """직무 한글명 (표시용). 없으면 job_id 그대로."""
    r = conn.execute("SELECT job_name FROM job WHERE job_id=?", (job_id,)).fetchone()
    return r["job_name"] if r else job_id


def load_rho(conn, job_id: str) -> dict[str, float]:
    """ρ_k — 목표 직무의 역량 요구수준 (job_competency)."""
    rows = conn.execute(
        "SELECT comp_id, required_level FROM job_competency WHERE job_id=?",
        (job_id,),
    ).fetchall()
    if not rows:
        raise ValueError(f"job 없음 또는 역량 미정의: job_id={job_id}")
    return {r["comp_id"]: r["required_level"] for r in rows}


def effective_year(conn, dept_id: str, admission_year: int) -> int | None:
    """이 학생에게 적용될 교육과정 개정 연도. 없으면 None.

    `graduation_requirement.admission_year`는 "그 연도 입학생만"이 아니라 **"그 연도부터
    다음 개정 전까지 적용"**이다(배포 설계 결정 ⑨). 대학의 실제 규칙이 그렇다 —
    경영 2022 교육과정은 22학번부터 계속 적용되고, 산데공 2026 과정은 26학번부터다.
    그래서 입학년도 **이하** 중 가장 최신 개정을 고른다.
    """
    r = conn.execute(
        "SELECT MAX(admission_year) FROM graduation_requirement "
        "WHERE dept_id=? AND admission_year<=?",
        (dept_id, admission_year),
    ).fetchone()
    return r[0] if r and r[0] is not None else None


def earliest_year(conn, dept_id: str) -> int | None:
    """이 학과가 지원하는 가장 이른 입학년도 (안내 메시지용). 없으면 None."""
    r = conn.execute(
        "SELECT MIN(admission_year) FROM graduation_requirement WHERE dept_id=?",
        (dept_id,),
    ).fetchone()
    return r[0] if r and r[0] is not None else None


def load_min_credits(conn, dept_id: str, admission_year: int) -> dict[str, int]:
    """영역별 최소학점. min_credits NULL(교양총합 cap)은 제외.

    적용 연도는 effective_year가 고른다(결정 ⑨).

    특성화교양·SW데이터활용역량은 매핑 과목이 0개라 후보에 없으므로 GradProgress에서
    자연히 무시된다(설계 3.5). 그래서 별도 필터 없이 둬도 무해하다.
    """
    year = effective_year(conn, dept_id, admission_year)
    if year is None:
        earliest = earliest_year(conn, dept_id)
        hint = (f"{earliest}학번부터 지원합니다" if earliest is not None
                else "졸업요건이 정의되지 않은 학과입니다")
        raise ValueError(
            f"졸업요건 없음: dept={dept_id}, year={admission_year} — {hint}")
    rows = conn.execute(
        """SELECT area, min_credits FROM graduation_requirement
           WHERE dept_id=? AND admission_year=? AND min_credits IS NOT NULL""",
        (dept_id, year),
    ).fetchall()
    return {r["area"]: r["min_credits"] for r in rows}
