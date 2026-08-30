"use client";

import type { RecommendedCourse } from "@/lib/types";
import { DAYS, periodRange, periodTime, toBlocks } from "@/lib/slots";

/** 과목별 색 — 채도·명도 고정, 색상만 회전. light 배경에서 텍스트 대비 확보. */
const HUES = [258, 168, 38, 292, 200, 118, 12, 320];

export function courseHue(index: number) {
  return HUES[index % HUES.length];
}

export function courseKey(c: RecommendedCourse) {
  return `${c.courseId}-${c.section}`;
}

interface Props {
  courses: RecommendedCourse[];
  /** 마우스 올린 과목 강조 — 과목 카드와 양방향 연동 */
  activeId?: string | null;
  onHover?: (id: string | null) => void;
}

type Cell = {
  course: RecommendedCourse;
  index: number;
  isStart: boolean;
};

export default function TimetableGrid({ courses, activeId, onHover }: Props) {
  const allSlots = courses.flatMap((c) => c.slots);
  const periods = periodRange(allSlots);

  const placed = new Map<string, Cell>();
  courses.forEach((course, index) => {
    for (const b of toBlocks(course.slots)) {
      for (let i = 0; i < b.span; i++) {
        placed.set(`${b.day}:${b.start + i}`, {
          course,
          index,
          isStart: i === 0,
        });
      }
    }
  });

  const unscheduled = courses.filter((c) => c.slots.length === 0);

  return (
    <div>
      <div
        className="grid overflow-hidden rounded-lg border border-border bg-surface"
        style={{ gridTemplateColumns: "3.25rem repeat(5, minmax(0, 1fr))" }}
      >
        <div className="border-b border-border bg-surface-3" />
        {DAYS.map((d) => (
          <div
            key={d}
            className="border-b border-l border-border bg-surface-3 py-2 text-center text-sm font-semibold text-text-muted"
          >
            {d}
          </div>
        ))}

        {periods.map((p) => (
          <Row
            key={p}
            period={p}
            placed={placed}
            activeId={activeId}
            onHover={onHover}
          />
        ))}
      </div>

      {unscheduled.length > 0 && (
        <p className="mt-3 text-caption text-text-soft">
          시간 미지정 · {unscheduled.map((c) => c.name).join(" · ")}
        </p>
      )}
    </div>
  );
}

function Row({
  period,
  placed,
  activeId,
  onHover,
}: {
  period: number;
  placed: Map<string, Cell>;
  activeId?: string | null;
  onHover?: (id: string | null) => void;
}) {
  return (
    <>
      <div className="flex min-h-[3.5rem] flex-col items-center justify-center border-b border-border bg-surface-3">
        <span className="tnum text-sm font-semibold text-text-muted">{period}</span>
        <span className="tnum text-[0.625rem] text-text-soft">
          {periodTime(period)}
        </span>
      </div>

      {DAYS.map((_, day) => {
        const cell = placed.get(`${day}:${period}`);

        if (!cell) {
          return (
            <div
              key={day}
              className="min-h-[3.5rem] border-b border-l border-border"
            />
          );
        }

        const key = courseKey(cell.course);
        const dim = activeId != null && activeId !== key;
        const hue = courseHue(cell.index);

        return (
          <div
            key={day}
            onMouseEnter={() => onHover?.(key)}
            onMouseLeave={() => onHover?.(null)}
            className="min-h-[3.5rem] border-b border-l border-border p-0.5 transition-opacity duration-200"
            style={{ opacity: dim ? 0.28 : 1 }}
          >
            <div
              className="flex h-full w-full flex-col justify-center overflow-hidden rounded-sm px-2 py-1"
              style={{
                background: `oklch(96.5% 0.026 ${hue})`,
                borderLeft: `3px solid oklch(60% 0.15 ${hue})`,
              }}
            >
              {cell.isStart && (
                <>
                  <span
                    className="text-caption font-semibold leading-tight"
                    style={{ color: `oklch(37% 0.105 ${hue})` }}
                  >
                    {cell.course.name}
                  </span>
                  {cell.course.professor && (
                    <span
                      className="mt-0.5 text-[0.625rem] leading-tight opacity-65"
                      style={{ color: `oklch(37% 0.105 ${hue})` }}
                    >
                      {cell.course.professor}
                    </span>
                  )}
                </>
              )}
            </div>
          </div>
        );
      })}
    </>
  );
}
