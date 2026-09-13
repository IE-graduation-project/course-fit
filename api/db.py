"""DB 경로 해석과 커넥션 — 읽기전용 시드와 쓰기 가능 사본을 분리한다.

무료 호스팅에는 영구 디스크가 없다. 그래서 시드 DB(CSV에서 빌드한 과목·역량·졸업요건)는
이미지에 구워 읽기 전용으로 두고, 기동할 때 쓰기 가능한 위치(/tmp)로 복사해 거기에 성적표를
적재한다. 재시작하면 학생 데이터는 사라진다 — 데모에서는 의도된 동작이다(성적표는 개인정보라
서버에 영구 보관하지 않는다). 배포 설계 §1.3.

로컬 개발에서는 둘 다 지정하지 않으면 db/app.db를 직접 쓴다.

    COURSE_FIT_SEED_DB   이미지에 구운 읽기전용 시드 (예: /app/db/app.db)
    COURSE_FIT_DB        실제로 열고 쓸 경로        (예: /tmp/app.db)
    COURSE_FIT_TTL_HOURS 성적표 보관 시간 (기본 24, 0이면 삭제 안 함 — 로컬 개발용)
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "db" / "app.db"
DEFAULT_TTL_HOURS = 24

# 쓰기 락 대기. 데모 규모(동시 수 명)에서 CBC 풀이 중 겹치는 INSERT를 흡수할 만큼.
BUSY_TIMEOUT_SEC = 10


def db_path() -> Path:
    """서버가 열어서 읽고 쓰는 DB 경로."""
    return Path(os.environ.get("COURSE_FIT_DB") or DEFAULT_DB)


def seed_path() -> Path | None:
    """이미지에 구워진 읽기전용 시드. 미지정이면 None (로컬 개발)."""
    v = os.environ.get("COURSE_FIT_SEED_DB")
    return Path(v) if v else None


def ttl_hours() -> int:
    return int(os.environ.get("COURSE_FIT_TTL_HOURS") or DEFAULT_TTL_HOURS)


def ensure_db() -> Path:
    """기동 시 1회. 시드가 있고 쓰기 사본이 없으면 복사한다. 최종 경로를 돌려준다."""
    target, seed = db_path(), seed_path()
    if seed is not None and not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(seed, target)
    if not target.exists():
        raise RuntimeError(
            f"DB 없음: {target}. 로컬이면 `python db/ingest.py --reset`을 먼저 실행하고, "
            f"컨테이너면 COURSE_FIT_SEED_DB 를 확인하세요."
        )
    return target


def connect() -> sqlite3.Connection:
    """API용 커넥션. recommender.data.connect와 달리 쓰기 락 대기시간을 준다."""
    conn = sqlite3.connect(str(db_path()), timeout=BUSY_TIMEOUT_SEC)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def purge_expired(conn: sqlite3.Connection, hours: int | None = None) -> int:
    """TTL 지난 성적표를 삭제한다(결정 ⑧). 삭제된 학생 수를 돌려준다.

    "성적표는 24시간 내 자동 삭제된다"는 고지를 **사실로 만드는** 장치다. 재시작으로만
    사라진다면 컨테이너가 며칠 사는 동안 남아 있어 그 진술이 부정확해진다.

    created_at은 UTC ISO8601 고정 포맷이라 문자열 비교로 시각 비교가 된다.
    student_course를 먼저 지운다(FK).
    """
    h = ttl_hours() if hours is None else hours
    if h <= 0:
        return 0        # 0이면 보관 무기한 — 로컬 개발용. 배포에서는 절대 0으로 두지 않는다.
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=h)).isoformat()
    conn.execute(
        "DELETE FROM student_course WHERE input_hash IN "
        "(SELECT input_hash FROM student WHERE created_at < ?)", (cutoff,))
    n = conn.execute("DELETE FROM student WHERE created_at < ?", (cutoff,)).rowcount
    conn.commit()
    return n
