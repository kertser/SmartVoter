"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { PartyResult } from "@/lib/api";

// Evidence type display names and colors (ordered by reliability per AGENTS.MD §2.1)
const EVIDENCE_META: Record<string, { label: string; color: string }> = {
  vote:               { label: "Parliamentary vote", color: "#1d4ed8" },
  bill:               { label: "Sponsored bill",     color: "#2563eb" },
  candidate_history:  { label: "Candidate history",  color: "#0d9488" },
  party_lineage:      { label: "Party lineage",       color: "#7c3aed" },
  party_platform:     { label: "Party platform",      color: "#d97706" },
  statement:          { label: "Public statement",    color: "#9ca3af" },
  coalition:          { label: "Coalition agreement", color: "#6b7280" },
};

const order = ["vote", "bill", "candidate_history", "party_lineage", "party_platform", "statement", "coalition"];

interface Props {
  parties: PartyResult[];
  lang?: string;
}

export function EvidenceCompositionBar({ parties, lang = "en" }: Props) {
  const topParties = parties.slice(0, 5);

  const getPartyName = (p: PartyResult) =>
    lang === "he" ? (p.name_he ?? p.name) :
    lang === "ru" ? (p.name_ru ?? p.name) :
    p.name;

  // Collect all evidence types present across all parties
  const allTypes = new Set<string>();
  topParties.forEach((p) => Object.keys(p.evidence_by_type).forEach((t) => allTypes.add(t)));
  const types = order.filter((t) => allTypes.has(t));

  if (types.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-slate-400 text-sm">
        No evidence type data available
      </div>
    );
  }

  const data = topParties.map((p) => ({
    party: getPartyName(p),
    party_id: p.party_id,
    ...types.reduce((acc, t) => ({ ...acc, [t]: Math.round((p.evidence_by_type[t] ?? 0) * 100) }), {}),
  }));

  return (
    <div className="space-y-2">
      <ResponsiveContainer width="100%" height={Math.max(160, topParties.length * 44)}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
          <XAxis
            type="number"
            domain={[0, 100]}
            tickFormatter={(v) => `${v}%`}
            tick={{ fontSize: 10, fill: "#94a3b8" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="party"
            width={90}
            tick={{ fontSize: 11, fill: "#475569" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            formatter={(value, name) => [
              `${Number(value)}%`,
              EVIDENCE_META[String(name)]?.label ?? String(name),
            ]}
            contentStyle={{ fontSize: 11, borderRadius: 8, border: "1px solid #e2e8f0" }}
          />
          <Legend
            formatter={(value) => EVIDENCE_META[value]?.label ?? value}
            wrapperStyle={{ fontSize: 11 }}
          />
          {types.map((t) => (
            <Bar key={t} dataKey={t} stackId="a" fill={EVIDENCE_META[t]?.color ?? "#94a3b8"} maxBarSize={24} />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <p className="text-xs text-slate-400">
        Higher bars = broader evidence base. Votes and bills indicate observed parliamentary behavior.
      </p>
    </div>
  );
}



