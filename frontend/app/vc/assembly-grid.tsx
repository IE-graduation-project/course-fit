"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { DAYS, type Course } from "@/lib/data";
import { COURSE_BLOCK } from "@/lib/course-colors";
import {
  ROW_H,
  blockHeight,
  blockTop,
  buildBlocks,
  maxPeriodFor,
  periodList,
} from "@/lib/timetable-layout";
import { diagonalDelay, EASE, SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";

/**
 * Direction C 결과 조립 격자 (THE ASSEMBLY).
 *
 * ACT 1: 빈 Mon~Fri 격자가 stage 로 clip-wipe 등장 (2px 그린 leading edge).
 * ACT 2: 실제 과목 블록이 대각 stagger(diagonalDelay)로 셀에 DROP (SPRING.snappy).
 * 직무 전환: 각 블록에 layoutId 를 주고 AnimatePresence mode="popLayout" 로 감싸,
 * 공유 과목은 새 셀로 GLIDE(SPRING.layout)하고 다른 과목만 fade. id 만으로 key 한다.
 * borderRadius 는 style 로 준다 (layoutId 요소의 className radius 왜곡 방지).
 * reduced-motion: stage/블록 즉시 최종 프레임, 직무 전환은 job key crossfade.
 */

const STAGE_REVEAL_MS = 0.42;

interface AssemblyGridProps {
  /** 현재 직무 키 (전환 crossfade 용). */
  jobKey: string;
  courses: Course[];
  selectedCourseId?: string | null;
  onSelectCourse?: (id: string) => void;
  /** 첫 등장(조립) 여부. false 면 직무 전환 → 블록 stagger 없이 glide/crossfade. */
  firstAssembly: boolean;
}

export function AssemblyGrid({
  jobKey,
  courses,
  selectedCourseId,
  onSelectCourse,
  firstAssembly,
}: AssemblyGridProps) {
  const reduce = useReducedMotion();
  const blocks = buildBlocks(courses);
  const maxPeriod = maxPeriodFor(courses);
  const periods = periodList(maxPeriod);
  const interactive = Boolean(onSelectCourse);

  // reduced-motion: 직무 전환을 job key crossfade 로. 블록은 즉시 최종 프레임.
  if (reduce) {
    return (
      <div className="w-full overflow-x-auto">
        <div className="min-w-[600px]">
          <GridHeader />
          <div className="grid grid-cols-[2.5rem_repeat(5,1fr)] gap-1">
            <PeriodLabels periods={periods} />
            <AnimatePresence mode="wait">
              <motion.div
                key={jobKey}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="contents"
              >
                {DAYS.map((_, dayIdx) => (
                  <DayColumn key={dayIdx} periods={periods}>
                    {blocks
                      .filter((b) => b.day === dayIdx)
                      .map((b) => (
                        <CourseBlock
                          key={b.course.id}
                          course={b.course}
                          top={blockTop(b.startPeriod)}
                          height={blockHeight(b.span)}
                          selected={selectedCourseId === b.course.id}
                          interactive={interactive}
                          onSelect={onSelectCourse}
                          motionMode="static"
                        />
                      ))}
                  </DayColumn>
                ))}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full overflow-x-auto">
      <div className="min-w-[600px]">
        <GridHeader />
        <div className="grid grid-cols-[2.5rem_repeat(5,1fr)] gap-1">
          <PeriodLabels periods={periods} />
          {DAYS.map((_, dayIdx) => (
            <DayColumn key={dayIdx} periods={periods}>
              {/* ACT 1: 첫 조립 때만 빈 stage 가 위→아래로 clip-wipe (2px 그린 leading edge). */}
              {firstAssembly && (
                <motion.div
                  aria-hidden
                  className="border-accent/0 pointer-events-none absolute inset-0 rounded-[var(--radius-sm)]"
                  initial={{ clipPath: "inset(0 0 100% 0)" }}
                  animate={{ clipPath: "inset(0 0 0% 0)" }}
                  transition={{
                    duration: STAGE_REVEAL_MS,
                    delay: 0.04 * dayIdx,
                    ease: EASE,
                  }}
                >
                  <span className="bg-accent absolute inset-x-0 bottom-0 h-[2px] origin-left" />
                </motion.div>
              )}

              {/* ACT 2 + 직무 전환: 블록. popLayout 로 공유 과목 glide, 나머지 fade. */}
              <AnimatePresence mode="popLayout">
                {blocks
                  .filter((b) => b.day === dayIdx)
                  .map((b, i) => (
                    <CourseBlock
                      key={b.course.id}
                      course={b.course}
                      top={blockTop(b.startPeriod)}
                      height={blockHeight(b.span)}
                      selected={selectedCourseId === b.course.id}
                      interactive={interactive}
                      onSelect={onSelectCourse}
                      motionMode={firstAssembly ? "drop" : "glide"}
                      dropDelay={
                        firstAssembly
                          ? STAGE_REVEAL_MS + diagonalDelay(i, dayIdx)
                          : 0
                      }
                    />
                  ))}
              </AnimatePresence>
            </DayColumn>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ──────────────────────────── 격자 골격 조각 ──────────────────────── */

function GridHeader() {
  return (
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
  );
}

function PeriodLabels({ periods }: { periods: number[] }) {
  return (
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
  );
}

function DayColumn({
  periods,
  children,
}: {
  periods: number[];
  children: React.ReactNode;
}) {
  return (
    <div className="relative grid auto-rows-fr gap-1">
      {periods.map((p) => (
        <div
          key={p}
          className="border-line/60 bg-surface-muted/35 rounded-[var(--radius-sm)] border"
          style={{ height: ROW_H }}
        />
      ))}
      {children}
    </div>
  );
}

/* ──────────────────────────── 과목 블록 ──────────────────────────── */

interface CourseBlockProps {
  course: Course;
  top: number;
  height: number;
  selected: boolean;
  interactive: boolean;
  onSelect?: (id: string) => void;
  motionMode: "drop" | "glide" | "static";
  dropDelay?: number;
}

function CourseBlock({
  course,
  top,
  height,
  selected,
  interactive,
  onSelect,
  motionMode,
  dropDelay = 0,
}: CourseBlockProps) {
  const c = COURSE_BLOCK[course.color];

  // drop: 첫 조립 시 셀로 떨어짐. glide: 직무 전환 시 새 셀로 활주(layout). static: 즉시.
  const initial =
    motionMode === "drop"
      ? { opacity: 0, y: -10, scale: 0.96 }
      : motionMode === "glide"
        ? { opacity: 0, scale: 0.96 }
        : false;
  const transition =
    motionMode === "drop"
      ? { ...SPRING.snappy, delay: dropDelay }
      : motionMode === "glide"
        ? SPRING.layout
        : { duration: 0 };

  return (
    <motion.button
      type="button"
      layoutId={`vc-course-${course.id}`}
      onClick={interactive ? () => onSelect?.(course.id) : undefined}
      disabled={!interactive}
      aria-pressed={interactive ? selected : undefined}
      initial={initial}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.96 }}
      transition={transition}
      // borderRadius 는 style 로 (layoutId 보간 시 className radius 왜곡 방지).
      style={{ top, height, borderRadius: "var(--radius-sm)" }}
      className={cn(
        "group absolute inset-x-0 flex flex-col justify-center gap-0.5 overflow-hidden border pr-2 pl-3 text-left transition-[border-color,background-color] outline-none focus-visible:ring-focus",
        interactive ? "cursor-pointer" : "cursor-default",
        selected
          ? "border-accent bg-accent-wash ring-2 ring-accent"
          : cn(
              c.block,
              "border-line hover:border-line-strong hover:ring-2 hover:ring-accent/40",
            ),
      )}
    >
      <span
        className={cn(
          "absolute inset-y-1.5 left-1 w-[2px] rounded-full",
          selected ? "bg-accent-strong" : c.bar,
        )}
      />
      <span
        className={cn(
          "truncate text-[0.78rem] font-semibold tracking-tight",
          selected ? "text-accent-strong" : "text-ink",
        )}
      >
        {course.name}
      </span>
      <span className="text-ink-muted truncate font-mono text-[0.6rem] tabular-nums">
        {course.professor}
      </span>
    </motion.button>
  );
}
