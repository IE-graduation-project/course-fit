"use client";

import { motion } from "motion/react";
import { Check } from "lucide-react";
import type { Job } from "@/lib/data";
import { cn } from "@/lib/utils";

const EASE = [0.16, 1, 0.3, 1] as const;

interface JobCardProps {
  job: Job;
  selected: boolean;
  onSelect: (id: Job["id"]) => void;
  index: number;
  /** "잘 모르겠어요" 방향 좁히기에서 해당 방향이 아닐 때 흐리게. */
  dimmed?: boolean;
}

export function JobCard({
  job,
  selected,
  onSelect,
  index,
  dimmed = false,
}: JobCardProps) {
  return (
    <motion.button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={() => onSelect(job.id)}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: dimmed ? 0.5 : 1, y: 0 }}
      whileHover={{ scale: 1.012 }}
      whileTap={{ scale: 0.994 }}
      transition={{ duration: 0.4, delay: 0.04 * index, ease: EASE }}
      className={cn(
        "group relative flex h-full flex-col gap-1.5 rounded-[var(--radius)] border p-4 text-left transition-[box-shadow,border-color,background-color] outline-none hover:shadow-sm focus-visible:ring-focus",
        selected
          ? "border-accent bg-accent-wash"
          : "border-line bg-surface hover:border-line-strong",
      )}
    >
      <span className="flex items-center justify-between gap-2">
        <span
          className={cn(
            "text-[0.98rem] font-semibold tracking-tight transition-colors",
            selected ? "text-accent-strong" : "text-ink",
          )}
        >
          {job.name}
        </span>
        <span
          className={cn(
            "flex size-5 shrink-0 items-center justify-center rounded-full border transition-colors",
            selected
              ? "border-accent bg-accent text-accent-ink"
              : "border-line text-transparent",
          )}
        >
          <Check className="size-3" strokeWidth={3} />
        </span>
      </span>
      <span className="text-ink-muted text-[0.82rem] leading-snug">
        {job.tagline}
      </span>
      <span className="text-ink-subtle mt-auto pt-1 font-mono text-[0.62rem] tracking-[0.06em]">
        {job.code}
      </span>
    </motion.button>
  );
}
