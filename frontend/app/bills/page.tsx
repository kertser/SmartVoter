"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { getBills, BillDetail } from "@/lib/api";
import { useLang, useT } from "@/lib/i18n";

/** Map API status string to label + colour */
function statusInfo(
  status: string | undefined,
  b: ReturnType<typeof useT>["browser"]
): { label: string; cls: string; icon: string } {
  const s = (status ?? "").toLowerCase();
  if (s.includes("pass") || s.includes("approv") || s.includes("enacted"))
    return { label: b.billStatusPassed, cls: "bg-emerald-50 text-emerald-700", icon: "✓" };
  if (s.includes("fail") || s.includes("reject") || s.includes("defeat"))
    return { label: b.billStatusFailed, cls: "bg-red-50 text-red-600", icon: "✗" };
  if (s.includes("withdraw") || s.includes("cancel"))
    return { label: b.billStatusWithdrawn, cls: "bg-slate-100 text-slate-500", icon: "←" };
  if (s)
    return { label: b.billStatusPending, cls: "bg-amber-50 text-amber-700", icon: "…" };
  return { label: "", cls: "", icon: "" };
}

type SortMode = "newest" | "oldest";

export default function BillsPage() {
  const { lang } = useLang();
  const t = useT();
  const b = t.browser;

  const [bills, setBills] = useState<BillDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortMode, setSortMode] = useState<SortMode>("newest");
  const [yearFilter, setYearFilter] = useState<string>("");

  useEffect(() => {
    getBills()
      .then(setBills)
      .catch(() => setError(b.noItemsFound))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const billTitle = (bi: BillDetail) =>
    lang === "he" ? bi.title_he : (bi.title_en ?? bi.title_he);

  const billSummary = (bi: BillDetail) =>
    lang === "he" ? bi.summary_he : (bi.summary_en ?? bi.summary_he);

  // Build year list
  const years = useMemo(() => {
    return Array.from(
      new Set(
        bills
          .map((b) => b.date_submitted?.slice(0, 4))
          .filter(Boolean) as string[]
      )
    ).sort((a, b) => b.localeCompare(a));
  }, [bills]);

  const filtered = useMemo(() => {
    let list = bills;
    if (yearFilter) {
      list = list.filter((bi) => bi.date_submitted?.startsWith(yearFilter));
    }
    if (search) {
      const s = search.toLowerCase();
      list = list.filter(
        (bi) =>
          bi.title_he?.toLowerCase().includes(s) ||
          bi.title_en?.toLowerCase().includes(s) ||
          bi.status?.toLowerCase().includes(s)
      );
    }
    if (sortMode === "oldest") {
      list = [...list].sort((a, b) =>
        (a.date_submitted ?? "").localeCompare(b.date_submitted ?? "")
      );
    } else {
      list = [...list].sort((a, b) =>
        (b.date_submitted ?? "").localeCompare(a.date_submitted ?? "")
      );
    }
    return list;
  }, [bills, search, sortMode, yearFilter]);

  const yearLabel = (y: string) => y;

  return (
    <div className="space-y-6 pb-16">
      {/* Header */}
      <div className="space-y-1">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{b.evidenceBrowser}</p>
        <h1 className="text-3xl font-bold text-slate-900">{b.billsHeading}</h1>
        <p className="text-slate-500 text-sm">
          {b.billsDesc}{" "}
          <Link href="/methodology" className="text-brand-600 hover:underline">{b.methodologyLink}</Link>
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-center">
        <input
          type="search"
          placeholder={b.searchBills}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-xs rounded-full border border-slate-200 px-4 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400 bg-white"
        />
        {/* Year filter */}
        <select
          value={yearFilter}
          onChange={(e) => setYearFilter(e.target.value)}
          className="rounded-full border border-slate-200 px-4 py-1.5 text-sm text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-brand-400"
        >
          <option value="">{b.billYearFilterAll}</option>
          {years.map((y) => (
            <option key={y} value={y}>{yearLabel(y)}</option>
          ))}
        </select>
        {/* Sort */}
        <div className="flex gap-1 bg-slate-100 rounded-full p-1">
          {(["newest", "oldest"] as SortMode[]).map((s) => (
            <button
              key={s}
              onClick={() => setSortMode(s)}
              className={`px-3 py-1 rounded-full transition-all text-sm font-medium ${
                sortMode === s
                  ? "bg-white shadow-sm text-slate-900"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {s === "newest" ? b.billSortNewest : b.billSortOldest}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-3 py-12 text-slate-500">
          <div className="h-5 w-5 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
          {b.loading}
        </div>
      )}
      {error && <p className="text-red-600">{error}</p>}

      {/* Bill list */}
      <div className="space-y-2">
        {filtered.map((bill) => {
          const title = billTitle(bill);
          const summary = billSummary(bill);
          const showHe = lang !== "he" && bill.title_he && bill.title_he !== title;
          const dateStr = bill.date_submitted ? bill.date_submitted.slice(0, 10) : null;
          const year = dateStr ? dateStr.slice(0, 4) : null;
          const si = statusInfo(bill.status, b);

          return (
            <Link
              key={bill.id}
              href={`/bills/${bill.id}`}
              className="group flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-4 hover:border-brand-300 hover:shadow-sm transition-all"
            >
              {/* Year column */}
              <div className="shrink-0 w-8 flex flex-col items-center pt-0.5 gap-0.5">
                <span className="text-lg leading-none">📄</span>
                {year && (
                  <span className="text-[10px] text-slate-400 font-mono leading-none">{year}</span>
                )}
              </div>

              <div className="flex-1 min-w-0 space-y-1">
                <p className="font-medium text-slate-900 leading-snug group-hover:text-brand-700 transition-colors">
                  {title}
                </p>
                {showHe && (
                  <p className="text-sm text-slate-400 truncate">{bill.title_he}</p>
                )}
                {summary && (
                  <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">{summary}</p>
                )}
                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  {dateStr && <span className="font-mono text-slate-400">{dateStr}</span>}
                  {si.label && (
                    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium ${si.cls}`}>
                      <span>{si.icon}</span>
                      {si.label}
                    </span>
                  )}
                </div>
              </div>

              {bill.source_url && (
                <a
                  href={bill.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="shrink-0 text-xs text-brand-600 hover:underline whitespace-nowrap self-start pt-0.5"
                >
                  {b.source}
                </a>
              )}
            </Link>
          );
        })}
      </div>

      {!loading && filtered.length === 0 && (
        <div className="py-12 text-center">
          <p className="text-4xl mb-3">📄</p>
          <p className="text-slate-500">{b.noItemsFound}</p>
        </div>
      )}

      {!loading && bills.length > 0 && (
        <p className="text-xs text-slate-400 text-center">
          {filtered.length} / {bills.length}
          {lang === "he" ? " הצעות חוק" : lang === "ru" ? " законопроектов" : " bills"}
        </p>
      )}
    </div>
  );
}

