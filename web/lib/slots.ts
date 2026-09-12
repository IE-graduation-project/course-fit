/**
 * 시간표 슬롯 유틸 — crawlers/courses/preprocess_time_slots.py 와 동일 규약.
 *   slot = 요일idx × 16 + 교시   (월=0 … 일=6, 교시 1..15)
 */
export const DAY_STRIDE = 16;
export const DAYS = ["월", "화", "수", "목", "금"] as const;

export interface Placed {
  day: number; // 0..4
  start: number; // 교시
  span: number; // 연강 길이
}

export function decode(slot: number): { day: number; period: number } {
  return { day: Math.floor(slot / DAY_STRIDE), period: slot % DAY_STRIDE };
}

/** 슬롯 배열 → 요일별 연속 블록. 시간표 그리드에서 rowSpan 으로 쓴다. */
export function toBlocks(slots: number[]): Placed[] {
  const byDay = new Map<number, number[]>();
  for (const s of slots) {
    const { day, period } = decode(s);
    if (!byDay.has(day)) byDay.set(day, []);
    byDay.get(day)!.push(period);
  }
  const out: Placed[] = [];
  for (const [day, periods] of byDay) {
    periods.sort((a, b) => a - b);
    let start = periods[0];
    let prev = periods[0];
    for (let i = 1; i <= periods.length; i++) {
      const p = periods[i];
      if (p === prev + 1) {
        prev = p;
        continue;
      }
      out.push({ day, start, span: prev - start + 1 });
      if (p === undefined) break;
      start = p;
      prev = p;
    }
  }
  return out;
}

/** 그리드에 그릴 교시 범위 — 실제 배치된 교시만 (빈 새벽·야간 줄 제거) */
export function periodRange(allSlots: number[]): number[] {
  const periods = allSlots.map((s) => decode(s).period);
  if (periods.length === 0) return [1, 2, 3, 4, 5, 6, 7, 8, 9];
  const lo = Math.min(...periods);
  const hi = Math.max(...periods);
  return Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);
}

/** 교시 → 실제 시각. 홍익대 1교시 09:00 시작, 1시간 단위. */
export function periodTime(period: number): string {
  const h = 8 + period;
  return `${String(h).padStart(2, "0")}:00`;
}
