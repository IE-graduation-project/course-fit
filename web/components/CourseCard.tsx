"use client";

import type { RecommendedCourse } from "@/lib/types";
import { compColor } from "@/lib/competency";
import { courseHue, courseKey } from "./TimetableGrid";

/**
 * 과목 하나가 왜 추천됐는지.
 *  - 위: 무슨 과목인가 (이름·학점·시간·교수)
 *  - 아래: 왜 (역량 갭 기여 비중 막대 + 졸업요건 기여)
 * share 는 Score_c 의 축별 분해 비중이라 합이 1이다 — 그래서 한 줄 누적 막대로 그린다.
 */
export default function CourseCard({
  course,
  index,
  active,
  onHover,
}: {
  course: RecommendedCourse;
  index: number;
  active: boolean;
  onHover?: (id: string | null) => void;
}) {
  const hue = courseHue(index);
  const key = courseKey(course);
  const reasons = course.careerReason.filter((r) => r.share >= 0.02);
  const grad = course.gradReason;

  return (
    <div
      onMouseEnter={() => onHover?.(key)}
      onMouseLeave={() => onHover?.(null)}
      className="card p-4 transition-all duration-200"
      style={{
        borderLeft: `4px solid oklch(60% 0.15 ${hue})`,
        boxShadow: active ? "var(--shadow-lift)" : undefined,
        transform: active ? "translateY(-2px)" : undefined,
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="truncate text-h3 font-semibold leading-snug">
            {course.name}
          </h4>
          <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-caption text-text-soft">
            <span className="tnum">{course.credit}학점</span>
            <span aria-hidden>·</span>
            <span>{course.area}</span>
            {course.timeRaw && (
              <>
                <span aria-hidden>·</span>
                <span className="tnum">{course.timeRaw}</span>
              </>
            )}
            {course.professor && (
              <>
                <span aria-hidden>·</span>
                <span>{course.professor}</span>
              </>
            )}
          </p>
        </div>
        <span
          className="shrink-0 rounded-sm px-2 py-1 text-caption font-semibold"
          style={{
            background: `oklch(96.5% 0.026 ${hue})`,
            color: `oklch(37% 0.105 ${hue})`,
          }}
        >
          {course.courseId}-{course.section}
        </span>
      </div>

      {/* 왜 — 역량 기여 분해 */}
      {reasons.length > 0 && (
        <div className="mt-3.5">
          <div className="flex h-2.5 gap-0.5 overflow-hidden rounded-sm">
            {reasons.map((r) => (
              <div
                key={r.comp}
                title={`${r.compKo} ${Math.round(r.share * 100)}%`}
                className="rounded-sm"
                style={{
                  width: `${r.share * 100}%`,
                  background: compColor(r.comp),
                }}
              />
            ))}
          </div>
          <p className="mt-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-sm text-text-muted">
            {reasons.map((r) => (
              <span key={r.comp} className="inline-flex items-center gap-1.5">
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ background: compColor(r.comp) }}
                />
                <span className="font-semibold text-text">{r.compKo}</span>
                <span className="tnum text-text-soft">
                  {Math.round(r.share * 100)}%
                </span>
              </span>
            ))}
          </p>
        </div>
      )}

      {grad.remaining > 0 && (
        <p className="mt-2 inline-flex items-center gap-1.5 rounded-sm bg-surface-3 px-2 py-1 text-caption text-text-muted">
          <span className="h-2 w-2 rounded-full bg-grad" />
          <span>
            <span className="font-semibold text-text">{grad.area}</span> 졸업요건{" "}
            <span className="tnum">{grad.remaining}학점</span> 남음
          </span>
        </p>
      )}
    </div>
  );
}
