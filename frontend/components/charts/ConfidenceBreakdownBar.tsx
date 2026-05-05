"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from "recharts";
import type { PartyResult } from "@/lib/api";

interface Props {
  party: PartyResult;
}

const COMPONENTS = [
  {
    key: "evidence_strength",
    label: "Evidence strength",
    description: "Avg. reliability of sources (votes > bills > platform)",
    color: "#2563eb",
  },
  {
    key: "coverage",
    label: "Topic coverage",
    description: "Fraction of your important topics with evidence",
    color: "#0d9488",
  },
  {
    key: "answer_stability",
    label: "Answer stability",
    description: "How much your ranking changes if one answer is removed",
    color: "#7c3aed",
  },
  {
    key: "volatility_inv",
    label: "Stability (no volatility)",
    description: "1 − volatility: lower for parties that changed a lot",
    color: "#d97706",
  },
];

export function ConfidenceBreakdownBar({ party }: Props) {
  const data = COMPONENTS.map((c) => ({
    label: c.label,
    value: Math.round(
      (c.key === "volatility_inv"
        ? 1 - party.volatility
        : (party[c.key as keyof PartyResult] as number) ?? 0) * 100
    ),
    description: c.description,
    color: c.color,
  }));

  // Geometric mean approximation of confidence displayed as reference
  const displayConf = Math.round(party.confidence * 100);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs text-slate-500">
          Each component contributes to the overall confidence score.
        </p>
        <span className="text-xs font-semibold text-slate-700">
          Overall: {displayConf}%
        </span>
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: "#64748b" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={[0, 100]}
            tickFormatter={(v) => `${v}%`}
            tick={{ fontSize: 10, fill: "#94a3b8" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            formatter={(value, _name, props) => {
              const desc = (props.payload as { description?: string } | undefined)?.description ?? "";
              return [`${Number(value)}%`, desc];
            }}
            contentStyle={{ fontSize: 11, borderRadius: 8, border: "1px solid #e2e8f0" }}
          />
          <ReferenceLine y={displayConf} stroke="#94a3b8" strokeDasharray="4 2" strokeWidth={1} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={48}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="text-xs text-slate-400">
        Dashed line = final confidence score ({displayConf}%).
      </p>
    </div>
  );
}


