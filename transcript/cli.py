"""성적표 -> DB 적재 CLI (이슈 #16). 두 트랙 지원.

복붙(전체성적조회) 트랙:
    python -m transcript --text 성적.txt --dept BIZ --year 2022 [--student-no C0000] [--name 홍길동]

PDF 트랙(보수적 골격):
    python -m transcript --pdf 성적표.pdf --dept BIZ --year 2022

공통 옵션: --db db/app.db, --init (스키마 없으면 생성 후 적재)
선행: db/ingest.py로 seed + 스키마가 적재돼 있어야 한다(없으면 --init).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .load import DB_PATH, connect, ensure_schema, load_transcript
from .parse_text import parse_transcript_text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="성적표 파싱 -> SQLite 적재")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", metavar="FILE", help="전체성적조회 복붙 텍스트 파일")
    src.add_argument("--pdf", metavar="FILE", help="성적표 PDF (트랙 1, 미정)")
    ap.add_argument("--dept", help="학과 dept_id (예: BIZ, IDE)")
    ap.add_argument("--year", type=int, help="입학년도 (예: 2022)")
    ap.add_argument("--student-no", help="학번 (선택)")
    ap.add_argument("--name", help="성명 (선택)")
    ap.add_argument("--db", default=str(DB_PATH), help="SQLite DB 경로")
    ap.add_argument("--init", action="store_true", help="스키마 없으면 생성 후 적재")
    args = ap.parse_args(argv)

    if args.text:
        path = Path(args.text)
        if not path.exists():
            print(f"ERROR: 파일 없음: {path}", file=sys.stderr)
            return 1
        result = parse_transcript_text(
            path.read_text(encoding="utf-8"),
            dept_id=args.dept,
            admission_year=args.year,
            student_no=args.student_no,
            name=args.name,
        )
        source_file = path.name
        if args.dept is None:
            print("WARN: --dept 미지정 -> 졸업요건(need_g) 계산 불가", file=sys.stderr)
    else:
        from .parse import parse_transcript_pdf

        path = Path(args.pdf)
        if not path.exists():
            print(f"ERROR: 파일 없음: {path}", file=sys.stderr)
            return 1
        result = parse_transcript_pdf(
            path,
            dept_id=args.dept,
            admission_year=args.year,
            student_no=args.student_no,
            name=args.name,
        )
        source_file = path.name
        if args.dept is None:
            print("WARN: --dept 미지정 -> 졸업요건(need_g) 계산 불가", file=sys.stderr)

    conn = connect(args.db)
    if args.init:
        ensure_schema(conn)
    h = load_transcript(result, conn, source_file=source_file)
    conn.close()

    m = result.meta
    print(
        f"[OK] 적재 완료 input_hash={h} "
        f"(과목 {len(result.courses)}건, dept={m.dept_id}, 입학={m.admission_year}, "
        f"취득학점={m.total_earned}, 평점={m.gpa})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
