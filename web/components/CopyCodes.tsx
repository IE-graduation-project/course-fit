"use client";

import { useState } from "react";
import type { RecommendedCourse } from "@/lib/types";

/**
 * 학수번호 한 번에 복사.
 *
 * 이 화면을 본 학생이 다음에 하는 일은 수강신청 창에 학수번호를 치는 것이다.
 * 여섯 개를 화면 보면서 하나씩 옮겨 적게 두는 건 우리가 일을 덜 한 것이다.
 */
export default function CopyCodes({ courses }: { courses: RecommendedCourse[] }) {
  const [state, setState] = useState<"idle" | "done" | "fail">("idle");

  const text = courses
    .map((c) => `${c.courseId}-${c.section}\t${c.name}\t${c.timeRaw ?? ""}`)
    .join("\n");

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setState("done");
    } catch {
      setState("fail");
    }
    setTimeout(() => setState("idle"), 2200);
  }

  if (courses.length === 0) return null;

  return (
    <div className="mt-4 flex flex-wrap items-center gap-2">
      <button
        onClick={copy}
        className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border-strong px-4 text-sm font-semibold text-text transition-colors hover:bg-surface-3"
      >
        <IconCopy />
        학수번호 {courses.length}개 복사
      </button>
      <span aria-live="polite" className="text-caption text-text-muted">
        {state === "done" && "복사했어요. 수강신청 창에 붙여넣으면 됩니다."}
        {state === "fail" && "복사가 막혔어요. 카드의 번호를 직접 옮겨 적어주세요."}
      </span>
    </div>
  );
}

function IconCopy() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V5a2 2 0 0 1 2-2h10" />
    </svg>
  );
}
