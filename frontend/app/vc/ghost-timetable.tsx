"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { GridScaffold } from "@/components/domain/grid-scaffold";
import { blockHeight, blockTop } from "@/lib/timetable-layout";
import { EASE } from "@/lib/motion";

/**
 * Direction C 자가시연 유령 시간표.
 *
 * 텍스트영역 카드 뒤에 실제 격자와 픽셀 단위로 동일한 기하(GridScaffold)를 깔아
 * 유령 → 실제 전환에서 CLS 0 을 보장한다. ~8% 불투명도의 골격 블록이 한 번에
 * 하나씩 plausible 한 셀에 clip-wipe 로 들어왔다 ~700ms 쉬고 사라지며, 다음 블록이
 * 다른 위치에 들어온다. "옵티마이저가 배치를 시도하는" 차분한 ~3.5s 루프.
 *
 * 루프는 setInterval 플래그로 구동한다 (framer repeat:Infinity 금지). active=false
 * 한 번으로 즉시 죽고, 포커스 순간 완전히 사라져 paste 스크린샷에 절대 잡히지 않는다.
 * reduced-motion: 정적 격자 + 한 칸에 쉬는 블록 하나, 루프/타이핑 없음.
 */

const GHOST_MAX_PERIOD = 9;

// 시도 후보들: 충돌 없이 plausible 한 위치 (요일 0=월~4=금, 시작교시, span).
interface GhostSlot {
  day: number;
  startPeriod: number;
  span: number;
}

const GHOST_SLOTS: GhostSlot[] = [
  { day: 0, startPeriod: 2, span: 3 },
  { day: 2, startPeriod: 1, span: 3 },
  { day: 1, startPeriod: 5, span: 2 },
  { day: 3, startPeriod: 4, span: 2 },
  { day: 4, startPeriod: 7, span: 2 },
  { day: 0, startPeriod: 6, span: 2 },
];

const CYCLE_MS = 3500;

interface GhostTimetableProps {
  /** false 가 되면 루프가 즉시 멈추고 블록이 사라진다 (포커스/입력 순간). */
  active: boolean;
}

export function GhostTimetable({ active }: GhostTimetableProps) {
  const reduce = useReducedMotion();
  const [slotIndex, setSlotIndex] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 루프: setInterval 로 후보 슬롯을 하나씩 순환 (effect 본문에서 동기 setState 안 함).
  useEffect(() => {
    if (reduce || !active) return;
    intervalRef.current = setInterval(() => {
      setSlotIndex((i) => (i + 1) % GHOST_SLOTS.length);
    }, CYCLE_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [reduce, active]);

  // reduced-motion: 정적 격자 + 한 칸에 쉬는 블록 하나. 루프 없음.
  if (reduce) {
    const resting = GHOST_SLOTS[0];
    return (
      <div aria-hidden className="pointer-events-none opacity-[0.09]">
        <GridScaffold
          maxPeriod={GHOST_MAX_PERIOD}
          faint
          renderDayBlocks={(dayIdx) =>
            dayIdx === resting.day ? (
              <GhostBlock slot={resting} animate={false} />
            ) : null
          }
        />
      </div>
    );
  }

  const current = GHOST_SLOTS[slotIndex];

  return (
    <div aria-hidden className="pointer-events-none opacity-[0.09]">
      <GridScaffold
        maxPeriod={GHOST_MAX_PERIOD}
        faint
        renderDayBlocks={(dayIdx) => (
          // AnimatePresence 로 감싸 exit 페이드를 보장한다 (사이클 전환 + active=false 양쪽).
          <AnimatePresence>
            {active && dayIdx === current.day && (
              // key 로 슬롯이 바뀔 때마다 새 블록 마운트 → clip-wipe in, 다음 사이클에 out.
              <GhostBlock key={slotIndex} slot={current} animate />
            )}
          </AnimatePresence>
        )}
      />
    </div>
  );
}

function GhostBlock({
  slot,
  animate,
}: {
  slot: GhostSlot;
  animate: boolean;
}) {
  const top = blockTop(slot.startPeriod);
  const height = blockHeight(slot.span);

  if (!animate) {
    return (
      <div
        className="border-line bg-surface-muted absolute inset-x-0 rounded-[var(--radius-sm)] border pl-3"
        style={{ top, height }}
      >
        <span className="bg-ink-subtle absolute inset-y-2 left-1 w-[2px] rounded-full" />
      </div>
    );
  }

  return (
    <motion.div
      className="border-line bg-surface-muted absolute inset-x-0 rounded-[var(--radius-sm)] border pl-3"
      style={{ top, height }}
      initial={{ clipPath: "inset(0 0 100% 0)", opacity: 0, y: 4 }}
      animate={{ clipPath: "inset(0 0 0% 0)", opacity: 1, y: 0 }}
      // 사이클이 끝나며 다음 블록 key 가 바뀌면 이 블록은 unmount 된다 → exit 로 페이드(140ms).
      exit={{ opacity: 0, transition: { duration: 0.14, ease: EASE } }}
      transition={{ duration: 0.52, ease: EASE }}
    >
      <span className="bg-ink-subtle absolute inset-y-2 left-1 w-[2px] rounded-full" />
    </motion.div>
  );
}
