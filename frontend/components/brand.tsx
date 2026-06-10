import { cn } from "@/lib/utils";

export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "border-line bg-surface text-ink inline-flex items-center justify-center rounded-[var(--radius-sm)] border",
        className,
      )}
    >
      <svg viewBox="0 0 24 24" fill="none" className="size-1/2">
        {/* 격자 + 체크 모티프: 적합한 시간표를 찾았다는 의미 */}
        <path
          d="M4 7h7M4 12h4M4 17h6"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <path
          d="M13 14.5l3 3 5-6.5"
          stroke="var(--accent)"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <BrandMark className="size-8" />
      <span className="text-[1.02rem] font-semibold tracking-[-0.02em]">
        course<span className="text-accent">-fit</span>
      </span>
    </span>
  );
}
