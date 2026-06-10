import type { Course } from "@/lib/data";

/**
 * 시간표 격자 기하 (단일 진실 공급원).
 *
 * TimetableGrid, GridScaffold(유령 시간표), 직무전환 활주 격자가 전부 같은 좌표계를
 * 쓰도록 배치 수학을 여기로 추출한다. 유령 → 실제 격자 전환에서 CLS 0 을 보장하는 핵심.
 */
export const ROW_H = 46;
export const GAP = 4;
/** 5요일 격자 템플릿 (교시 라벨 열 + 월~금). 모든 격자가 동일 사용. */
export const GRID_TEMPLATE = "grid-cols-[2.5rem_repeat(5,1fr)]";

export interface PlacedBlock {
  course: Course;
  day: number;
  startPeriod: number;
  span: number;
}

/** 연속 교시를 하나의 블록으로 합쳐 배치 정보를 만든다. */
export function buildBlocks(courses: Course[]): PlacedBlock[] {
  const blocks: PlacedBlock[] = [];
  for (const course of courses) {
    const byDay = new Map<number, number[]>();
    for (const slot of course.slots) {
      const arr = byDay.get(slot.day) ?? [];
      arr.push(slot.period);
      byDay.set(slot.day, arr);
    }
    for (const [day, periods] of byDay) {
      const sorted = [...periods].sort((a, b) => a - b);
      let runStart = sorted[0];
      let prev = sorted[0];
      for (let i = 1; i <= sorted.length; i++) {
        const cur = sorted[i];
        if (cur === prev + 1) {
          prev = cur;
          continue;
        }
        blocks.push({ course, day, startPeriod: runStart, span: prev - runStart + 1 });
        runStart = cur;
        prev = cur;
      }
    }
  }
  return blocks;
}

/** 실제 쓰이는 마지막 교시까지 (최소 9교시로 안정적 높이). */
export function maxPeriodFor(courses: Course[]): number {
  return Math.max(9, ...courses.flatMap((c) => c.slots.map((s) => s.period)));
}

export function periodList(maxPeriod: number): number[] {
  return Array.from({ length: maxPeriod }, (_, i) => i + 1);
}

/** 블록의 절대 top(px): (시작교시-1) * (행높이+간격). */
export function blockTop(startPeriod: number): number {
  return (startPeriod - 1) * (ROW_H + GAP);
}

/** 블록의 높이(px): span 행 + 사이 간격. */
export function blockHeight(span: number): number {
  return span * ROW_H + (span - 1) * GAP;
}
