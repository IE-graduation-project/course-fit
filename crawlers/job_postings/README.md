# crawlers/job_postings

채용공고 크롤러 모음. 각 모듈은 `def fetch() -> list[dict]` 를 export 하며, `run_all.py` 가 모두 호출해 `data/job_posting.csv` 로 통합 저장.

## 실행

```bash
python -m crawlers.job_postings.run_all
python -m crawlers.job_postings.run_all --only greenhouse,naver
```

## 산출물 스펙

`data/README.md` 의 `job_posting.csv` 스펙과 1:1:

| 컬럼 | 값 |
|---|---|
| `job_id` | 빈 문자열 (LLM 매핑이 추후 채움) |
| `source` | `"Greenhouse:krafton"`, `"NaverCareers"`, `"KakaoCareers"`, `"Greeting:kurly"`, `"Toss"`, `"Jumpit"` 등 |
| `posting_url` | 원본 공고 URL |
| `raw_text` | 본문 전체 평문 (HTML 제거, 한국어 우선) |
| `crawled_at` | ISO 8601 UTC (`2026-05-10T05:30:11+00:00`) |

## 모듈 인터페이스

```python
from crawlers.job_postings._common import make_record, http_get, html_to_text, polite_sleep

def fetch() -> list[dict]:
    records = []
    resp = http_get("https://...")
    # ... 처리 ...
    records.append(make_record(
        source="Greenhouse:krafton",
        posting_url="https://...",
        raw_text=html_to_text(content_html),
    ))
    polite_sleep()
    return records
```

## 매너 규칙

- User-Agent: `HongikCapstone-CourseFit/0.1 (+repo URL)` — `_common.DEFAULT_HEADERS` 자동 적용
- 요청 간격 ≥ 1.5초 — `polite_sleep()` 사용
- 호출 직전 robots.txt + ToS 재확인 (`docs/채용공고_소스_리서치.md` Tier 표 참조)
- ❌ 자동수집 금지 사이트: 원티드 직접페이지, 로켓펀치, OKKY, 인크루트, Indeed 등
- ✅ 합법 sources만: Tier 1 (Greenhouse / 네이버 / 카카오), Tier 3 (점핏 / 링커리어), Tier 4 (회사별 자체 페이지 — robots 허용한 곳만)

## 등록된 fetchers

- `greenhouse.py` — 쿠팡 / 크래프톤 / 당근 / Seoul Robotics (한국 4사 통합)
- `naver.py` — recruit.navercorp.com 자체 JSON
- `kakao.py` — careers.kakao.com 자체 JSON
- `greetinghr.py` — 컬리 / 카카오페이 / 카카오모빌리티 (GreetingHR SaaS, 3사 통합)
- `toss.py` — toss.im/career/jobs (Next.js `__NEXT_DATA__`)
- `jumpit.py` — 점핏 (사람인 자회사, robots 명시 허용)

## 법적 근거

대법원 2017다222757 (사람인HR ↔ 잡코리아) — 무단 크롤링 = 데이터베이스권 침해. 본 모듈은 **공식 API + robots 명시 허용 사이트** 한정으로 운영.
