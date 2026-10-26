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

const dayCount = (s: WeekShape) => (s.days === "없음" ? 0 : [...s.days].length);

/** AltDiff 에서 「무엇이 바뀐 과목인가」 한 조각만 — 코스 라벨이 똑같을 때 가르는 용도 */
function changedCourse(d: AltDiff | undefined): string {
  const c = d?.changes[0];
  if (!c) {
    const w = d?.week[0];
    return w ? w.split(" ")[0] + " 다름" : "다른 분반";
  }
  if (c.startsWith("+ ")) return c.slice(2).split(" (")[0] + " 추가";
  if (c.startsWith("− ")) return c.slice(2) + " 빠짐";
  // c 는 `${name}: ${detail}` 꼴. detail 로 안끼리를 가른다 — 같은 과목의 다른 분반이면
  // 바뀐 시간(또는 교수)이 안마다 달라 라벨이 서로 겹치지 않는다(#75 중복 라벨).
  const sep = c.indexOf(": ");
  if (sep < 0) return c + " 다른 시간";
  const name = c.slice(0, sep);
  const detail = c.slice(sep + 2);
  // diffFromFirst 가 분반만 바뀌고 시간은 같을 때 내보내는 꼴: "같은 시간, 교수 X → Y"
  if (detail.startsWith("같은 시간, 교수")) {
    const prof = detail.split(" → ")[1];
    return prof ? `${name} 교수 ${prof}` : `${name} 교수 바뀜`;
  }
  // 시간이 바뀐 경우: detail 은 "wb → wc". 옮겨 간 시간(wc)으로 가른다.
  const dest = detail.split(" → ")[1];
  return dest ? `${name} ${dest}` : `${name} 다른 시간`;
}

/**
 * 대안 버튼에 붙일 라벨 — 번호(안 1/2/3)나 「안 1 대비」 없이, 각 안이 서로 무엇으로 갈리는지.
 * 읽는이는 「몇 번 안」이 아니라 「이 시간표가 어떤 한 주인가」로 고른다. 실측(픽스처)에서
 * 대안 셋이 거의 같아 거친 한 줄 설명은 다 겹쳤다 — 그래서 **세트에서 실제로 변하는 축만**
 * 쓰고(주 며칠·주말·저녁·오전), 그래도 겹치면 **바뀐 과목 한 개**로 가른다.
 */
export function altChips(timetables: Timetable[]): string[] {
  const shapes = timetables.map(shape);
  const vary = {
    day: new Set(shapes.map(dayCount)).size > 1,
    weekend: new Set(shapes.map((s) => s.weekend > 0)).size > 1,
    evening: new Set(shapes.map((s) => s.evening > 0)).size > 1,
    morning: new Set(shapes.map((s) => s.morning > 0)).size > 1,
  };
  const base = shapes.map((s) => {
    const parts: string[] = [];
    if (vary.day) parts.push(`주 ${dayCount(s)}일`);
    if (vary.weekend) parts.push(s.weekend > 0 ? "주말 포함" : "주중만");
    if (vary.evening) parts.push(s.evening > 0 ? "저녁 있음" : "저녁 없음");
    if (vary.morning) parts.push(s.morning > 0 ? "9시 수업 있음" : "9시 수업 없음");
    return parts.slice(0, 2).join(" · ");
  });
  const diffs = diffFromFirst(timetables); // timetables[1..] 에 정렬
  const labels = base.map((b, i) => {
    const unique = b && base.filter((x) => x === b).length === 1;
    if (i === 0) return b || "기본";
    if (unique) return b;
    const tb = changedCourse(diffs[i - 1]);
    return b ? `${b} · ${tb}` : tb;
  });
  // 여기까지도 라벨이 겹치면(같은 과목의 다른 분반이 시간까지 같은 경우) 분반/교수로 한 번 더 가른다.
  const seen = new Map<string, number>();
  for (const l of labels) seen.set(l, (seen.get(l) ?? 0) + 1);
  return labels.map((l, i) => {
    if (i === 0 || (seen.get(l) ?? 0) < 2) return l;
    const extra = sectionTag(timetables[i], diffs[i - 1]);
    return extra ? `${l} · ${extra}` : l;
  });
}

/** 라벨이 끝까지 겹칠 때 쓰는 최후 구분자 — 바뀐 과목의 교수, 없으면 분반 번호. */
function sectionTag(tt: Timetable, d: AltDiff | undefined): string | null {
  const c = d?.changes[0];
  const sep = c ? c.indexOf(": ") : -1;
  const name = sep >= 0 ? c!.slice(0, sep) : null;
  if (!name) return null;
  const course = tt.courses.find((x) => x.name === name);
  if (!course) return null;
  return course.professor ? `교수 ${course.professor}` : `${course.section}분반`;
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
