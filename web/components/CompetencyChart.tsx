"use client";

import type { CompId, Diagnosis, Reference } from "@/lib/types";
import { compColor } from "@/lib/competency";

/**
 * σ(보유) 와 ρ(직무 요구)를 한 축에 겹쳐 보여준다.
 *  - 막대 = σ, 학생이 쌓은 양
 *  - 세로 눈금 = ρ, 이 직무가 요구하는 수준
 *  - 눈금이 막대보다 오른쪽에 있으면 그 구간이 gap (주황)
 * 숫자는 최소로 — 형태로 먼저 읽히고, 값은 확인용으로만 붙인다.
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

  // 이 직무가 요구하는 축만, 요구 큰 순으로. 요구 0인 축은 노이즈라 뺀다.
  const rows = (Object.keys(diagnosis.rho) as CompId[])
    .filter((k) => diagnosis.rho[k] > 0.05)
    .sort((a, b) => diagnosis.rho[b] - diagnosis.rho[a]);

  return (
    <div className="space-y-3">
      {rows.map((k) => {
        const sigma = diagnosis.sigma[k];
        const rho = diagnosis.rho[k];
        const gap = diagnosis.gap[k];
        const lacking = gap > 0.03;

        return (
          <div key={k} className="grid grid-cols-[7.25rem_1fr_2.75rem] items-center gap-3">
            <span className="flex min-w-0 items-center gap-1.5">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: compColor(k), opacity: lacking ? 1 : 0.35 }}
              />
              <span
                className={
                  "truncate text-sm " +
                  (lacking ? "font-semibold text-text" : "text-text-muted")
                }
              >
                {labels.get(k) ?? k}
              </span>
            </span>

            <div className="relative h-6 overflow-hidden rounded-sm bg-surface-3">
              {/* σ — 보유 */}
              <div
                className="absolute inset-y-0 left-0 origin-left rounded-sm"
                style={{
                  width: `${Math.min(sigma, 1) * 100}%`,
                  background: lacking
                    ? "var(--color-have)"
                    : "oklch(62% 0.132 168 / 0.45)",
                  animation: "growX 0.6s cubic-bezier(0.16,1,0.3,1) both",
                }}
              />
              {/* gap — σ와 ρ 사이 */}
              {lacking && (
                <div
                  className="absolute inset-y-0 origin-left"
                  style={{
                    left: `${sigma * 100}%`,
                    width: `${gap * 100}%`,
                    background:
                      "repeating-linear-gradient(45deg, var(--color-gap) 0 4px, oklch(70% 0.16 38) 4px 8px)",
                    animation: "growX 0.6s cubic-bezier(0.16,1,0.3,1) 0.15s both",
                  }}
                />
              )}
              {/* ρ — 요구 눈금 */}
              <div
                className="absolute inset-y-0 w-0.5 bg-ink"
                style={{ left: `calc(${rho * 100}% - 1px)` }}
                title={`직무 요구 ${rho.toFixed(2)}`}
              />
            </div>

            <span
              className={
                "tnum text-right text-caption " +
                (lacking ? "font-semibold text-gap" : "text-text-soft")
              }
            >
              {lacking ? `−${gap.toFixed(2)}` : "충족"}
            </span>
          </div>
        );
      })}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 pt-1 text-caption text-text-soft">
        <Legend swatch={<span className="h-2.5 w-4 rounded-sm bg-have" />}>
          내가 쌓은 것 σ
        </Legend>
        <Legend
          swatch={
            <span
              className="h-2.5 w-4 rounded-sm"
              style={{
                background:
                  "repeating-linear-gradient(45deg, var(--color-gap) 0 3px, oklch(70% 0.16 38) 3px 6px)",
              }}
            />
          }
        >
          부족한 만큼 gap
        </Legend>
        <Legend swatch={<span className="h-3.5 w-0.5 bg-ink" />}>
          이 직무가 원하는 수준 ρ
        </Legend>
      </div>
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
