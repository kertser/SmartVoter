"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getVote, VoteDetail } from "@/lib/api";
import { useLang } from "@/lib/i18n";

const VOTE_COLOR: Record<string, string> = {
  for: "bg-green-100 text-green-700",
  against: "bg-red-100 text-red-700",
  abstain: "bg-amber-100 text-amber-700",
  absent: "bg-slate-100 text-slate-500",
  unknown: "bg-slate-100 text-slate-400",
};

export default function VoteDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { lang } = useLang();
  const [vote, setVote] = useState<VoteDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getVote(id)
      .then(setVote)
      .catch(() => setError("Failed to load vote."))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <div className="flex items-center gap-3 py-20 text-slate-500">
      <div className="h-6 w-6 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
      Loading…
    </div>
  );
  if (error || !vote) return <p className="text-red-600 py-20">{error ?? "Not found"}</p>;

  const title = lang === "he" ? vote.title_he : (vote.title_en ?? vote.title_he);

  // Aggregate by vote value
  const counts = vote.results.reduce<Record<string, number>>((acc, r) => {
    acc[r.vote_value] = (acc[r.vote_value] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-8 pb-16">
      <Link href="/parties" className="text-sm text-brand-600 hover:underline">← Parties</Link>

      <div className="space-y-1">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Plenary Vote</p>
        <h1 className="text-2xl font-bold text-slate-900 leading-snug">{title}</h1>
        {vote.title_en && lang !== "en" && (
          <p className="text-slate-400 text-sm">{vote.title_en}</p>
        )}
        <p className="text-sm text-slate-500">
          {vote.date && <>{vote.date} · </>}
          {vote.knesset_number && <>Knesset {vote.knesset_number} · </>}
          {vote.vote_type}
          {vote.is_procedural_estimate && (
            <span className="ms-2 text-xs text-amber-600">(estimated procedural)</span>
          )}
        </p>
        {vote.source_url && (
          <a
            href={vote.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-brand-600 hover:underline"
          >
            Source ↗
          </a>
        )}
      </div>

      {/* Result summary */}
      <section className="rounded-xl border border-slate-200 bg-white px-5 py-4 space-y-3">
        <h2 className="text-sm font-semibold text-slate-700">Result summary</h2>
        <div className="flex gap-4 flex-wrap text-sm">
          {Object.entries(counts).map(([v, n]) => (
            <span key={v} className={`rounded-full px-3 py-1 font-medium capitalize ${VOTE_COLOR[v] ?? "bg-slate-100 text-slate-600"}`}>
              {v}: {n}
            </span>
          ))}
        </div>
        {vote.importance_score != null && (
          <p className="text-xs text-slate-400">
            Importance score: {(vote.importance_score * 100).toFixed(0)}%
          </p>
        )}
      </section>

      {/* Per-person breakdown */}
      {vote.results.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-800">Vote breakdown by MK</h2>
          <div className="rounded-xl border border-slate-200 divide-y divide-slate-100 overflow-hidden">
            {vote.results.map((r) => {
              const name = lang === "he" ? r.name_he ?? r.name_en : r.name_en ?? r.name_he;
              return (
                <div key={r.person_id} className="flex items-center justify-between px-4 py-2.5 bg-white hover:bg-slate-50">
                  <Link href={`/persons/${r.person_id}`} className="text-sm text-brand-700 hover:underline">
                    {name ?? r.person_id.slice(0, 8)}
                  </Link>
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${VOTE_COLOR[r.vote_value] ?? "bg-slate-100"}`}>
                    {r.vote_value}
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}

