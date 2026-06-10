"use client";

import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";
import { cn } from "@/lib/utils";

/**
 * 0(또는 from)에서 value 까지 RAF 로 세는 카운트업 (FitScore 와 동일 규율).
 * "방금 이 값을 계산했다"를 모션으로 증명. reduced-motion 이면 즉시 최종값으로 snap.
 */
export function useCountUp(
  value: number,
  { duration = 520, from = 0 }: { duration?: number; from?: number } = {},
) {
  const reduce = useReducedMotion();
  const [display, setDisplay] = useState(from);
  const fromRef = useRef(from);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (reduce) return; // reduced: 렌더에서 value 를 그대로 반환 (setState 안 함)
    const startVal = fromRef.current;
    if (startVal === value) return;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      setDisplay(startVal + (value - startVal) * eased);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = value;
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      fromRef.current = value;
    };
  }, [value, duration, reduce]);

  return reduce ? value : display;
}

interface CountUpProps {
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
  className?: string;
}

/** 숫자 카운트업 + 단위 라벨. 숫자는 tabular-nums 라 자릿수가 흔들리지 않는다. */
export function CountUp({
  value,
  decimals = 0,
  prefix = "",
  suffix = "",
  duration = 520,
  className,
}: CountUpProps) {
  const display = useCountUp(value, { duration });
  return (
    <span className={cn("font-mono tabular-nums", className)}>
      {prefix}
      {display.toFixed(decimals)}
      {suffix}
    </span>
  );
}
