"""
CSV -> SQLite 적재 모듈

Usage:
    python db/ingest.py             # CSV 적재 + 검증
    python db/ingest.py --reset     # DB 삭제 후 재생성
    python db/ingest.py --validate  # 적재 없이 검증만
"""

import argparse
import csv
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "app.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"
DATA_DIR = ROOT / "data"

# CSV 파일 적재 순서 -- FK 의존성 고려
LOAD_ORDER = [
    ("department",             "department.csv"),
    ("graduation_requirement", "graduation_requirement.csv"),
    ("competency",             "competency.csv"),
    ("course",                 "course.csv"),
    ("course",                 "course_crawled.csv"),  # 다년도 시간표 보강분 (이슈 #18)
    ("course_section",         "course_section.csv"),  # 개설 학기 분반/시간표 (FK: course 적재 후)
    ("job",                    "job.csv"),
    ("course_competency",      "course_competency.csv"),
    ("job_competency",         "job_competency.csv"),
]

# course.area enum (data/README.md와 동기화)
VALID_AREAS = {
    "교양필수", "특성화교양", "SW데이터활용역량", "공통교양",
    "전공기초영어", "전공필수", "전공선택", "일반선택",
    "MSC", "전공기초", "교양총합",
}


def init_schema(conn: sqlite3.Connection) -> None:
    """schema.sql 실행하여 빈 테이블 생성."""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def load_csv(conn: sqlite3.Connection, table: str, csv_path: Path) -> int:
    """CSV 파일을 테이블에 INSERT. 적재 행 수 반환."""
    if not csv_path.exists():
        print(f"  [SKIP] {csv_path.name} 파일 없음")
        return 0

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print(f"  [SKIP] {csv_path.name} 비어있음")
        return 0

    # 테이블에 실제 존재하는 컬럼만 적재 (CSV가 더 많은 컬럼을 가질 수 있음.
    # 예: course_section.csv 16컬럼 → 테이블 11컬럼. provenance 컬럼은 미저장)
    table_cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    csv_cols = list(rows[0].keys())
    cols = [c for c in csv_cols if c in table_cols]
    dropped = [c for c in csv_cols if c not in table_cols]
    if dropped:
        print(f"  [INFO] {csv_path.name}: 테이블에 없는 컬럼 제외 → {dropped}")

    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"

    count = 0
    for row in rows:
        # 빈 문자열은 NULL로 변환
        values = [row[c] if row[c] != "" else None for c in cols]
        try:
            conn.execute(sql, values)
            count += 1
        except sqlite3.IntegrityError as e:
            print(f"  [ERROR] {table} {count + 1}번째 행: {e}", file=sys.stderr)
            print(f"          행 내용: {row}", file=sys.stderr)
            raise
    conn.commit()
    print(f"  [OK]   {csv_path.name} → {table}: {count}행")
    return count


def validate(conn: sqlite3.Connection) -> list[str]:
    """무결성 검증. 에러 메시지 리스트 반환 (빈 리스트면 OK)."""
    errors: list[str] = []

    # 검증 2: course_competency.weight 합 ≤ 1.0 (= r_c relevance, 무관 과목은 0에 가까움)
    cur = conn.execute("""
        SELECT course_id, ROUND(SUM(weight), 4) AS total
        FROM course_competency
        GROUP BY course_id
        HAVING SUM(weight) > 1.0 + 0.01
    """)
    for row in cur:
        errors.append(
            f"course_competency: course_id={row[0]} weight 합={row[1]} (기대 ≤ 1.0)"
        )

    # 검증 4: course.area ∈ enum
    placeholders = ",".join(["?"] * len(VALID_AREAS))
    cur = conn.execute(
        f"SELECT DISTINCT area FROM course WHERE area NOT IN ({placeholders})",
        tuple(VALID_AREAS),
    )
    for row in cur:
        errors.append(f"course.area enum 위반: '{row[0]}'")

    # 검증 5: course.area가 해당 dept의 graduation_requirement에 존재 (warning)
    cur = conn.execute("""
        SELECT DISTINCT c.dept_id, c.area
        FROM course c
        WHERE NOT EXISTS (
            SELECT 1 FROM graduation_requirement g
            WHERE g.dept_id = c.dept_id AND g.area = c.area
        )
    """)
    for row in cur:
        print(
            f"  [WARN] dept={row[0]}의 졸업요건에 area='{row[1]}' 없음",
            file=sys.stderr,
        )

    # 검증 6: course.allowed_years 1~4 범위
    cur = conn.execute("SELECT course_id, allowed_years FROM course WHERE allowed_years IS NOT NULL")
    for course_id, years_str in cur:
        try:
            years = [int(y.strip()) for y in years_str.split(",")]
            if any(y < 1 or y > 4 for y in years):
                errors.append(f"course {course_id}: allowed_years 범위 위반 '{years_str}'")
        except ValueError:
            errors.append(f"course {course_id}: allowed_years 파싱 실패 '{years_str}'")

    # 검증 7: msc_subarea NOT NULL ⟹ area = 'MSC'
    cur = conn.execute("""
        SELECT course_id, area, msc_subarea FROM course
        WHERE msc_subarea IS NOT NULL AND area != 'MSC'
    """)
    for row in cur:
        errors.append(
            f"course {row[0]}: msc_subarea='{row[2]}'인데 area='{row[1]}' (기대 'MSC')"
        )

    # 검증 8: course_section 은 한 학기만 — 섞이면 같은 분반이 중복 후보가 되고
    # 분반 메타 dict((course_id, section) 2축)가 지난 학기 행으로 덮어써진다.
    terms = [r[0] for r in conn.execute(
        "SELECT DISTINCT source_term FROM course_section ORDER BY source_term")]
    if len(terms) != 1:
        errors.append(
            f"course_section.source_term 이 {len(terms)}종입니다: {terms} (기대 1종). "
            "학기 교체는 덮어쓰기여야 하고 누적이면 안 됩니다."
        )

    # 검증 9: 개설 분반의 과목이 카탈로그에 있나 (FK)
    # PRAGMA foreign_keys 가 꺼진 채 적재된 DB 도 여기서 걸린다.
    cur = conn.execute("""
        SELECT DISTINCT s.course_id FROM course_section s
        LEFT JOIN course c ON c.course_id = s.course_id
        WHERE c.course_id IS NULL
    """)
    orphans = [r[0] for r in cur]
    if orphans:
        errors.append(
            f"course_section: 카탈로그에 없는 course_id {len(orphans)}개 "
            f"(예: {orphans[:5]}). 새 학기 과목은 카탈로그 크롤·병합을 먼저 돌리세요."
        )

    # 검증 10: 개설 분반의 과목에 역량 가중치가 있나
    # 없으면 score_of 가 0.0 을 돌려주는데 그 0.0 은 "진로와 무관"이 아니라 "모른다"다.
    # 후보에서 빠지지도 않아서, 졸업학점만 채우는 과목이 진로 근거 없이 시간표에 들어간다.
    cur = conn.execute("""
        SELECT DISTINCT s.course_id FROM course_section s
        LEFT JOIN course_competency cc ON cc.course_id = s.course_id
        WHERE cc.course_id IS NULL
    """)
    unmapped = [r[0] for r in cur]
    if unmapped:
        errors.append(
            f"course_section: 역량 매핑이 없는 과목 {len(unmapped)}개 "
            f"(예: {unmapped[:5]}). mapping 파이프라인(01→03→04→05)을 다시 돌리세요."
        )

    # 검증 11: 시간표 원문은 있는데 파싱 결과가 비었나
    # NULL 은 "비대면·논문이라 시간 미지정"이라는 뜻이라, 파싱 실패가 NULL 로 들어가면
    # 시간충돌 제약에서 조용히 빠져 겹치는 시간표가 만들어진다.
    cur = conn.execute("""
        SELECT course_id, section, time_slots_raw FROM course_section
        WHERE COALESCE(TRIM(time_slots_raw), '') != ''
          AND COALESCE(TRIM(time_slots_int), '') = ''
    """)
    lost = cur.fetchall()
    if lost:
        sample = [f"{r[0]}-{r[1]}({r[2]})" for r in lost[:5]]
        errors.append(
            f"course_section: 시간표 원문이 있는데 교시 파싱이 빈 행 {len(lost)}개 "
            f"(예: {sample}). preprocess_time_slots 를 다시 돌리세요."
        )

    # 검증 12: 지정 학년이 비었거나 범위 밖인가 (#42)
    # 0 은 "학년 무관"이라는 뜻이라, 크롤러가 이 열을 빠뜨려 NULL·빈 값이 들어오면
    # 학년 제약이 조용히 풀려 1학년에게 4학년 전공이 추천된다.
    cur = conn.execute("""
        SELECT course_id, section, grade FROM course_section
        WHERE grade IS NULL OR grade NOT IN (0, 1, 2, 3, 4)
    """)
    bad = cur.fetchall()
    if bad:
        sample = [f"{r[0]}-{r[1]}({r[2]!r})" for r in bad[:5]]
        errors.append(
            f"course_section: 지정 학년이 비었거나 0~4 밖인 행 {len(bad)}개 "
            f"(예: {sample}). 시간표 크롤의 grade 열을 확인하세요."
        )

    return errors


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ingest(reset: bool) -> sqlite3.Connection:
    """schema 생성 + LOAD_ORDER 적재. reset=True면 기존 DB 삭제 후 재생성."""
    if reset and DB_PATH.exists():
        DB_PATH.unlink()
        print(f"[RESET] 기존 DB 삭제: {DB_PATH.name}")

    conn = connect()
    init_schema(conn)
    print("[SCHEMA] 테이블 생성 완료")

    total = 0
    for table, fname in LOAD_ORDER:
        total += load_csv(conn, table, DATA_DIR / fname)
    print(f"[LOAD] 총 {total}행 적재")
    return conn


def main() -> int:
    ap = argparse.ArgumentParser(description="CSV → SQLite 적재")
    ap.add_argument("--reset", action="store_true", help="DB 삭제 후 재생성")
    ap.add_argument("--validate", action="store_true", help="적재 없이 검증만")
    args = ap.parse_args()

    if args.validate:
        if not DB_PATH.exists():
            print(f"ERROR: DB 없음 ({DB_PATH}). 먼저 적재하세요.", file=sys.stderr)
            return 1
        conn = connect()
    else:
        conn = ingest(reset=args.reset)

    errors = validate(conn)
    conn.close()

    if errors:
        print(f"\n[검증 실패] {len(errors)}건:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("[검증 통과] 무결성 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())