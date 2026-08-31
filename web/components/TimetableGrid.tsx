"use client";

import type { RecommendedCourse } from "@/lib/types";
import { DAYS, periodRange, periodTime, toBlocks } from "@/lib/slots";

export function courseKey(c: RecommendedCourse) {
  return `${c.courseId}-${c.section}`;
}

interface Props {
  courses: RecommendedCourse[];
  /** 마우스 올린 과목 — 과목 카드와 양방향 연동 */
  activeId?: string | null;
  onHover?: (id: string | null) => void;
}

/**
 * 월~금 × 교시 시간표.
 *
 * 격자(빈 칸)를 먼저 깔고, 과목 블록을 grid 명시 배치로 그 위에 얹는다.
 * 그래야 연강이 칸마다 쪼개지지 않고 한 덩어리로 읽힌다.
 *
 * 블록에 과목명이 이미 적혀 있어서 색은 식별을 하지 않는다 — 그래서 과목마다
 * hue 를 돌리지 않고 전부 중립으로 두고, 강조(호버)에만 accent 하나를 쓴다.
 */
export default function TimetableGrid({ courses, activeId, onHover }: Props) {
  const periods = periodRange(courses.flatMap((c) => c.slots));
  const rowOf = new Map(periods.map((p, i) => [p, i]));

  const blocks = courses.flatMap((course) =>
    toBlocks(course.slots).map((b) => ({ course, ...b })),
  );

  const unscheduled = courses.filter((c) => c.slots.length === 0);

  return (
    <div>
      <div
        className="grid overflow-hidden rounded-lg border border-border bg-surface"
        style={{
          gridTemplateColumns: "3rem repeat(5, minmax(0, 1fr))",
          gridTemplateRows: `auto repeat(${periods.length}, minmax(3.25rem, auto))`,
        }}
      >
        {/* 헤더 */}
        <div className="border-b border-border bg-surface-2" />
        {DAYS.map((d) => (
          <div
            key={d}
            className="border-b border-l border-border bg-surface-2 py-2 text-center text-sm font-medium text-text-muted"
          >
            {d}
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
          DAYS.map((_, day) => (
            <div
              key={`cell-${day}-${p}`}
              className="border-b border-l border-border"
              style={{ gridColumn: day + 2, gridRow: r + 2 }}
            />
          )),
        )}

        {/* 과목 블록 — 연강은 rowSpan 하나로 */}
        {blocks.map((b) => {
          const key = courseKey(b.course);
          const active = activeId === key;
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
                  (active ? "bg-brand-100 ring-1 ring-brand-400" : "bg-surface-3")
                }
                style={{
                  borderLeft: `3px solid var(${
                    active ? "--color-brand-500" : "--color-border-strong"
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

      {unscheduled.length > 0 && (
        <p className="mt-3 text-caption text-text-soft">
          시간 미지정 · {unscheduled.map((c) => c.name).join(" · ")}
        </p>
      )}
    </div>
  );
}
