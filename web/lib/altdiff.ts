/**
 * 대안 시간표끼리 무엇이 다른지 — 안 1을 기준으로 바뀐 분반·과목과 한 주의 모양(요일, 9시, 18시 이후, 토요일).
 * 안 1/2/3 버튼만으로는 눌러 보기 전에 차이를 알 수 없었다(#75).
 */
import { DAYS, toBlocks } from "./slots";
import type { RecommendedCourse, Timetable } from "./types";

/** 「화 13~15시」 — 교시 p 는 (8+p)시 시작 */
export function when(c: RecommendedCourse): string {
  const blocks = toBlocks(c.slots).sort((a, b) => a.day - b.day || a.start - b.start);
  if (blocks.length === 0) return "시간 미지정";
  return blocks.map((b) => `${DAYS[b.day]} ${8 + b.start}~${8 + b.start + b.span}시`).join(", ");
}

export interface WeekShape {
  days: string;
  /** 9시에 시작하는 수업 */
  morning: number;
  /** 18시 이후에 걸치는 수업 */
  evening: number;
  weekend: number;
}

export function shape(t: Timetable): WeekShape {
  const blocks = t.courses.flatMap((c) => toBlocks(c.slots));
  const days = [...new Set(blocks.map((b) => b.day))].sort((a, b) => a - b);
  return {
    days: days.map((d) => DAYS[d]).join("") || "없음",
    morning: blocks.filter((b) => b.start === 1).length,
    evening: blocks.filter((b) => b.start + b.span - 1 >= 10).length,
    weekend: blocks.filter((b) => b.day >= 5).length,
  };
}

export function describeShape(s: WeekShape): string {
  const n = (k: number) => (k === 0 ? "없음" : `${k}번`);
  return `${s.days} · 9시 수업 ${n(s.morning)} · 18시 이후 ${n(s.evening)} · 주말 ${n(s.weekend)}`;
}

export interface AltDiff {
  rank: number;
  /** 바뀐 분반, 더하고 뺀 과목 */
  changes: string[];
  /** 한 주의 모양에서 달라진 것 */
  week: string[];
}

export function diffFromFirst(timetables: Timetable[]): AltDiff[] {
  const [base, ...rest] = timetables;
  if (!base) return [];
  const sb = shape(base);
  const byId = new Map(base.courses.map((c) => [c.courseId, c]));
  return rest.map((t) => {
    const changes: string[] = [];
    const ids = new Set(t.courses.map((c) => c.courseId));
    for (const c of t.courses) {
      const b = byId.get(c.courseId);
      if (!b) changes.push(`+ ${c.name} (${when(c)})`);
      else if (b.section !== c.section) {
        const [wb, wc] = [when(b), when(c)];
        changes.push(
          wb === wc
            ? `${c.name}: 같은 시간, 교수 ${b.professor ?? "미정"} → ${c.professor ?? "미정"}`
            : `${c.name}: ${wb} → ${wc}`,
        );
      }
    }
    for (const b of base.courses) if (!ids.has(b.courseId)) changes.push(`− ${b.name}`);

    const st = shape(t);
    const week: string[] = [];
    if (sb.days !== st.days) week.push(`요일 ${sb.days} → ${st.days}`);
    if (sb.morning !== st.morning) week.push(`9시 수업 ${sb.morning} → ${st.morning}번`);
    if (sb.evening !== st.evening) week.push(`18시 이후 ${sb.evening} → ${st.evening}번`);
    if (sb.weekend !== st.weekend) week.push(`주말 ${sb.weekend} → ${st.weekend}번`);
    return { rank: t.rank, changes, week };
  });
}
