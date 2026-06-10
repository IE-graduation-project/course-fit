import type { Transition } from "motion/react";

/**
 * course-fit 모션 토큰 (단일 진실 공급원).
 *
 * 리서치 합의: 모션은 장식이 아니라 서사다. 거의 임계감쇠 스프링만 쓴다
 * (motion/react 기본 stiffness 100 / damping 10 의 통통 튐을 제거).
 * 프로젝터에서 wobble(damping < 18)은 아마추어로 읽히고 글자가 흔들려 안 읽힌다.
 * transform / opacity / clip-path 만 애니메이트 (compositor-only, 프레임 드랍 방지).
 */

/** 프로젝트 표준 이징 (duration 기반 reveal 전용). globals 의 EASE 와 동일 곡선. */
export const EASE = [0.16, 1, 0.3, 1] as const;

export const SPRING: Record<"snappy" | "layout" | "smooth", Transition> = {
  /** 탭/팝/블록 드롭/직무전환 reflow. 빠른 onset, 깔끔한 settle, 미세한 overshoot. */
  snappy: { type: "spring", stiffness: 420, damping: 36, mass: 0.8 },
  /** layoutId / FLIP 변형 (카드→머리글, 블록 활주). 위치+크기 보간이 물리적으로 읽히게. */
  layout: { type: "spring", stiffness: 350, damping: 35, mass: 0.9 },
  /** 큰 표면의 등장/disclosure. 차분한 도착. */
  smooth: { type: "spring", stiffness: 260, damping: 30, mass: 1 },
};

/** 시간표 블록 2D 대각 배치 딜레이: 월요일 아침 → 금요일 저녁 파동 (≤ ~0.9s). */
export function diagonalDelay(index: number, day: number) {
  return 0.035 * index + 0.025 * day;
}
