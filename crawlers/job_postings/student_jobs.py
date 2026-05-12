"""링커리어 + 자소설닷컴 학부생 채용·공채 메타데이터 fetcher.

학부생 페르소나 직접 매칭 — 두 사이트는 dataset 단계에서 이미 공채 일정 + 인턴
+ 자소서 트랙으로 정렬됨. 일반 사이트의 "신입" 필터(경력 무관 혼재) 와 차별.

robots.txt 직접 확인 (2026-05-10):
    linkareer — `/stem/learn/*` 외 채용 경로 Allow.
    jasoseol — `/crt/*`, `/core`, `/webview/`, `/demo/` 외 Allow.

추출 방식 (둘 다 SPA + SSR Next dehydration):
    링커리어 — `/list/{recruit,intern}?page=N` 의 NEXT_DATA `__APOLLO_STATE__`
        에 Activity 24건/페이지 메타 인라인 (회사·Category·지역·마감 등).
        본문 detailText 는 list 에서 None — 메타만.
    자소설닷컴 — `/sitemap/{,intern_}employment_companies.xml` 이 lastmod
        내림차순. 각 `/recruit/{id}` 의 NEXT_DATA `initialEmploymentCompany`
        에 회사·일정·employments 메타 인라인.
        ⚠️ 자소서 본문(문항·답변)은 client fetch + ToS 상업이용 금지로 의도적 제외.

사이트당 최대 100건. polite_sleep 2초.
"""
from __future__ import annotations

import html as _html
import json
import re
import sys
from datetime import datetime, timezone
from typing import Any

from crawlers.job_postings._common import (
    html_to_text,
    http_get,
    make_record,
    polite_sleep,
)


STUDENT_INTERVAL_SEC = 2.0
MAX_PER_SITE = 100
MIN_RAW_TEXT_LEN = 80


def _extract_next_data(html: str) -> dict | None:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', html, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _epoch_ms_to_date(ms: Any) -> str:
    if not isinstance(ms, (int, float)) or ms <= 0:
        return ""
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OSError, OverflowError, ValueError):
        return ""


def _iso_to_date(s: Any) -> str:
    return s[:10] if isinstance(s, str) and len(s) >= 10 else ""


# --- 1. 링커리어 (linkareer.com) -------------------------------------------

LK_LIST_URLS = (
    "https://linkareer.com/list/recruit",
    "https://linkareer.com/list/intern",
)
LK_ACTIVITY = "https://linkareer.com/activity/{aid}"
LK_PAGES_PER_LIST = 3  # 24건/페이지 * 3 * 2 list = ~144 → 100 cap


def _lk_resolve_refs(refs: Any, ap: dict) -> list[str]:
    """`[{'__ref':'Category:56'}, ...]` → name 배열."""
    out: list[str] = []
    if not isinstance(refs, list):
        return out
    for r in refs:
        if isinstance(r, dict) and "__ref" in r:
            obj = ap.get(r["__ref"]) or {}
            v = obj.get("name")
            if isinstance(v, str) and v.strip():
                out.append(v.strip())
    return out


def _lk_build_record(activity: dict, ap: dict) -> dict | None:
    aid = activity.get("id")
    if not aid:
        return None
    title = (activity.get("title") or "").strip()
    org = (activity.get("organizationName") or "").strip()
    job_types = activity.get("jobTypes") or []
    rtype = (activity.get("recruitType") or "").strip()
    body = ""
    dt = activity.get("detailText")
    if isinstance(dt, dict) and "__ref" in dt:
        raw_html = (ap.get(dt["__ref"]) or {}).get("text") or ""
        if raw_html:
            body = html_to_text(_html.unescape(raw_html))

    # title 이 이미 `[회사명]` 으로 시작하면 prefix 중복 방지.
    head = title if (org and title.startswith(f"[{org}]")) else \
        (f"[{org}] {title}" if org else (title or org))
    lines: list[str] = [head]
    for label, val in (
        ("직군", " / ".join(_lk_resolve_refs(activity.get("categories"), ap)[:5])),
        ("지원자격", ", ".join(j for j in job_types if isinstance(j, str))
            if isinstance(job_types, list) else ""),
        ("경력", rtype if rtype and rtype != "NORMAL" else ""),
        ("기업유형", (activity.get("organizationType") or "").strip()),
        ("근무지", " / ".join(_lk_resolve_refs(activity.get("regions"), ap)[:3])),
        ("대상", " / ".join(_lk_resolve_refs(activity.get("targets"), ap)[:3])),
        ("관심분야", " / ".join(_lk_resolve_refs(activity.get("interests"), ap)[:3])),
        ("기술스택", " / ".join(_lk_resolve_refs(activity.get("skills"), ap)[:5])),
        ("마감", _epoch_ms_to_date(activity.get("recruitCloseAt"))),
    ):
        if val:
            lines.append(f"{label}: {val}")
    header = "\n".join(ln for ln in lines if ln)
    raw_text = f"{header}\n\n{body}".strip() if body else header
    if len(raw_text) < MIN_RAW_TEXT_LEN:
        raw_text = f"{raw_text}\nactivityId: {aid}"
    return make_record(
        source="Linkareer",
        posting_url=LK_ACTIVITY.format(aid=aid),
        raw_text=raw_text,
    )


def _lk_collect(list_url: str, max_pages: int) -> list[tuple[dict, dict]]:
    out: list[tuple[dict, dict]] = []
    for page in range(1, max_pages + 1):
        try:
            resp = http_get(f"{list_url}?page={page}")
        except Exception as exc:  # noqa: BLE001
            print(f"[linkareer] list {page} 실패: {exc}", file=sys.stderr)
            break
        nd = _extract_next_data(resp.text)
        if not nd:
            break
        ap = nd.get("props", {}).get("pageProps", {}).get("__APOLLO_STATE__", {})
        page_acts = [
            (v, ap) for k, v in ap.items()
            if k.startswith("Activity:") and "recruitType" in v
        ]
        if not page_acts:
            break
        out.extend(page_acts)
        polite_sleep(STUDENT_INTERVAL_SEC)
    return out


def _fetch_linkareer() -> list[dict]:
    """링커리어 — 채용/인턴 메타데이터 (best-effort, 사이트당 최대 100건)."""
    seen: set[str] = set()
    pairs: list[tuple[dict, dict]] = []
    for url in LK_LIST_URLS:
        for act, ap in _lk_collect(url, LK_PAGES_PER_LIST):
            aid = act.get("id")
            if not aid or aid in seen:
                continue
            seen.add(aid)
            pairs.append((act, ap))
            if len(pairs) >= MAX_PER_SITE:
                break
        if len(pairs) >= MAX_PER_SITE:
            break
    print(f"[linkareer] list 수집: {len(pairs)} activities", file=sys.stderr)
    records = [r for r in (_lk_build_record(a, p) for a, p in pairs) if r]
    print(f"[linkareer] 최종: {len(records)} records", file=sys.stderr)
    return records


# --- 2. 자소설닷컴 (jasoseol.com) -------------------------------------------

JS_RECRUIT_SITEMAP = "https://jasoseol.com/sitemap/employment_companies.xml"
JS_INTERN_SITEMAP = "https://jasoseol.com/sitemap/intern_employment_companies.xml"
JS_RECRUIT_URL = "https://jasoseol.com/recruit/{rid}"
# target 코드 → 사이트 라벨 (매뉴얼 검수)
JS_TARGET_LABELS = {0: "전체", 1: "신입", 2: "경력", 3: "인턴", 4: "신입/경력", 5: "공채"}


def _js_parse_sitemap(xml_text: str) -> list[str]:
    """sitemap → recruit id (lastmod 내림차순 = 위쪽이 신선). 중복 제거."""
    ids = re.findall(r"<loc>https://jasoseol\.com/recruit/(\d+)</loc>", xml_text)
    seen: set[str] = set()
    out: list[str] = []
    for rid in ids:
        if rid not in seen:
            seen.add(rid)
            out.append(rid)
    return out


def _js_build_record(rid: str, ec: dict) -> dict | None:
    title = (ec.get("title") or "").strip()
    company = (ec.get("name") or "").strip()
    if not title and not company:
        return None
    target_code = ec.get("target")
    target_label = (JS_TARGET_LABELS.get(target_code, "")
                    if isinstance(target_code, int) else "")

    fields = [
        e["field"].strip() for e in (ec.get("employments") or [])
        if isinstance(e, dict) and isinstance(e.get("field"), str) and e["field"].strip()
    ]
    fields_uniq = list(dict.fromkeys(fields))[:10]

    cg = ec.get("company_group") or {}
    company_meta = [b for b in (cg.get("business_size"), cg.get("business_type"))
                    if isinstance(b, str) and b]

    raw_content = ec.get("content") or ""
    body = html_to_text(_html.unescape(raw_content)) if raw_content.strip() else ""

    start, end = _iso_to_date(ec.get("start_time")), _iso_to_date(ec.get("end_time"))
    period = f"{start or '?'} ~ {end or '?'}" if (start or end) else ""

    lines: list[str] = [f"[{company}] {title}".strip()]
    for label, val in (
        ("채용유형", target_label),
        ("직군", " / ".join(fields_uniq)),
        ("공고기간", period),
        ("기업", " / ".join(company_meta)),
        ("채용페이지", (ec.get("employment_page_url") or "").strip()),
    ):
        if val:
            lines.append(f"{label}: {val}")
    header = "\n".join(lines)

    raw_text = f"{header}\n\n{body}".strip() if body else header
    if len(raw_text) < MIN_RAW_TEXT_LEN:
        raw_text = f"{raw_text}\nrecruitId: {rid}"
    return make_record(
        source="Jasoseol",
        posting_url=JS_RECRUIT_URL.format(rid=rid),
        raw_text=raw_text,
    )


def _js_fetch_detail(rid: str) -> dict | None:
    try:
        resp = http_get(JS_RECRUIT_URL.format(rid=rid))
    except Exception as exc:  # noqa: BLE001
        print(f"[jasoseol] /recruit/{rid} 실패: {exc}", file=sys.stderr)
        return None
    nd = _extract_next_data(resp.text)
    if not nd:
        return None
    ec = nd.get("props", {}).get("pageProps", {}).get("initialEmploymentCompany")
    if not isinstance(ec, dict) or not ec.get("ret", True):
        return None
    return ec


def _fetch_jasoseol() -> list[dict]:
    """자소설닷컴 — 대기업 공채 일정·직무 메타 (best-effort 100건).

    ⚠️ 자소서 본문(질문·답변)은 ToS 상업이용 금지 — 의도적으로 수집하지 않음.
    """
    rids: list[str] = []
    # 정상 채용 60 + 인턴 40 → 100
    for sm_url, take in (
        (JS_RECRUIT_SITEMAP, 60),
        (JS_INTERN_SITEMAP, MAX_PER_SITE - 60),
    ):
        try:
            resp = http_get(sm_url, headers={"Accept": "application/xml"})
        except Exception as exc:  # noqa: BLE001
            print(f"[jasoseol] sitemap 실패 ({sm_url}): {exc}", file=sys.stderr)
            continue
        rids.extend(_js_parse_sitemap(resp.text)[:take])
        polite_sleep(STUDENT_INTERVAL_SEC)
    rids = list(dict.fromkeys(rids))[:MAX_PER_SITE]
    print(f"[jasoseol] sitemap 후보: {len(rids)}", file=sys.stderr)

    records: list[dict] = []
    for idx, rid in enumerate(rids):
        ec = _js_fetch_detail(rid)
        polite_sleep(STUDENT_INTERVAL_SEC)
        if ec is None:
            continue
        rec = _js_build_record(rid, ec)
        if rec is not None:
            records.append(rec)
        if (idx + 1) % 20 == 0:
            print(f"[jasoseol] {idx + 1}/{len(rids)} | {len(records)} records",
                  file=sys.stderr)
        if len(records) >= MAX_PER_SITE:
            break
    print(f"[jasoseol] 최종: {len(records)} records", file=sys.stderr)
    return records


# --- Public entrypoint -----------------------------------------------------


def fetch() -> list[dict]:
    """학부생 페르소나 채용 메타 — 링커리어 + 자소설닷컴 통합."""
    records: list[dict] = []
    for fn in (_fetch_linkareer, _fetch_jasoseol):
        try:
            records.extend(fn())
        except Exception as exc:  # noqa: BLE001
            print(f"[{fn.__name__}] skip: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
        polite_sleep(STUDENT_INTERVAL_SEC)
    return records


if __name__ == "__main__":
    out = fetch()
    print(f"\n=== TOTAL: {len(out)} records ===", file=sys.stderr)
    if out:
        print(json.dumps(out[0], ensure_ascii=False, indent=2))
