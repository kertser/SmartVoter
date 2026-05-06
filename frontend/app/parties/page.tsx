"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getParties, PartyListItem } from "@/lib/api";
import { useLang, useT } from "@/lib/i18n";

const STATUS_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  active:    { bg: "bg-emerald-50",  text: "text-emerald-700", dot: "bg-emerald-500" },
  dissolved: { bg: "bg-slate-100",   text: "text-slate-500",   dot: "bg-slate-300" },
  merged:    { bg: "bg-amber-50",    text: "text-amber-700",   dot: "bg-amber-400" },
  split:     { bg: "bg-orange-50",   text: "text-orange-700",  dot: "bg-orange-400" },
  renamed:   { bg: "bg-blue-50",     text: "text-blue-700",    dot: "bg-blue-400" },
};

type FilterMode = "active" | "all";

/** Status label translation */
function statusLabel(status: string, lang: string): string {
  const map: Record<string, Record<string, string>> = {
    active:    { en: "Active",    he: "פעיל",     ru: "Активна" },
    dissolved: { en: "Dissolved", he: "מפורקת",   ru: "Ликвидирована" },
    merged:    { en: "Merged",    he: "מאוחדת",   ru: "Объединилась" },
    split:     { en: "Split",     he: "נפצלה",    ru: "Разделилась" },
    renamed:   { en: "Renamed",   he: "שונתה שם", ru: "Переименована" },
  };
  return map[status]?.[lang] ?? map[status]?.["en"] ?? status;
}

export default function PartiesPage() {
  const { lang } = useLang();
  const t = useT();
  const b = t.browser;

  const [parties, setParties] = useState<PartyListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterMode>("active");
  const [search, setSearch] = useState("");

  useEffect(() => {
    getParties(true)
      .then(setParties)
      .catch(() => setError(b.noItemsFound))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Primary display name: always Hebrew (since these are Israeli parties).
   * Hebrew is the authoritative name for Israeli political parties.
   */
  const primaryName = (p: PartyListItem) => p.name_he || p.official_name || p.name;

  /**
   * Secondary name shown in a smaller chip below:
   * - In Russian: show Russian transliteration (often same as English)
   * - In English: show the English/official name
   * - In Hebrew: nothing (already showing Hebrew)
   * Only show if different from primary.
   */
  const secondaryName = (p: PartyListItem): string | null => {
    if (lang === "he") return null;
    const sec =
      lang === "ru" ? (p.name_ru ?? p.name) :
      (p.name_ru ? null : p.name); // only show English if no Russian
    if (!sec || sec === primaryName(p)) return null;
    return sec;
  };

  const filtered = parties.filter((p) => {
    if (filter === "active" && p.status !== "active") return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        primaryName(p).toLowerCase().includes(q) ||
        p.name.toLowerCase().includes(q) ||
        (p.name_he ?? "").toLowerCase().includes(q) ||
        (p.official_name ?? "").toLowerCase().includes(q)
      );
    }
    return true;
  });

  const activeCount = parties.filter((p) => p.status === "active").length;

  const searchPlaceholder =
    lang === "he" ? "חיפוש מפלגה…" :
    lang === "ru" ? "Поиск партии…" :
    "Search party…";

  return (
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div className="space-y-1">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{b.evidenceBrowser}</p>
        <h1 className="text-3xl font-bold text-slate-900">{b.partiesHeading}</h1>
        <p className="text-slate-500 text-sm">
          {b.partiesDesc}{" "}
          <Link href="/methodology" className="text-brand-600 hover:underline">{b.methodologyLink}</Link>
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex gap-1 bg-slate-100 rounded-full p-1">
          {(["active", "all"] as FilterMode[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded-full transition-all text-sm font-medium ${
                filter === f
                  ? "bg-white shadow-sm text-slate-900"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {f === "active"
                ? `${b.filterActive}${activeCount > 0 ? ` (${activeCount})` : ""}`
                : b.filterAll}
            </button>
          ))}
        </div>
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={searchPlaceholder}
          className="w-full max-w-xs rounded-full border border-slate-200 px-4 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400 bg-white"
        />
      </div>

      {loading && (
        <div className="flex items-center gap-3 py-12 text-slate-500">
          <div className="h-5 w-5 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
          {b.loading}
        </div>
      )}
      {error && <p className="text-red-600">{error}</p>}

      {/* Party grid */}
      <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((party) => {
          const sc = STATUS_COLORS[party.status] ?? STATUS_COLORS.dissolved;
          const main = primaryName(party);
          const sub = secondaryName(party);

          return (
            <Link
              key={party.id}
              href={`/parties/${party.id}`}
              className="group flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 hover:border-brand-300 hover:shadow-md transition-all"
            >
              {/* Status dot */}
              <div className={`shrink-0 h-2.5 w-2.5 rounded-full ${sc.dot}`} />

              {/* Names — left aligned, flexible */}
              <div className="flex-1 min-w-0">
                <p
                  className="font-semibold text-slate-900 group-hover:text-brand-700 transition-colors truncate leading-tight max-w-[16rem]"
                  dir="rtl"
                  title={main}
                >
                  {main}
                </p>
                {sub && (
                  <p className="text-xs text-slate-400 truncate leading-tight mt-0.5">{sub}</p>
                )}
                {/* Knesset + cycle meta */}
                <div className="flex items-center gap-1.5 mt-1 text-xs text-slate-400 flex-wrap">
                  {party.knesset_number && (
                    <span className="font-medium text-slate-500">
                      {lang === "ru" ? `Кнессет ${party.knesset_number}` :
                       lang === "he" ? `כנסת ${party.knesset_number}` :
                       `Knesset ${party.knesset_number}`}
                    </span>
                  )}
                  {party.knesset_number && party.election_cycle && (
                    <span className="text-slate-200">·</span>
                  )}
                  {party.election_cycle && <span>{party.election_cycle}</span>}
                </div>
              </div>

              {/* Status badge */}
              <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${sc.bg} ${sc.text}`}>
                {statusLabel(party.status, lang)}
              </span>
            </Link>
          );
        })}
      </div>

      {!loading && filtered.length === 0 && (
        <div className="py-12 text-center">
          <p className="text-4xl mb-3">🏳️</p>
          <p className="text-slate-500">{b.noItemsFound}</p>
        </div>
      )}

      {!loading && parties.length > 0 && (
        <p className="text-xs text-slate-400 text-center">
          {filtered.length} / {parties.length}
          {lang === "he" ? " מפלגות" : lang === "ru" ? " партий" : " parties"}
        </p>
      )}
    </div>
  );
}
