"""추천 품질 자 — 변별력(#31)과 1학년 추천(#47)을 한 번에 잰다.

σ·ρ 계산을 바꾸는 수정은 한쪽만 보고 고치면 다른 쪽이 무너진다. 그래서 둘을 같은 자로 잰다.

1. 변별력 — 산업데이터공학과 학생이 과목을 쌓아 갈 때 직무 6개 적합도(0~100)의 최대−최소 격차.
   과목은 1학년 샘플(web/lib/sample.ts 의 IDE_2026) 다음에 산데공 전공·MSC 를 지정 학년 순으로
   붙인다. 격차가 기수강과 함께 무너지면 고학년일수록 「어느 직무가 맞나」를 못 가른다.
2. 1학년 추천 — 같은 샘플로 데이터 분석가 Score 상위 10과목. 창업·디자인 교양이 데이터 입문을
   밀어내는지 본다.
3. σ 타당성 — 1학년 7과목만 들은 학생의 머신러닝·프로그래밍 σ.

변형(variant)은 매핑 원본 가중치(load_weights top_k=None)·ρ 에 씌우는 함수다. 「원본」이 절단
전(#31 이전), 「배포」가 params.COURSE_TOP_K 절단이다. 새 후보도 여기 넣어 같은 자로 잰 뒤에
params.py / 매핑 파이프라인으로 옮긴다.

    python -m recommender.diagnose              # 원본·배포 + 후보 전부
    python -m recommender.diagnose --only 배포
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path
from typing import Callable

from . import data, params

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_TS = ROOT / "web" / "lib" / "sample.ts"
ARCHIVE = ROOT / "data" / "archive"
STEPS = (7, 10, 13, 16, 19, 22, 25, 28)   # 1학년 1학기(7) → 약 4학년
JOB = "DA"

Weights = dict[str, dict[str, float]]
Rho = dict[str, float]


# ── 입력 ─────────────────────────────────────────────────────────────────────
def _ide_sample_ids() -> list[str]:
    src = SAMPLE_TS.read_text(encoding="utf-8")
    body = re.search(r"const IDE_2026 = `(.*?)`;", src, re.S).group(1)
    return re.findall(r"^(\d{6})\t", body, re.M)


def _designated_grade(conn) -> dict[str, int]:
    """과목별 지정 학년 — 이번 학기 분반과 보관한 지난 학기 분반 중 가장 낮은 값. 0(무관)은 뺀다."""
    out: dict[str, int] = {}
    for cid, g in conn.execute("SELECT course_id, grade FROM course_section WHERE grade > 0"):
        out[cid] = min(g, out.get(cid, 9))
    import csv
    for p in ARCHIVE.glob("course_section.*.csv"):
        with p.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                g = int(r["grade"] or 0)
                if g > 0:
                    out[r["course_id"]] = min(g, out.get(r["course_id"], 9))
    return out


def curriculum(conn) -> list[str]:
    """1학년 샘플 → 산데공 전공·MSC 를 지정 학년, 학수번호 순으로. 역량 매핑이 있는 것만."""
    first = _ide_sample_ids()
    grade = _designated_grade(conn)
    mapped = {r[0] for r in conn.execute("SELECT DISTINCT course_id FROM course_competency")}
    rest = [
        cid for (cid,) in conn.execute(
            "SELECT course_id FROM course WHERE dept_id='IDE' "
            "AND area IN ('전공필수','전공선택','MSC') ORDER BY course_id")
        if cid in grade and cid in mapped and cid not in first
    ]
    rest.sort(key=lambda c: (grade[c], c))
    return first + rest


# ── 변형 ─────────────────────────────────────────────────────────────────────
def w_identity(w: Weights) -> Weights:
    return w


def w_threshold(t: float) -> Callable[[Weights], Weights]:
    def f(w: Weights) -> Weights:
        return {c: {k: v for k, v in d.items() if v >= t} for c, d in w.items()}
    f.__name__ = f"w≥{t}"
    return f


def w_topk(k: int) -> Callable[[Weights], Weights]:
    """배포 절단 함수(params.top_k_weights)를 그대로 부른다 — 자와 배포본이 갈라지지 않게."""
    def f(w: Weights) -> Weights:
        return {c: params.top_k_weights(d, k) for c, d in w.items()}
    f.__name__ = f"top{k}"
    return f


def r_identity(r: Rho) -> Rho:
    return r


def r_power(p: float) -> Callable[[Rho], Rho]:
    """ρ^p — 1위는 1 로 두고 2·3위를 낮춘다. min-max 가 3위를 0.95 로 부풀린 걸 되돌린다."""
    def f(r: Rho) -> Rho:
        return {k: v ** p for k, v in r.items()}
    f.__name__ = f"ρ^{p}"
    return f


VARIANTS: dict[str, tuple[Callable, Callable]] = {
    "원본": (w_identity, r_identity),
    "배포": (w_topk(params.COURSE_TOP_K), r_identity),
    "w≥0.05": (w_threshold(0.05), r_identity),
    "w≥0.10": (w_threshold(0.10), r_identity),
    "top2": (w_topk(2), r_identity),
    "ρ^2": (w_identity, r_power(2)),
    "top3+ρ^2": (w_topk(3), r_power(2)),
    "w≥0.10+ρ^2": (w_threshold(0.10), r_power(2)),
}


# ── 측정 ─────────────────────────────────────────────────────────────────────
def job_fit(sigma: dict[str, float], rho: Rho, comps: list[str]) -> float:
    """api.serialize.job_fit 과 같은 식 — 화면에 뜨는 0~100 적합도."""
    total = sum(rho.get(k, 0.0) for k in comps)
    if total <= 0:
        return 0.0
    gap = params.compute_gap(sigma, rho, comps)
    return 100.0 * (1.0 - sum(rho.get(k, 0.0) * gap[k] for k in comps) / total)


def measure(conn, wf: Callable, rf: Callable) -> dict:
    comps = data.comp_ids(conn)
    jobs = [r[0] for r in conn.execute("SELECT job_id FROM job ORDER BY job_id")]
    rhos = {j: rf(data.load_rho(conn, j)) for j in jobs}
    path = curriculum(conn)
    w_all = wf(data.load_weights(conn, path, top_k=None))

    spread = {}
    for n in STEPS:
        taken = path[:n]
        passed = {c: (4.0, 0) for c in taken}           # 전 과목 A0 — 성적 효과를 빼고 매핑만 본다
        sigma = params.compute_sigma(passed, {c: w_all.get(c, {}) for c in taken}, comps)
        fits = {j: job_fit(sigma, rhos[j], comps) for j in jobs}
        spread[n] = (max(fits.values()) - min(fits.values()), max(fits, key=fits.get))

    # 1학년 샘플 = path 앞 7개
    first = path[:7]
    sigma1 = params.compute_sigma({c: (4.0, 0) for c in first},
                                  {c: w_all.get(c, {}) for c in first}, comps)
    gap = params.compute_gap(sigma1, rhos[JOB], comps)
    cands = data.load_candidates(conn, "IDE", term=data.active_term(conn), grade=1)
    cw = wf(data.load_weights(conn, [c.course_id for c in cands], top_k=None))
    scored = sorted({(params.score_of(cw.get(c.course_id, {}), gap, comps), c.course_name)
                     for c in cands}, reverse=True)[:10]
    # 경영 샘플(BIZ_2022, 3학년 2학기까지)의 1위 직무 — 산데공 경로와 반대쪽 끝을 본다
    src = SAMPLE_TS.read_text(encoding="utf-8")
    biz = re.findall(r"^(\d{6})\t", re.search(r"const BIZ_2022 = `(.*?)`;", src, re.S).group(1), re.M)
    wb = wf(data.load_weights(conn, biz, top_k=None))
    sigb = params.compute_sigma({c: (4.0, 0) for c in biz if c in wb}, wb, comps)
    fb = {j: job_fit(sigb, rhos[j], comps) for j in jobs}

    return {"spread": spread, "sigma1": sigma1, "top10": scored,
            "startup": sum("창업" in name for _, name in scored),
            "path_len": len(path),
            "biz_top": max(fb, key=fb.get), "biz_spread": max(fb.values()) - min(fb.values())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", choices=list(VARIANTS))
    ap.add_argument("--db", default=str(data.DB_PATH))
    args = ap.parse_args()
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    names = [args.only] if args.only else list(VARIANTS)

    print(f"경로: 1학년 샘플 7과목 + 산데공 전공·MSC 지정 학년 순 (총 {len(curriculum(conn))}과목)")
    print(f"{'변형':<12}" + "".join(f"{n:>6}" for n in STEPS)
          + "   1학년 σ(ML,PROG)  DA상위10 창업   산데공 1위 직무(단계별)   경영샘플 1위·격차")
    for name in names:
        m = measure(conn, *VARIANTS[name])
        cells = "".join(f"{m['spread'][n][0]:>6.1f}" for n in STEPS)
        s = m["sigma1"]
        tops = "".join(f"{m['spread'][n][1]:<4}" for n in STEPS)
        print(f"{name:<12}{cells}   {s['ML']:.2f}, {s['PROG']:.2f}        {m['startup']}        "
              f"{tops}  {m['biz_top']} {m['biz_spread']:.1f}")
    if len(names) == 1:
        m = measure(conn, *VARIANTS[names[0]])
        print("\n1학년 DA Score 상위 10:")
        for sc, nm in m["top10"]:
            print(f"   {sc:.3f}  {nm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
