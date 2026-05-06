"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getBills, BillDetail } from "@/lib/api";
import { useLang, useT } from "@/lib/i18n";

export default function BillsPage() {
  const { lang } = useLang();
  const t = useT();
  const b = t.browser;
  const [bills, setBills] = useState<BillDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    getBills()
      .then(setBills)
      .catch(() => setError(b.noItemsFound))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const billTitle = (bi: BillDetail) =>
    lang === "he"
      ? bi.title_he
      : (bi.title_en ?? bi.title_he);

  const filtered = bills.filter((bi) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      bi.title_he?.toLowerCase().includes(s) ||
      bi.title_en?.toLowerCase().includes(s) ||
      bi.status?.toLowerCase().includes(s)
    );
  });

  return (
    <div className="space-y-6 pb-16">
      <div className="space-y-1">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{b.evidenceBrowser}</p>
        <h1 className="text-3xl font-bold text-slate-900">{b.billsHeading}</h1>
        <p className="text-slate-500 text-sm">
          {b.billsDesc}{" "}
          <Link href="/methodology" className="text-brand-600 hover:underline">{b.methodologyLink}</Link>
        </p>
      </div>

      <input
        type="search"
        placeholder={b.searchBills}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full max-w-sm rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
      />

      {loading && (
        <div className="flex items-center gap-3 py-12 text-slate-500">
          <div className="h-5 w-5 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
          {b.loading}
        </div>
      )}
      {error && <p className="text-red-600">{error}</p>}

      <div className="space-y-2">
        {filtered.map((bill) => (
          <Link
            key={bill.id}
            href={`/bills/${bill.id}`}
            className="block rounded-xl border border-slate-200 bg-white p-4 hover:border-slate-300 hover:shadow-sm transition-all"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-1 min-w-0">
                <p className="font-medium text-slate-900 leading-snug">{billTitle(bill)}</p>
                {lang !== "he" && bill.title_he && bill.title_he !== billTitle(bill) && (
                  <p className="text-sm text-slate-400 truncate">{bill.title_he}</p>
                )}
                <p className="text-xs text-slate-500">
                  {bill.date_submitted && <span>{bill.date_submitted.slice(0, 10)}</span>}
                  {bill.status && <span className="ms-2">{bill.status}</span>}
                </p>
              </div>
              {bill.source_url && (
                <a
                  href={bill.source_url}
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

