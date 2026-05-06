"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getVotes, VoteListItem } from "@/lib/api";
import { useLang, useT } from "@/lib/i18n";

/** Returns dot colour class for importance score */
function importanceDot(score?: number): string {
  if (score == null) return "bg-slate-200";
  if (score >= 0.7) return "bg-emerald-400";
  if (score >= 0.4) return "bg-amber-400";
  return "bg-slate-300";
}

function importanceLabel(score: number | undefined, b: ReturnType<typeof useT>["browser"]): string {
  if (score == null) return "";
  if (score >= 0.7) return b.voteImportanceHigh;
  if (score >= 0.4) return b.voteImportanceMedium;
  return b.voteImportanceLow;
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

  useEffect(() => {
    setLoading(true);
    getVotes(knessetFilter)
      .then(setVotes)
      .catch(() => setError(b.noItemsFound))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [knessetFilter]);

  const voteTitle = (v: VoteListItem) =>
    lang === "he" ? v.title_he : (v.title_en ?? v.title_he);

  const filtered = votes.filter((v) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      v.title_he?.toLowerCase().includes(s) ||
      v.title_en?.toLowerCase().includes(s)
    );
  });

  // Build knesset list from data
  const knessetNumbers = Array.from(
    new Set(votes.map((v) => v.knesset_number).filter(Boolean) as number[])
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
        <select
          value={knessetFilter ?? ""}
          onChange={(e) => {
            setKnessetFilter(e.target.value ? Number(e.target.value) : undefined);
          }}
          className="rounded-full border border-slate-200 px-4 py-1.5 text-sm text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-brand-400"
        >
          <option value="">{b.allKnessets}</option>
          {knessetNumbers.map((n) => (
            <option key={n} value={n}>{knessetLabel(n)}</option>
          ))}
        </select>
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
          const showHe = lang !== "he" && vote.title_he && vote.title_he !== title;
          const dot = importanceDot(vote.importance_score);
          const impLabel = importanceLabel(vote.importance_score, b);
          const dateStr = vote.date ? vote.date.slice(0, 10) : null;
          const year = dateStr ? dateStr.slice(0, 4) : null;

          return (
            <Link
              key={vote.id}
              href={`/votes/${vote.id}`}
              className="group flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-4 hover:border-brand-300 hover:shadow-sm transition-all"
            >
              {/* Importance dot */}
              <div className="shrink-0 flex flex-col items-center gap-1 pt-1">
                <div className={`h-2.5 w-2.5 rounded-full ${dot}`} title={impLabel} />
                {year && (
                  <span className="text-[10px] text-slate-400 font-mono leading-none">{year}</span>
                )}
              </div>

              <div className="flex-1 min-w-0 space-y-1">
                <p className="font-medium text-slate-900 leading-snug group-hover:text-brand-700 transition-colors">
                  {title}
                </p>
                {showHe && (
                  <p className="text-sm text-slate-400 truncate">{vote.title_he}</p>
                )}
                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  {dateStr && <span className="font-mono">{dateStr}</span>}
                  {vote.knesset_number && (
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 font-medium text-slate-600">
                      {knessetLabel(vote.knesset_number)}
                    </span>
                  )}
                  {impLabel && (
                    <span className={`rounded-full px-2 py-0.5 font-medium ${
                      (vote.importance_score ?? 0) >= 0.7 ? "bg-emerald-50 text-emerald-700" :
                      (vote.importance_score ?? 0) >= 0.4 ? "bg-amber-50 text-amber-700" :
                      "bg-slate-50 text-slate-500"
                    }`}>
                      {impLabel}
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

