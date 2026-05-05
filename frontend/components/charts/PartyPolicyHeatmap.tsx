"use client";

import type { PartyResult } from "@/lib/api";

interface Props {
  parties: PartyResult[];
  lang?: string;
  onCellClick?: (partyId: string, topic: string) => void;
}

function cellClass(score: number | undefined): string {
  if (score === undefined) return "bg-slate-100 text-slate-400";
  if (score >= 0.7) return "bg-emerald-50 text-emerald-800 font-medium";
  if (score >= 0.5) return "bg-slate-50 text-slate-600";
  return "bg-red-50 text-red-700";
}

export function PartyPolicyHeatmap({ parties, lang = "en", onCellClick }: Props) {
  const topParties = parties.slice(0, 5);

  // Collect all topics that appear in at least one party
  const topicSet = new Set<string>();
  topParties.forEach((p) => Object.keys(p.topic_scores).forEach((t) => topicSet.add(t)));
  const topics = [...topicSet].sort();

  if (topics.length === 0 || topParties.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-slate-400 text-sm rounded-lg border border-slate-100 bg-slate-50">
        No data available
      </div>
    );
  }

  const getPartyName = (p: PartyResult) =>
    lang === "he" ? (p.name_he ?? p.name) :
    lang === "ru" ? (p.name_ru ?? p.name) :
    p.name;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr>
            <th className="text-left py-2 pe-3 text-slate-500 font-medium w-32">Topic</th>
            {topParties.map((p) => (
              <th key={p.party_id} className="py-2 px-1 text-center text-slate-700 font-medium min-w-[80px]">
                <span className="block truncate max-w-[90px]" title={getPartyName(p)}>
                  {getPartyName(p)}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {topics.map((topic) => (
            <tr key={topic} className="border-t border-slate-100">
              <td className="py-1.5 pe-3 text-slate-600 whitespace-nowrap">{topic}</td>
              {topParties.map((p) => {
                const score = p.topic_scores[topic];
                return (
                  <td
                    key={p.party_id}
                    className={`py-1.5 px-1 text-center rounded transition-colors ${cellClass(score)} ${
                      onCellClick ? "cursor-pointer hover:opacity-80" : ""
                    }`}
                    title={score !== undefined ? `${Math.round(score * 100)}% similarity` : "No data"}
                    onClick={() => onCellClick?.(p.party_id, topic)}
                  >
                    {score !== undefined ? `${Math.round(score * 100)}%` : "—"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {/* Legend */}
      <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-emerald-100" /> ≥70% agree
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-slate-100" /> 50–69%
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-red-100" /> &lt;50% disagree
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded bg-slate-100 text-slate-400 text-center leading-3">—</span> No data
        </span>
      </div>
    </div>
  );
}

