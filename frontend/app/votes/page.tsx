"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getVotes, VoteListItem } from "@/lib/api";
import { useLang, useT } from "@/lib/i18n";

function importanceDot(score?: number | null): string {
  if (score == null) return "bg-slate-200";
  if (score >= 0.7) return "bg-emerald-400";
  if (score >= 0.4) return "bg-amber-400";
  return "bg-slate-300";
}

export default function VotesPage() {
  const { lang } = useLang();
  const t = useT();
  const b = t.browser;

  const [votes, setVotes] = useState<VoteListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [knessetFilter, setKnessetFilter] = useState<number | undefined>(undefined);
  const [hideProcedural, setHideProcedural] = useState(true);

  const fetchVotes = (kn: number | undefined, hideProc: boolean) => {
    setLoading(true);
    setError(null);
    getVotes(kn, hideProc)
      .then(setVotes)
      .catch(() => setError(b.noItemsFound))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchVotes(knessetFilter, hideProcedural);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [knessetFilter, hideProcedural]);

  const voteTitle = (v: VoteListItem) => {
    // Prefer non-Hebrew display when lang is not Hebrew
    if (lang !== "he" && v.title_en) return v.title_en;
    return v.title_he;
  };

  const filtered = votes.filter((v) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      v.title_he?.toLowerCase().includes(s) ||
      v.title_en?.toLowerCase().includes(s)
    );
  });

  // Build knesset list from loaded data
  const knessetNumbers = Array.from(
    new Set(votes.map((v) => v.knesset_number).filter((n): n is number => n != null))
  ).sort((a, b) => b - a);

  const knessetLabel = (n: number) =>
    lang === "he" ? `כנסת ${n}` : lang === "ru" ? `Кнессет ${n}` : `Knesset ${n}`;

  return (
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div className="space-y-1">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{b.evidenceBrowser}</p>
        <h1 className="text-3xl font-bold text-slate-900">{b.votesHeading}</h1>
        <p className="text-slate-500 text-sm">
          {b.votesDesc}{" "}
          <Link href="/methodology" className="text-brand-600 hover:underline">{b.methodologyLink}</Link>
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-center">
        <input
          type="search"
          placeholder={b.searchVotes}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-xs rounded-full border border-slate-200 px-4 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400 bg-white"
        />

        {/* Knesset filter */}
        <select
          value={knessetFilter ?? ""}
          onChange={(e) => setKnessetFilter(e.target.value ? Number(e.target.value) : undefined)}
          className="rounded-full border border-slate-200 px-4 py-1.5 text-sm text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-brand-400"
        >
          <option value="">{b.allKnessets}</option>
          {knessetNumbers.map((n) => (
            <option key={n} value={n}>{knessetLabel(n)}</option>
          ))}
        </select>

        {/* Procedural filter toggle */}
        <div className="flex gap-1 bg-slate-100 rounded-full p-1 text-sm">
          <button
            onClick={() => setHideProcedural(true)}
            className={`px-3 py-1 rounded-full transition-all font-medium ${
              hideProcedural ? "bg-white shadow-sm text-slate-900" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {b.voteHideProcedural}
          </button>
          <button
            onClick={() => setHideProcedural(false)}
            className={`px-3 py-1 rounded-full transition-all font-medium ${
              !hideProcedural ? "bg-white shadow-sm text-slate-900" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {b.voteShowProcedural}
          </button>
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-3 py-12 text-slate-500">
          <div className="h-5 w-5 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
          {b.loading}
        </div>
      )}
      {error && <p className="text-red-600">{error}</p>}

      {/* Vote list */}
      <div className="space-y-2">
        {filtered.map((vote) => {
          const title = voteTitle(vote);
          const heTitle = vote.title_he;
          // Show Hebrew alongside when the primary is English
          const showHe = lang !== "he" && heTitle && heTitle !== title;
          const dot = importanceDot(vote.importance_score);
          const dateStr = vote.date ? vote.date.slice(0, 10) : null;
          const year = dateStr ? dateStr.slice(0, 4) : null;
          const isProcedural = vote.is_procedural_estimate;

          return (
            <Link
              key={vote.id}
              href={`/votes/${vote.id}`}
              className={`group flex items-start gap-3 rounded-xl border bg-white p-4 hover:shadow-sm transition-all ${
                isProcedural
                  ? "border-slate-150 opacity-75 hover:border-slate-300"
                  : "border-slate-200 hover:border-brand-300"
              }`}
            >
              {/* Importance dot + year column */}
              <div className="shrink-0 flex flex-col items-center gap-1 pt-1 w-8">
                <div className={`h-2.5 w-2.5 rounded-full ${dot}`} />
                {year && (
                  <span className="text-[10px] text-slate-400 font-mono leading-none">{year}</span>
                )}
              </div>

              <div className="flex-1 min-w-0 space-y-1">
                <p className={`font-medium leading-snug transition-colors ${
                  isProcedural ? "text-slate-500" : "text-slate-900 group-hover:text-brand-700"
                }`}>
                  {title}
                </p>
                {showHe && (
                  <p className="text-sm text-slate-400 font-hebrew">{heTitle}</p>
                )}
                <div className="flex flex-wrap items-center gap-1.5 text-xs">
                  {dateStr && (
                    <span className="font-mono text-slate-400">{dateStr}</span>
                  )}
                  {vote.knesset_number && (
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-600">
                      {knessetLabel(vote.knesset_number)}
                    </span>
                  )}
                  {isProcedural && (
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-400 italic">
                      {b.voteProceduralBadge}
                    </span>
                  )}
                  {!isProcedural && vote.importance_score != null && vote.importance_score >= 0.7 && (
                    <span className="rounded-full bg-emerald-50 text-emerald-700 px-2 py-0.5 font-medium">
                      {b.voteImportanceHigh}
                    </span>
                  )}
                  {!isProcedural && vote.importance_score != null && vote.importance_score >= 0.4 && vote.importance_score < 0.7 && (
                    <span className="rounded-full bg-amber-50 text-amber-700 px-2 py-0.5 font-medium">
                      {b.voteImportanceMedium}
                    </span>
                  )}
                </div>
              </div>

              {vote.source_url && (
                <a
                  href={vote.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="shrink-0 text-xs text-brand-600 hover:underline whitespace-nowrap self-start pt-0.5"
                >
                  {b.source}
                </a>
              )}
            </Link>
          );
        })}
      </div>

      {!loading && filtered.length === 0 && (
        <div className="py-12 text-center">
          <p className="text-4xl mb-3">🗳️</p>
          <p className="text-slate-500">{b.noItemsFound}</p>
        </div>
      )}

      {!loading && votes.length > 0 && (
        <p className="text-xs text-slate-400 text-center">
          {filtered.length} / {votes.length}
          {lang === "he" ? " הצבעות" : lang === "ru" ? " голосований" : " votes"}
        </p>
      )}
    </div>
  );
}

