"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getParty, PartyDetail } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import { formatPercent } from "@/lib/utils";

function PositionBar({ value }: { value: number }) {
  // value in -1..+1 → 0..100%
  const pct = ((value + 1) / 2) * 100;
  return (
    <div className="relative h-2 bg-slate-100 rounded-full overflow-hidden">
      <div className="absolute top-0 left-1/2 h-full w-px bg-slate-300" />
      <div
        className="absolute top-0 h-full w-2 rounded-full bg-brand-500"
        style={{ left: `${pct}%`, transform: "translateX(-50%)" }}
      />
    </div>
  );
}

export default function PartyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { lang } = useLang();
  const [party, setParty] = useState<PartyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getParty(id)
      .then(setParty)
      .catch(() => setError("Failed to load party."))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <div className="flex items-center gap-3 py-20 text-slate-500">
      <div className="h-6 w-6 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
      Loading…
    </div>
  );
  if (error || !party) return <p className="text-red-600 py-20">{error ?? "Not found"}</p>;

  // Party names are always shown in Hebrew — they are proper nouns.
  const partyName = party.name_he ?? party.name;

  const topicName = (pos: PartyDetail["positions"][0]) =>
    lang === "he" ? pos.topic_name_he ?? pos.topic_slug ?? ""
    : lang === "ru" ? pos.topic_name_ru ?? pos.topic_slug ?? ""
    : pos.topic_name_en ?? pos.topic_slug ?? "";

  return (
    <div className="space-y-8 pb-16">
      {/* Breadcrumb */}
      <Link href="/parties" className="text-sm text-brand-600 hover:underline">← All Parties</Link>

      {/* Header */}
      <div className="space-y-1">
        <h1 className="text-3xl font-bold text-slate-900">{partyName}</h1>
        {lang !== "he" && party.name_he && (
          <p className="text-slate-400">{party.name_he}</p>
        )}
        <p className="text-sm text-slate-500">
          {party.official_name}
          {party.knesset_number && ` · Knesset ${party.knesset_number}`}
          {party.election_cycle && ` · ${party.election_cycle}`}
          {" · "}
          <span className="capitalize">{party.status}</span>
        </p>
      </div>

      {/* Policy Positions */}
      {party.positions.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-800">Policy Positions</h2>
          <p className="text-xs text-slate-500">
            Position axis: −1 = one pole, 0 = centre, +1 = opposite pole.
            See <Link href="/methodology" className="text-brand-600 hover:underline">methodology</Link> for evidence reliability.
          </p>
          <div className="rounded-xl border border-slate-200 divide-y divide-slate-100 overflow-hidden">
            {party.positions.map((pos) => (
              <div key={pos.policy_item_id} className="px-4 py-3 space-y-2 bg-white hover:bg-slate-50 transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{pos.policy_item_title}</p>
                    <p className="text-xs text-slate-500 mt-0.5 capitalize">
                      {topicName(pos)} · {pos.evidence_type}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-sm font-semibold text-slate-700">
                      {pos.position_mean > 0 ? "+" : ""}{pos.position_mean.toFixed(2)}
                    </p>
                    <p className="text-xs text-slate-400">
                      strength {formatPercent(pos.evidence_strength)}
                    </p>
                  </div>
                </div>
                <PositionBar value={pos.position_mean} />
                {pos.llm_explanation && (
                  <p className="text-xs text-slate-400 italic">{pos.llm_explanation}</p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Members */}
      {party.members.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-800">Members / Candidates</h2>
          <div className="rounded-xl border border-slate-200 divide-y divide-slate-100 overflow-hidden">
            {party.members.map((m) => (
              <Link
                key={m.person_id}
                href={`/persons/${m.person_id}`}
                className="flex items-center justify-between px-4 py-3 bg-white hover:bg-slate-50 transition-colors"
              >
                <div>
                  <p className="text-sm font-medium text-slate-800">
                    {lang === "he" ? m.name_he ?? m.name_en : m.name_en ?? m.name_he}
                  </p>
                  {m.name_he && lang !== "he" && (
                    <p className="text-xs text-slate-400">{m.name_he}</p>
                  )}
                </div>
                <div className="text-right text-xs text-slate-500">
                  <p className="capitalize">{m.role}</p>
                  {m.start_date && <p>{m.start_date.slice(0, 7)}{m.end_date ? ` – ${m.end_date.slice(0, 7)}` : " – present"}</p>}
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Lineage */}
      {party.lineage.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-800">Party Lineage</h2>
          <div className="space-y-2">
            {party.lineage.map((edge) => (
              <div key={edge.id} className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 space-y-1">
                <p>
                  <span className="capitalize font-medium text-brand-600">{edge.relation_type}</span>
                  {" "}· continuity weight {edge.continuity_weight.toFixed(2)}
                  {" "}· review: <span className="capitalize">{edge.human_review_status}</span>
                </p>
                {edge.llm_explanation && (
                  <p className="text-xs text-slate-500 italic">{edge.llm_explanation}</p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

