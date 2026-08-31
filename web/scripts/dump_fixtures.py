"""course-fit 실데이터 -> 프론트 픽스처(JSON) 덤프.

recommend.recommend() 를 직무 6종 x 성향 3종으로 돌려 API 계약 형태의 JSON 을 만든다.
이 스크립트의 출력 스키마 = web/ 이 기대하는 API 응답 스키마 = 백엔드가 구현할 계약.

    python dump_fixtures.py <input_hash> <out_dir>
"""
import csv
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from recommender import data, params                      # noqa: E402
from recommender.explain import COMP_KR, build_explanation  # noqa: E402
from recommender.recommend import PREFERENCE_EPS, recommend  # noqa: E402

DAY_STRIDE = 16
IDX_TO_DAY = {0: "월", 1: "화", 2: "수", 3: "목", 4: "금", 5: "토", 6: "일"}


def slot_human(slot: int) -> str:
    day, period = divmod(slot, DAY_STRIDE)
    return f"{IDX_TO_DAY[day]}{period}"


def load_section_meta() -> dict:
    """(course_id, section) -> {professor, timeRaw, offeringDept, category}"""
    meta = {}
    with open(ROOT / "data" / "course_section.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            meta[(row["course_id"], str(row["section"]).strip())] = {
                "professor": row["professor"] or None,
                "timeRaw": row["time_slots_raw"] or None,
                "offeringDept": row["offering_dept"] or None,
                "category": row["category"] or None,
            }
    return meta


def job_fit(sigma: dict, rho: dict, comp_ids) -> float:
    """직무 적합도 0~100 — 학생의 지금 σ 가 이 직무의 ρ 를 얼마나 채우나.

    fit = 1 − Σ_k ρ_k·gap_k / Σ_k ρ_k   (gap = max(0, ρ−σ))

    갭을 ρ 로 가중하는 이유: 그 직무가 중시하지 않는 축(ρ≈0)의 부족은
    적합도를 깎으면 안 된다. 시간표와 무관한 값이라 성향(ε)에 흔들리지 않는다.
    """
    denom = sum(rho.get(k, 0.0) for k in comp_ids)
    if denom <= 0:
        return 0.0
    penalty = sum(rho.get(k, 0.0) * max(0.0, rho.get(k, 0.0) - sigma[k]) for k in comp_ids)
    return round(max(0.0, min(1.0, 1 - penalty / denom)) * 100, 1)


def main() -> int:
    input_hash, out_dir = sys.argv[1], Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    sec_meta = load_section_meta()

    conn = data.connect(str(ROOT / "db" / "app.db"))
    comp_ids = data.comp_ids(conn)
    jobs = [(r[0], r[1]) for r in conn.execute("SELECT job_id, job_name FROM job ORDER BY job_id")]
    comps = [(r[0], r[1]) for r in conn.execute("SELECT comp_id, comp_name FROM competency")]
    conn.close()

    # ── 참조 데이터 ────────────────────────────────────────────
    (out_dir / "reference.json").write_text(json.dumps({
        "jobs": [{"id": j, "name": n} for j, n in jobs],
        "competencies": [{"id": c, "nameKo": COMP_KR[c], "nameEn": n} for c, n in comps],
        "modes": [
            {"id": "gap", "eps": 0.0, "label": "역량 우선",
             "desc": "부족한 역량을 채우는 걸 최우선. 교양이어도 갭을 메우면 추천."},
            {"id": "balanced", "eps": 0.3, "label": "균형",
             "desc": "역량과 졸업 진척을 함께. 기본값."},
            {"id": "graduation", "eps": 0.6, "label": "졸업 우선",
             "desc": "졸업요건·전공 학점을 먼저 채움. 역량은 그 다음."},
        ],
        "areas": ["교양필수", "특성화교양", "SW데이터활용역량", "공통교양",
                  "전공기초영어", "전공필수", "전공선택", "일반선택", "MSC", "전공기초"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    index = []
    for job_id, job_name in jobs:
        for mode, eps in PREFERENCE_EPS.items():
            rec = recommend(input_hash, job_id, db_path=str(ROOT / "db" / "app.db"),
                            U=18, L=12, alpha=params.ALPHA_DEFAULT, eps=eps, k=3)
            expl = build_explanation(rec, job_name)

            conn = data.connect(str(ROOT / "db" / "app.db"))
            rho = data.load_rho(conn, job_id)
            conn.close()

            timetables = []
            for rank, res in enumerate(rec.results, 1):
                courses = []
                for c in sorted(res.selected,
                                key=lambda c: -sum(rec.gap[k] * c.weights.get(k, 0) for k in comp_ids)):
                    contrib = sorted(((rec.gap[k] * c.weights.get(k, 0), k) for k in comp_ids),
                                     reverse=True)
                    score = sum(v for v, _ in contrib)
                    m = sec_meta.get((c.course_id, str(c.section).strip()), {})
                    assert m, f"section meta 못 찾음: {c.course_id}-{c.section}"
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

            conn = data.connect(str(ROOT / "db" / "app.db"))
            fit_by_job = [
                {"job": jid, "name": jname,
                 "fit": job_fit(rec.sigma, data.load_rho(conn, jid), comp_ids)}
                for jid, jname in jobs
            ]
            conn.close()

            payload = {
                "student": {"deptId": rec.dept_id, "admissionYear": rec.admission_year},
                "fitByJob": fit_by_job,
                "job": {"id": job_id, "name": job_name},
                "params": {"mode": mode, "eps": eps, "alpha": params.ALPHA_DEFAULT,
                           "maxCredits": 18, "minCredits": 12, "topK": 3},
                "diagnosis": {
                    "sigma": {k: round(rec.sigma[k], 4) for k in comp_ids},
                    "rho": {k: round(rho.get(k, 0.0), 4) for k in comp_ids},
                    "gap": {k: round(rec.gap[k], 4) for k in comp_ids},
                    "strengths": [{"comp": k, "compKo": COMP_KR[k], "sigma": round(rec.sigma[k], 4)}
                                  for k, _ in sorted(rec.sigma.items(), key=lambda x: -x[1])
                                  if rec.gap[k] <= 0.03 and rec.sigma[k] >= 0.5],
                    "gaps": [{"comp": k, "compKo": COMP_KR[k], "gap": round(rec.gap[k], 4)}
                             for k, _ in sorted(rec.gap.items(), key=lambda x: -x[1])
                             if rec.gap[k] > 0.03],
                },
                "need": {a: n for a, n in sorted(rec.need.items()) if n > 0},
                "timetables": timetables,
                "constraints": {"noTimeConflict": True, "creditBounds": True,
                                "excludeTaken": True, "prereqSatisfied": True},
            }
            name = f"{job_id}_{mode}.json"
            (out_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
            index.append({"job": job_id, "mode": mode, "file": name,
                          "nCourses": len(timetables[0]["courses"])})
            print(f"  {name}  과목 {len(timetables[0]['courses'])} · 대안 {len(timetables)}")

    (out_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2),
                                        encoding="utf-8")

    # 검증 — 조용한 실패 금지
    assert len(index) == 18, f"픽스처 18개여야 하는데 {len(index)}개"
    assert all(e["nCourses"] > 0 for e in index), "빈 시간표가 있다"
    print(f"OK  픽스처 {len(index)}개 + reference.json -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
