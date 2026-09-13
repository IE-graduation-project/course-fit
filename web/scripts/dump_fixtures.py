"""course-fit 실데이터 -> 프론트 픽스처(JSON) 덤프.

recommend.recommend()를 직무 6종 x 성향 3종으로 돌려 API 계약 형태의 JSON을 만든다.

직렬화는 `api/serialize.py`가 한다 — 실 API와 **같은 코드**다(배포 설계 결정 ①).
그래서 이 스크립트의 출력은 정의상 `POST /api/recommend` 응답과 같은 모양이다.

    python web/scripts/dump_fixtures.py <input_hash> <out_dir>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from api.serialize import build_payload, build_reference, load_ref_data  # noqa: E402
from recommender import data, params                                    # noqa: E402
from recommender.recommend import PREFERENCE_EPS, recommend             # noqa: E402

DB = str(ROOT / "db" / "app.db")
U, L, TOP_K = 18, 12, 3


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    input_hash, out_dir = sys.argv[1], Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = data.connect(DB)
    ref = load_ref_data(conn)
    write_json(out_dir / "reference.json", build_reference(ref))

    index = []
    for job_id, _job_name in ref.jobs:
        for mode, eps in PREFERENCE_EPS.items():
            rec = recommend(input_hash, job_id, db_path=DB,
                            U=U, L=L, alpha=params.ALPHA_DEFAULT, eps=eps, k=TOP_K)
            payload = build_payload(conn, rec, ref, job_id=job_id, mode=mode, eps=eps,
                                    alpha=params.ALPHA_DEFAULT,
                                    max_credits=U, min_credits=L, top_k=TOP_K)
            name = f"{job_id}_{mode}.json"
            write_json(out_dir / name, payload)
            n = len(payload["timetables"][0]["courses"]) if payload["timetables"] else 0
            index.append({"job": job_id, "mode": mode, "file": name, "nCourses": n})
            print(f"  {name}  과목 {n} · 대안 {len(payload['timetables'])}")
    conn.close()

    write_json(out_dir / "index.json", index)

    # 검증 — 조용한 실패 금지
    assert len(index) == 18, f"픽스처 18개여야 하는데 {len(index)}개"
    assert all(e["nCourses"] > 0 for e in index), "빈 시간표가 있다"
    print(f"OK  픽스처 {len(index)}개 + reference.json -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
