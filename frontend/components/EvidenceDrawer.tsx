"use client";

import { useEffect, useState } from "react";
import { getPartyEvidence, PartyEvidenceItem } from "@/lib/api";
import { useT, useLang } from "@/lib/i18n";

const EVIDENCE_TYPE_COLORS: Record<string, string> = {
  vote:              "bg-blue-50 text-blue-700 border-blue-200",
  bill:              "bg-sky-50 text-sky-700 border-sky-200",
  candidate_history: "bg-teal-50 text-teal-700 border-teal-200",
  party_lineage:     "bg-purple-50 text-purple-700 border-purple-200",
  party_platform:    "bg-amber-50 text-amber-700 border-amber-200",
  statement:         "bg-slate-100 text-slate-600 border-slate-200",
};

interface Props {
  partyId: string | null;
  partyName: string;
  /** Close the drawer */
  onClose: () => void;
  /** Highlight only a specific topic (undefined = show all) */
  highlightTopic?: string;
}

function PositionBar({ value }: { value: number }) {
  // -1..+1 → 0..100% position on bar
  const pct = ((value + 1) / 2) * 100;
  return (
    <div className="relative h-2 w-full bg-slate-100 rounded-full overflow-hidden" title={`${value > 0 ? "+" : ""}${value.toFixed(2)}`}>
      <div className="absolute top-0 bottom-0 w-0.5 bg-slate-300" style={{ left: "50%" }} />
      <div
        className="absolute top-0 bottom-0 w-2 rounded-full bg-brand-500"
        style={{ left: `calc(${pct}% - 4px)` }}
      />
    </div>
  );
}

export function EvidenceDrawer({ partyId, partyName, onClose, highlightTopic }: Props) {
  const t = useT();
  const { lang } = useLang();
  const r = t.results;
  const [evidence, setEvidence] = useState<PartyEvidenceItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [topicFilter, setTopicFilter] = useState<string>(highlightTopic ?? "");

  useEffect(() => {
    if (!partyId) return;
    setLoading(true);
    setError(false);
    getPartyEvidence(partyId)
      .then(setEvidence)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [partyId]);

  useEffect(() => {
    setTopicFilter(highlightTopic ?? "");
  }, [highlightTopic]);

  if (!partyId) return null;

  const allTopics = [...new Set(evidence.map((e) => e.topic_name_en ?? "").filter(Boolean))];
  const displayed = topicFilter
    ? evidence.filter((e) => e.topic_name_en === topicFilter)
    : evidence;

  const getTopicName = (e: PartyEvidenceItem) =>
    lang === "he" ? (e.topic_name_he ?? e.topic_name_en ?? "") :
    lang === "ru" ? (e.topic_name_ru ?? e.topic_name_en ?? "") :
    (e.topic_name_en ?? "");

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/30 z-40 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />

      {/* Drawer */}
      <aside
        role="dialog"
        aria-label={r.evidenceDrawerTitle}
        className="fixed inset-y-0 end-0 w-full max-w-md bg-white shadow-2xl z-50 flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
          <div>
            <p className="text-xs text-slate-400 uppercase tracking-wide">{r.evidenceDrawerTitle}</p>
            <h2 className="font-semibold text-slate-900">{partyName}</h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
            aria-label={r.evidenceDrawerClose}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
              <path d="M12 4L4 12M4 4l8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* Topic filter */}
        {allTopics.length > 1 && (
          <div className="flex gap-1.5 flex-wrap px-5 py-3 border-b border-slate-100 bg-slate-50">
            <button
              onClick={() => setTopicFilter("")}
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium border transition-colors ${
                !topicFilter
                  ? "bg-brand-600 text-white border-brand-600"
                  : "border-slate-200 text-slate-600 hover:border-slate-400"
              }`}
            >
              All
            </button>
            {allTopics.map((t) => (
              <button
                key={t}
                onClick={() => setTopicFilter(t === topicFilter ? "" : t)}
                className={`rounded-full px-2.5 py-0.5 text-xs font-medium border transition-colors ${
                  topicFilter === t
                    ? "bg-brand-600 text-white border-brand-600"
                    : "border-slate-200 text-slate-600 hover:border-slate-400"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {loading && (
            <div className="flex justify-center py-12">
              <div className="h-6 w-6 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
            </div>
          )}
          {error && (
            <p className="text-sm text-red-600 py-8 text-center">Failed to load evidence.</p>
          )}
          {!loading && !error && displayed.length === 0 && (
            <p className="text-sm text-slate-400 py-8 text-center">No evidence records found.</p>
          )}
          {!loading && !error && displayed.map((item) => (
            <div key={item.position_id} className="rounded-xl border border-slate-100 bg-slate-50 p-4 space-y-3">
              {/* Title + topic */}
              <div className="space-y-0.5">
                <p className="text-sm font-medium text-slate-800">{item.policy_item_title}</p>
                {item.topic_name_en && (
                  <p className="text-xs text-slate-400">{getTopicName(item)}</p>
                )}
              </div>

              {/* Evidence type */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${EVIDENCE_TYPE_COLORS[item.evidence_type] ?? "bg-slate-100 text-slate-600"}`}>
                  {item.evidence_type.replace(/_/g, " ")}
                </span>
                <span className="text-xs text-slate-400">
                  strength {Math.round(item.evidence_strength * 100)}%
                </span>
              </div>

              {/* Position bar */}
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-slate-400">
                  <span>− pole</span>
                  <span className="font-medium text-slate-600">
                    {item.position_mean > 0 ? "+" : ""}{item.position_mean.toFixed(2)} ± {item.position_uncertainty.toFixed(2)}
                  </span>
                  <span>+ pole</span>
                </div>
                <PositionBar value={item.position_mean} />
              </div>

              {/* Axis description */}
              {item.directional_axis && (
                <p className="text-xs text-slate-400 italic">{item.directional_axis}</p>
              )}

              {/* LLM explanation */}
              {item.llm_explanation && (
                <p className="text-xs text-slate-600 leading-relaxed border-s-2 border-slate-200 ps-3">
                  {item.llm_explanation}
                </p>
              )}

              {/* Sources */}
              <div className="text-xs text-slate-400">
                {Array.isArray(item.source_refs_json) && item.source_refs_json.length > 0 ? (
                  <span>{r.sourceRefsLabel}: {item.source_refs_json.length} reference(s)</span>
                ) : (
                  <span>{r.noSources}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </aside>
    </>
  );
}

