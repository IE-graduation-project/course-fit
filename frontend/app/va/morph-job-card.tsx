"use client";

import { useRef } from "react";
import {
  motion,
  useMotionValue,
  useReducedMotion,
  useSpring,
} from "motion/react";
import { Check } from "lucide-react";
import type { Job } from "@/lib/data";
import { EASE, SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";

interface MorphJobCardProps {
  job: Job;
  selected: boolean;
  onSelect: (id: Job["id"]) => void;
  index: number;
  dimmed?: boolean;
}

/**
 * 모핑 직무 카드 (방향 A).
 *
 * 기존 JobCard 와 동일한 외형 + 두 가지 추가:
 *  (1) layoutId=`job-${id}` : 선택 시 결과 머리글로 자라나는 공유요소.
 *      borderRadius 는 style 로 지정해 scale 보간 시 모서리 왜곡을 자동보정.
 *  (2) capped 자석: 커서를 향해 ±10px(25% falloff). layoutId 와 transform 충돌을
 *      피하려 자석은 INNER 래퍼에만(바깥 button 은 layout/morph 전용).
 * reduced-motion 이면 자석 비활성.
 */
export function MorphJobCard({
  job,
  selected,
  onSelect,
  index,
  dimmed = false,
}: MorphJobCardProps) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLButtonElement>(null);
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const x = useSpring(mx, { stiffness: 150, damping: 22 });
  const y = useSpring(my, { stiffness: 150, damping: 22 });

  function handleMove(e: React.MouseEvent) {
    if (reduce || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const dx = (e.clientX - (r.left + r.width / 2)) * 0.25;
    const dy = (e.clientY - (r.top + r.height / 2)) * 0.25;
    mx.set(Math.max(-10, Math.min(10, dx)));
    my.set(Math.max(-10, Math.min(10, dy)));
  }
  function handleLeave() {
    mx.set(0);
    my.set(0);
  }

  return (
    <motion.button
      ref={ref}
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={() => onSelect(job.id)}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
      layoutId={`job-${job.id}`}
      style={{ borderRadius: "var(--radius)" }}
      initial={{ opacity: 0 }}
      animate={{ opacity: dimmed ? 0.5 : 1 }}
      whileHover={{ scale: 1.012 }}
      whileTap={{ scale: 0.994 }}
      transition={{
        ...SPRING.snappy,
        opacity: { duration: 0.4, delay: 0.04 * index, ease: EASE },
      }}
      className={cn(
        "group relative flex h-full flex-col border p-4 text-left transition-[border-color,background-color] outline-none hover:shadow-sm focus-visible:ring-focus",
        selected
          ? "border-accent bg-accent-wash"
          : "border-line bg-surface hover:border-line-strong",
      )}
    >
      <motion.span style={{ x, y }} className="flex flex-col gap-1.5">
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
      </motion.span>
    </motion.button>
  );
}
