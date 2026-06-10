"use client";

import type { ReactNode } from "react";
import { DAYS } from "@/lib/data";
import { ROW_H, periodList } from "@/lib/timetable-layout";

interface GridScaffoldProps {
  /** 렌더할 교시 수 (보통 maxPeriodFor 결과). */
  maxPeriod: number;
  /** 각 요일 열(0=월)에 절대 배치로 얹을 블록 레이어. 유령/실제 블록을 주입. */
  renderDayBlocks?: (dayIdx: number) => ReactNode;
  /** 헤더(요일)와 교시 라벨을 더 흐리게 (유령 모드). */
  faint?: boolean;
}

/**
 * 빈 시간표 격자 골격 (요일 헤더 + 교시 라벨 + 헤어라인 빈 셀).
 *
 * 유령 시간표(자가시연)와 실제 추천 격자가 픽셀 단위로 동일한 기하를 쓰도록 공유한다.
 * renderDayBlocks 로 블록 레이어만 갈아끼우면 유령 → 실제가 CLS 0 으로 전환된다.
 */
export function GridScaffold({ maxPeriod, renderDayBlocks, faint = false }: GridScaffoldProps) {
  const periods = periodList(maxPeriod);
  return (
    <div className="w-full overflow-x-auto">
      <div className="min-w-[600px]">
        {/* 헤더 (요일) */}
        <div className="grid grid-cols-[2.5rem_repeat(5,1fr)] gap-1">
          <div />
          {DAYS.map((day) => (
            <div
              key={day}
              className={
                faint
                  ? "text-ink-subtle/55 pb-2 text-center text-[0.8rem] font-semibold tracking-tight"
                  : "text-ink-muted pb-2 text-center text-[0.8rem] font-semibold tracking-tight"
              }
            >
              {day}
            </div>
          ))}
        </div>

        {/* 본문: 교시 라벨 열 + 5개 요일 열 */}
        <div className="grid grid-cols-[2.5rem_repeat(5,1fr)] gap-1">
          <div className="grid auto-rows-fr gap-1">
            {periods.map((p) => (
              <div
                key={p}
                className={
                  faint
                    ? "text-ink-subtle/45 flex items-center justify-center font-mono text-[0.68rem] tabular-nums"
                    : "text-ink-subtle flex items-center justify-center font-mono text-[0.68rem] tabular-nums"
                }
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
              {renderDayBlocks?.(dayIdx)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
