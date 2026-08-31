/**
 * course-fit API 계약 (프론트/백엔드 공용 타입)
 *
 * 이 파일이 프론트가 기대하는 응답의 정본이다. 백엔드는 `recommender.recommend()` 와
 * `transcript.load` 를 이 형태로 감싸기만 하면 된다 — 계산 로직은 이미 다 있다.
 * 각 필드가 어느 파이썬 값에서 오는지는 필드 주석에 적어두었다.
 *
 * 스펙 문서: docs/API_계약.md
 */

// ── 참조 데이터 ─────────────────────────────────────────────────

/** GET /api/reference */
export interface Reference {
  jobs: JobRef[];
  competencies: CompetencyRef[];
  modes: ModeRef[];
  areas: string[];
}

/** data/job.csv */
export interface JobRef {
  id: string; // DA | DE | DS | PM | MKT | FIN
  name: string;
}

/** data/competency.csv + explain.COMP_KR */
export interface CompetencyRef {
  id: CompId;
  nameKo: string;
  nameEn: string;
}

export type CompId =
  | "PROG" | "DATA" | "ML" | "DB" | "VIZ"
  | "BIZ" | "FIN" | "MKT" | "OR" | "COMM";

/** recommend.PREFERENCE_EPS — ε 프리셋 3종 */
export interface ModeRef {
  id: ModeId;
  eps: number;
  label: string;
  desc: string;
}

export type ModeId = "gap" | "balanced" | "graduation";

// ── 성적표 적재 ─────────────────────────────────────────────────

/** POST /api/transcript — 클래스넷 '전체성적조회' 복붙 텍스트 */
export interface TranscriptRequest {
  text: string;
  dept: "IDE" | "BIZ";
  admissionYear: number;
}

/** transcript.load 의 input_hash 가 곧 studentId 다 (idempotent) */
export interface TranscriptResponse {
  studentId: string;
  deptId: string;
  admissionYear: number;
  courseCount: number;
  matchedCount: number;
  semesters: TranscriptSemester[];
}

export interface TranscriptSemester {
  term: string; // "2025-1"
  courses: { courseId: string; name: string; credit: number; grade: string | null }[];
}

// ── 추천 ────────────────────────────────────────────────────────

/** POST /api/recommend */
export interface RecommendRequest {
  studentId: string;
  job: string;
  mode?: ModeId;
  eps?: number; // 주면 mode 무시
  maxCredits?: number; // 기본 18
  minCredits?: number; // 기본 12
  topK?: number; // 기본 3
}

/** POST /api/recommend 응답 = recommender.explain.build_explanation 확장판 */
export interface Recommendation {
  student: { deptId: string; admissionYear: number };
  job: JobRef;
  /**
   * 직무 6종 각각의 적합도(0~100). σ 는 직무와 무관해서 한 번에 다 낼 수 있고,
   * 시간표·성향(ε)에 흔들리지 않는다 — 목표를 고르기 전에 비교하라고 있는 값이다.
   * fit = 1 − Σ_k ρ_k·gap_k / Σ_k ρ_k
   */
  fitByJob: JobFit[];
  params: {
    mode: ModeId;
    eps: number;
    alpha: number;
    maxCredits: number;
    minCredits: number;
    topK: number;
  };
  diagnosis: Diagnosis;
  /** 졸업요건 영역별 남은 부족학점. params.compute_need */
  need: Record<string, number>;
  /** 상위 k개 대안 시간표. [0] 이 1순위 */
  timetables: Timetable[];
  constraints: {
    noTimeConflict: boolean;
    creditBounds: boolean;
    excludeTaken: boolean;
    prereqSatisfied: boolean;
  };
}

export interface JobFit {
  job: string;
  name: string;
  fit: number;
}

export interface Diagnosis {
  /** σ — 학생 보유 역량 (포화 누적, 0~1) */
  sigma: Record<CompId, number>;
  /** ρ — 직무 요구 역량 (직무별 min-max, 0~1) */
  rho: Record<CompId, number>;
  /** gap = max(0, ρ − σ) */
  gap: Record<CompId, number>;
  strengths: { comp: CompId; compKo: string; sigma: number }[];
  gaps: { comp: CompId; compKo: string; gap: number }[];
}

export interface Timetable {
  rank: number;
  /** 1순위 목적함수 값 Σ credit·Score */
  careerfit: number;
  /** 2순위 목적함수 값 — 졸업요건 진척 학점 */
  gradProgress: number;
  totalCredit: number;
  status: string; // "Optimal"
  courses: RecommendedCourse[];
}

export interface RecommendedCourse {
  courseId: string;
  section: string;
  name: string;
  credit: number;
  area: string;
  /** 정수 슬롯 = 요일idx(월0..일6) × 16 + 교시 */
  slots: number[];
  /** ["화2","화3","화4"] */
  slotsHuman: string[];
  professor: string | null;
  timeRaw: string | null; // "화234"
  offeringDept: string | null;
  category: string | null; // 전선/전필/...
  /** Score_c = Σ_k gap_k · w_{c,k} */
  score: number;
  /** 어느 역량 갭을 얼마나 채우나 (상위 3) */
  careerReason: { comp: CompId; compKo: string; value: number; share: number }[];
  /** 졸업 기여 — 그 영역의 남은 부족학점 */
  gradReason: { area: string; remaining: number };
}
