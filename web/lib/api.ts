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

export const isMock = () => API_BASE === "";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

/** GET /api/reference */
export async function fetchReference(): Promise<Reference> {
  if (isMock()) return getJson<Reference>("/fixtures/reference.json");
  return getJson<Reference>(`${API_BASE}/api/reference`);
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
    const lines = req.text.split("\n").filter((l) => /^\s*\d{6}[\s\t]/.test(l));
    await delay(400);
    return {
      studentId: "746696b793744f17",
      deptId: req.dept,
      admissionYear: req.admissionYear,
      courseCount: lines.length || 45,
      matchedCount: lines.length || 45,
      semesters: [],
    };
  }
  const res = await fetch(`${API_BASE}/api/transcript`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`transcript → ${res.status}`);
  return res.json();
}

/** POST /api/recommend */
export async function fetchRecommendation(
  req: RecommendRequest,
): Promise<Recommendation> {
  if (isMock()) {
    const mode = req.mode ?? "balanced";
    return getJson<Recommendation>(`/fixtures/${req.job}_${mode}.json`);
  }
  const res = await fetch(`${API_BASE}/api/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(`recommend → ${res.status}`);
  return res.json();
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));
