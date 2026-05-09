"""채널톡 (Channel Corp) 자체 채용 페이지 fetcher.

대상 endpoint (검증 완료 — 2026-05-10):
    GET https://channel.io/ko/jobs   → 308 redirect → /ko/careers
    GET https://channel.io/ko/careers (HTTP 200, ~950KB HTML)

페이지는 Next.js SSG/SSR 라 HTML 안에
    <script id="__NEXT_DATA__" type="application/json">{...}</script>
가 있고, ``props.pageProps.jobs`` 에 47 건의 job 객체 배열이 그대로 임베드된다.
별도 detail endpoint 호출 불필요.

각 job 객체 키 (라운드4 검증):
    id, text(=title), createdAt,
    descriptionPlain / description (HTML),
    descriptionBodyPlain / descriptionBody (HTML),
    additionalPlain / additional (HTML, 개인정보 동의 등 부록),
    lists: [{text: 섹션라벨, content: HTML <li>...}]  ← 핵심 본문
    categories: {commitment, department, team, location, allLocations[]},
    country, workplaceType, opening, openingPlain,
    hostedUrl(=Lever 호스팅 상세), applyUrl

robots.txt (channel.io/robots.txt) 정책:
    Disallow: /app, /touch, /@*, /download/windows,
              /{ko,ja,en}/oss, /{ko,ja,en}/terms, /{ko,ja,en}/email,
              /{ko,ja,en}/blog/p/, /{ko,ja,en}/pricing-old
    /ko/jobs, /ko/careers 는 Allow 범위. ✅
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

from crawlers.job_postings._common import (
    html_to_text,
    http_get,
    make_record,
    polite_sleep,
)


JOBS_URL = "https://channel.io/ko/jobs"  # 308 → /ko/careers (requests follows by default)
SOURCE = "ChannelIO"

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.S,
)

# 본문 placeholder ('인재풀' 등) 노이즈 제거 — toss/greenhouse fetcher 와 동일 정책
MIN_BODY_LEN = 80
SKIP_TITLE_KEYWORDS = ("인재풀", "talent pool")


def _extract_next_data(html: str) -> dict[str, Any] | None:
    m = NEXT_DATA_RE.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        print(f"[channelio] __NEXT_DATA__ JSON 파싱 실패: {exc}", file=sys.stderr)
        return None


def _norm(text: str | None) -> str:
    """non-breaking space (\xa0) 제거 + strip."""
    if not text:
        return ""
    return text.replace("\xa0", " ").strip()


def _join_lists(lists: list[dict] | None) -> str:
    """`lists` 배열 -> '◆ 섹션라벨\\n평문' 합쳐 반환."""
    if not isinstance(lists, list):
        return ""
    out: list[str] = []
    for item in lists:
        if not isinstance(item, dict):
            continue
        label = _norm(item.get("text"))
        content_html = item.get("content") or ""
        body = _norm(html_to_text(content_html))
        if not body:
            continue
        if label:
            out.append(f"◆ {label}\n{body}")
        else:
            out.append(body)
    return "\n\n".join(out)


def _build_raw_text(job: dict) -> str:
    title = _norm(job.get("text"))
    cats = job.get("categories") or {}
    team = _norm(cats.get("team"))
    department = _norm(cats.get("department"))
    location = _norm(cats.get("location"))
    commitment = _norm(cats.get("commitment"))
    workplace = _norm(job.get("workplaceType"))

    head = f"[채널톡] {title}".strip() if title else "[채널톡]"
    header_lines = [head]
    meta_pairs = [
        ("팀", team),
        ("부서", department),
        ("근무지", location),
        ("고용형태", commitment),
        ("근무형태", workplace),
    ]
    for label, val in meta_pairs:
        if val:
            header_lines.append(f"{label}: {val}")
    header = "\n".join(header_lines)

    # 본문: descriptionBodyPlain (intro) + lists (섹션 본문) + opening/additional
    body_parts: list[str] = []
    intro = _norm(
        job.get("descriptionBodyPlain") or job.get("descriptionPlain") or ""
    )
    if intro:
        body_parts.append(intro)

    sections = _join_lists(job.get("lists"))
    if sections:
        body_parts.append(sections)

    opening_plain = _norm(job.get("openingPlain"))
    if opening_plain:
        body_parts.append(f"◆ 채용 소개\n{opening_plain}")

    body = "\n\n".join(p for p in body_parts if p)
    return f"{header}\n\n{body}".strip() if body else header


def _is_skippable(title: str, body_len: int) -> bool:
    t = title.lower()
    if any(kw.lower() in t for kw in SKIP_TITLE_KEYWORDS):
        return True
    return body_len < MIN_BODY_LEN


def fetch() -> list[dict]:
    """채널톡 자체 채용 페이지 (Next.js __NEXT_DATA__ 파싱)."""
    try:
        resp = http_get(JOBS_URL)  # requests 가 308 을 자동 follow
    except Exception as exc:  # noqa: BLE001
        print(
            f"[channelio] page 요청 실패: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return []

    polite_sleep()

    data = _extract_next_data(resp.text)
    if data is None:
        print("[channelio] __NEXT_DATA__ 스크립트 못 찾음", file=sys.stderr)
        return []

    page_props = (data.get("props") or {}).get("pageProps") or {}
    jobs = page_props.get("jobs") or []
    if not isinstance(jobs, list):
        print(
            f"[channelio] pageProps.jobs 형식 이상: {type(jobs).__name__}",
            file=sys.stderr,
        )
        return []

    print(f"[channelio] page jobs={len(jobs)}", file=sys.stderr)

    records: list[dict] = []
    skipped = 0
    seen_ids: set[str] = set()

    for job in jobs:
        if not isinstance(job, dict):
            continue
        job_uid = _norm(job.get("id"))
        if job_uid and job_uid in seen_ids:
            continue
        if job_uid:
            seen_ids.add(job_uid)

        title = _norm(job.get("text"))
        raw_text = _build_raw_text(job)
        body_len = len(raw_text) - raw_text.find("\n\n") if "\n\n" in raw_text else 0

        if _is_skippable(title, body_len):
            skipped += 1
            continue

        posting_url = _norm(job.get("hostedUrl")) or _norm(job.get("applyUrl"))
        if not posting_url:
            # 페이지 내 앵커 fallback (url 없는 케이스 안전망)
            posting_url = f"https://channel.io/ko/careers#{job_uid}" if job_uid else JOBS_URL

        records.append(
            make_record(
                source=SOURCE,
                posting_url=posting_url,
                raw_text=raw_text,
            )
        )

    print(
        f"[channelio] done: kept {len(records)}, skipped {skipped} of {len(jobs)}",
        file=sys.stderr,
    )
    return records
