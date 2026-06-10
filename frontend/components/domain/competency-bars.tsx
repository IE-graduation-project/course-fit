"use client";

import { motion } from "motion/react";
import type { Competency } from "@/lib/data";

const EASE = [0.16, 1, 0.3, 1] as const;

interface CompetencyBarsProps {
  competencies: Competency[];
}

/**
 * 역량별 요구 vs 달성 가로 막대. 갭이 큰 항목(요구-달성)을 위로 정렬해서
 * "무엇을 채워야 하는지"를 한눈에 보여준다. 색은 warm 트랙 + 그린 1색.
 */
export function CompetencyBars({ competencies }: CompetencyBarsProps) {
  const sorted = [...competencies].sort(
    (a, b) => b.required - b.achieved - (a.required - a.achieved),
  );

  return (
    <ul className="space-y-3">
      {sorted.map((c, i) => {
        const gap = Math.round((c.required - c.achieved) * 100);
        return (
          <li key={c.label}>
            <div className="mb-1 flex items-center justify-between text-[0.82rem]">
              <span className="text-ink font-medium">{c.label}</span>
              <span className="text-ink-subtle font-mono tabular-nums">
                {Math.round(c.achieved * 100)} / {Math.round(c.required * 100)}
                {gap > 0 && (
                  <span className="text-accent ml-1.5 font-medium">-{gap}</span>
                )}
              </span>
            </div>
            <div className="bg-surface-muted border-line relative h-2 overflow-hidden rounded-full border">
              {/* 요구 수준 (warm 트랙) */}
              <motion.div
                initial={{ width: 0 }}
                whileInView={{ width: `${c.required * 100}%` }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: 0.03 * i, ease: EASE }}
                className="bg-line-strong absolute inset-y-0 left-0 rounded-full"
              />
              {/* 달성 수준 (그린 accent) */}
              <motion.div
                initial={{ width: 0 }}
                whileInView={{ width: `${c.achieved * 100}%` }}
                viewport={{ once: true }}
                transition={{
                  duration: 0.7,
                  delay: 0.03 * i + 0.08,
                  ease: EASE,
                }}
                className="bg-accent absolute inset-y-0 left-0 rounded-full"
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
