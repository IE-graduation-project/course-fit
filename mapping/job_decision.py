"""직무 선정: job_posting.csv → job.csv

`docs/직무_클러스터링_가이드.md` 의 7단계를 자동화한다.
대상 직무는 가이드와 `docs/역량_taxonomy_근거.md` 가 전제하는 4개:
DA / DS / PM / MKT.

산출물
- `data/job.csv`                 : 선정 직무 4개
- `data/job_posting.csv`         : 원본 보존 + job_id 갱신 (매핑 실패 = 빈 값)
- `data/job_posting_filtered.csv`: 매핑된 4개 직무 공고만
- `data/job_decision_report.json`: 분포 / 미매핑 표본 / 검증 결과

사용법
    python -m mapping.job_decision                   # 휴리스틱만
    python -m mapping.job_decision --llm             # OPENAI_API_KEY 있을 때 LLM fallback
    python -m mapping.job_decision --top 50          # 빈도 상위 N개 출력
    python -m mapping.job_decision --dry-run         # 파일 쓰지 않고 분포만 확인
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("job_decision")

# Exit codes
EXIT_OK = 0
EXIT_INPUT_NOT_FOUND = 2
EXIT_VALIDATION_FAILED = 3
EXIT_UNEXPECTED = 1

MIN_POSTINGS_PER_JOB = 20  # 가이드 권고 최소치

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SRC_POSTING = DATA / "job_posting.csv"
OUT_JOB = DATA / "job.csv"
OUT_FILTERED = DATA / "job_posting_filtered.csv"
OUT_REPORT = DATA / "job_decision_report.json"
OVERRIDES_CSV = Path(__file__).resolve().parent / "job_decision_overrides.csv"

TARGET_JOBS = [
    ("DA", "데이터 분석가"),
    ("DS", "데이터 사이언티스트"),
    ("PM", "프로덕트 매니저"),
    ("MKT", "마케팅 매니저"),
]
TARGET_IDS = [jid for jid, _ in TARGET_JOBS]

# raw_text 앞부분에서 추출할 라벨 패턴 (직무명 시그널이 강한 순)
# 부서/팀 라벨은 직무명이 아닐 가능성이 높아 제외 — 첫 segment fallback이 더 정확
LABEL_PATTERNS = [
    re.compile(r"직무\s*카테고리\s*[:：]\s*([^\n|]+)"),
    re.compile(r"포지션\s*[:：]\s*([^\n|]+)"),
    re.compile(r"직무\s*[:：]\s*([^\n|]+)"),
    re.compile(r"직군\s*[:：]\s*([^\n|]+)"),
    re.compile(r"채용분야\s*[:：]\s*([^\n|]+)"),
]

# 풀(pool)·다중직무 모집 차단 패턴 — 매칭되면 무조건 미분류
# (한 공고에 여러 직군이 묶여 있어서 특정 직무로 매핑하면 통계 왜곡)
POOL_RECRUIT_PATTERNS = [
    re.compile(r"인턴십\s*모집\s*\([^)]*[,/][^)]*\)"),
    re.compile(r"공개채용\s*\([^)]*외[^)]*\)"),
    re.compile(r"외\s*직무"),
    re.compile(r"인재\s*pool", re.IGNORECASE),
    re.compile(r"talent\s*pool", re.IGNORECASE),
    re.compile(r"부문별\s*경력사원\s*채용"),
    re.compile(r"수시\s*모집$|수시채용$"),
]

# 첫 segment가 이런 일반 단어/부서명이면 라벨 fallback 사용
GENERIC_FIRST_TOKENS = {
    "tech", "engineering", "finance", "hardware", "sales", "marketing",
    "business", "data", "development", "corporate", "logistics",
    "operations", "customer service", "management supporting",
    "토스코어", "토스증권", "토스뱅크", "토스플레이스", "토스페이먼츠",
    "토스인컴", "korea(hq)", "korea", "japan", "global",
}

BRACKET_PAT = re.compile(r"\[[^\]]*\]")
NORM_STRIP_PAT = re.compile(r"[\s_\-/·,()\[\]&>+]+")

# 키워드 매핑: 정규화된 후보 문자열 부분일치
# 순서가 우선순위 — 더 구체적인 키워드를 먼저 검사
JOB_KEYWORDS: dict[str, list[str]] = {
    "DA": [
        "데이터분석가", "데이터분석", "데이터어널리스트", "데이터애널리스트",
        "dataanalyst", "dataanalysis", "dataanalytics",
        "dataanalyticengineer", "dataanalyticsengineer",
        "bi애널리스트", "bianalyst", "bi분석가",
        "비즈니스애널리스트", "businessanalyst", "비즈니스분석가",
        "데이터analyst", "businessdevelopmentanalyst",
        "businessstrategicanalyst",
    ],
    "DS": [
        "데이터사이언티스트", "datascientist", "데이터과학자",
        "datascienceresearcher", "datasciencescientist",
        "머신러닝엔지니어", "machinelearningengineer", "mlengineer",
        "ml엔지니어", "ml리서치", "mlresearch", "mlresearcher",
        "mlplatform", "mldataengineer", "mlbackend", "mlbackendengineer",
        "ai엔지니어", "aiengineer", "appliedscientist",
        "ai개발자", "ai개발", "ai연구원", "ai연구개발",
        "ai모델개발", "aimodel", "researchscientist",
        "airesearch", "ai리서치", "airesearcher",
        "인공지능엔지니어", "딥러닝엔지니어", "deeplearningengineer",
        "데이터사이언스", "physicalai", "agenticai",
        "computationallinguist",
    ],
    "PM": [
        "프로덕트매니저", "productmanager", "프로덕트오너", "productowner",
        "서비스기획자", "서비스기획", "프로덕트기획",
        "프로덕트마케팅매니저", "productmarketingmanager",
        "productmanagement", "projectmanagement",
        "프로젝트매니저", "projectmanager",
        "사업pm", "개발pm", "기술pm", "운영pm", "마케팅pm",
        "프로젝트관리자",
    ],
    "MKT": [
        "마케팅매니저", "marketingmanager", "브랜드매니저", "brandmanager",
        "brandmanagement", "브랜드매니지먼트",
        "디지털마케팅", "digitalmarketing", "퍼포먼스마케팅", "performancemarketing",
        "그로스마케팅", "growthmarketing", "콘텐츠마케팅", "contentmarketing",
        "콘텐트마케팅",
        "crm마케팅", "performance마케터", "그로스마케터", "growthmarketer",
        "브랜드마케팅", "brandmarketing", "마케터", "marketer",
        "마케팅&커뮤니케이션", "marketing&communication",
        "marketing", "마케팅",
        "crmmarketing", "affiliatemarketing", "channelmarketing",
        "trademarketing", "retailmarketing", "influencermarketing",
        "productmarketing", "bizmarketing", "businessmarketing",
        "marketingofficer", "marketingspecialist",
        "marketingoperations", "marketingcommunication", "마케팅커뮤니케이션",
    ],
}

# 부정 키워드 — 이게 들어있으면 해당 job_id 매핑을 약화/차단
NEGATIVE_KEYWORDS: dict[str, list[str]] = {
    "PM": [
        "md", "머천다이저", "merchandiser",
        "현장pm", "건설pm", "건설", "조선", "안전관리", "산업설비",
        # 게임/엔터테인먼트 도메인 기획자(우리 PM과 다름) — title-only 매칭이므로 강함
        "게임기획", "전투기획", "밸런스기획", "콘텐츠기획자", "콘텐트기획",
        "시스템기획", "레벨디자인", "세계관기획", "시나리오기획",
        "bm기획", "설정기획자", "아트기획", "기획팀어시",
    ],
    "DS": [
        "백엔드", "backend", "프론트엔드", "frontend", "ios", "android",
        "infrastructure", "인프라", "devops", "데브옵스",
        "디자이너", "designer", "compiler", "컴파일러",
        "aml",  # Anti-Money Laundering: "AI"와 별개, 컴플라이언스 직무
        "growthsales", "salesintern", "salesmanager",
        "chiparchitect", "칩아키텍트",
        "platformengineer",  # 플랫폼 엔지니어는 SW (단 mlplatform은 keyword에서 명시적으로 잡힘)
        "infrastructureengineer", "ai플랫폼엔지니어",
    ],
    "MKT": [
        "designer", "디자이너", "graphicdesigner",
        "크리에이터", "creator", "영상크리에이터",
        "사무보조", "어시스턴트",
        "샵온라인",  # "카카오프렌즈샵 온라인 마케팅" 같은 케이스도 일단 어시스턴트는 부정
        "marketingdesigner",
    ],
    "DA": [
        "security", "보안", "compliance", "컴플라이언스", "threatanalyst",
        "financialanalyst", "financialanalysis", "financialplanning",
        "ITsupport", "itsupport",
        "vulnerabilityanalyst",
    ],
}


def strip_brackets(text: str) -> str:
    return BRACKET_PAT.sub(" ", text)


def extract_title_candidate(raw_text: str) -> str:
    """첫 segment에서 회사/부서 대괄호 토큰을 제거한 직무명 추출.
    첫 segment가 일반 단어/부서명이면 라벨('직무:', '직군:' 등)로 fallback.
    """
    if not isinstance(raw_text, str) or not raw_text.strip():
        return ""
    head = raw_text[:1500]
    first = re.split(r"[|\n]", head, maxsplit=1)[0]
    first_clean = strip_brackets(first).strip(" ,/>·\t")

    is_generic = (
        len(first_clean) < 4 or first_clean.lower() in GENERIC_FIRST_TOKENS
    )
    if not is_generic:
        return first_clean

    for pat in LABEL_PATTERNS:
        m = pat.search(head)
        if m:
            cand = strip_brackets(m.group(1)).strip(" ,/>·\t")
            if cand and len(cand) >= 3:
                return cand
    return first_clean


def normalize(text: str) -> str:
    return NORM_STRIP_PAT.sub("", text.lower())


def classify(title: str, raw_text: str = "") -> str | None:
    """title만으로 분류. raw_text는 사용하지 않음 (본문 매칭은 오분류율 ↑).
    풀(pool)·다중직무 공고는 무조건 None.
    """
    if not title:
        return None
    # 풀/다중직무 모집 차단 — title 또는 raw_text 앞부분에 패턴이 있으면 미분류
    head = raw_text[:300] if raw_text else ""
    for pat in POOL_RECRUIT_PATTERNS:
        if pat.search(title) or pat.search(head):
            return None
    norm_title = normalize(title)
    for job_id in TARGET_IDS:
        for kw in JOB_KEYWORDS[job_id]:
            if kw in norm_title:
                neg = NEGATIVE_KEYWORDS.get(job_id, [])
                if any(nk in norm_title for nk in neg):
                    break
                return job_id
    return None


def load_overrides() -> dict[str, str | None]:
    """mapping/job_decision_overrides.csv 가 있으면 posting_url → job_id 로드.
    job_id == 'NONE' 이면 None으로 변환 (강제 미분류).
    """
    if not OVERRIDES_CSV.exists():
        return {}
    try:
        df = pd.read_csv(OVERRIDES_CSV, dtype=str).fillna("")
    except Exception:
        return {}
    out: dict[str, str | None] = {}
    for _, r in df.iterrows():
        url = r.get("posting_url", "").strip()
        jid = r.get("job_id", "").strip().upper()
        if not url:
            continue
        out[url] = None if jid in ("", "NONE") else jid
    return out


# ----- LLM fallback (옵션) -----------------------------------------------

LLM_PROMPT = (
    "다음 채용공고가 어느 직무에 가장 가까운지 분류하세요.\n"
    "선택지: DA(데이터 분석가) / DS(데이터 사이언티스트/ML 엔지니어) / "
    "PM(프로덕트 매니저/서비스 기획) / MKT(마케팅 매니저)\n"
    "넷 다 아니면 NONE.\n"
    "답은 정확히 DA, DS, PM, MKT, NONE 중 하나의 단어만 출력.\n\n"
    "직무명 후보: {title}\n"
    "공고 발췌:\n{excerpt}"
)


def llm_classify(title: str, raw_excerpt: str) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None
    client = OpenAI(api_key=api_key)
    prompt = LLM_PROMPT.format(title=title, excerpt=raw_excerpt[:800])
    try:
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5.4-nano"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=4,
        )
        out = resp.choices[0].message.content.strip().upper()
        return out if out in set(TARGET_IDS) else None
    except Exception as e:
        print(f"  [llm error] {e}")
        return None


# ----- 메인 ---------------------------------------------------------------


def run(use_llm: bool = False, top: int = 30, dry_run: bool = False, llm_limit: int | None = None) -> dict:
    if not SRC_POSTING.exists():
        logger.error("입력 파일 없음: %s", SRC_POSTING)
        return {"ok": False, "reason": "input_not_found", "path": str(SRC_POSTING)}
    df = pd.read_csv(SRC_POSTING)
    logger.info("[입력] %s: %d건", SRC_POSTING.name, len(df))
    print(f"[입력] {SRC_POSTING.name}: {len(df):,}건")

    # Step 1: 직무명 후보 추출
    df["title_raw"] = df["raw_text"].fillna("").apply(extract_title_candidate)

    # Step 3: 빈도 분포 (정규화 전 raw 텍스트 기준)
    counts = df["title_raw"].value_counts().head(top)
    print(f"\n[Step 3] 직무명 후보 상위 {top} (raw):")
    for t, c in counts.items():
        print(f"  {c:5d}  {t[:80]}")

    # Step 4: 키워드 매핑
    df["job_id"] = [classify(t, r) for t, r in zip(df["title_raw"], df["raw_text"].fillna(""))]

    # Step 4a: override 적용 (수작업 큐레이션)
    overrides = load_overrides()
    override_applied = 0
    if overrides:
        for idx, url in df["posting_url"].items():
            if url in overrides:
                df.at[idx, "job_id"] = overrides[url]
                override_applied += 1
        print(f"\n[Step 4a] overrides 적용: {override_applied}건 ({len(overrides)} 등록 / {OVERRIDES_CSV.name})")

    pre_llm_unmapped = int(df["job_id"].isna().sum())

    # Step 4b: LLM fallback
    llm_calls = 0
    if use_llm:
        unmapped_idx = df.index[df["job_id"].isna()].tolist()
        if llm_limit is not None:
            unmapped_idx = unmapped_idx[:llm_limit]
        print(f"\n[LLM] 미매핑 {pre_llm_unmapped:,}건 중 {len(unmapped_idx):,}건 LLM 분류")
        for i, idx in enumerate(unmapped_idx, 1):
            res = llm_classify(df.at[idx, "title_raw"], str(df.at[idx, "raw_text"]))
            if res:
                df.at[idx, "job_id"] = res
            llm_calls += 1
            if i % 100 == 0:
                print(f"  {i}/{len(unmapped_idx)}")

    # 분포
    dist = Counter(df["job_id"].fillna("UNMAPPED"))
    print("\n[Step 4] 매핑 결과 분포:")
    for k in TARGET_IDS + ["UNMAPPED"]:
        v = dist.get(k, 0)
        flag = ""
        if k in TARGET_IDS:
            flag = "✅" if v >= 20 else "⚠️ (<20)"
        print(f"  {k:10s} {v:5d}  {flag}")

    # 미매핑 표본 (다음 라운드에서 키워드 보강 / LLM 진입 판단용)
    unmapped_sample = (
        df[df["job_id"].isna()]["title_raw"]
        .value_counts()
        .head(30)
        .to_dict()
    )

    # 검증: 직무별 최소 공고 수
    below_min = {jid: int(dist.get(jid, 0)) for jid in TARGET_IDS if dist.get(jid, 0) < MIN_POSTINGS_PER_JOB}
    if below_min:
        logger.warning("검증 미통과 — 직무별 최소 %d건 미달: %s", MIN_POSTINGS_PER_JOB, below_min)

    report = {
        "ok": not below_min,
        "input_rows": int(len(df)),
        "distribution": {k: int(v) for k, v in dist.items()},
        "pre_llm_unmapped": pre_llm_unmapped,
        "llm_calls": llm_calls,
        "unmapped_top30": unmapped_sample,
        "target_jobs": TARGET_JOBS,
        "min_postings_per_job": MIN_POSTINGS_PER_JOB,
        "validation_below_min": below_min,
    }

    if dry_run:
        print("\n[dry-run] 파일 쓰지 않음")
        return report

    # Step 5: job.csv
    pd.DataFrame(TARGET_JOBS, columns=["job_id", "job_name"]).to_csv(
        OUT_JOB, index=False, encoding="utf-8"
    )
    print(f"\n[Step 5] {OUT_JOB.name} 작성 ({len(TARGET_JOBS)}건)")

    # Step 6: 원본 갱신 (job_id 채움, 매핑 안된 행은 빈 값)
    out_cols = ["job_id", "source", "posting_url", "raw_text", "crawled_at"]
    df_out = df[out_cols].copy()
    df_out["job_id"] = df_out["job_id"].fillna("")
    df_out.to_csv(SRC_POSTING, index=False, encoding="utf-8")
    print(f"[Step 6] {SRC_POSTING.name} 갱신")

    df_filtered = df[df["job_id"].isin(TARGET_IDS)][out_cols].copy()
    df_filtered.to_csv(OUT_FILTERED, index=False, encoding="utf-8")
    print(f"[Step 6] {OUT_FILTERED.name} 작성 ({len(df_filtered):,}건)")

    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Report] {OUT_REPORT.name} 작성")

    return report


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--llm", action="store_true", help="OPENAI_API_KEY로 미매핑 건 LLM 분류")
    p.add_argument("--llm-limit", type=int, default=None, help="LLM 호출 건수 상한")
    p.add_argument("--top", type=int, default=30, help="빈도 표시 상위 N")
    p.add_argument("--dry-run", action="store_true", help="파일 쓰지 않음")
    p.add_argument("--strict", action="store_true",
                   help="직무별 공고 수 < %d 면 비-0 exit (CI/cron 용)" % MIN_POSTINGS_PER_JOB)
    p.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"),
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = p.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        report = run(use_llm=args.llm, top=args.top, dry_run=args.dry_run, llm_limit=args.llm_limit)
    except FileNotFoundError as e:
        logger.error("필요 파일 누락: %s", e)
        return EXIT_INPUT_NOT_FOUND
    except Exception as e:  # 의도적: 어떤 예외든 cron/CI에서 비-0 exit
        logger.exception("예기치 못한 오류: %s", e)
        return EXIT_UNEXPECTED

    if report.get("reason") == "input_not_found":
        return EXIT_INPUT_NOT_FOUND
    if args.strict and not report.get("ok", True):
        logger.error("--strict: 검증 미통과로 exit %d", EXIT_VALIDATION_FAILED)
        return EXIT_VALIDATION_FAILED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
