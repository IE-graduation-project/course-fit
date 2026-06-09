"""성적표 PDF -> DB 적재 CLI (이슈 #16).

Usage:
    python -m transcript <성적표.pdf> [--db db/app.db]

선행: db/ingest.py로 seed + 스키마가 적재돼 있어야 한다(없으면 --init).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .load import DB_PATH, connect, ensure_schema, load_transcript
from .parse import parse_transcript


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="성적표 PDF 파싱 -> SQLite 적재")
    ap.add_argument("pdf", help="성적표 PDF 경로")
    ap.add_argument("--db", default=str(DB_PATH), help="SQLite DB 경로")
    ap.add_argument("--init", action="store_true", help="스키마 없으면 생성 후 적재")
    args = ap.parse_args(argv)

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"ERROR: PDF 없음: {pdf_path}", file=sys.stderr)
        return 1

    result = parse_transcript(pdf_path)

    conn = connect(args.db)
    if args.init:
        ensure_schema(conn)
    h = load_transcript(result, conn, source_file=pdf_path.name)
    conn.close()

    print(
        f"[OK] 적재 완료 input_hash={h} "
        f"(과목 {len(result.courses)}건, dept={result.meta.dept_id}, "
        f"입학={result.meta.admission_year})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
