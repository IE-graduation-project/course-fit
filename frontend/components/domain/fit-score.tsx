"use client";

import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";

interface FitScoreProps {
  value: number;
  className?: string;
  /** 카운트업이 끝난 뒤 1회 호출 (첫 등장 피크 연출용). */
  onSettled?: () => void;
}

/**
 * 적합도 점수.
 * 첫 등장에는 0에서 값까지 세어 결과의 피크를 만들고,
 * 이후 직무 토글로 값이 바뀌면 이전 값에서 새 값으로 짧게 카운트한다.
 * 점수표/수식은 노출하지 않고, 결과 한 줄 요약의 숫자 하이라이트로만 쓴다.
 */
export function FitScore({ value, className, onSettled }: FitScoreProps) {
  const reduce = useReducedMotion();
  // 첫 등장은 0에서 시작하도록 display/from을 0으로 둔다.
  const [display, setDisplay] = useState(0);
  const fromRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const settledRef = useRef(onSettled);

  // 최신 콜백을 ref에 보관 (effect 안에서만 갱신, 렌더 중 ref 쓰기 금지).
  useEffect(() => {
    settledRef.current = onSettled;
  }, [onSettled]);

  useEffect(() => {
    // reduced-motion: 카운트업 없이 최종값으로 즉시 확정 (렌더는 value 를 그대로 반환).
    if (reduce) {
      fromRef.current = value;
      settledRef.current?.();
      return;
    }
    const from = fromRef.current;
    const to = value;
    if (from === to) {
      settledRef.current?.();
      return;
    }
    const duration = 480;
    const start = performance.now();

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      // easeOutCubic
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(Math.round(from + (to - from) * eased));
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = to;
        settledRef.current?.();
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      fromRef.current = to;
    };
  }, [value, reduce]);

  return (
    <span className={className}>
      <span className="font-mono tabular-nums">{reduce ? value : display}</span>
    </span>
  );
}
