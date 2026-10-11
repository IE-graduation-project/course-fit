"use client";

import type { RecommendedCourse } from "@/lib/types";
import { DAYS, WEEKDAYS, periodRange, periodTime, toBlocks } from "@/lib/slots";

export function courseKey(c: RecommendedCourse) {
  return `${c.courseId}-${c.section}`;
}

interface Props {
  courses: RecommendedCourse[];
  /** 마우스 올린 과목 — 과목 카드와 양방향 연동 */
  activeId?: string | null;
  onHover?: (id: string | null) => void;
  /** 공강으로 비운 요일(0=월 … 4=금). 그 열을 칠해 일부러 비운 날이라는 걸 밝힌다 */
  freeDays?: number[];
}

/**
 * 월~금(토·일 분반이 있으면 그 요일까지) × 교시 시간표. 공강으로 비운 요일은 열을 칠한다.
 *
 * 격자(빈 칸)를 먼저 깔고, 과목 블록을 grid 명시 배치로 그 위에 얹는다.
 * 그래야 연강이 칸마다 쪼개지지 않고 한 덩어리로 읽힌다.
 *
 * 블록에 과목명이 이미 적혀 있어서 색은 식별을 하지 않는다 — 그래서 과목마다
 * hue 를 돌리지 않고 전부 중립으로 두고, 강조(호버)에만 accent 하나를 쓴다.
 */
export default function TimetableGrid({ courses, activeId, onHover, freeDays = [] }: Props) {
  const periods = periodRange(courses.flatMap((c) => c.slots));
  const rowOf = new Map(periods.map((p, i) => [p, i]));

  const blocks = courses.flatMap((course) =>
    toBlocks(course.slots).map((b) => ({ course, ...b })),
  );
  const days = DAYS.slice(0, Math.max(WEEKDAYS, ...blocks.map((b) => b.day + 1)));

  const unscheduled = courses.filter((c) => c.slots.length === 0);

  // 「시간 충돌 0」이 이 앱이 보증하는 것이다. 그게 깨진 데이터가 오면 격자에서
  // 한 과목이 다른 과목을 덮어 조용히 사라지므로, 숨기지 말고 드러낸다.
  const owners = new Map<number, Set<string>>();
  for (const c of courses) {
    for (const slot of c.slots) {
      if (!owners.has(slot)) owners.set(slot, new Set());
      owners.get(slot)!.add(courseKey(c));
    }
  }
  const clashing = new Set<string>();
  for (const keys of owners.values()) {
    if (keys.size > 1) for (const k of keys) clashing.add(k);
  }
  const clashNames = courses
    .filter((c) => clashing.has(courseKey(c)))
    .map((c) => c.name);

  return (
    <div>
      <div
        className="grid overflow-hidden rounded-lg border border-border bg-surface"
        style={{
          gridTemplateColumns: `3rem repeat(${days.length}, minmax(0, 1fr))`,
          gridTemplateRows: `auto repeat(${periods.length}, minmax(3.25rem, auto))`,
        }}
      >
        {/* 헤더 */}
        <div className="border-b border-border bg-surface-2" />
        {days.map((d, day) => (
          <div
            key={d}
            className="border-b border-l border-border bg-surface-2 py-2 text-center text-sm font-medium text-text-muted"
          >
            {d}
            {freeDays.includes(day) && (
              <span className="ml-1.5 text-caption font-semibold text-brand-700">공강</span>
            )}
          </div>
        ))}

        {/* 교시 라벨 + 빈 격자 */}
        {periods.map((p, r) => (
          <div key={`lab-${p}`} style={{ gridColumn: 1, gridRow: r + 2 }}>
            <div className="flex h-full flex-col items-center justify-center border-b border-border bg-surface-2">
              <span className="tnum text-sm text-text-muted">{p}</span>
              <span className="tnum text-[0.625rem] text-text-soft">
                {periodTime(p)}
              </span>
            </div>
          </div>
        ))}
        {periods.map((p, r) =>
          days.map((_, day) => (
            <div
              key={`cell-${day}-${p}`}
              className={
                "border-b border-l border-border" + (freeDays.includes(day) ? " bg-surface-3" : "")
              }
              style={{ gridColumn: day + 2, gridRow: r + 2 }}
            />
          )),
        )}

        {/* 과목 블록 — 연강은 rowSpan 하나로 */}
        {blocks.map((b) => {
          const key = courseKey(b.course);
          const active = activeId === key;
          const clash = clashing.has(key);
          const r = rowOf.get(b.start);
          if (r === undefined) return null;

          return (
            <div
              key={`${key}-${b.day}-${b.start}`}
              onMouseEnter={() => onHover?.(key)}
              onMouseLeave={() => onHover?.(null)}
              className="p-0.5"
              style={{
                gridColumn: b.day + 2,
                gridRow: `${r + 2} / span ${b.span}`,
              }}
            >
              <div
                className={
                  "flex h-full w-full flex-col justify-center overflow-hidden rounded-sm px-2 py-1.5 transition-colors duration-150 " +
                  (clash
                    ? "bg-danger/10 ring-1 ring-danger"
                    : active
                      ? "bg-brand-100 ring-1 ring-brand-400"
                      : "bg-surface-3")
                }
                style={{
                  borderLeft: `3px solid var(${
                    clash
                      ? "--color-danger"
                      : active
                        ? "--color-brand-500"
                        : "--color-border-strong"
                  })`,
                }}
              >
                <span
                  className={
                    "text-caption font-semibold leading-tight " +
                    (active ? "text-brand-800" : "text-text")
                  }
                >
                  {b.course.name}
                </span>
                {b.course.professor && (
                  <span className="mt-0.5 text-[0.625rem] leading-tight text-text-soft">
                    {b.course.professor}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {clashNames.length > 0 && (
        <p role="alert" className="mt-3 text-caption font-semibold text-danger">
          시간이 겹치는 과목이 있습니다 — {clashNames.join(" · ")}. 추천 결과에
          문제가 있으니 그대로 신청하지 마세요.
        </p>
      )}

      {/* 격자 칸 수와 과목 수가 어긋나 보이는 원인이다(9/14 피드백 ②).
          흐린 한 줄로 두면 칸만 세고 「과목이 모자라다」고 읽는다 — 이유까지 적는다. */}
      {unscheduled.length > 0 && (
        <p className="mt-3 rounded-md border border-border bg-surface-3 px-3 py-2 text-caption text-text-muted">
          <b className="text-text">
            시간 미지정 {unscheduled.length}과목
          </b>{" "}
          — {unscheduled.map((c) => c.name).join(" · ")}. 정해진 교시가 없는
          분반(비대면·논문·실습 등)이라 격자에는 자리가 없지만,{" "}
          <b className="text-text">추천에는 포함된 과목</b>입니다.
        </p>
      )}
    </div>
  );
}
