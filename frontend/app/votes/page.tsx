"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getVotes, VoteListItem } from "@/lib/api";
import { useLang, useT } from "@/lib/i18n";

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
    getVotes(knessetFilter)
      .then(setVotes)
      .catch(() => setError(b.noItemsFound))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [knessetFilter]);

  const voteTitle = (v: VoteListItem) =>
    lang === "he"
      ? v.title_he
      : (v.title_en ?? v.title_he);

  const filtered = votes.filter((v) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      v.title_he?.toLowerCase().includes(s) ||
      v.title_en?.toLowerCase().includes(s)
    );
  });

  const importanceColor = (score?: number) => {
    if (score == null) return "text-slate-300";
    if (score >= 0.7) return "text-green-600";
    if (score >= 0.4) return "text-amber-500";
    return "text-slate-400";
  };

  return (
    <div className="space-y-6 pb-16">
      <div className="space-y-1">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{b.evidenceBrowser}</p>
        <h1 className="text-3xl font-bold text-slate-900">{b.votesHeading}</h1>
        <p className="text-slate-500 text-sm">
          {b.votesDesc}{" "}
          <Link href="/methodology" className="text-brand-600 hover:underline">{b.methodologyLink}</Link>
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <input
          type="search"
          placeholder={b.searchVotes}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-xs rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
        />
        <select
          value={knessetFilter ?? ""}
          onChange={(e) => {
            setLoading(true);
            setKnessetFilter(e.target.value ? Number(e.target.value) : undefined);
          }}
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
        >
          <option value="">{b.allKnessets}</option>
          {[25, 24, 23, 22, 21].map((n) => (
            <option key={n} value={n}>{b.knessetN(n)}</option>
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

      <div className="space-y-2">
        {filtered.map((vote) => (
          <Link
            key={vote.id}
            href={`/votes/${vote.id}`}
            className="block rounded-xl border border-slate-200 bg-white p-4 hover:border-slate-300 hover:shadow-sm transition-all"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1 min-w-0">
                <p className="font-medium text-slate-900 leading-snug">{voteTitle(vote)}</p>
                {lang !== "he" && vote.title_he && vote.title_he !== voteTitle(vote) && (
                  <p className="text-sm text-slate-400 truncate">{vote.title_he}</p>
                )}
                <p className="text-xs text-slate-500">
                  {vote.date && <span>{vote.date.slice(0, 10)}</span>}
                  {vote.knesset_number && <span className="ms-2">{b.knessetN(vote.knesset_number)}</span>}
                  {vote.importance_score != null && (
                    <span className={`ms-2 ${importanceColor(vote.importance_score)}`}>
                      {b.importanceLabel(Math.round(vote.importance_score * 100))}
                    </span>
                  )}
                </p>
              </div>
              {vote.source_url && (
                <a
                  href={vote.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="shrink-0 text-xs text-brand-600 hover:underline whitespace-nowrap"
                >
                  {b.source}
                </a>
              )}
            </div>
          </Link>
        ))}
      </div>

      {!loading && filtered.length === 0 && (
        <p className="text-slate-500 py-8 text-center">{b.noItemsFound}</p>
      )}
    </div>
  );
}

