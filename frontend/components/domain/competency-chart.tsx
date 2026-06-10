"use client";

import { useMemo } from "react";
import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
} from "recharts";
import type { Competency } from "@/lib/data";

interface TooltipPayloadItem {
  name: string;
  value: number;
  color: string;
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="border-line bg-surface rounded-[var(--radius-sm)] border p-2.5">
      <p className="mb-1 text-xs font-semibold">{label}</p>
      {payload.map((item) => (
        <p
          key={item.name}
          className="flex items-center gap-1.5 font-mono text-[0.7rem] tabular-nums"
          style={{ color: item.color }}
        >
          <span
            className="size-2 rounded-[2px]"
            style={{ background: item.color }}
          />
          {item.name} {item.value}
        </p>
      ))}
    </div>
  );
}

interface CompetencyChartProps {
  competencies: Competency[];
}

export function CompetencyChart({ competencies }: CompetencyChartProps) {
  const required = "var(--line-strong)";
  const achieved = "var(--accent)";

  const chartData = competencies.map((c) => ({
    label: c.label,
    요구: Math.round(c.required * 100),
    달성: Math.round(c.achieved * 100),
  }));

  const legend = useMemo(
    () => [
      { name: "요구 수준", color: required },
      { name: "현재 달성", color: achieved },
    ],
    [required, achieved],
  );

  return (
    <div className="flex flex-col">
      <div className="mb-1 flex items-center justify-end gap-4">
        {legend.map((l) => (
          <span
            key={l.name}
            className="text-ink-muted flex items-center gap-1.5 font-mono text-[0.68rem] tracking-[0.02em] uppercase"
          >
            <span
              className="size-2.5 rounded-[2px]"
              style={{ background: l.color }}
            />
            {l.name}
          </span>
        ))}
      </div>
      <div className="h-[300px] w-full min-w-0">
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <RadarChart data={chartData} outerRadius="72%">
            <PolarGrid strokeOpacity={0.8} />
            <PolarAngleAxis
              dataKey="label"
              tick={{ fontSize: 11 }}
              tickLine={false}
            />
            <RechartsTooltip
              content={<ChartTooltip />}
              cursor={{ strokeOpacity: 0.2 }}
            />
            <Radar
              name="요구 수준"
              dataKey="요구"
              stroke={required}
              fill={required}
              fillOpacity={0.18}
              strokeWidth={1.5}
            />
            <Radar
              name="현재 달성"
              dataKey="달성"
              stroke={achieved}
              fill={achieved}
              fillOpacity={0.28}
              strokeWidth={2}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
