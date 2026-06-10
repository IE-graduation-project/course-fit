"use client";

import { motion } from "motion/react";
import { DAYS, type Course } from "@/lib/data";
import { COURSE_BLOCK } from "@/lib/course-colors";
import { cn } from "@/lib/utils";

const EASE = [0.16, 1, 0.3, 1] as const;

interface TimetableGridProps {
  courses: Course[];
  selectedCourseId?: string | null;
  onSelectCourse?: (id: string) => void;
  /** 첫 등장 시 첫 과목 블록을 1회 pulse (탭 가능을 알리는 보너스 넛지). */
  pulseFirstBlock?: boolean;
}

interface PlacedBlock {
  course: Course;
  day: number;
  startPeriod: number;
  span: number;
}

/** 연속된 교시를 하나의 블록으로 합쳐서 배치 정보를 만든다. */
function buildBlocks(courses: Course[]): PlacedBlock[] {
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
        blocks.push({
          course,
          day,
          startPeriod: runStart,
          span: prev - runStart + 1,
        });
        runStart = cur;
        prev = cur;
      }
    }
  }
  return blocks;
}

const ROW_H = 46;
const GAP = 4;

export function TimetableGrid({
  courses,
  selectedCourseId,
  onSelectCourse,
  pulseFirstBlock = false,
}: TimetableGridProps) {
  const blocks = buildBlocks(courses);
  // 실제 쓰이는 마지막 교시까지만 렌더 (최소 9교시로 안정적인 높이 유지).
  const maxPeriod = Math.max(
    9,
    ...courses.flatMap((c) => c.slots.map((s) => s.period)),
  );
  const periods = Array.from({ length: maxPeriod }, (_, i) => i + 1);
  const interactive = Boolean(onSelectCourse);
  // 첫 추천 과목: 정적 ring + (첫 등장) pulse 대상. 탭 가능을 글 없이 알린다.
  const firstCourseId = courses[0]?.id ?? null;

  return (
    <div className="w-full overflow-x-auto">
      <div className="min-w-[600px]">
        {/* 헤더 (요일) */}
        <div className="grid grid-cols-[2.5rem_repeat(5,1fr)] gap-1">
          <div />
          {DAYS.map((day) => (
            <div
              key={day}
              className="text-ink-muted pb-2 text-center text-[0.8rem] font-semibold tracking-tight"
            >
              {day}
            </div>
          ))}
        </div>

        {/* 본문: 교시 라벨 열 + 5개 요일 열 */}
        <div className="grid grid-cols-[2.5rem_repeat(5,1fr)] gap-1">
          {/* 교시 라벨 (숫자 = mono) */}
          <div className="grid auto-rows-fr gap-1">
            {periods.map((p) => (
              <div
                key={p}
                className="text-ink-subtle flex items-center justify-center font-mono text-[0.68rem] tabular-nums"
                style={{ height: ROW_H }}
              >
                {p}
              </div>
            ))}
          </div>

          {/* 요일별 열 */}
          {DAYS.map((_, dayIdx) => (
            <div key={dayIdx} className="relative grid auto-rows-fr gap-1">
              {/* 빈 셀 배경 (헤어라인) */}
              {periods.map((p) => (
                <div
                  key={p}
                  className="border-line/60 bg-surface-muted/35 rounded-[var(--radius-sm)] border"
                  style={{ height: ROW_H }}
                />
              ))}

              {/* 과목 블록 (절대 배치) */}
              {blocks
                .filter((b) => b.day === dayIdx)
                .map((b, i) => {
                  const c = COURSE_BLOCK[b.course.color];
                  const top = (b.startPeriod - 1) * (ROW_H + GAP);
                  const height = b.span * ROW_H + (b.span - 1) * GAP;
                  const isSelected = selectedCourseId === b.course.id;
                  const isFirst =
                    interactive && b.course.id === firstCourseId;
                  const shouldPulse =
                    isFirst && pulseFirstBlock && !isSelected;
                  return (
                    <motion.button
                      type="button"
                      key={`${b.course.id}-${b.startPeriod}`}
                      onClick={
                        interactive
                          ? () => onSelectCourse?.(b.course.id)
                          : undefined
                      }
                      disabled={!interactive}
                      aria-pressed={interactive ? isSelected : undefined}
                      initial={{ opacity: 0, y: 4 }}
                      animate={
                        shouldPulse
                          ? { opacity: 1, y: 0, scale: [1, 1.04, 1] }
                          : { opacity: 1, y: 0 }
                      }
                      transition={
                        shouldPulse
                          ? { duration: 0.4, ease: EASE }
                          : {
                              duration: 0.38,
                              delay: 0.035 * i + 0.025 * b.day,
                              ease: EASE,
                            }
                      }
                      style={{ top, height }}
                      className={cn(
                        "group absolute inset-x-0 flex flex-col justify-center gap-0.5 overflow-hidden rounded-[var(--radius-sm)] border pr-2 pl-3 text-left transition-[box-shadow,border-color,background-color] outline-none focus-visible:ring-focus",
                        interactive ? "cursor-pointer" : "cursor-default",
                        isSelected
                          ? "border-accent bg-accent-wash ring-2 ring-accent"
                          : cn(
                              c.block,
                              "border-line hover:border-line-strong hover:ring-2 hover:ring-accent/40",
                              isFirst && "ring-1 ring-accent/20",
                            ),
                      )}
                    >
                      <span
                        className={cn(
                          "absolute inset-y-1.5 left-1 w-[2px] rounded-full",
                          isSelected ? "bg-accent-strong" : c.bar,
                        )}
                      />
                      <span
                        className={cn(
                          "truncate text-[0.78rem] font-semibold tracking-tight",
                          isSelected ? "text-accent-strong" : "text-ink",
                        )}
                      >
                        {b.course.name}
                      </span>
                      <span className="text-ink-muted truncate font-mono text-[0.6rem] tabular-nums">
                        {b.course.professor}
                      </span>
                    </motion.button>
                  );
                })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
