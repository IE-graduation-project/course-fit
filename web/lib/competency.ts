/**
 * 역량·직무 표시 규칙.
 *
 * 역량별 고정 색을 두지 않는다. 진단 막대에는 축 이름이 이미 적혀 있어서 색이
 * 식별을 하지 않고, 10축에 hue 를 주면 색각 이상에서 구분이 무너진다
 * (실측: 비즈니스↔데이터시각화 ΔE 0.8, 최적화↔마케팅은 정상 시야에서도 6.2).
 * 그래서 색은 「보유 / 부족」 두 역할만 나르고, 정체는 글자가 나른다.
 */

/** 직무 표시 순서 — 데이터 · 제품 · 비즈니스 묶음 순. job.csv 는 id 사전순이라 여기서 다시 세운다. */
export const JOB_ORDER = ["DA", "DS", "DE", "PM", "MKT", "FIN"];

export const jobRank = (id: string) => {
  const i = JOB_ORDER.indexOf(id);
  return i === -1 ? 99 : i;
};

/** gap 으로 볼지 「충족」으로 볼지 가르는 선. 이 아래는 반올림하면 0 이라 노이즈다. */
export const GAP_EPSILON = 0.03;

/**
 * 근거 막대 세그먼트 색 — share 는 정체가 아니라 크기다.
 * 그래서 hue 를 돌리지 않고 한 hue 를 진하기로만 3단 쓴다(순차 램프).
 */
const SEQ = ["var(--color-seq-1)", "var(--color-seq-2)", "var(--color-seq-3)"];

export const seqColor = (rank: number) => SEQ[Math.min(rank, SEQ.length - 1)];
