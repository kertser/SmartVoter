"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { getResults, ResultsOut, PartyResult } from "@/lib/api";
import { clearSession } from "@/lib/session";
import { formatPercent, confidenceLabel, confidenceColor } from "@/lib/utils";
import Link from "next/link";
import { Suspense } from "react";
import { useT, useLang } from "@/lib/i18n";
import type { Translations } from "@/locales/types";
import { Tooltip } from "@/components/Tooltip";

function ResultsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const t = useT();
  const lang = useLang().lang;
  const r = t.results;
  const sessionId = searchParams.get("session_id") || "";
  const [results, setResults] = useState<ResultsOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) {
      router.push("/");
      return;
    }
    getResults(sessionId)
      .then(setResults)
      .catch(() => setError(r.errorLoad))
      .finally(() => setLoading(false));
  }, [sessionId, router, r]);

  const handleStartOver = () => {
    clearSession();
    router.push("/");
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center gap-4 py-20">
        <div className="h-8 w-8 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
        <p className="text-slate-500">{r.loadingResults}</p>
      </div>
    );
  }

  if (error || !results) {
    return (
      <div className="text-center py-20 space-y-4">
        <p className="text-red-600">{error || r.errorLoad}</p>
        <Link href="/" className="text-brand-600 hover:underline">{r.backToStart}</Link>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      {/* Header */}
      <div className="space-y-2">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
          {r.basedOnEvidence}
        </p>
        <h1 className="text-3xl font-bold text-slate-900">{r.heading}</h1>
        <p className="text-slate-500 text-sm">
          {r.description}
          <Link href="/methodology" className="text-brand-600 ml-1 hover:underline">
            {r.howCalculated}
          </Link>
        </p>
      </div>

      {/* Party match cards */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-800">{r.partyMatchesHeading}</h2>
        <div className="space-y-3">
          {results.parties.map((party, i) => (
            <PartyMatchCard key={party.party_id} party={party} rank={i + 1} r={r} lang={lang} />
          ))}
        </div>
      </section>

      {/* Representation gap */}
      <section className="rounded-xl border border-slate-200 bg-white shadow-sm p-6 space-y-4">
        <h2 className="text-lg font-semibold text-slate-800">{r.representationHeading}</h2>
        <p className="text-sm text-slate-600">{results.representation_gap.explanation}</p>
        {results.representation_gap.best_party_by_topic.length > 0 && (
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">
              {r.bestPartyByTopic}
            </p>
            <div className="flex flex-wrap gap-2">
              {results.representation_gap.best_party_by_topic.map((item) => (
                <div
                  key={item.topic}
                  className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs"
                >
                  <span className="font-medium text-slate-700">{item.topic}</span>
                  <span className="text-slate-400 mx-1">→</span>
                  <span className="text-brand-700">{item.party}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Actions */}
      <div className="flex flex-wrap gap-4">
        <Link
          href="/methodology"
          className="rounded-lg border border-slate-300 bg-white px-6 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
        >
          {r.viewMethodology}
        </Link>
        <button
          onClick={handleStartOver}
          className="rounded-lg border border-slate-200 px-6 py-2.5 text-sm font-medium text-slate-500 hover:text-slate-700 hover:bg-slate-50 transition-colors"
        >
          {r.startOver}
        </button>
      </div>
    </div>
  );
}

function PartyMatchCard({
  party,
  rank,
  r,
  lang,
}: {
  party: PartyResult;
  rank: number;
  r: Translations["results"];
  lang: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const displayName =
    lang === "he" ? (party.name_he ?? party.name) :
    lang === "ru" ? (party.name_ru ?? party.name) :
    party.name;

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="p-5 space-y-3">
        {/* Header row */}
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-600">
                {rank}
              </span>
              <div>
                <h3 className="font-semibold text-slate-900">{displayName}</h3>
                {party.is_new_party && (
                  <Tooltip content={r.tooltipNewParty} position="bottom">
                    <span className="inline-block rounded-full bg-orange-50 border border-orange-200 px-2 py-0.5 text-xs text-orange-700 mt-0.5 cursor-help">
                      {r.newParty}
                    </span>
                  </Tooltip>
                )}
              </div>
            </div>
            <div className="text-right shrink-0">
              <Tooltip content={r.tooltipMatchScore}>
                <p className="text-2xl font-bold text-slate-900 cursor-help">
                  {formatPercent(party.match_score)}
                </p>
              </Tooltip>
              <p className="text-xs text-slate-400">{r.matchLabel}</p>
            </div>
          </div>

          {/* Score bar */}
          <Tooltip content={r.tooltipScoreBar} position="bottom">
            <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden cursor-help">
              <div
                className="h-full bg-brand-500 rounded-full transition-all"
                style={{ width: `${Math.round(party.match_score * 100)}%` }}
              />
            </div>
          </Tooltip>

          {/* Badges */}
          <div className="flex flex-wrap gap-2">
            <Tooltip content={r.tooltipConfidence}>
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium cursor-help ${confidenceColor(party.confidence)}`}>
                {r.confidenceLabel(confidenceLabel(party.confidence))}
              </span>
            </Tooltip>
            <Tooltip content={r.tooltipEvidence}>
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600 cursor-help">
                {r.evidenceLabel(formatPercent(party.evidence_strength))}
              </span>
            </Tooltip>
            <Tooltip content={r.tooltipCoverage}>
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600 cursor-help">
                {r.coverageLabel(formatPercent(party.coverage))}
              </span>
            </Tooltip>
            {party.volatility > 0.3 && (
              <Tooltip content={r.tooltipVolatility}>
                <span className="rounded-full bg-yellow-50 border border-yellow-200 px-2.5 py-0.5 text-xs text-yellow-700 cursor-help">
                  {r.highVolatility}
                </span>
              </Tooltip>
            )}
          </div>

        {/* Explanation */}
        <p className="text-sm text-slate-500">{party.explanation}</p>

        {/* Expand for details */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-slate-400 hover:text-slate-600"
        >
          {expanded ? r.hideDetails : r.showDetails}
        </button>

        {expanded && (
          <div className="grid grid-cols-2 gap-4 pt-2 border-t border-slate-100">
            <div>
              <p className="text-xs font-medium text-green-700 mb-1">{r.agreements}</p>
              {party.top_agreements.length > 0 ? (
                <ul className="space-y-1">
                  {party.top_agreements.map((topic) => (
                    <li key={topic} className="text-xs text-slate-600 flex items-center gap-1">
                      <span className="text-green-500">✓</span> {topic}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-slate-400">{r.noAgreements}</p>
              )}
            </div>
            <div>
              <p className="text-xs font-medium text-red-700 mb-1">{r.disagreements}</p>
              {party.top_disagreements.length > 0 ? (
                <ul className="space-y-1">
                  {party.top_disagreements.map((topic) => (
                    <li key={topic} className="text-xs text-slate-600 flex items-center gap-1">
                      <span className="text-red-400">✗</span> {topic}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-slate-400">{r.noDisagreements}</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ResultsPage() {
  return (
    <Suspense fallback={<div className="py-20 text-center text-slate-500">Loading…</div>}>
      <ResultsContent />
    </Suspense>
  );
}
