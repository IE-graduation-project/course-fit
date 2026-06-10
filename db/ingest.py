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
    ("course_section",         "course_section.csv"),  # 2026-1 분반/시간표 (FK: course 적재 후)
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