"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { DAYS, type Course } from "@/lib/data";
import { COURSE_BLOCK } from "@/lib/course-colors";
import { EASE, SPRING, diagonalDelay } from "@/lib/motion";
import {
  ROW_H,
  blockHeight,
  blockTop,
  buildBlocks,
  maxPeriodFor,
  periodList,
} from "@/lib/timetable-layout";
import { cn } from "@/lib/utils";

interface MorphGridProps {
  courses: Course[];
  selectedCourseId?: string | null;
  onSelectCourse?: (id: string) => void;
  /** 첫 등장 시 첫 블록 1회 pulse (탭 가능 넛지). */
  pulseFirstBlock?: boolean;
}

/**
 * 모핑 시간표 격자 (방향 A).
 *
 * 블록마다 layoutId=`course-${course.id}` + popLayout 으로, 직무 전환 시 두 직무가
 * 공유하는 과목은 새 셀로 미끄러져 이동(SPRING.layout)하고 빠지는/드는 과목만
 * fade. 관객이 "무엇이 남고 무엇이 바뀌었나"를 눈으로 비교한다. 첫 등장은 2D 대각
 * stagger(diagonalDelay) 로 월요일 아침→금요일 저녁 파동.
 * reduced-motion 이면 layout 글라이드 없이 opacity 크로스페이드.
 */
export function MorphGrid({
  courses,
  selectedCourseId,
  onSelectCourse,
  pulseFirstBlock = false,
}: MorphGridProps) {
  const reduce = useReducedMotion();
  const blocks = buildBlocks(courses);
  const maxPeriod = maxPeriodFor(courses);
  const periods = periodList(maxPeriod);
  const interactive = Boolean(onSelectCourse);
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

        {/* 본문 */}
        <div className="grid grid-cols-[2.5rem_repeat(5,1fr)] gap-1">
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

          {DAYS.map((_, dayIdx) => (
            <div key={dayIdx} className="relative grid auto-rows-fr gap-1">
              {periods.map((p) => (
                <div
                  key={p}
                  className="border-line/60 bg-surface-muted/35 rounded-[var(--radius-sm)] border"
                  style={{ height: ROW_H }}
                />
              ))}

              <AnimatePresence mode="popLayout">
                {blocks
                  .filter((b) => b.day === dayIdx)
                  .map((b, i) => {
                    const c = COURSE_BLOCK[b.course.color];
                    const top = blockTop(b.startPeriod);
                    const height = blockHeight(b.span);
                    const isSelected = selectedCourseId === b.course.id;
                    const isFirst = interactive && b.course.id === firstCourseId;
                    const shouldPulse =
                      isFirst && pulseFirstBlock && !isSelected && !reduce;
                    return (
                      <motion.button
                        type="button"
                        key={b.course.id}
                        layoutId={reduce ? undefined : `course-${b.course.id}`}
                        layout={!reduce}
                        onClick={
                          interactive
                            ? () => onSelectCourse?.(b.course.id)
                            : undefined
                        }
                        disabled={!interactive}
                        aria-pressed={interactive ? isSelected : undefined}
                        initial={{ opacity: 0, y: 6 }}
                        animate={
                          shouldPulse
                            ? { opacity: 1, y: 0, scale: [1, 1.04, 1] }
                            : { opacity: 1, y: 0 }
                        }
                        exit={{ opacity: 0, y: 6 }}
                        transition={{
                          layout: SPRING.layout,
                          opacity: {
                            duration: 0.34,
                            delay: diagonalDelay(i, b.day),
                            ease: EASE,
                          },
                          y: {
                            ...SPRING.snappy,
                            delay: diagonalDelay(i, b.day),
                          },
                          scale: { duration: 0.4, ease: EASE },
                        }}
                        style={{ top, height, borderRadius: "var(--radius-sm)" }}
                        className={cn(
                          "group absolute inset-x-0 flex flex-col justify-center gap-0.5 overflow-hidden border pr-2 pl-3 text-left transition-[box-shadow,border-color,background-color] outline-none focus-visible:ring-focus",
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
              </AnimatePresence>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
