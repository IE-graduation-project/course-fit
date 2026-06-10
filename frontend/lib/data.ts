/**
 * course-fit mock 데이터 (단일 진실 공급원)
 *
 * 백엔드 연결 없이 발표 데모용으로 씁니다. switch and see (직무 토글로 시간표가
 * 실제로 바뀌는 동작)를 위해 직무별로 사전 계산된 시간표를 미리 넣어 둡니다.
 * 실제 추천 엔진 연결 시 이 파일의 형태를 그대로 API 응답으로 대체하면 됩니다.
 *
 * 요일 index: 월0 화1 수2 목3 금4 / 교시: 1~12
 * 모든 직무 시간표는 시간 충돌 0건이 되도록 조합했습니다.
 */

/* ---------------------------------------------------------------- 직무 */
export type JobId =
  | "data-analyst"
  | "data-engineer"
  | "data-scientist"
  | "product-manager"
  | "marketing-manager"
  | "finance-analyst";

export interface Job {
  id: JobId;
  name: string;
  tagline: string;
  /** mono 라벨용 직무 코드 (데이터 컨텍스트) */
  code: string;
}

export const JOBS: Job[] = [
  {
    id: "data-analyst",
    name: "데이터 분석가",
    tagline: "지표를 읽고 의사결정을 돕는 역할",
    code: "ANALYTICS",
  },
  {
    id: "data-engineer",
    name: "데이터 엔지니어",
    tagline: "데이터 파이프라인을 설계하고 운영",
    code: "ENGINEERING",
  },
  {
    id: "data-scientist",
    name: "데이터 사이언티스트",
    tagline: "모델로 문제를 푸는 역할",
    code: "SCIENCE",
  },
  {
    id: "product-manager",
    name: "프로덕트 매니저",
    tagline: "제품의 방향과 우선순위를 정의",
    code: "PRODUCT",
  },
  {
    id: "marketing-manager",
    name: "마케팅 매니저",
    tagline: "성장과 시장을 책임지는 역할",
    code: "GROWTH",
  },
  {
    id: "finance-analyst",
    name: "재무 분석가",
    tagline: "숫자로 사업의 건강도를 진단",
    code: "FINANCE",
  },
];

/**
 * 진로 미정 학생을 위한 힌트.
 * 자동 선택은 하지 않고 (확정 결정: 학생이 직접 고른다), 좁혀줄 방향만 제시한다.
 */
export const UNSURE_HINT = {
  lead: "이수 과목을 보면 데이터 쪽이 가까워요.",
  buckets: [
    {
      label: "데이터",
      jobs: ["data-analyst", "data-engineer", "data-scientist"],
    },
    { label: "비즈니스", jobs: ["product-manager", "marketing-manager"] },
    { label: "금융", jobs: ["finance-analyst"] },
  ],
} as const;

/* ---------------------------------------------------------------- 학점 */
export const CREDIT_RANGE = { min: 12, max: 21 } as const;
export const DEFAULT_CREDITS = 18;

/* ---------------------------------------------------- 인식 결과 (mock) */
/** paste 후 textarea 가 recognized 로 전환되면 노출되는 칩. */
export const RECOGNITION = {
  admissionYear: "22학번",
  department: "산업데이터공학",
  earnedCredits: 98,
  gpa: 3.6,
  recognizedCourses: 24,
} as const;

/* ----------------------------------------------------------- 과목 모델 */
export type CourseColor = 1 | 2 | 3 | 4 | 5 | 6;

export interface Course {
  id: string;
  name: string;
  professor: string;
  credits: number;
  category: string; // 이수구분
  /** 시간 슬롯: [요일index(0=월), 교시] */
  slots: { day: number; period: number }[];
  slotLabel: string; // 사람이 읽는 라벨
  color: CourseColor;
  /** 과목 블록 탭 시: 이 과목이 길러주는 핵심 역량 1줄 */
  competency: string;
  /**
   * 근사 반사실: 이 과목을 빼면 적합도가 대략 얼마나 떨어지는지 (음수 저장).
   * 화면에서는 절댓값에 하강 글리프를 붙여 방향과 크기를 함께 보인다 (예: 15pt 하락).
   */
  counterfactual: number;
}

export const DAYS = ["월", "화", "수", "목", "금"] as const;
export const PERIODS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] as const;

/**
 * 산업데이터공학 실제 과목 풀.
 * 직무별 시간표는 여기서 충돌 없이 5~6과목씩 골라 조합한다.
 */
const POOL = {
  ai: {
    id: "ai-intro",
    name: "인공지능개론",
    professor: "이용오",
    credits: 3,
    category: "전선",
    slots: [
      { day: 2, period: 1 },
      { day: 2, period: 2 },
      { day: 2, period: 3 },
    ],
    slotLabel: "수 1, 수 2, 수 3",
    competency: "인공지능 기초",
    counterfactual: -16,
  },
  dataScience: {
    id: "data-science",
    name: "데이터사이언스",
    professor: "박희석",
    credits: 3,
    category: "전선",
    slots: [
      { day: 2, period: 8 },
      { day: 2, period: 9 },
    ],
    slotLabel: "수 8, 수 9",
    competency: "데이터 분석",
    counterfactual: -18,
  },
  cognitive: {
    id: "cognitive",
    name: "인지공학",
    professor: "정민근",
    credits: 3,
    category: "전선",
    slots: [
      { day: 0, period: 2 },
      { day: 0, period: 3 },
      { day: 0, period: 4 },
    ],
    slotLabel: "월 2, 월 3, 월 4",
    competency: "사용자 이해",
    counterfactual: -9,
  },
  decision: {
    id: "decision",
    name: "의사결정(1)",
    professor: "하정훈",
    credits: 3,
    category: "전선",
    slots: [
      { day: 0, period: 6 },
      { day: 0, period: 7 },
      { day: 0, period: 8 },
    ],
    slotLabel: "월 6, 월 7, 월 8",
    competency: "의사결정 분석",
    counterfactual: -12,
  },
  smartMfg: {
    id: "smart-mfg",
    name: "스마트제조",
    professor: "옥창수",
    credits: 3,
    category: "전선",
    slots: [
      { day: 0, period: 1 },
      { day: 0, period: 2 },
      { day: 0, period: 3 },
    ],
    slotLabel: "월 1, 월 2, 월 3",
    competency: "제조 데이터",
    counterfactual: -8,
  },
  dbDesign: {
    id: "db-design",
    name: "데이터베이스설계",
    professor: "김도현",
    credits: 3,
    category: "전선",
    slots: [
      { day: 3, period: 6 },
      { day: 3, period: 7 },
    ],
    slotLabel: "목 6, 목 7",
    competency: "데이터베이스",
    counterfactual: -19,
  },
  economics: {
    id: "economics",
    name: "경제성분석",
    professor: "옥창수",
    credits: 3,
    category: "전선",
    slots: [
      { day: 1, period: 1 },
      { day: 1, period: 2 },
      { day: 1, period: 3 },
    ],
    slotLabel: "화 1, 화 2, 화 3",
    competency: "경제성 평가",
    counterfactual: -10,
  },
  quality: {
    id: "quality",
    name: "품질신뢰성",
    professor: "권혁무",
    credits: 3,
    category: "전선",
    slots: [
      { day: 1, period: 8 },
      { day: 1, period: 9 },
    ],
    slotLabel: "화 8, 화 9",
    competency: "품질 관리",
    counterfactual: -7,
  },
  optimization: {
    id: "data-optimization",
    name: "데이터기반최적화",
    professor: "옥창수",
    credits: 3,
    category: "전선",
    slots: [
      { day: 3, period: 6 },
      { day: 3, period: 7 },
    ],
    slotLabel: "목 6, 목 7",
    competency: "최적화",
    counterfactual: -15,
  },
  ml1: {
    id: "ml-1",
    name: "기계학습1",
    professor: "이용오",
    credits: 3,
    category: "전선",
    slots: [
      { day: 3, period: 4 },
      { day: 3, period: 5 },
    ],
    slotLabel: "목 4, 목 5",
    competency: "머신러닝",
    counterfactual: -18,
  },
  sysAnalysis: {
    id: "sys-analysis",
    name: "시스템분석",
    professor: "박세호",
    credits: 3,
    category: "전선",
    slots: [
      { day: 0, period: 9 },
      { day: 0, period: 10 },
      { day: 0, period: 11 },
    ],
    slotLabel: "월 9, 월 10, 월 11",
    competency: "시스템 분석",
    counterfactual: -11,
  },
  plm: {
    id: "plm",
    name: "제품생애관리",
    professor: "김도현",
    credits: 3,
    category: "전선",
    slots: [
      { day: 1, period: 5 },
      { day: 1, period: 6 },
      { day: 1, period: 7 },
    ],
    slotLabel: "화 5, 화 6, 화 7",
    competency: "제품 관리",
    counterfactual: -9,
  },
  simulation: {
    id: "simulation",
    name: "시뮬레이션",
    professor: "하정훈",
    credits: 3,
    category: "전선",
    slots: [
      { day: 2, period: 6 },
      { day: 2, period: 7 },
      { day: 2, period: 8 },
    ],
    slotLabel: "수 6, 수 7, 수 8",
    competency: "시뮬레이션",
    counterfactual: -10,
  },
  networkData: {
    id: "network-data",
    name: "네트워크데이터분석",
    professor: "박희석",
    credits: 3,
    category: "전선",
    slots: [
      { day: 3, period: 2 },
      { day: 3, period: 3 },
      { day: 3, period: 4 },
    ],
    slotLabel: "목 2, 목 3, 목 4",
    competency: "네트워크 분석",
    counterfactual: -12,
  },
  timeSeries: {
    id: "time-series",
    name: "시계열분석",
    professor: "하정훈",
    credits: 3,
    category: "전선",
    slots: [
      { day: 0, period: 5 },
      { day: 0, period: 6 },
      { day: 0, period: 7 },
    ],
    slotLabel: "월 5, 월 6, 월 7",
    competency: "시계열 예측",
    counterfactual: -13,
  },
  capstone: {
    id: "capstone",
    name: "시스템설계캡스톤",
    professor: "정민근",
    credits: 3,
    category: "전필",
    slots: [
      { day: 1, period: 10 },
      { day: 1, period: 11 },
      { day: 1, period: 12 },
    ],
    slotLabel: "화 10, 화 11, 화 12",
    competency: "종합 설계",
    counterfactual: -14,
  },
  dataAnalysisApp: {
    id: "data-analysis-app",
    name: "데이터분석응용",
    professor: "박세호",
    credits: 3,
    category: "전선",
    slots: [
      { day: 2, period: 1 },
      { day: 2, period: 2 },
      { day: 2, period: 3 },
    ],
    slotLabel: "수 1, 수 2, 수 3",
    competency: "분석 실무",
    counterfactual: -17,
  },
} satisfies Record<string, Omit<Course, "color">>;

/** 과목에 색 인덱스를 입혀 시간표용 Course 로 만든다. */
function withColors(courses: Omit<Course, "color">[]): Course[] {
  return courses.map((c, i) => ({ ...c, color: ((i % 6) + 1) as CourseColor }));
}

/* ---------------------------------------------------- 직무별 추천 시간표 */
export interface JobPlan {
  /** 0~100 적합도 점수 (mock 사전 계산값) */
  fitScore: number;
  /** 한 줄 요약 근거 */
  rationale: string;
  courses: Course[];
}

/**
 * 직무 → 시간표. 데이터 3직무(분석가/엔지니어/사이언티스트)는 눈에 띄게 다르고,
 * 나머지 3직무는 데이터 코스를 줄이고 비즈니스/금융 과목을 섞은 변형.
 * 모든 조합은 시간 충돌 0건.
 */
export const JOB_PLANS: Record<JobId, JobPlan> = {
  // 데이터 분석가: 분석 + 시각화 + 시계열 + DB + 의사결정 (수/월/화/목 분산)
  "data-analyst": {
    fitScore: 84,
    rationale: "지표 해석과 분석 실무 갭을 가장 크게 줄이는 조합이에요.",
    courses: withColors([
      POOL.dataScience,
      POOL.dataAnalysisApp,
      POOL.timeSeries,
      POOL.dbDesign,
      POOL.quality,
      POOL.economics,
    ]),
  },
  // 데이터 엔지니어: DB + 시스템 + 네트워크 + 시뮬레이션 + 스마트제조 (파이프라인 결)
  "data-engineer": {
    fitScore: 79,
    rationale: "파이프라인 설계와 시스템 운영 역량을 함께 끌어올리는 조합이에요.",
    courses: withColors([
      POOL.dbDesign,
      POOL.sysAnalysis,
      POOL.networkData,
      POOL.simulation,
      POOL.smartMfg,
      POOL.quality,
    ]),
  },
  // 데이터 사이언티스트: 머신러닝 + AI + 데이터사이언스 + 최적화 + 시계열 (모델링 결)
  "data-scientist": {
    fitScore: 88,
    rationale: "머신러닝과 모델링 핵심을 채우는, 적합도가 가장 높은 조합이에요.",
    courses: withColors([
      POOL.ml1,
      POOL.ai,
      POOL.dataScience,
      POOL.optimization,
      POOL.timeSeries,
      POOL.economics,
    ]),
  },
  // 프로덕트 매니저: 의사결정 + 제품생애관리 + 인지공학 + 캡스톤 + 데이터사이언스
  "product-manager": {
    fitScore: 73,
    rationale: "제품 의사결정과 사용자 이해를 데이터 감각과 함께 보강해요.",
    courses: withColors([
      POOL.decision,
      POOL.plm,
      POOL.cognitive,
      POOL.capstone,
      POOL.dataScience,
    ]),
  },
  // 마케팅 매니저: 데이터사이언스 + 인지공학 + 경제성 + 시계열 + 의사결정
  "marketing-manager": {
    fitScore: 68,
    rationale: "고객 데이터 해석과 성장 의사결정에 필요한 분석을 모았어요.",
    courses: withColors([
      POOL.dataScience,
      POOL.cognitive,
      POOL.economics,
      POOL.timeSeries,
      POOL.plm,
    ]),
  },
  // 재무 분석가: 경제성 + 의사결정 + 시계열 + 품질 + 시뮬레이션 + 데이터사이언스
  "finance-analyst": {
    fitScore: 71,
    rationale: "재무 판단의 토대인 경제성, 예측, 리스크 분석을 우선했어요.",
    courses: withColors([
      POOL.economics,
      POOL.dbDesign,
      POOL.timeSeries,
      POOL.quality,
      POOL.networkData,
      POOL.dataScience,
    ]),
  },
};

/* ----------------------------------------------------- 결과 요약 헬퍼 */
export function planSummary(jobId: JobId) {
  const job = JOBS.find((j) => j.id === jobId)!;
  const plan = JOB_PLANS[jobId];
  const totalCredits = plan.courses.reduce((s, c) => s + c.credits, 0);
  return {
    jobName: job.name,
    jobCode: job.code,
    fitScore: plan.fitScore,
    rationale: plan.rationale,
    conflicts: 0,
    courseCount: plan.courses.length,
    totalCredits,
  };
}

/* ----------------------------------------------- 직무 적합도 상세 (토글) */
export interface Competency {
  label: string;
  required: number; // 0~1 요구 수준
  achieved: number; // 0~1 달성 수준
}

/** 직무마다 요구 역량 프로필이 다르다 (자세히 보기 토글에서만 노출). */
export const JOB_COMPETENCIES: Record<JobId, Competency[]> = {
  "data-analyst": [
    { label: "데이터 분석", required: 0.95, achieved: 0.82 },
    { label: "데이터 시각화", required: 0.85, achieved: 0.72 },
    { label: "시계열 예측", required: 0.7, achieved: 0.6 },
    { label: "데이터베이스", required: 0.65, achieved: 0.58 },
    { label: "의사결정", required: 0.6, achieved: 0.55 },
    { label: "커뮤니케이션", required: 0.55, achieved: 0.5 },
  ],
  "data-engineer": [
    { label: "데이터베이스", required: 0.9, achieved: 0.74 },
    { label: "시스템 분석", required: 0.85, achieved: 0.7 },
    { label: "네트워크 분석", required: 0.7, achieved: 0.58 },
    { label: "시뮬레이션", required: 0.65, achieved: 0.6 },
    { label: "품질 관리", required: 0.6, achieved: 0.55 },
    { label: "프로그래밍", required: 0.7, achieved: 0.5 },
  ],
  "data-scientist": [
    { label: "머신러닝", required: 0.95, achieved: 0.78 },
    { label: "인공지능", required: 0.85, achieved: 0.72 },
    { label: "데이터 분석", required: 0.85, achieved: 0.8 },
    { label: "최적화", required: 0.7, achieved: 0.62 },
    { label: "시계열 예측", required: 0.65, achieved: 0.6 },
    { label: "프로그래밍", required: 0.75, achieved: 0.6 },
  ],
  "product-manager": [
    { label: "의사결정", required: 0.85, achieved: 0.66 },
    { label: "사용자 이해", required: 0.8, achieved: 0.6 },
    { label: "제품 관리", required: 0.8, achieved: 0.62 },
    { label: "데이터 분석", required: 0.6, achieved: 0.58 },
    { label: "커뮤니케이션", required: 0.7, achieved: 0.6 },
    { label: "비즈니스 전략", required: 0.6, achieved: 0.45 },
  ],
  "marketing-manager": [
    { label: "데이터 분석", required: 0.75, achieved: 0.62 },
    { label: "사용자 이해", required: 0.75, achieved: 0.58 },
    { label: "경제성 평가", required: 0.6, achieved: 0.5 },
    { label: "시계열 예측", required: 0.55, achieved: 0.48 },
    { label: "비즈니스 전략", required: 0.7, achieved: 0.46 },
    { label: "커뮤니케이션", required: 0.7, achieved: 0.55 },
  ],
  "finance-analyst": [
    { label: "경제성 평가", required: 0.9, achieved: 0.66 },
    { label: "의사결정", required: 0.8, achieved: 0.62 },
    { label: "시계열 예측", required: 0.75, achieved: 0.6 },
    { label: "품질/리스크", required: 0.65, achieved: 0.52 },
    { label: "데이터 분석", required: 0.7, achieved: 0.6 },
    { label: "시뮬레이션", required: 0.55, achieved: 0.5 },
  ],
};

/** 직무별 한 줄 인사이트 (자세히 보기 토글). */
export const JOB_INSIGHT: Record<JobId, string> = {
  "data-analyst": "이 시간표를 들으면 데이터 시각화와 시계열 갭이 가장 크게 줄어요.",
  "data-engineer": "데이터베이스와 시스템 분석을 함께 채워 파이프라인 역량이 올라가요.",
  "data-scientist": "머신러닝과 인공지능 갭을 메워 모델링 적합도가 가장 높아요.",
  "product-manager": "의사결정과 사용자 이해를 보강해 제품 감각을 끌어올려요.",
  "marketing-manager": "고객 데이터 해석과 비즈니스 전략 갭을 함께 줄여요.",
  "finance-analyst": "경제성 평가와 예측 역량을 채워 재무 판단의 토대를 다져요.",
};
