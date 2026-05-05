"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getParties, PartyListItem } from "@/lib/api";
import { useLang } from "@/lib/i18n";
const STATUS_COLOR: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  dissolved: "bg-slate-100 text-slate-500",
  merged: "bg-amber-100 text-amber-700",
  split: "bg-orange-100 text-orange-700",
  renamed: "bg-blue-100 text-blue-700",
};

export default function PartiesPage() {
  const { lang } = useLang();
  const [parties, setParties] = useState<PartyListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "active">("active");

  useEffect(() => {
    getParties()
      .then(setParties)
      .catch(() => setError("Failed to load parties."))
      .finally(() => setLoading(false));
  }, []);

  const displayed = filter === "active"
    ? parties.filter((p) => p.status === "active")
    : parties;

  const partyName = (p: PartyListItem) =>
    lang === "he" ? p.name_he ?? p.name : lang === "ru" ? p.name_ru ?? p.name : p.name;

  return (
    <div className="space-y-6 pb-16">
      <div className="space-y-1">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Evidence Browser</p>
        <h1 className="text-3xl font-bold text-slate-900">Parties</h1>
        <p className="text-slate-500 text-sm">
          All political party instances tracked by SmartVoter.{" "}
          <Link href="/methodology" className="text-brand-600 hover:underline">Methodology</Link>
        </p>
      </div>

      {/* Filter */}
      <div className="flex gap-2 text-sm">
        {(["active", "all"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-full border transition-colors ${
              filter === f
                ? "border-brand-500 bg-brand-50 text-brand-700 font-medium"
                : "border-slate-200 text-slate-600 hover:border-slate-300"
            }`}
          >
            {f === "active" ? "Active parties" : "All instances"}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex items-center gap-3 py-12 text-slate-500">
          <div className="h-5 w-5 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
          Loading…
        </div>
      )}
      {error && <p className="text-red-600">{error}</p>}

      <div className="grid gap-3">
        {displayed.map((party) => (
          <Link
            key={party.id}
            href={`/parties/${party.id}`}
            className="block rounded-xl border border-slate-200 bg-white p-4 hover:border-slate-300 hover:shadow-sm transition-all"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1">
                <p className="font-semibold text-slate-900">{partyName(party)}</p>
                {lang !== "he" && party.name_he && (
                  <p className="text-sm text-slate-400">{party.name_he}</p>
                )}
                <p className="text-xs text-slate-500">
                  {party.official_name}
                  {party.knesset_number && ` · Knesset ${party.knesset_number}`}
                  {party.election_cycle && ` · ${party.election_cycle}`}
                </p>
              </div>
              <span
                className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium capitalize ${
                  STATUS_COLOR[party.status] ?? "bg-slate-100 text-slate-600"
                }`}
              >
                {party.status}
              </span>
            </div>
          </Link>
        ))}
      </div>

      {!loading && displayed.length === 0 && (
        <p className="text-slate-500 py-8 text-center">No parties found.</p>
      )}
    </div>
  );
}




