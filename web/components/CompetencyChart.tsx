"use client";

import { useState } from "react";
import type { CompId, Diagnosis, Reference, SigmaSource } from "@/lib/types";
import { GAP_EPSILON } from "@/lib/competency";

/**
 * σ(보유) 와 ρ(직무 요구)를 한 축에 겹쳐 보여준다.
 *   막대 = σ · 눈금 = ρ · 빗금 = gap
 *
 * 색은 두 역할만 나른다 — 쌓인 양 하나, 모자란 만큼 하나. 역량 정체는 글자가 나른다.
 * 부족한 축만 진하게 두고 충족은 눌러 강조로 읽히게 한다.
 * 모자란 만큼(−0.86)과 범례 글자는 막대와 같은 색 계열(*-ink)이다 — 회색이면 숫자와 막대를
 * 한 번 더 이어 읽어야 했다(9/28 피드백).
 *
 * 역량 이름을 누르면 그 σ 를 쌓은 기수강 과목이 펼쳐진다(diagnosis.sources).
 * 「충족」이 무엇으로 찼는지 학생이 확인할 수 있어야 숫자를 믿는다.
 */
export default function CompetencyChart({
  diagnosis,
  reference,
}: {
  diagnosis: Diagnosis;
  reference: Reference | null;
}) {
  const labels = new Map<string, string>(
    (reference?.competencies ?? []).map((c) => [c.id, c.nameKo]),
  );
  const [open, setOpen] = useState<CompId | null>(null);
  const sourcesOf = (k: CompId) => diagnosis.sources?.[k] ?? [];
  const toggle = (k: CompId) => setOpen((cur) => (cur === k ? null : k));

  // 이 직무가 요구하는 축만. 요구 0인 축은 노이즈라 뺀다.
  const asked = (Object.keys(diagnosis.rho) as CompId[])
    .filter((k) => diagnosis.rho[k] > 0.05)
    .sort((a, b) => diagnosis.gap[b] - diagnosis.gap[a] || diagnosis.rho[b] - diagnosis.rho[a]);

  // 충족한 축은 막대 모양이 전부 같아 여러 줄을 그리면 노이즈만 는다.
  // 부족한 것만 펼치고 나머지는 한 줄로 접는다.
  const rows = asked.filter((k) => diagnosis.gap[k] > GAP_EPSILON);
  const met = asked.filter((k) => diagnosis.gap[k] <= GAP_EPSILON);

  return (
    <div>
      <div className="space-y-2">
        {rows.map((k) => {
          const sigma = diagnosis.sigma[k];
          const rho = diagnosis.rho[k];
          const gap = diagnosis.gap[k];
          const lacking = gap > GAP_EPSILON;

          return (
            <div key={k}>
            <div className="grid grid-cols-[6.5rem_1fr_3rem] items-center gap-3">
              <CompLabel
                name={labels.get(k) ?? k}
                clickable={sourcesOf(k).length > 0}
                expanded={open === k}
                onToggle={() => toggle(k)}
                controls={`src-${k}`}
                className={lacking ? "font-semibold text-text" : "text-text-soft"}
              />

              <div className="relative h-5 overflow-hidden rounded-sm bg-surface-3">
                {/* σ — 쌓인 양 */}
                <div
                  className="absolute inset-y-0 left-0 rounded-sm"
                  style={{
                    width: `${Math.min(sigma, 1) * 100}%`,
                    background: lacking
                      ? "var(--color-have)"
                      : "var(--color-have-soft)",
                    animation: "growX .55s cubic-bezier(.16,1,.3,1) both",
                  }}
                />
                {/* gap — σ와 ρ 사이. 2px 틈으로 두 마크를 떼어 놓는다 */}
                {lacking && (
                  <div
                    className="absolute inset-y-0"
                    style={{
                      left: `calc(${sigma * 100}% + 2px)`,
                      width: `calc(${gap * 100}% - 2px)`,
                      background:
                        "repeating-linear-gradient(45deg, var(--color-gap) 0 4px, var(--color-gap-soft) 4px 8px)",
                      animation: "growX .55s cubic-bezier(.16,1,.3,1) .12s both",
                    }}
                  />
                )}
                {/* ρ — 요구 눈금 */}
                <div
                  className="absolute inset-y-0 w-0.5 bg-ink"
                  style={{ left: `calc(${rho * 100}% - 1px)` }}
                />
              </div>

              <span
                className={
                  "tnum text-right text-caption " +
                  (lacking ? "font-semibold text-gap-ink" : "text-success-ink")
                }
              >
                {lacking ? `−${gap.toFixed(2)}` : "충족"}
              </span>
            </div>
            {open === k && (
              <SourceList id={`src-${k}`} name={labels.get(k) ?? k} items={sourcesOf(k)} />
            )}
            </div>
          );
        })}
      </div>

      {met.length > 0 && (
        <div className="mt-3">
          <p className="flex items-baseline gap-2 text-caption text-text-muted">
            <span className="text-success-ink" aria-hidden>✓</span>
            <span>
              <span className="tnum font-semibold text-success-ink">{met.length}개 충족</span> ·{" "}
              {met.map((k, i) => (
                <span key={k}>
                  {i > 0 && <span className="text-text-soft"> · </span>}
                  <CompLabel
                    name={labels.get(k) ?? k}
                    clickable={sourcesOf(k).length > 0}
                    expanded={open === k}
                    onToggle={() => toggle(k)}
                    controls={`src-${k}`}
                    className="text-text-soft"
                  />
                </span>
              ))}
            </span>
          </p>
          {open !== null && met.includes(open) && (
            <SourceList id={`src-${open}`} name={labels.get(open) ?? open} items={sourcesOf(open)} />
          )}
        </div>
      )}

      {Object.values(diagnosis.sources ?? {}).some((l) => l && l.length > 0) && (
        <p className="mt-2 text-caption text-text-soft">
          역량 이름을 누르면 어떤 과목으로 쌓였는지 보여요
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-caption text-text-muted">
        <Legend
          swatch={
            <span
              className="h-2.5 w-4 rounded-sm"
              style={{ background: "var(--color-have)" }}
            />
          }
        >
          <span className="text-have-ink">쌓은 것 σ</span>
        </Legend>
        <Legend
          swatch={
            <span
              className="h-2.5 w-4 rounded-sm"
              style={{
                background:
                  "repeating-linear-gradient(45deg, var(--color-gap) 0 3px, var(--color-gap-soft) 3px 6px)",
              }}
            />
          }
        >
          <span className="text-gap-ink">모자란 만큼 gap</span>
        </Legend>
        <Legend swatch={<span className="h-3.5 w-0.5 bg-ink" />}>
          직무가 원하는 수준 ρ
        </Legend>
      </div>
    </div>
  );
}

/** 역량 이름. 기여 과목이 있으면 눌러서 펼치는 버튼이 된다. */
function CompLabel({
  name,
  clickable,
  expanded,
  onToggle,
  controls,
  className,
}: {
  name: string;
  clickable: boolean;
  expanded: boolean;
  onToggle: () => void;
  controls: string;
  className: string;
}) {
  if (!clickable) return <span className={"truncate text-sm " + className}>{name}</span>;
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={expanded}
      aria-controls={controls}
      className={
        "truncate text-left text-sm underline decoration-dotted underline-offset-4 hover:text-text " +
        className
      }
    >
      {name}
    </button>
  );
}

/** 받침 있으면 「은」, 없으면 「는」. 한글이 아니면 둘 다 적는다. */
function topic(word: string): string {
  const c = word.charCodeAt(word.length - 1);
  if (!(c >= 0xac00 && c <= 0xd7a3)) return "은(는)";
  return (c - 0xac00) % 28 ? "은" : "는";
}

/** 이 역량을 쌓은 기수강 과목. share 는 그 역량에 쌓인 것 중 과목 몫이다. */
function SourceList({ id, name, items }: { id: string; name: string; items: SigmaSource[] }) {
  const shown = items.reduce((a, it) => a + it.share, 0);
  return (
    <div id={id} className="mt-2 mb-1 rounded-sm bg-surface-3 px-3 py-2.5">
      <p className="text-caption text-text-muted">
        <b className="text-text">{name}</b>{topic(name)} 이 과목들로 쌓였어요
      </p>
      <ul className="mt-1.5 space-y-1">
        {items.map((it) => (
          <li
            key={it.courseId}
            className="grid grid-cols-[1fr_3rem] items-center gap-3 text-sm"
          >
            <span className="truncate text-text">{it.name}</span>
            <span className="tnum text-right text-caption text-text-soft">
              {Math.round(it.share * 100)}%
            </span>
          </li>
        ))}
      </ul>
      {shown < 0.995 && (
        <p className="mt-1.5 text-caption text-text-soft">
          나머지 <span className="tnum">{Math.round((1 - shown) * 100)}%</span>는 다른 과목들
        </p>
      )}
    </div>
  );
}

function Legend({
  swatch,
  children,
}: {
  swatch: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {swatch}
      {children}
    </span>
  );
}
