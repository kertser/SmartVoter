"use client";

import { useEffect, useState } from "react";
import { getLineage, LineageGraph } from "@/lib/api";

const RELATION_STYLE: Record<string, { label: string; color: string; dashed?: boolean }> = {
  rename:    { label: "Rename",    color: "#0d9488" },
  rebrand:   { label: "Rebrand",   color: "#7c3aed" },
  merger:    { label: "Merger",    color: "#2563eb" },
  split:     { label: "Split",     color: "#d97706", dashed: true },
  successor: { label: "Successor", color: "#64748b" },
  alliance:  { label: "Alliance",  color: "#9ca3af", dashed: true },
};

interface Props {
  lang?: string;
}

export function PartyLineageTimeline({ lang = "en" }: Props) {
  const [graph, setGraph] = useState<LineageGraph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    getLineage()
      .then(setGraph)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-24 text-slate-400 text-sm">
        Loading lineage data…
      </div>
    );
  }
  if (error || !graph) {
    return (
      <div className="flex items-center justify-center h-24 text-slate-400 text-sm">
        Lineage data unavailable
      </div>
    );
  }
  if (graph.edges.length === 0) {
    return (
      <div className="flex items-center justify-center h-24 text-slate-400 text-sm">
        No lineage relationships recorded
      </div>
    );
  }

  const nodeMap = new Map(graph.nodes.map((n) => [n.id, n]));

  const getName = (id: string) => {
    const n = nodeMap.get(id);
    if (!n) return id.slice(0, 8);
    // Party names always in Hebrew — they are proper nouns.
    return n.name_he ?? n.name;
  };

  const getStatusBadge = (status: string) => {
    if (status === "active") return "bg-emerald-50 text-emerald-700 border-emerald-200";
    if (status === "dissolved") return "bg-slate-100 text-slate-500 border-slate-200";
    return "bg-orange-50 text-orange-700 border-orange-200";
  };

  return (
    <div className="space-y-4">
      {/* Edge list — clear prose format */}
      <div className="space-y-3">
        {graph.edges.map((edge) => {
          const style = RELATION_STYLE[edge.relation_type] ?? { label: edge.relation_type, color: "#94a3b8" };
          const fromNode = nodeMap.get(edge.from_id);
          const toNode = nodeMap.get(edge.to_id);
          const continuityPct = Math.round(edge.continuity_weight * 100);

          return (
            <div
              key={edge.id}
              className="rounded-xl border border-slate-200 bg-white p-4 space-y-2"
            >
              <div className="flex flex-wrap items-center gap-2 text-sm">
                {/* From party */}
                <span
                  className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${getStatusBadge(fromNode?.status ?? "")}`}
                >
                  {getName(edge.from_id)}
                  {fromNode?.knesset_number ? ` (K${fromNode.knesset_number})` : ""}
                </span>

                {/* Arrow + relation */}
                <span
                  className="flex items-center gap-1 text-xs font-semibold"
                  style={{ color: style.color }}
                >
                  <svg width="24" height="10" viewBox="0 0 24 10" fill="none" aria-hidden>
                    <line
                      x1="0" y1="5" x2="20" y2="5"
                      stroke={style.color}
                      strokeWidth="1.5"
                      strokeDasharray={style.dashed ? "4 2" : undefined}
                    />
                    <polygon points="20,2 24,5 20,8" fill={style.color} />
                  </svg>
                  {style.label}
                </span>

                {/* To party */}
                <span
                  className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${getStatusBadge(toNode?.status ?? "")}`}
                >
                  {getName(edge.to_id)}
                  {toNode?.knesset_number ? ` (K${toNode.knesset_number})` : ""}
                </span>

                {/* Continuity badge */}
                <span
                  className={`ms-auto rounded-full px-2 py-0.5 text-xs ${
                    continuityPct >= 70
                      ? "bg-emerald-50 text-emerald-700"
                      : continuityPct >= 40
                      ? "bg-amber-50 text-amber-700"
                      : "bg-slate-100 text-slate-500"
                  }`}
                  title="How much policy continuity this relation implies (0–100%)"
                >
                  {continuityPct}% continuity
                </span>
              </div>

              {edge.llm_explanation && (
                <p className="text-xs text-slate-500 leading-relaxed">{edge.llm_explanation}</p>
              )}

              <div className="flex items-center gap-3 text-xs text-slate-400">
                <span>
                  Review:{" "}
                  <span
                    className={
                      edge.human_review_status === "approved"
                        ? "text-emerald-600"
                        : "text-amber-600"
                    }
                  >
                    {edge.human_review_status}
                  </span>
                </span>
                {edge.source_url && (
                  <a
                    href={edge.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:underline text-brand-600"
                  >
                    Source ↗
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-4 text-xs text-slate-500 pt-1">
        {Object.entries(RELATION_STYLE).map(([key, s]) => (
          <span key={key} className="flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-5" style={{ backgroundColor: s.color, borderStyle: s.dashed ? "dashed" : "solid", borderTopWidth: 2, borderColor: s.color }} />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}

