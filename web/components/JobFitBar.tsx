"use client";

import { useEffect, useRef, useState } from "react";
import type { JobFit } from "@/lib/types";
import { jobRank } from "@/lib/competency";

/**
 * 직무 6종을 한 줄에 나란히 놓고 적합도를 같이 보여준다 — switch and see.
 * (6월 프론트 `job-toggle-bar` 의 아이디어. 거기선 mock 이었고 여기선 실제 σ/ρ 산출이다.)
 *
 * 순서는 고정한다. 적합도 순으로 재정렬하면 누를 때마다 위치가 흔들려서
 * "아까 그 자리"가 사라진다. 대신 1등에만 표식을 둔다.
 */
export default function JobFitBar({
  fits,
  active,
  onChange,
}: {
  fits: JobFit[];
  active: string;
  onChange: (jobId: string) => void;
}) {
  const ordered = [...fits].sort((a, b) => jobRank(a.job) - jobRank(b.job));
  const best = fits.reduce<JobFit | null>(
    (m, f) => (m === null || f.fit > m.fit ? f : m),
    null,
  );

  return (
    <div
      role="tablist"
      aria-label="목표 직무"
      className="flex gap-1 overflow-x-auto rounded-lg border border-border bg-surface p-1"
    >
      {ordered.map((f) => {
        const selected = f.job === active;
        return (
          <button
            key={f.job}
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(f.job)}
            className={
              "flex shrink-0 items-center gap-2 whitespace-nowrap rounded-sm px-3 py-2 text-sm transition-colors " +
              (selected
                ? "bg-ink text-white"
                : "text-text-muted hover:bg-surface-3 hover:text-text")
            }
          >
            <span className={selected ? "font-semibold" : undefined}>
              {f.name}
            </span>
            <span
              className={
                "tnum text-caption " +
                (selected ? "text-white/80" : "text-text-soft")
              }
            >
              <CountUp value={f.fit} />
            </span>
            {best?.job === f.job && (
              <span
                aria-label="가장 잘 맞음"
                title="지금 가장 잘 맞는 직무"
                className={selected ? "text-white/70" : "text-success"}
              >
                ★
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/** 첫 등장에 0 → 값. reduced-motion 이면 즉시 확정한다. */
function CountUp({ value }: { value: number }) {
  const [shown, setShown] = useState(value);
  const from = useRef(0);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reduce) {
      from.current = value;
      setShown(value);
      return;
    }

    const start = performance.now();
    const a = from.current;
    const b = value;
    const DURATION = 420;

    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / DURATION);
      const eased = 1 - Math.pow(1 - t, 3); // easeOutCubic
      setShown(a + (b - a) * eased);
      if (t < 1) raf.current = requestAnimationFrame(tick);
      else from.current = b;
    };
    raf.current = requestAnimationFrame(tick);

    return () => {
      if (raf.current !== null) cancelAnimationFrame(raf.current);
    };
  }, [value]);

  return <>{shown.toFixed(0)}</>;
}
