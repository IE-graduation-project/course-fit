"""NAVER Corp 그룹사 채용공고 크롤러.

대상 endpoint
- 목록: GET https://recruit.navercorp.com/rcrt/loadJobList.do
  · 응답 schema: {"result":"Y","list":[...],"totalSize":N}
  · 페이지네이션: query string `firstIndex` (0, 10, 20, ...). 한 페이지 10건 고정.
  · 그룹사 필터: `sysCompanyCdArr` (KR=NAVER, NL=NAVER LABS, ...) — 미지정 시 전체.
- 상세: GET https://recruit.navercorp.com/rcrt/view.do?annoId={annoId}
  · 본문은 `<div class="detail_wrap">` 내부 다수의 `<div class="detail_box">`
    구조 (h4=섹션 제목, p=본문). 그룹사(NAVER / LABS / WEBTOON)별 tmplatPath 가
    달라도 동일 마크업 사용.

처리 흐름
1. 목록 API를 firstIndex 0부터 10씩 증가시키며 totalSize 까지 호출.
2. 각 annoId 에 대해 상세 페이지 GET → detail_wrap 추출 → 평문 변환.
3. raw_text = annoSubject + 그룹사명 + 모집기간 + 직무카테고리 + 본문.
   상세 추출 실패 시 메타만으로 fallback.
4. source = "NaverCareers:{그룹사}" (예: NaverCareers:NAVER WEBTOON).

매너
- robots.txt: /robots.txt = HTTP 404, 채용 경로 명시 disallow 없음 (확인 2026-05-10).
- User-Agent: _common.DEFAULT_HEADERS (HongikCapstone-CourseFit/0.1).
- 호출 사이 polite_sleep() (≥ 1.5초).
- 한 번 batch 만 호출, cron 등 빈도 ↑ 자제.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from crawlers.job_postings._common import (
    html_to_text,
    http_get,
    make_record,
    polite_sleep,
)


LIST_URL = "https://recruit.navercorp.com/rcrt/loadJobList.do"
DETAIL_URL = "https://recruit.navercorp.com/rcrt/view.do"
PAGE_SIZE = 10  # 서버 고정값 (loadJobList.do 응답)
MAX_PAGES = 200  # 안전 상한 (≈ 2000건)


def _fetch_list_all() -> list[dict]:
    """firstIndex 페이지네이션으로 모든 공고 메타 수집."""
    items: list[dict] = []
    seen_ids: set[int] = set()
    first_index = 0

    for _ in range(MAX_PAGES):
        resp = http_get(LIST_URL, params={"firstIndex": first_index})
        data = resp.json()
        page = data.get("list") or []
        if not page:
            break

        new_count = 0
        for it in page:
            anno_id = it.get("annoId")
            if anno_id is None or anno_id in seen_ids:
                continue
            seen_ids.add(anno_id)
            items.append(it)
            new_count += 1

        total_size = int(data.get("totalSize") or 0)
        first_index += PAGE_SIZE
        polite_sleep()

        # 종료 조건: 누적이 totalSize 이상이거나, 신규 추가 0 이거나, 페이지가 PAGE_SIZE 미만.
        if total_size and len(items) >= total_size:
            break
        if new_count == 0:
            break
        if len(page) < PAGE_SIZE:
            break

    return items


def _extract_detail_text(html: str) -> str:
    """상세 페이지에서 detail_wrap 내부 본문(섹션 제목 + 본문) 평문 추출."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    wrap = soup.select_one("div.detail_wrap")
    if wrap is None:
        return ""

    parts: list[str] = []
    for box in wrap.select("div.detail_box"):
        title_el = box.select_one("h4.detail_title, h4")
        body_el = box.select_one("p.detail_text, p")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        body_html = body_el.decode_contents() if body_el else ""
        body_text = html_to_text(body_html)
        if title:
            parts.append(f"## {title}")
        if body_text:
            parts.append(body_text)
    return "\n\n".join(p for p in parts if p)


def _fmt_period(item: dict) -> str:
    sta = item.get("staYmdTime") or item.get("staYmd") or ""
    end = item.get("endYmdTime") or item.get("endYmd") or ""
    if sta and end:
        return f"{sta} ~ {end}"
    return sta or end


def _build_raw_text(item: dict, detail_text: str) -> str:
    """annoSubject + 그룹사 + 모집기간 + 직무카테고리 + 본문."""
    subject = (item.get("annoSubject") or "").strip()
    group = (item.get("sysCompanyCdNm") or "").strip()
    period = _fmt_period(item)
    class_cd = (item.get("classCdNm") or "").strip()
    sub_job = (item.get("subJobCdNm") or "").strip()
    ent_type = (item.get("entTypeCdNm") or "").strip()
    emp_type = (item.get("empTypeCdNm") or "").strip()
    keyword = (item.get("annoKeyword") or "").strip()

    meta_lines: list[str] = []
    if subject:
        meta_lines.append(subject)
    if group:
        meta_lines.append(f"그룹사: {group}")
    if period:
        meta_lines.append(f"모집기간: {period}")
    cat_parts = [p for p in (class_cd, sub_job) if p]
    if cat_parts:
        meta_lines.append("직무카테고리: " + " / ".join(cat_parts))
    type_parts = [p for p in (ent_type, emp_type) if p]
    if type_parts:
        meta_lines.append("고용형태: " + " / ".join(type_parts))
    if keyword:
        meta_lines.append(f"키워드: {keyword}")

    blocks = ["\n".join(meta_lines)]
    if detail_text:
        blocks.append(detail_text)
    return "\n\n".join(blocks).strip()


def fetch() -> list[dict]:
    """NAVER Corp 그룹사 전체 공고."""
    items = _fetch_list_all()
    records: list[dict] = []

    for item in items:
        anno_id = item.get("annoId")
        if anno_id is None:
            continue
        posting_url = (
            item.get("jobDetailLink")
            or f"{DETAIL_URL}?annoId={anno_id}"
        )
        group = (item.get("sysCompanyCdNm") or "").strip() or "NAVER"
        source = f"NaverCareers:{group}"

        detail_text = ""
        try:
            resp = http_get(DETAIL_URL, params={"annoId": anno_id})
            detail_text = _extract_detail_text(resp.text)
        except Exception:
            # 상세 추출 실패 시 메타로 fallback (raw_text 빈 값 방지).
            detail_text = ""
        polite_sleep()

        raw_text = _build_raw_text(item, detail_text)
        if not raw_text:
            continue

        records.append(
            make_record(
                source=source,
                posting_url=posting_url,
                raw_text=raw_text,
            )
        )

    return records
