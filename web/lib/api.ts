/**
 * API 클라이언트 — mock 과 실 백엔드를 같은 인터페이스로 감싼다.
 *
 * NEXT_PUBLIC_API_BASE 가 비어 있으면 `public/fixtures/` 의 정적 JSON 을 읽는다(현재 상태).
 * 백엔드가 docs/API_계약.md 대로 뜨면 그 값만 채우면 코드 수정 없이 실 API 로 넘어간다.
 */
import type {
  Recommendation,
  RecommendRequest,
  Reference,
  TranscriptRequest,
  TranscriptResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

/** 서버가 준 에러. HTTP 상태와 계약의 error 코드(student_not_found 등)를 들고 다닌다 */
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string | null,
    message: string,
  ) {
    super(message);
  }
}

/**
 * 실 API 호출 — 서버가 깨는 동안은 기다렸다가 다시 부른다.
 *
 * 백엔드는 Render 무료 인스턴스라 15분 동안 요청이 없으면 잠들고, 깨는 데 1분쯤 걸린다
 * (render.com/docs/free). 그동안 오는 것은 네트워크 오류, 502/503/504, JSON 이 아닌 대기 페이지다.
 * 한 번 실패로 포기하면 학생은 「서버에 연결하지 못했어요」를 보고 떠난다. 이런 「아직 깨는 중」
 * 응답만 WAKE_BUDGET_MS 안에서 다시 부르고, 4xx 같은 진짜 답은 바로 돌려준다.
 * 다시 불러도 되는 호출만 여기를 지난다 — 성적표 적재는 같은 내용이면 같은 해시(멱등),
 * 추천과 참조는 읽기다.
 */
const WAKE_BUDGET_MS = 90_000;

async function callApi<T>(path: string, init?: RequestInit): Promise<T> {
  const until = Date.now() + WAKE_BUDGET_MS;
  let wait = 1500;
  for (;;) {
    let res: Response | null = null;
    try {
      res = await fetch(`${API_BASE}${path}`, init);
    } catch {
      res = null; // 네트워크 오류, 대기 페이지에 CORS 헤더가 없어 막힌 경우
    }
    const json = (res?.headers.get("content-type") ?? "").includes("json");
    const waking = res === null || [502, 503, 504].includes(res.status) || !json;
    if (res && !waking) {
      if (res.ok) return res.json() as Promise<T>;
      const body = (await res.json().catch(() => ({}))) as { error?: string };
      throw new ApiError(res.status, body.error ?? null, `${path} → ${res.status}`);
    }
    if (Date.now() + wait > until) {
      throw new ApiError(res?.status ?? 0, "server_unavailable", `${path} → 서버가 응답하지 않음`);
    }
    await delay(wait);
    wait = Math.min(wait * 1.5, 8000);
  }
}

export const isMock = () => API_BASE === "";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

/**
 * GET /api/reference
 *
 * 참조 데이터는 런타임에 안 바뀐다(API 계약 §1). 탭이 사는 동안 한 번만 받아 두면
 * 화면을 옮겨다닐 때마다 다시 기다릴 이유가 없다 — 무료 호스팅이라 첫 호출이
 * 콜드스타트로 20~30초 걸리는데, 그게 학과 선택 화면을 통째로 비워 둔다.
 */
const REF_CACHE_KEY = "course-fit:reference";

export async function fetchReference(): Promise<Reference> {
  if (typeof window !== "undefined") {
    const hit = window.sessionStorage.getItem(REF_CACHE_KEY);
    if (hit) {
      try {
        return JSON.parse(hit) as Reference;
      } catch {
        // 캐시가 깨졌으면 그냥 다시 받는다. 여기서 죽을 이유는 없다.
        window.sessionStorage.removeItem(REF_CACHE_KEY);
      }
    }
  }

  const ref = isMock()
    ? await getJson<Reference>("/fixtures/reference.json")
    : await callApi<Reference>("/api/reference");

  if (typeof window !== "undefined") {
    try {
      window.sessionStorage.setItem(REF_CACHE_KEY, JSON.stringify(ref));
    } catch {
      // 용량 초과 등. 캐시는 편의일 뿐이라 실패해도 그대로 진행한다.
    }
  }
  return ref;
}

/**
 * 백엔드를 미리 깨운다. 랜딩에서 한 번 부르면, 사용자가 안내를 읽고
 * 「시작하기」를 누르는 동안 콜드스타트가 끝나 있다.
 *
 * 실패는 삼킨다 — 예열은 보조 장치라, 안 되면 원래대로 /start 에서 기다릴 뿐이다.
 */
export function warmUp(): void {
  if (isMock()) return;
  void fetchReference().catch(() => {});
}

/**
 * POST /api/transcript
 *
 * mock 에서는 파싱을 흉내만 낸다 — 학수번호(6자리)로 시작하는 행을 세고,
 * 실제 적재는 하지 않은 채 고정 studentId 를 돌려준다.
 */
export async function submitTranscript(
  req: TranscriptRequest,
): Promise<TranscriptResponse> {
  if (isMock()) {
    const n = countCourseLines(req.text);
    await delay(400);
    return {
      // 픽스처를 만든 학생. mock 의 추천 응답도 이 학생 것이라 화면이 일관된다.
      studentId: "412813643e89d53f",
      deptId: req.dept,
      admissionYear: req.admissionYear,
      courseCount: n,
      matchedCount: n,
      semesters: [],
    };
  }
  return callApi<TranscriptResponse>("/api/transcript", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

/** POST /api/recommend */
export async function fetchRecommendation(
  req: RecommendRequest,
): Promise<Recommendation> {
  if (isMock()) {
    const mode = req.mode ?? "balanced";
    return getJson<Recommendation>(`/fixtures/${req.job}_${mode}.json`);
  }
  const call = (r: RecommendRequest) =>
    callApi<Recommendation>("/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(r),
    });
  try {
    return await call(req);
  } catch (e) {
    // 서버가 잠들었다 깨면(또는 재시작하면) 적재한 성적표가 사라져 404 가 난다. 시작 화면이
    // 이 탭에 둔 성적표를 다시 적재하고 한 번 더 부른다. 같은 성적표는 같은 studentId 다.
    const saved = typeof window !== "undefined" ? window.sessionStorage.getItem("transcript") : null;
    if (!(e instanceof ApiError && e.code === "student_not_found") || !saved) throw e;
    const res = await submitTranscript(JSON.parse(saved) as TranscriptRequest);
    window.sessionStorage.setItem("studentId", res.studentId);
    return call({ ...req, studentId: res.studentId });
  }
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * 붙여넣은 텍스트에서 성적표 행이 몇 개인지 센다.
 *
 * 서버 파서(`transcript/parse_text.py` 의 `_split_fields` + `_COURSE_ID_RE`)와
 * 같은 규칙이어야 한다. 화면이 "N과목 인식했어요" 라고 해놓고 서버가 0개를
 * 파싱하면 그건 거짓말이다.
 *
 * 규칙: 탭이 있으면 탭으로, 없으면 2칸 이상 공백으로 나누고,
 * 첫 필드가 정확히 6자리 숫자여야 한다.
 */
function isCourseLine(line: string): boolean {
  const fields = line.includes("\t")
    ? line.split("\t").map((f) => f.trim())
    : line.trim().split(/\s{2,}/).map((f) => f.trim());
  return /^\d{6}$/.test(fields[0] ?? "");
}

export function countCourseLines(text: string): number {
  return text.split("\n").filter(isCourseLine).length;
}
