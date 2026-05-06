"use client";

import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";
import { useState } from "react";
import type { PartyResult } from "@/lib/api";

// Neutral, non-partisan palette — blues, teals, purples
const PARTY_COLORS = [
  "#2563eb", "#0d9488", "#7c3aed", "#d97706", "#dc2626",
];

interface Props {
  parties: PartyResult[];
  /** Max number of parties to show initially */
  maxParties?: number;
  lang?: string;
}

export function TopicRadarChart({ parties, maxParties = 3, lang = "en" }: Props) {
  const top = parties.slice(0, maxParties);
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  // Gather all topic names across all parties
  const topicSet = new Set<string>();
  top.forEach((p) => Object.keys(p.topic_scores).forEach((t) => topicSet.add(t)));
  const topics = [...topicSet];

  if (topics.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-slate-400 text-sm">
        No topic data available
      </div>
    );
  }

  // Build data array: one entry per topic
  const data = topics.map((topic) => {
    const entry: Record<string, string | number> = { topic: topic.replace(" & ", " &\n") };
    top.forEach((p) => {
      entry[p.party_id] = p.topic_scores[topic] ?? 0;
    });
    return entry;
  });

  // Party names always in Hebrew — they are proper nouns.
  const getPartyName = (p: PartyResult) => p.name_he ?? p.name;

  const toggleParty = (id: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-2">
      {/* Party toggle buttons */}
      <div className="flex flex-wrap gap-2">
        {top.map((p, i) => (
          <button
            key={p.party_id}
            onClick={() => toggleParty(p.party_id)}
            className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-opacity ${
              hidden.has(p.party_id) ? "opacity-40" : "opacity-100"
            }`}
            style={{ borderColor: PARTY_COLORS[i], color: PARTY_COLORS[i] }}
          >
            <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: PARTY_COLORS[i] }} />
            {getPartyName(p)}
          </button>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <RadarChart data={data} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
          <PolarGrid stroke="#e2e8f0" />
          <PolarAngleAxis
            dataKey="topic"
            tick={{ fontSize: 11, fill: "#64748b" }}
          />
          <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
          <Tooltip
            formatter={(value) => {
              const v = Number(value);
              return [`${Math.round(v * 100)}%`, "Similarity"];
            }}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}
          />
          {top.map((p, i) =>
            hidden.has(p.party_id) ? null : (
              <Radar
                key={p.party_id}
                name={getPartyName(p)}
                dataKey={p.party_id}
                fill={PARTY_COLORS[i]}
                fillOpacity={0.18}
                stroke={PARTY_COLORS[i]}
                strokeWidth={2}
                dot={false}
              />
            )
          )}
          <Legend
            formatter={(value) => {
              const party = top.find((p) => p.party_id === value);
              return party ? getPartyName(party) : value;
            }}
            wrapperStyle={{ fontSize: 11 }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}


