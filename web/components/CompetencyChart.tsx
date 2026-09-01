"use client";

import type { CompId, Diagnosis, Reference } from "@/lib/types";
import { GAP_EPSILON } from "@/lib/competency";

/**
 * σ(보유) 와 ρ(직무 요구)를 한 축에 겹쳐 보여준다.
 *   막대 = σ · 눈금 = ρ · 빗금 = gap
 *
 * 색은 두 역할만 나른다 — 쌓인 양 하나, 모자란 만큼 하나. 역량 정체는 글자가 나른다.
 * 부족한 축만 진하게 두고 충족은 눌러 강조로 읽히게 한다.
 * 숫자는 항상 text 토큰이다 — 데이터 색을 글자에 입히지 않는다.
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
            <div
              key={k}
              className="grid grid-cols-[6.5rem_1fr_3rem] items-center gap-3"
            >
              <span
                className={
                  "truncate text-sm " +
                  (lacking ? "font-semibold text-text" : "text-text-soft")
                }
              >
                {labels.get(k) ?? k}
              </span>

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
                  (lacking ? "font-semibold text-text" : "text-text-soft")
                }
              >
                {lacking ? `−${gap.toFixed(2)}` : "충족"}
              </span>
            </div>
          );
        })}
      </div>

      {met.length > 0 && (
        <p className="mt-3 flex items-baseline gap-2 text-caption text-text-muted">
          <span className="text-success" aria-hidden>✓</span>
          <span>
            <span className="tnum font-semibold text-text">{met.length}개</span> 충족 ·{" "}
            <span className="text-text-soft">
              {met.map((k) => labels.get(k) ?? k).join(" · ")}
            </span>
          </span>
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
          쌓은 것 σ
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
          모자란 만큼 gap
        </Legend>
        <Legend swatch={<span className="h-3.5 w-0.5 bg-ink" />}>
          직무가 원하는 수준 ρ
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
