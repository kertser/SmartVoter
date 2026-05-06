"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getPersons, PersonListItem } from "@/lib/api";
import { useLang, useT } from "@/lib/i18n";

export default function PersonsPage() {
  const { lang } = useLang();
  const t = useT();
  const b = t.browser;
  const [persons, setPersons] = useState<PersonListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    getPersons()
      .then(setPersons)
      .catch(() => setError(b.noItemsFound))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const displayed = query.trim()
    ? persons.filter((p) => {
        const q = query.toLowerCase();
        return (
          (p.name_en ?? "").toLowerCase().includes(q) ||
          (p.name_he ?? "").toLowerCase().includes(q)
        );
      })
    : persons;

  const displayName = (p: PersonListItem) =>
    lang === "he" ? p.name_he ?? p.name_en : p.name_en;

  const altName = (p: PersonListItem) =>
    lang === "he" ? p.name_en : p.name_he;

  return (
    <div className="space-y-6 pb-16">
      <div className="space-y-1">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{b.evidenceBrowser}</p>
        <h1 className="text-3xl font-bold text-slate-900">{b.personsHeading}</h1>
        <p className="text-slate-500 text-sm">
          {b.personsDesc}{" "}
          <Link href="/methodology" className="text-brand-600 hover:underline">{b.methodologyLink}</Link>
        </p>
      </div>

      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={b.searchPersons}
        className="w-full max-w-sm rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
      />

      {loading && (
        <div className="flex items-center gap-3 py-12 text-slate-500">
          <div className="h-5 w-5 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
          {b.loading}
        </div>
      )}
      {error && <p className="text-red-600">{error}</p>}

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {displayed.map((person) => (
          <Link
            key={person.id}
            href={`/persons/${person.id}`}
            className="block rounded-xl border border-slate-200 bg-white p-4 hover:border-slate-300 hover:shadow-sm transition-all"
          >
            <div className="space-y-0.5">
              <p className="font-semibold text-slate-900">{displayName(person)}</p>
              {altName(person) && altName(person) !== displayName(person) && (
                <p className="text-sm text-slate-400">{altName(person)}</p>
              )}
              {person.birth_year && (
                <p className="text-xs text-slate-400">{b.birthYear(person.birth_year)}</p>
              )}
            </div>
          </Link>
        ))}
      </div>

      {!loading && displayed.length === 0 && (
        <p className="text-slate-500 py-8 text-center">{b.noItemsFound}</p>
      )}

      {!loading && persons.length > 0 && (
        <p className="text-xs text-slate-400 text-center">
          {b.countOf(displayed.length, persons.length)}
        </p>
      )}
    </div>
  );
}
