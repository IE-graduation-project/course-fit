import type { CompId } from "./types";

/**
 * 역량 10축의 고정 색상(oklch hue).
 *
 * 한 역량은 화면 어디서든 같은 색이다 — 진단 차트의 라벨 점과 과목 카드의 근거 막대가
 * 같은 색을 쓰기 때문에, "데이터베이스가 부족하다 → 이 과목이 그 색을 크게 물고 있다" 가
 * 글씨를 읽지 않고도 연결된다. (소연님 6/10 요청: 글씨 최대한 줄이고 UI 로 표현)
 */
export const COMP_HUE: Record<CompId, number> = {
  PROG: 258,
  DATA: 205,
  ML: 295,
  DB: 170,
  VIZ: 45,
  BIZ: 130,
  FIN: 95,
  MKT: 345,
  OR: 320,
  COMM: 20,
};

export const compColor = (id: CompId, l = 60, c = 0.14) =>
  `oklch(${l}% ${c} ${COMP_HUE[id] ?? 258})`;

/** 직무 표시 순서 — 데이터/제품/비즈니스 묶음 순. job.csv 는 id 사전순이라 여기서 다시 세운다. */
export const JOB_ORDER = ["DA", "DS", "DE", "PM", "MKT", "FIN"];

export const jobRank = (id: string) => {
  const i = JOB_ORDER.indexOf(id);
  return i === -1 ? 99 : i;
};
