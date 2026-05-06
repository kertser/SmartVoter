"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getPerson, PersonDetail } from "@/lib/api";
import { useLang } from "@/lib/i18n";

export default function PersonDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { lang } = useLang();
  const [person, setPerson] = useState<PersonDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getPerson(id)
      .then(setPerson)
      .catch(() => setError("Failed to load person."))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <div className="flex items-center gap-3 py-20 text-slate-500">
      <div className="h-6 w-6 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
      Loading…
    </div>
  );
  if (error || !person) return <p className="text-red-600 py-20">{error ?? "Not found"}</p>;

  const displayName = lang === "he" ? person.name_he : person.name_en;
  const altName = lang === "he" ? person.name_en : person.name_he;

  return (
    <div className="space-y-8 pb-16">
      <Link href="/persons" className="text-sm text-brand-600 hover:underline">← Persons</Link>

      <div className="space-y-1">
        <h1 className="text-3xl font-bold text-slate-900">{displayName}</h1>
        {altName && altName !== displayName && (
          <p className="text-slate-400">{altName}</p>
        )}
        {person.birth_year && (
          <p className="text-sm text-slate-500">Born {person.birth_year}</p>
        )}
      </div>

      {/* Party membership timeline */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-800">Party Memberships</h2>
        {person.memberships.length === 0 ? (
          <p className="text-slate-500 text-sm">No membership records.</p>
        ) : (
          <div className="relative ms-4">
            {/* Timeline line */}
            <div className="absolute top-0 bottom-0 start-0 w-px bg-slate-200" />
            <div className="space-y-4">
              {person.memberships.map((m, i) => {
                // Always use Hebrew for party names — they are proper nouns
                const partyName = m.party_name_he ?? m.party_name;
                return (
                  <div key={i} className="ms-6 relative">
                    {/* Dot */}
                    <div
                      className={`absolute -start-9 top-1.5 h-3 w-3 rounded-full border-2 ${
                        m.is_current
                          ? "bg-brand-500 border-brand-500"
                          : "bg-white border-slate-300"
                      }`}
                    />
                    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 space-y-0.5">
                      <Link
                        href={`/parties/${m.party_instance_id}`}
                        className="text-sm font-medium text-brand-700 hover:underline"
                      >
                        {partyName}
                      </Link>
                      <p className="text-xs text-slate-500 capitalize">
                        {m.role}
                        {m.is_current && " · current"}
                      </p>
                      <p className="text-xs text-slate-400">
                        {m.start_date?.slice(0, 7) ?? "?"}
                        {" – "}
                        {m.end_date ? m.end_date.slice(0, 7) : "present"}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

