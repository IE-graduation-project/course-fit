"""Recommendation → API 계약 JSON 직렬화.

**픽스처와 실 API의 단일 원천**(배포 설계 결정 ①). `web/scripts/dump_fixtures.py`가 이 모듈을
import하므로, 픽스처와 실 응답이 같은 코드에서 나오는 것이 구조적으로 보장된다. 두 벌로 두면
한쪽에 필드를 추가하고 다른 쪽을 잊는 일이 반드시 생긴다.

section 메타(교수·시간표원문·개설학과·이수구분)는 `data/course_section.csv`가 아니라 **DB의
course_section 테이블**에서 읽는다(결정 ②). 컨테이너 이미지에 CSV를 넣지 않기 위해서다.
"""
from __future__ import annotations

from dataclasses import dataclass

from recommender import data, params
from recommender.explain import COMP_KR
from recommender.recommend import Recommendation

# 슬롯 인코딩 — crawlers/courses/preprocess_time_slots.py와 동일 규약
DAY_STRIDE = 16
IDX_TO_DAY = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"}

# 진단에서 "충족"으로 볼 gap 하한. web/lib/competency.ts의 GAP_EPSILON과 같은 값이어야 한다.
GAP_EPSILON = 0.03
# 강점으로 표시할 σ 하한
STRENGTH_SIGMA = 0.5
# 역량 하나를 눌렀을 때 보여 줄 기여 과목 수
SOURCES_PER_COMP = 6

# ε 프리셋의 사용자 표시 문구. eps 값 자체는 recommend.PREFERENCE_EPS가 정본이다.
MODES = [
    {"id": "gap", "label": "역량 우선",
     "desc": "부족한 역량을 채우는 걸 최우선. 교양이어도 갭을 메우면 추천."},
    {"id": "balanced", "label": "균형",
     "desc": "역량과 졸업 진척을 함께. 기본값."},
    {"id": "graduation", "label": "졸업 우선",
     "desc": "졸업요건·전공 학점을 먼저 채움. 역량은 그 다음."},
]

# 표시용 영역 순서. db/ingest.VALID_AREAS와 달리 '교양총합'(상한만 있는 ceiling 요건)은 뺀다.
AREAS = ["교양필수", "특성화교양", "SW데이터활용역량", "공통교양",
         "전공기초영어", "전공필수", "전공선택", "일반선택", "MSC", "전공기초"]


def slot_human(slot: int) -> str:
    """정수 슬롯 → 사람이 읽는 표기. 18 → '화2'."""
    day, period = divmod(slot, DAY_STRIDE)
    return f"{IDX_TO_DAY[day]}{period}"


@dataclass
class RefData:
    """요청 간 변하지 않는 참조 데이터. 서버 기동 시 1회 로드해 재사용한다."""
    comp_ids: list[str]                 # 역량 taxonomy 순서
    comps: list[tuple[str, str]]        # (comp_id, comp_name 영문)
    jobs: list[tuple[str, str]]         # (job_id, job_name)
    programs: list[dict]                # 지원 학과 · 적용 시작 연도 (결정 ⑨)
    sec_meta: dict[tuple[str, str], dict]   # (course_id, section) -> 표시용 메타
    term: str                           # sec_meta 가 담고 있는 개설 학기


def load_ref_data(conn) -> RefData:
    """참조 데이터 1회 로드. 분반 메타는 DB 에 적재된 그 학기분만 담는다."""
    term = data.active_term(conn)
    return RefData(
        comp_ids=data.comp_ids(conn),
        comps=[(r[0], r[1]) for r in conn.execute("SELECT comp_id, comp_name FROM competency")],
        jobs=[(r[0], r[1]) for r in
              conn.execute("SELECT job_id, job_name FROM job ORDER BY job_id")],
        programs=load_programs(conn),
        sec_meta=load_section_meta(conn, term=term),
        term=term,
    )


def load_programs(conn) -> list[dict]:
    """지원 학과와 **적용 시작 연도**(결정 ⑨). 프론트 드롭다운의 원천.

    `fromYear ~ 현재 학년도`가 고를 수 있는 입학년도다. 연도 목록이 아니라 시작 연도를
    주는 이유는, 교육과정이 개정될 때까지 계속 적용되기 때문이다 — 목록으로 주면 개정될
    때마다 프론트를 고쳐야 한다.

    졸업요건이 없는 학과(COMMON)는 JOIN에서 자연히 빠진다.
    """
    return [
        {"dept": r[0], "name": r[1], "fromYear": r[2]}
        for r in conn.execute(
            """SELECT d.dept_id, d.dept_name, MIN(g.admission_year)
               FROM department d JOIN graduation_requirement g ON g.dept_id = d.dept_id
               GROUP BY d.dept_id, d.dept_name
               ORDER BY d.dept_id"""
        )
    ]


def load_section_meta(conn, *, term: str) -> dict[tuple[str, str], dict]:
    """(course_id, section) -> {professor, timeRaw, offeringDept, category}.

    빈 문자열은 None으로 접는다 — 계약상 이 넷은 nullable이고, 프론트는 null을 '미지정'으로
    그린다. ''를 그대로 주면 빈 칸이 그려진다.
    """
    return {
        (r[0], str(r[1]).strip()): {
            "professor": r[2] or None,
            "timeRaw": r[3] or None,
            "offeringDept": r[4] or None,
            "category": r[5] or None,
        }
        for r in conn.execute(
            "SELECT course_id, section, professor, time_slots_raw, offering_dept, category "
            "FROM course_section WHERE source_term = ?",
            (term,),
        )
    }


def job_fit(sigma: dict, rho: dict, comp_ids) -> float:
    """직무 적합도 0~100 — 학생의 지금 σ가 이 직무의 ρ를 얼마나 채우나.

    fit = 1 − Σ_k ρ_k·gap_k / Σ_k ρ_k   (gap = max(0, ρ−σ))

    갭을 ρ로 가중하는 이유: 그 직무가 중시하지 않는 축(ρ≈0)의 부족은 적합도를 깎으면 안 된다.
    시간표와 무관한 값이라 성향(ε)에 흔들리지 않는다 — 목표를 고르기 전에 비교하라고 있는 값이다.
    """
    denom = sum(rho.get(k, 0.0) for k in comp_ids)
    if denom <= 0:
        return 0.0
    penalty = sum(rho.get(k, 0.0) * max(0.0, rho.get(k, 0.0) - sigma[k]) for k in comp_ids)
    return round(max(0.0, min(1.0, 1 - penalty / denom)) * 100, 1)


def build_reference(ref: RefData) -> dict:
    """GET /api/reference — 드롭다운·라벨용 참조 데이터. 정적이라 캐시 가능."""
    from recommender.recommend import PREFERENCE_EPS
    return {
        "jobs": [{"id": j, "name": n} for j, n in ref.jobs],
        "competencies": [{"id": c, "nameKo": COMP_KR[c], "nameEn": n} for c, n in ref.comps],
        "modes": [{"id": m["id"], "eps": PREFERENCE_EPS[m["id"]],
                   "label": m["label"], "desc": m["desc"]} for m in MODES],
        "areas": list(AREAS),
        "programs": list(ref.programs),
    }


def sigma_sources(conn, contributions: dict[str, list[tuple[str, float]]], comp_ids,
                  *, limit: int = SOURCES_PER_COMP) -> dict[str, list[dict]]:
    """역량마다 σ 를 쌓은 기수강 과목 — 기여 큰 순 상위 limit 개와 그 몫(share).

    share = grade_factor·w / Σ(같은 역량의 기여). σ 는 이 합의 단조 함수라 몫이 곧
    「이 역량에 쌓인 것 중 이 과목 비중」이다. 키는 역량 전부이고 σ 가 0 이면 빈 목록이다 —
    학생마다 키가 달라지면 계약(픽스처 모양)이 학생에 따라 흔들린다.
    """
    ids = sorted({cid for k in comp_ids for cid, _ in contributions.get(k, [])})
    names = {}
    if ids:
        q = ",".join("?" * len(ids))
        names = {r["course_id"]: r["course_name"] for r in conn.execute(
            f"SELECT course_id, course_name FROM course WHERE course_id IN ({q})", ids)}
    out = {}
    for k in comp_ids:
        items = [(cid, v) for cid, v in contributions.get(k, []) if v > 0]
        total = sum(v for _, v in items)
        items.sort(key=lambda t: (-t[1], t[0]))
        out[k] = [{"courseId": cid, "name": names.get(cid, cid), "share": round(v / total, 4)}
                  for cid, v in items[:limit]]
    return out


def build_payload(conn, rec: Recommendation, ref: RefData, *, job_id: str, mode: str, eps: float,
                  alpha: float = params.ALPHA_DEFAULT, max_credits: int = 18,
                  min_credits: int = 12, top_k: int = 3) -> dict:
    """POST /api/recommend 응답. explain.build_explanation의 확장판.

    근거의 원천이 전부 모델 내부값이라 사후 합리화가 아니다 — careerReason은 Score_c의 축별
    분해(gap_k · w_{c,k}), gradReason은 그 영역의 남은 졸업 부족학점이다.
    """
    comp_ids = ref.comp_ids
    job_name = dict(ref.jobs).get(job_id, job_id)
    rho = data.load_rho(conn, job_id)

    # 계약: ILP가 못 풀면 500이 아니라 200 + timetables: []. 학생 입장에서 500은
    # "서비스 고장", 빈 결과는 "조건이 빡세다"라 화면 메시지가 달라야 한다.
    solved = [r for r in rec.results if r.status == "Optimal"]
    timetables = []
    for rank, res in enumerate(solved, 1):
        courses = []
        for c in sorted(res.selected,
                        key=lambda c: -sum(rec.gap[k] * c.weights.get(k, 0) for k in comp_ids)):
            contrib = sorted(((rec.gap[k] * c.weights.get(k, 0), k) for k in comp_ids), reverse=True)
            score = sum(v for v, _ in contrib)
            m = ref.sec_meta.get((c.course_id, str(c.section).strip()), {})
            courses.append({
                "courseId": c.course_id, "section": c.section, "name": c.course_name,
                "credit": c.credit, "area": c.area,
                "slots": list(c.slots),
                "slotsHuman": [slot_human(s) for s in c.slots],
                "professor": m.get("professor"), "timeRaw": m.get("timeRaw"),
                "offeringDept": m.get("offeringDept"), "category": m.get("category"),
                "score": round(score, 4),
                "careerReason": [
                    {"comp": k, "compKo": COMP_KR[k], "value": round(v, 4),
                     "share": round(v / score, 4) if score > 0 else 0}
                    for v, k in contrib if v > 0
                ][:3],
                "gradReason": {"area": c.area, "remaining": rec.need.get(c.area, 0)},
            })
        timetables.append({
            "rank": rank,
            "careerfit": round(res.careerfit, 4),
            "gradProgress": res.gradprogress,
            "totalCredit": res.total_credit,
            "status": res.status,
            "courses": courses,
        })

    payload = {
        "student": {"deptId": rec.dept_id, "admissionYear": rec.admission_year,
                    # 적용된 교육과정 연도. 입학년도와 다를 수 있어 화면에 고지한다(결정 ⑨).
                    "requirementYear": rec.requirement_year,
                    # 후보를 거른 학년(#42). 성적표의 마지막 학기에서 계산해 입학년도와 다를 수 있다.
                    "gradeLevel": rec.grade_level,
                    # 추천한 분반의 개설 학기("2026-2"). 화면이 「이번 학기」가 언제인지 밝힌다.
                    "term": data.active_term(conn)},
        "fitByJob": [{"job": jid, "name": jname,
                      "fit": job_fit(rec.sigma, data.load_rho(conn, jid), comp_ids)}
                     for jid, jname in ref.jobs],
        "job": {"id": job_id, "name": job_name},
        "params": {"mode": mode, "eps": eps, "alpha": alpha,
                   "maxCredits": max_credits, "minCredits": min_credits, "topK": top_k},
        "diagnosis": {
            "sigma": {k: round(rec.sigma[k], 4) for k in comp_ids},
            "rho": {k: round(rho.get(k, 0.0), 4) for k in comp_ids},
            "gap": {k: round(rec.gap[k], 4) for k in comp_ids},
            "strengths": [{"comp": k, "compKo": COMP_KR[k], "sigma": round(rec.sigma[k], 4)}
                          for k, _ in sorted(rec.sigma.items(), key=lambda x: -x[1])
                          if rec.gap[k] <= GAP_EPSILON and rec.sigma[k] >= STRENGTH_SIGMA],
            "gaps": [{"comp": k, "compKo": COMP_KR[k], "gap": round(rec.gap[k], 4)}
                     for k, _ in sorted(rec.gap.items(), key=lambda x: -x[1])
                     if rec.gap[k] > GAP_EPSILON],
            "sources": sigma_sources(conn, rec.contributions, comp_ids),
        },
        "need": {a: n for a, n in sorted(rec.need.items()) if n > 0},
        "timetables": timetables,
        "constraints": {"noTimeConflict": True, "creditBounds": True,
                        "excludeTaken": True, "prereqSatisfied": True,
                        # 후보집합에서 걸렀으니 구조적으로 참이다(data.load_candidates, #42)
                        "gradeEligible": True},
    }
    if not solved:
        # 못 푼 이유를 디버깅용으로만 덧붙인다. Optimal일 때는 넣지 않는다 —
        # 픽스처와의 스키마 동일성을 깨지 않기 위해서다.
        payload["solverStatus"] = rec.results[0].status if rec.results else "no_results"
    return payload
