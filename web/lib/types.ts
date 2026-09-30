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
  programs: ProgramRef[];
}

/**
 * 지원 학과와 **적용 시작 연도**. department ⋈ graduation_requirement.
 *
 * `fromYear` 는 "그 연도 입학생만"이 아니라 **그 연도부터 다음 개정 전까지** 적용된다.
 * 그래서 고를 수 있는 입학년도는 `fromYear ~ 올해` 다. 연도 목록이 아니라 시작 연도를
 * 받는 이유는, 교육과정이 개정될 때마다 프론트를 고치지 않기 위해서다.
 */
export interface ProgramRef {
  dept: string; // IDE | BIZ
  name: string;
  fromYear: number;
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
  /** 유효값은 reference.programs 가 정한다 — 리터럴로 박으면 학과가 늘 때 프론트를 고쳐야 한다 */
  dept: string;
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
  /**
   * requirementYear = 실제 적용된 교육과정 개정 연도. 입학년도와 다를 수 있어 화면에 밝힌다.
   * gradeLevel = 후보를 거른 학년. 성적표의 마지막 학기에서 계산해 입학년도와 다를 수 있다(#42)
   */
  student: {
    deptId: string;
    admissionYear: number;
    requirementYear: number;
    gradeLevel: number;
  };
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
    gradeEligible: boolean;
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
  /**
   * 역량마다 σ 를 쌓은 기수강 과목, 기여 큰 순 최대 6개. σ 가 0 인 역량은 빈 목록.
   * 옛 서버 응답엔 없을 수 있어 optional — 없으면 화면이 누를 거리를 그리지 않는다.
   */
  sources?: Partial<Record<CompId, SigmaSource[]>>;
}

/** share = 그 역량에 쌓인 것(Σ 성적계수·가중치) 중 이 과목 몫 */
export interface SigmaSource {
  courseId: string;
  name: string;
  share: number;
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
