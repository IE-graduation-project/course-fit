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
  /** 복사가 막힌 브라우저(카카오톡 인앱 등)에선 번호를 직접 고를 수 있게 펼쳐 둔다 */
  const [shown, setShown] = useState(false);

  const text = courses
    .map((c) => `${c.courseId}-${c.section}\t${c.name}\t${c.timeRaw || "시간 미지정"}`)
    .join("\n");

  async function copy() {
    let ok = false;
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch {
      // 클립보드 API 가 막힌 곳 — 예전 방식으로 한 번 더
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        ok = document.execCommand("copy");
      } catch {
        ok = false;
      }
      ta.remove();
    }
    setState(ok ? "done" : "fail");
    if (!ok) setShown(true);
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
        {state === "fail" && "이 브라우저는 자동 복사가 막혀 있어요. 아래 칸을 길게 눌러 복사해 주세요."}
      </span>
      {shown && (
        <textarea
          readOnly
          value={courses.map((c) => `${c.courseId}-${c.section} ${c.name}`).join("\n")}
          rows={courses.length}
          aria-label="추천 과목 학수번호"
          onFocus={(e) => e.currentTarget.select()}
          className="tnum w-full resize-none rounded-md border border-border bg-surface p-3 font-mono text-sm"
        />
      )}
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
