"use client";

import type { ReactNode } from "react";
import { motion, useReducedMotion } from "motion/react";
import { SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";

interface MaskRevealProps {
  children: ReactNode;
  className?: string;
  delay?: number;
}

/**
 * 활자 마스크 등장: overflow-hidden 안에서 한 줄이 y 110% → 0 으로 밀려 올라온다.
 * 인쇄물처럼 읽히는 editorial 등장. 헤드라인급 단어에만 쓰고 본문에는 절대 쓰지 않는다.
 * reduced-motion 이면 그냥 정적 텍스트.
 */
export function MaskReveal({ children, className, delay = 0 }: MaskRevealProps) {
  const reduce = useReducedMotion();
  if (reduce) {
    return <span className={cn("inline-block", className)}>{children}</span>;
  }
  return (
    <span className={cn("inline-block overflow-hidden align-bottom", className)}>
      <motion.span
        className="inline-block"
        initial={{ y: "115%" }}
        animate={{ y: 0 }}
        transition={{ ...SPRING.layout, delay }}
      >
        {children}
      </motion.span>
    </span>
  );
}
