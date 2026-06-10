import type { CourseColor } from "@/lib/data";

/**
 * 과목 색(1~6) → 무채색 명도 사다리 클래스.
 * Instrument Panel: 무지개 6색을 폐기하고 그레이 6단계 + 좌측 accent bar 1색으로 통일.
 * 모든 블록은 동일한 그린 accent bar 를 쓰고, 표면 명도만 단계적으로 다릅니다.
 */
export const COURSE_BLOCK: Record<
  CourseColor,
  { block: string; bar: string; text: string }
> = {
  1: { block: "bg-grade-1", bar: "bg-accent-strong", text: "text-ink" },
  2: { block: "bg-grade-2", bar: "bg-accent-strong", text: "text-ink" },
  3: { block: "bg-grade-3", bar: "bg-accent-strong", text: "text-ink" },
  4: { block: "bg-grade-4", bar: "bg-accent-strong", text: "text-ink" },
  5: { block: "bg-grade-5", bar: "bg-accent-strong", text: "text-ink" },
  6: { block: "bg-grade-6", bar: "bg-accent-strong", text: "text-ink" },
};
