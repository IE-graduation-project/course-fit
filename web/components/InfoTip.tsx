"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";

/**
 * 작은 ⓘ. 마우스를 올리거나 누르면(휴대폰, 키보드 Enter) 짧은 설명을 띄우고, 바깥을 누르거나
 * Esc, 스크롤로 닫는다.
 *
 * 꼭 읽어야 하는 설명에는 쓰지 않는다 — 사용자 점검(#71)에서 title 에만 있던 설명은 아무도 못 봤다.
 * 궁금할 때 열어 보면 되는 부가 설명용이다.
 */
export default function InfoTip({ label, children }: { label: string; children: React.ReactNode }) {
  const [pinned, setPinned] = useState(false);
  const [hover, setHover] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null);
  const btn = useRef<HTMLButtonElement>(null);
  const tip = useRef<HTMLDivElement>(null);
  const id = useId();
  const open = pinned || hover;

  // 화면 밖으로 안 나가게 버튼 아래에서 좌우를 맞춘다. 좁은 화면에선 버튼이 오른쪽 끝 근처에 있다
  useLayoutEffect(() => {
    if (!open || !btn.current) return;
    const r = btn.current.getBoundingClientRect();
    const width = Math.min(320, window.innerWidth - 24);
    const left = Math.min(Math.max(12, r.left + r.width / 2 - width / 2), window.innerWidth - width - 12);
    setPos({ top: r.bottom + 4, left, width });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const close = () => {
      setPinned(false);
      setHover(false);
    };
    const onDown = (e: PointerEvent) => {
      const t = e.target as Node;
      if (!btn.current?.contains(t) && !tip.current?.contains(t)) close();
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", close, { passive: true });
    window.addEventListener("resize", close);
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", close);
      window.removeEventListener("resize", close);
    };
  }, [open]);

  return (
    <>
      <button
        ref={btn}
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => setPinned((p) => !p)}
        // 휴대폰의 탭도 pointerenter 를 낸다 — 마우스만 hover 로 본다. 아니면 탭 한 번에 열리고 닫히지 않는다
        onPointerEnter={(e) => e.pointerType === "mouse" && setHover(true)}
        onPointerLeave={(e) => e.pointerType === "mouse" && setHover(false)}
        className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-text-soft transition-colors hover:text-text"
      >
        <span
          aria-hidden
          className="flex h-[18px] w-[18px] items-center justify-center rounded-full border-[1.5px] border-current text-[11px] font-bold leading-none"
        >
          i
        </span>
      </button>
      {open && pos && (
        <div
          ref={tip}
          id={id}
          role="tooltip"
          style={{ position: "fixed", top: pos.top, left: pos.left, width: pos.width }}
          className="z-50 rounded-md border border-border bg-surface px-3.5 py-3 text-caption leading-relaxed text-text-muted shadow-card"
        >
          {children}
        </div>
      )}
    </>
  );
}
