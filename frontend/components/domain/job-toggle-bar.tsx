"use client";

import { motion } from "motion/react";
import { JOBS, JOB_PLANS, type JobId } from "@/lib/data";
import { cn } from "@/lib/utils";

interface JobToggleBarProps {
  active: JobId;
  onChange: (id: JobId) => void;
}

/**
 * switch and see: 결과 상단에 머무는 직무 토글 바.
 * 다른 직무를 누르면 사전 계산된 시간표로 즉시 바뀐다 (mock 캐시 조회).
 */
export function JobToggleBar({ active, onChange }: JobToggleBarProps) {
  return (
    <div
      role="tablist"
      aria-label="직무 전환"
      className="border-line bg-surface scrollbar-none flex w-full gap-1 overflow-x-auto rounded-[var(--radius)] border p-1"
    >
      {JOBS.map((job) => {
        const selected = job.id === active;
        return (
          <button
            key={job.id}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(job.id)}
            className={cn(
              "relative flex shrink-0 items-center gap-2 rounded-[var(--radius-sm)] px-3 py-1.5 text-[0.85rem] font-medium whitespace-nowrap transition-colors outline-none focus-visible:ring-focus",
              selected ? "text-accent-ink" : "text-ink-muted hover:text-ink",
            )}
          >
            {selected && (
              <motion.span
                layoutId="job-toggle-active"
                transition={{ type: "spring", stiffness: 420, damping: 34 }}
                className="bg-accent absolute inset-0 -z-10 rounded-[var(--radius-sm)]"
              />
            )}
            {job.name}
            <span
              className={cn(
                "font-mono text-[0.72rem] tabular-nums",
                selected
                  ? "text-accent-ink/90 font-semibold"
                  : "text-ink-subtle",
              )}
            >
              {JOB_PLANS[job.id].fitScore}
            </span>
          </button>
        );
      })}
    </div>
  );
}
