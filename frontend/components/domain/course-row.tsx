"use client";

import { motion } from "motion/react";
import type { Course } from "@/lib/data";

const EASE = [0.16, 1, 0.3, 1] as const;

interface CourseRowProps {
  course: Course;
  index: number;
}

export function CourseRow({ course, index }: CourseRowProps) {
  return (
    <motion.li
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.04 * index, ease: EASE }}
      className="border-line bg-surface hover:border-line-strong group flex items-stretch gap-3 rounded-[var(--radius-sm)] border p-3 transition-colors"
    >
      <span className="bg-accent w-[2px] shrink-0 rounded-full" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-[0.9rem] font-semibold tracking-tight">
            {course.name}
          </span>
          <span className="text-ink-subtle shrink-0 font-mono text-[0.7rem] tabular-nums">
            {course.credits}학점
          </span>
        </div>
        <div className="text-ink-subtle mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-0.5 font-mono text-[0.7rem] tabular-nums">
          <span className="text-ink-muted">{course.category}</span>
          <span aria-hidden className="text-line-strong">/</span>
          <span>{course.professor}</span>
          <span aria-hidden className="text-line-strong">/</span>
          <span>{course.slotLabel}</span>
        </div>
      </div>
    </motion.li>
  );
}
