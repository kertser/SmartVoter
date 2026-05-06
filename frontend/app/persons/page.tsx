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
  const [sortMode, setSortMode] = useState<SortMode>("party");
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
    loadPersons(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFilterChange = (mode: FilterMode) => {
    setFilterMode(mode);
    loadPersons(mode === "current");
  };

  /**
   * Primary: Hebrew name (authoritative for Israeli persons)
   * Secondary: English name as small transliteration
   */
  const hebrewName = (p: PersonListItem) => p.name_he || p.name_en;
  const englishName = (p: PersonListItem) => p.name_en;

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
        const na = hebrewName(a) || "";
        const nb = hebrewName(b) || "";
        return na.localeCompare(nb, "he");
      });
    } else {
      list = [...list].sort((a, b) => {
        const pa = partyName(a) || "ω";
        const pb = partyName(b) || "ω";
        if (pa === pb) {
          return (hebrewName(a) || "").localeCompare(hebrewName(b) || "", "he");
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

        <div className="flex gap-1 bg-slate-100 rounded-full p-1">
          {(["party", "name"] as SortMode[]).map((s) => (
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
        <div className="space-y-5">
          {Array.from(groups.entries()).map(([groupKey, members]) => (
            <div key={groupKey}>
              <div className="flex items-center gap-2 mb-2">
                {groupKey ? (
                  <>
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shrink-0" />
                    <span className="text-sm font-semibold text-slate-700" dir="rtl">
                      {groupKey}
                    </span>
                  </>
                ) : (
                  <span className="text-sm font-semibold text-slate-400 italic">{b.noCurrentParty}</span>
                )}
                <span className="text-xs text-slate-400">({members.length})</span>
              </div>
              <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {members.map((person) => (
                  <PersonCard
                    key={person.id}
                    person={person}
                    hebrewName={hebrewName(person)}
                    englishName={englishName(person)}
                    showParty={false}
                    b={b}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Flat list by name */}
      {!loading && sortMode === "name" && (
        <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((person) => (
            <PersonCard
              key={person.id}
              person={person}
              hebrewName={hebrewName(person)}
              englishName={englishName(person)}
              showParty
              partyDisplay={partyName(person)}
              b={b}
            />
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
            <span className="ms-1 text-emerald-600">
              · {currentCount}{" "}
              {lang === "he" ? "פעילים" : lang === "ru" ? "активных" : "active"}
            </span>
          )}
        </p>
      )}
    </div>
  );
}

function PersonCard({
  person,
  hebrewName,
  englishName,
  showParty,
  partyDisplay,
  b,
}: {
  person: PersonListItem;
  hebrewName: string | undefined;
  englishName: string | undefined;
  showParty: boolean;
  partyDisplay?: string | undefined | null;
  b: ReturnType<typeof useT>["browser"];
}) {
  const hasParty = !!person.current_party_instance_id;
  // Initial for avatar: take first Hebrew char if available
  const initials = hebrewName?.[0] ?? englishName?.[0] ?? "?";

  return (
    <Link
      href={`/persons/${person.id}`}
      className="group flex items-center gap-2.5 rounded-lg border border-slate-200 bg-white px-3 py-2.5 hover:border-brand-300 hover:shadow-sm transition-all"
    >
      {/* Avatar */}
      <div className={`shrink-0 h-8 w-8 rounded-full flex items-center justify-center text-sm font-bold ${
        hasParty ? "bg-brand-50 text-brand-700" : "bg-slate-100 text-slate-400"
      }`}>
        {initials}
      </div>

      {/* Info */}
      <div className="min-w-0 flex-1">
        {/* Hebrew name — primary */}
        <p
          className="font-medium text-slate-900 group-hover:text-brand-700 transition-colors truncate text-sm leading-tight"
          dir="rtl"
        >
          {hebrewName || "—"}
        </p>
        {/* English name — secondary, only show if has value and differs */}
        {englishName && englishName !== hebrewName && (
          <p className="text-xs text-slate-400 truncate leading-tight">{englishName}</p>
        )}
        {showParty && (
          <p className="text-xs truncate leading-tight mt-0.5">
            {partyDisplay ? (
              <span className="text-slate-500" dir="rtl">{partyDisplay}</span>
            ) : (
              <span className="text-slate-300 italic">{b.noCurrentParty}</span>
            )}
          </p>
        )}
      </div>
    </Link>
  );
}
