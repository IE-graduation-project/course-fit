"""전학과 교육과정 판독(parsed/) + 졸업요건(grad_requirements.json) → 라이브 CSV 병합 (이슈 #57).

생성/갱신 대상 (repo 의 data/):
  department.csv · graduation_requirement.csv · course.csv · course_dept.csv

지상진실: IDE/BIZ 의 raw_area→area 매핑을 기준으로, 타 단과대 전용 area(교직·교양선택·기본소양
계열)만 norm_area 규칙으로 확장한다. area 에 따라 과목의 소속을 정한다.
  - 교양필수·공통교양·특성화교양·SW데이터활용역량·전공기초영어 = 전교/단과대 공통 → dept_id=COMMON
  - 전공필수·전공선택·전공기초·MSC = 학과 고유 → dept_id=code
  - 일반선택 = 후보 제외 영역 → course_dept 미생성(적재 때 자연히 일반선택 처리)

전공 total(T)은 전공필수+전공선택 합. 전공필수 min = 판독 is_major_required 학점 합,
전공선택 min = max(0, T - 전공필수).

멱등: 기존 data/*.csv 를 읽어 겹치지 않는 (course_id,dept_id)·dept·졸업요건 행만 append 한다.
실행: python data/curriculum_2026/load_all_departments.py
"""
import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent          # data/curriculum_2026
ROOT = HERE.parent.parent                         # repo 루트
DATA = ROOT / "data"

COURSE_COLS = ["course_id", "course_name", "credit", "prerequisites", "time_slots_raw",
               "time_slots_int", "semester", "is_pn", "is_certified_sw", "liberal_area"]
DEPT_COLS = ["course_id", "dept_id", "area", "is_major_required", "msc_subarea", "allowed_years"]

CODES = ["CE", "EE", "MSE", "CHE", "CSE", "IDE", "MSD", "BIZ", "ACM", "ASA", "PFA", "ELA", "IOT",
         "IRB", "SCD", "DEN", "BDB", "FMB", "DSC", "MAI", "HCS", "ARCH", "INT", "URB", "DAM", "ARM",
         "ENG", "GER", "FRE", "KOR", "LAW", "ECON", "MED", "KED", "EED", "HED", "EDU", "OKP", "PNT",
         "PRT", "SCU", "VCD", "IND", "MCD", "CGC", "WFU", "TFD", "ART", "MUS", "APM"]

COMMON_AREAS = {"교양필수", "공통교양", "특성화교양", "SW데이터활용역량", "전공기초영어"}


def norm_area(raw, is_major):
    raw = (raw or "").strip()
    if raw.startswith("전공필수"): return ("전공필수", "")
    if raw.startswith("전공선택"): return ("전공선택", "")
    if raw.startswith("전공기초영어"): return ("전공기초영어", "")
    if raw.startswith("전공기초"): return ("전공기초", "")
    if raw.startswith("MSC"):
        sub = "math" if "수학" in raw else "science" if "과학" in raw else "cs" if "전산" in raw else ""
        return ("MSC", sub)
    if raw.startswith("PBL"): return ("전공선택", "")          # IDE 지상진실: PBL1+1 → 전공선택
    if "교직" in raw: return ("전공필수" if is_major else "전공선택", "")  # 사범 교직 = 전공 트랙
    if "기초교양" in raw or raw == "기본소양": return ("교양필수", "")
    if "교양필수" in raw: return ("교양필수", "")
    if any(k in raw for k in ("핵심교양", "일반교양", "일반/핵심", "일반·핵심", "공통교양", "교양선택", "기본소양")):
        return ("공통교양", "")
    if raw.startswith("일반선택"): return ("일반선택", "")
    return ("일반선택", "")                                    # 미상 → 일반선택(후보 제외, 안전)


def cohort_year(s):
    m = re.search(r"(\d{4})학년도", s or "")
    return int(m.group(1)) if m else 2022


def main():
    # 기존 데이터 (겹침 방지)
    existing_cid = set()
    for fn in ["course.csv", "course_crawled.csv"]:
        for r in csv.DictReader(open(DATA / fn, encoding="utf-8")):
            existing_cid.add(r["course_id"])
    cd_existing = list(csv.DictReader(open(DATA / "course_dept.csv", encoding="utf-8")))
    existing_pair = {(r["course_id"], r["dept_id"]) for r in cd_existing}
    existing_dept = {r["dept_id"] for r in csv.DictReader(open(DATA / "department.csv", encoding="utf-8"))}
    gr_existing = list(csv.DictReader(open(DATA / "graduation_requirement.csv", encoding="utf-8")))
    existing_gr = {(r["dept_id"], r["admission_year"], r["area"]) for r in gr_existing}
    course_existing = list(csv.DictReader(open(DATA / "course.csv", encoding="utf-8")))
    dept_existing = list(csv.DictReader(open(DATA / "department.csv", encoding="utf-8")))

    GR = json.load(open(HERE / "grad_requirements.json", encoding="utf-8"))
    colleges, d2c, not_found = dict(GR["colleges"]), dict(GR["dept_to_college"]), set(GR["not_found"])

    # 졸업요건 미확보 6학과(ASA·ELA·BDB·FMB·MAI·HCS)는 선택지에서 뺀다.
    # 재조사 결과, 이 6개는 모두 **다전공형 융합전공**이라 독립 졸업학점이 없다 — 주전공(소속
    # 학과) 졸업요건을 채우면서 융합전공 교과목 36학점(중복 최대 12)을 더 듣는 구조다(정본
    # 『융합전공 이수내규』, 책자 융합전공 섹션 머리말의 "36학점 이상"). 따라서 "내 학과 졸업요건"을
    # 묻는 course-fit 의 주전공 선택지가 될 수 없다. ELA·BDB·FMB 는 세종캠이기도 하다.
    # 과목(course/course_dept)은 카탈로그에 남겨 공유 후보로 쓰되, graduation_requirement 를
    # 안 만들어 드롭다운(department ⋈ graduation_requirement)에서 자연히 빠진다.
    # 책자 page-26~28 이 자율전공 "주전공" 졸업요건(전공50·MSC24·총132)을 명시한 DEN·IOT·IRB·
    # SCD·DSC 는 정당한 주전공 경로가 있어 그대로 둔다(not_found 아님).
    # not_found = {ASA, ELA, BDB, FMB, MAI, HCS} 그대로 — 아무 추정도 적용하지 않는다.

    new_course, new_cd, new_dept, new_gr = [], [], [], []
    seen_course, seen_pair = set(), set()

    for code in CODES:
        path = HERE / "parsed" / f"{code}.json"
        if not path.exists():
            continue
        d = json.load(open(path, encoding="utf-8"))
        dept_name = d.get("dept") or code
        courses = [c for c in d.get("courses", []) if c.get("course_id")]

        major_req = 0
        for c in courses:
            cid = str(c["course_id"])
            area, sub = norm_area(c.get("raw_area"), c.get("is_major_required"))
            is_mr = 1 if c.get("is_major_required") else 0
            if area == "전공필수":
                major_req += int(c.get("credit") or 0)
            if cid not in existing_cid and cid not in seen_course:
                seen_course.add(cid)
                yr, sem = c.get("year"), c.get("semester")
                new_course.append({
                    "course_id": cid, "course_name": c.get("course_name"), "credit": c.get("credit"),
                    "prerequisites": "", "time_slots_raw": "", "time_slots_int": "",
                    "semester": f"{yr}-{sem}" if yr and sem else "", "is_pn": 0,
                    "is_certified_sw": 0, "liberal_area": "",
                })
            if area == "일반선택":
                continue
            tdept = "COMMON" if area in COMMON_AREAS else code
            key = (cid, tdept)
            if key in existing_pair or key in seen_pair:
                continue
            seen_pair.add(key)
            new_cd.append({"course_id": cid, "dept_id": tdept, "area": area,
                           "is_major_required": is_mr if tdept == code else 0,
                           "msc_subarea": sub, "allowed_years": ""})

        college = colleges.get(d2c.get(code, ""), {})
        total = college.get("total_credits") or 132
        if code not in existing_dept:
            new_dept.append({"dept_id": code, "dept_name": dept_name,
                             "total_credits_required": total})

        if code in not_found or not college:
            continue
        areas = college["areas"]
        exc = college.get("dept_exceptions", {}).get(code, {})
        year = cohort_year(college.get("cohort"))

        def put(area, mn, mx=""):
            if mn is None and mx == "":
                return
            if (code, str(year), area) in existing_gr:
                return
            new_gr.append({"dept_id": code, "admission_year": year, "area": area,
                           "min_credits": "" if mn is None else mn, "max_credits": mx})

        put("교양필수", areas.get("교양필수_기초교양", areas.get("교양필수")))
        put("공통교양", areas.get("공통교양"))
        put("특성화교양", areas.get("특성화교양"))
        put("SW데이터활용역량", areas.get("SW데이터활용역량"))
        put("전공기초영어", areas.get("전공기초영어"))
        put("MSC", exc.get("MSC", areas.get("MSC")))
        cap = areas.get("교양총합_상한")
        if cap is not None:
            put("교양총합", None, cap)
        T = exc.get("전공", areas.get("전공"))
        if T is not None:
            put("전공필수", major_req)
            put("전공선택", max(0, T - major_req))

    def write_merged(fn, cols, existing_rows, new_rows):
        with open(DATA / fn, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in existing_rows + new_rows:
                w.writerow({c: r.get(c, "") for c in cols})

    write_merged("department.csv", ["dept_id", "dept_name", "total_credits_required"], dept_existing, new_dept)
    write_merged("graduation_requirement.csv",
                 ["dept_id", "admission_year", "area", "min_credits", "max_credits"], gr_existing, new_gr)
    write_merged("course.csv", COURSE_COLS, course_existing, new_course)
    write_merged("course_dept.csv", DEPT_COLS, cd_existing, new_cd)
    print(f"신규 dept +{len(new_dept)} / grad_req +{len(new_gr)} / course +{len(new_course)} / course_dept +{len(new_cd)}")


if __name__ == "__main__":
    main()
