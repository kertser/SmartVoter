"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { getResults, ResultsOut, PartyResult } from "@/lib/api";
import { clearSession } from "@/lib/session";
import { formatPercent, confidenceLabel, confidenceColor } from "@/lib/utils";
import Link from "next/link";
import { Suspense } from "react";

function ResultsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
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
      .catch(() => setError("Failed to load results. Please try again."))
      .finally(() => setLoading(false));
  }, [sessionId, router]);

  const handleStartOver = () => {
    clearSession();
    router.push("/");
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center gap-4 py-20">
        <div className="h-8 w-8 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
        <p className="text-slate-500">Computing your results…</p>
      </div>
    );
  }

  if (error || !results) {
    return (
      <div className="text-center py-20 space-y-4">
        <p className="text-red-600">{error || "No results found."}</p>
        <Link href="/" className="text-brand-600 hover:underline">Back to start</Link>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      {/* Header */}
      <div className="space-y-2">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
          Based on available evidence
        </p>
        <h1 className="text-3xl font-bold text-slate-900">Your results</h1>
        <p className="text-slate-500 text-sm">
          These scores reflect similarity between your stated preferences and each party&rsquo;s
          observed parliamentary behavior and declared positions.
          <Link href="/methodology" className="text-brand-600 ml-1 hover:underline">
            How are scores calculated?
          </Link>
        </p>
      </div>

      {/* Party match cards */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-800">Party matches</h2>
        <div className="space-y-3">
          {results.parties.map((party, i) => (
            <PartyMatchCard key={party.party_id} party={party} rank={i + 1} />
          ))}
        </div>
      </section>

      {/* Representation gap */}
      <section className="rounded-xl border border-slate-200 bg-white shadow-sm p-6 space-y-4">
        <h2 className="text-lg font-semibold text-slate-800">Representation picture</h2>
        <p className="text-sm text-slate-600">{results.representation_gap.explanation}</p>
        {results.representation_gap.best_party_by_topic.length > 0 && (
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">
              Best party by topic
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
          View methodology
        </Link>
        <button
          onClick={handleStartOver}
          className="rounded-lg border border-slate-200 px-6 py-2.5 text-sm font-medium text-slate-500 hover:text-slate-700 hover:bg-slate-50 transition-colors"
        >
          Start over
        </button>
      </div>
    </div>
  );
}

function PartyMatchCard({ party, rank }: { party: PartyResult; rank: number }) {
  const [expanded, setExpanded] = useState(false);

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
              <h3 className="font-semibold text-slate-900">{party.name}</h3>
              {party.is_new_party && (
                <span className="inline-block rounded-full bg-orange-50 border border-orange-200 px-2 py-0.5 text-xs text-orange-700 mt-0.5">
                  New party — limited evidence
                </span>
              )}
            </div>
          </div>
          <div className="text-right shrink-0">
            <p className="text-2xl font-bold text-slate-900">
              {formatPercent(party.match_score)}
            </p>
            <p className="text-xs text-slate-400">match</p>
          </div>
        </div>

        {/* Score bar */}
        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-brand-500 rounded-full transition-all"
            style={{ width: `${Math.round(party.match_score * 100)}%` }}
          />
        </div>

        {/* Badges */}
        <div className="flex flex-wrap gap-2">
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${confidenceColor(party.confidence)}`}>
            {confidenceLabel(party.confidence)} confidence
          </span>
          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600">
            Evidence: {formatPercent(party.evidence_strength)}
          </span>
          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600">
            Coverage: {formatPercent(party.coverage)}
          </span>
          {party.volatility > 0.3 && (
            <span className="rounded-full bg-yellow-50 border border-yellow-200 px-2.5 py-0.5 text-xs text-yellow-700">
              High volatility
            </span>
          )}
        </div>

        {/* Explanation */}
        <p className="text-sm text-slate-500">{party.explanation}</p>

        {/* Expand for details */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-slate-400 hover:text-slate-600"
        >
          {expanded ? "▲ Hide details" : "▼ Show agreements & disagreements"}
        </button>

        {expanded && (
          <div className="grid grid-cols-2 gap-4 pt-2 border-t border-slate-100">
            <div>
              <p className="text-xs font-medium text-green-700 mb-1">Agreements</p>
              {party.top_agreements.length > 0 ? (
                <ul className="space-y-1">
                  {party.top_agreements.map((t) => (
                    <li key={t} className="text-xs text-slate-600 flex items-center gap-1">
                      <span className="text-green-500">✓</span> {t}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-slate-400">No strong agreements</p>
              )}
            </div>
            <div>
              <p className="text-xs font-medium text-red-700 mb-1">Disagreements</p>
              {party.top_disagreements.length > 0 ? (
                <ul className="space-y-1">
                  {party.top_disagreements.map((t) => (
                    <li key={t} className="text-xs text-slate-600 flex items-center gap-1">
                      <span className="text-red-400">✗</span> {t}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-slate-400">No strong disagreements</p>
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

