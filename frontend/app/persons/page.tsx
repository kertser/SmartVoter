"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { getPersons, PersonListItem } from "@/lib/api";
import { useLang, useT } from "@/lib/i18n";

type SortMode = "name" | "party";
type FilterMode = "current" | "all";

export default function PersonsPage() {
  const { lang } = useLang();
  const t = useT();
  const b = t.browser;

  const [persons, setPersons] = useState<PersonListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sortMode, setSortMode] = useState<SortMode>("name");
  const [filterMode, setFilterMode] = useState<FilterMode>("current");

  const loadPersons = (currentOnly: boolean) => {
    setLoading(true);
    setError(null);
    getPersons(currentOnly)
      .then(setPersons)
      .catch(() => setError(b.noItemsFound))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadPersons(true); // default: current members only
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFilterChange = (mode: FilterMode) => {
    setFilterMode(mode);
    loadPersons(mode === "current");
  };

  const displayName = (p: PersonListItem) =>
    lang === "he" ? (p.name_he || p.name_en) : p.name_en;

  const altName = (p: PersonListItem) =>
    lang === "he" ? p.name_en : p.name_he;

  const partyName = (p: PersonListItem) =>
    lang === "he" ? (p.current_party_name_he ?? p.current_party_name) :
    lang === "ru" ? (p.current_party_name_ru ?? p.current_party_name) :
    p.current_party_name;

  const filtered = useMemo(() => {
    let list = persons;
    if (query.trim()) {
      const q = query.toLowerCase();
      list = list.filter((p) =>
        (p.name_en || "").toLowerCase().includes(q) ||
        (p.name_he || "").toLowerCase().includes(q)
      );
    }
    if (sortMode === "name") {
      list = [...list].sort((a, b) => {
        const na = (lang === "he" ? a.name_he : a.name_en) || "";
        const nb = (lang === "he" ? b.name_he : b.name_en) || "";
        return na.localeCompare(nb);
      });
    } else {
      list = [...list].sort((a, b) => {
        const pa = partyName(a) || "ω"; // no party → sort last
        const pb = partyName(b) || "ω";
        if (pa === pb) {
          const na = displayName(a) || "";
          const nb_ = displayName(b) || "";
          return na.localeCompare(nb_);
        }
        return pa.localeCompare(pb);
      });
    }
    return list;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [persons, query, sortMode, lang]);

  // Group by party when sorting by party
  const groups = useMemo(() => {
    if (sortMode !== "party") return null;
    const map = new Map<string, PersonListItem[]>();
    for (const p of filtered) {
      const key = partyName(p) || "";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(p);
    }
    return map;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtered, sortMode, lang]);

  const currentCount = persons.filter((p) => p.current_party_instance_id).length;

  return (
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div className="space-y-1">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{b.evidenceBrowser}</p>
        <h1 className="text-3xl font-bold text-slate-900">{b.personsHeading}</h1>
        <p className="text-slate-500 text-sm">
          {b.personsDesc}{" "}
          <Link href="/methodology" className="text-brand-600 hover:underline">{b.methodologyLink}</Link>
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-center">
        {/* Filter */}
        <div className="flex gap-1 bg-slate-100 rounded-full p-1">
          {(["current", "all"] as FilterMode[]).map((f) => (
            <button
              key={f}
              onClick={() => handleFilterChange(f)}
              disabled={loading}
              className={`px-3 py-1 rounded-full transition-all text-sm font-medium ${
                filterMode === f
                  ? "bg-white shadow-sm text-slate-900"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {f === "current" ? b.filterCurrentOnly : b.filterAllPersons}
            </button>
          ))}
        </div>

        {/* Sort */}
        <div className="flex gap-1 bg-slate-100 rounded-full p-1">
          {(["name", "party"] as SortMode[]).map((s) => (
            <button
              key={s}
              onClick={() => setSortMode(s)}
              className={`px-3 py-1 rounded-full transition-all text-sm font-medium ${
                sortMode === s
                  ? "bg-white shadow-sm text-slate-900"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {s === "name" ? b.sortByName : b.sortByParty}
            </button>
          ))}
        </div>

        {/* Search */}
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={b.searchPersons}
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

      {/* Grouped by party */}
      {!loading && sortMode === "party" && groups && (
        <div className="space-y-6">
          {Array.from(groups.entries()).map(([groupKey, members]) => (
            <div key={groupKey}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {groupKey || b.noCurrentParty}
                </span>
                <span className="text-xs text-slate-400">({members.length})</span>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {members.map((person) => (
                  <PersonCard key={person.id} person={person} displayName={displayName(person)} altName={altName(person)} partyName={partyName(person)} showParty={false} b={b} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Flat list by name */}
      {!loading && sortMode === "name" && (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((person) => (
            <PersonCard key={person.id} person={person} displayName={displayName(person)} altName={altName(person)} partyName={partyName(person)} showParty b={b} />
          ))}
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div className="py-12 text-center">
          <p className="text-4xl mb-3">👤</p>
          <p className="text-slate-500">{b.noItemsFound}</p>
        </div>
      )}

      {!loading && persons.length > 0 && (
        <p className="text-xs text-slate-400 text-center">
          {b.countOf(filtered.length, persons.length)}
          {filterMode === "current" && currentCount > 0 && (
            <span className="ms-1 text-emerald-600">· {currentCount} {lang === "he" ? "פעילים" : lang === "ru" ? "активных" : "active"}</span>
          )}
        </p>
      )}
    </div>
  );
}

function PersonCard({
  person,
  displayName,
  altName,
  partyName,
  showParty,
  b,
}: {
  person: PersonListItem;
  displayName: string | undefined;
  altName: string | undefined;
  partyName: string | undefined;
  showParty: boolean;
  b: ReturnType<typeof useT>["browser"];
}) {
  const hasParty = !!person.current_party_instance_id;
  return (
    <Link
      href={`/persons/${person.id}`}
      className="group block rounded-xl border border-slate-200 bg-white p-4 hover:border-brand-300 hover:shadow-md transition-all"
    >
      <div className="flex items-start gap-3">
        {/* Avatar placeholder */}
        <div className={`shrink-0 h-9 w-9 rounded-full flex items-center justify-center text-sm font-bold ${
          hasParty ? "bg-brand-100 text-brand-700" : "bg-slate-100 text-slate-400"
        }`}>
          {(displayName || "?")[0]?.toUpperCase()}
        </div>
        <div className="min-w-0 space-y-0.5">
          <p className="font-semibold text-slate-900 leading-tight group-hover:text-brand-700 transition-colors truncate">
            {displayName || "—"}
          </p>
          {altName && altName !== displayName && (
            <p className="text-xs text-slate-400 truncate">{altName}</p>
          )}
          {showParty && (
            <p className="text-xs text-slate-500 truncate">
              {partyName ? (
                <span className="inline-flex items-center gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 inline-block" />
                  {partyName}
                </span>
              ) : (
                <span className="text-slate-300 italic">{b.noCurrentParty}</span>
              )}
            </p>
          )}
          {person.birth_year && (
            <p className="text-xs text-slate-400">{b.birthYear(person.birth_year)}</p>
          )}
        </div>
      </div>
    </Link>
  );
}
