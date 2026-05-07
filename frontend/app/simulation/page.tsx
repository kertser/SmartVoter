"use client";

/**
 * Knesset Simulator page — Phase 14B.
 * Per AGENTS.MD Sections 14B.10, 14B.11, 14B.14.
 *
 * Three tabs:
 *   1. Current Knesset — real 25th Knesset composition sorted left → right
 *   2. Election Forecast — probabilistic seat distribution from polling aggregation
 *   3. Coalition Builder — drag-and-drop scenario builder
 *
 * IMPORTANT: This page is VISUALLY AND SEMANTICALLY SEPARATE from personal
 * political matching results. It shows probabilistic scenarios only.
 * It never recommends whom to vote for or presents outputs as predictions.
 */

import { useEffect, useState } from "react";
import { useT } from "@/lib/i18n";
import {
  getLatestSimulation,
  getKnessetCurrent,
  adminRefreshPolling,
  SimulationRun,
  SimulationPartyResult,
  CoalitionScenario,
  KnessetComposition,
} from "@/lib/api";
import { KnessetSemicircleChart } from "@/components/charts/KnessetSemicircleChart";
import { SeatDistributionChart } from "@/components/charts/SeatDistributionChart";
import { KnessetSpectrumBar } from "@/components/charts/KnessetSpectrumBar";
import { CoalitionBuilder } from "@/components/CoalitionBuilder";
import Link from "next/link";

// ── Threshold Risk Bar ────────────────────────────────────────────────────────

function ThresholdRiskBars({
  parties,
  label,
}: {
  parties: SimulationPartyResult[];
  label: string;
}) {
  const sorted = [...parties].sort(
    (a, b) => b.threshold_pass_probability - a.threshold_pass_probability
  );
  return (
    <div className="space-y-2">
      {sorted.map((p) => {
        const pct = Math.round(p.threshold_pass_probability * 100);
        const color = p.color_hex || "#94a3b8";
        const displayName = p.name_he || p.party_name;
        const riskLevel =
          pct >= 90 ? "text-emerald-700" : pct >= 50 ? "text-amber-700" : "text-red-700";
        return (
          <div key={p.party_name} className="flex items-center gap-3">
            <span className="w-32 text-xs font-semibold text-slate-700 text-right truncate shrink-0" dir="rtl">
              {displayName}
            </span>
            <div className="flex-1 h-5 bg-slate-100 rounded overflow-hidden">
              <div
                className="h-full rounded transition-all"
                style={{ width: `${pct}%`, backgroundColor: color, opacity: 0.85 }}
              />
            </div>
            <span className={`w-12 text-xs font-bold text-right ${riskLevel}`}>{pct}%</span>
          </div>
        );
      })}
      {/* At-risk callout */}
      {sorted.filter((p) => p.threshold_pass_probability < 0.65).length > 0 && (
        <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800 mt-2">
          <strong>⚠ At threshold risk:</strong>{" "}
          {sorted
            .filter((p) => p.threshold_pass_probability < 0.65)
            .map((p) => p.name_he || p.party_name)
            .join(", ")}
          {" — "}below 65% probability of passing the 3.25% threshold in simulations.
        </div>
      )}
      <p className="text-xs text-slate-400 pt-1">{label}</p>
    </div>
  );
}

// ── Coalition Scenario Card ───────────────────────────────────────────────────

function CoalitionCard({
  scenario,
  s,
}: {
  scenario: CoalitionScenario;
  s: ReturnType<typeof useT>["simulation"];
}) {
  const feasPct = Math.round((scenario.feasibility_score ?? 0) * 100);
  const stabPct = Math.round((scenario.stability_score ?? 0) * 100);
  const probPct = Math.round((scenario.probability_estimate ?? 0) * 100);
  const feasColor =
    feasPct >= 65 ? "text-emerald-700" : feasPct >= 40 ? "text-amber-700" : "text-red-700";
  const stabColor =
    stabPct >= 65 ? "text-emerald-700" : stabPct >= 40 ? "text-amber-700" : "text-red-700";

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-5 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-800 leading-snug" dir="rtl">
          {scenario.scenario_name}
        </h3>
        <span className="shrink-0 rounded-full bg-brand-50 border border-brand-200 text-brand-700 text-xs font-bold px-2 py-0.5">
          {probPct > 0 ? `~${probPct}%` : "—"}
        </span>
      </div>
      <p className="text-xs text-slate-500">
        {s.coalSeats(scenario.seat_mean, scenario.seat_p10, scenario.seat_p90)}
      </p>
      <div className="flex gap-4 text-xs">
        <span className={`font-medium ${feasColor}`}>
          {s.feasibilityLabel}: {feasPct}%
        </span>
        <span className={`font-medium ${stabColor}`}>
          {s.stabilityLabel}: {stabPct}%
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {scenario.members.map((m) => (
          <span
            key={m.party_name}
            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-white"
            style={{ backgroundColor: m.color_hex || "#94a3b8" }}
            dir="rtl"
          >
            {m.name_he || m.party_name}
            <span className="opacity-80">({Math.round(m.expected_seats)})</span>
          </span>
        ))}
      </div>
      {scenario.explanation && (
        <p className="text-xs text-slate-500 leading-relaxed">{scenario.explanation}</p>
      )}
    </div>
  );
}

// ── Assumptions Panel ─────────────────────────────────────────────────────────

function AssumptionsPanel({
  run,
  s,
}: {
  run: SimulationRun;
  s: ReturnType<typeof useT>["simulation"];
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-3 text-sm font-medium text-slate-700"
      >
        <span>{s.assumptionsHeading}</span>
        <span className="text-slate-400">{open ? s.assumptionsHide : s.assumptionsShow}</span>
      </button>
      {open && (
        <div className="border-t border-slate-200 px-5 py-4 space-y-2 text-xs text-slate-600">
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5">
            <span className="font-medium">{s.modelVersionLabel}</span>
            <span className="text-slate-500">{run.model_version}</span>
            <span className="font-medium">{s.iterationsLabel}</span>
            <span className="text-slate-500">{run.n_iterations.toLocaleString()}</span>
            {run.data_cutoff_date && (
              <>
                <span className="font-medium">Data cutoff</span>
                <span className="text-slate-500">{run.data_cutoff_date}</span>
              </>
            )}
            <span className="font-medium">{s.totalSeatsLabel}</span>
            <span className="text-slate-500">120</span>
          </div>
          {Object.entries(run.assumptions).map(([k, v]) => (
            <div key={k} className="flex gap-2">
              <span className="font-medium shrink-0 capitalize">{k.replace(/_/g, " ")}:</span>
              <span className="text-slate-500">{String(v)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Party Registration Panel ───────────────────────────────────────────────────

const FORECAST_PARTIES: Array<{
  name_he: string;
  name_ru: string;
  status: "active_25" | "new_26" | "split_26";
  note_he: string;
  note_ru: string;
  color: string;
}> = [
  { name_he: "הליכוד",          name_ru: "Ликуд",               status: "active_25", note_he: "25 מנדטים, פעיל", note_ru: "32 места, действует", color: "#1E3A8A" },
  { name_he: "יש עתיד",         name_ru: "Еш Атид",             status: "active_25", note_he: "24 מנדטים, פעיל", note_ru: "24 места, действует", color: "#3B82F6" },
  { name_he: "מחנה ממלכתי",     name_ru: "Нац. единство (Ганц)",status: "active_25", note_he: "12 מנדטים, פעיל", note_ru: "12 мест, действует", color: "#0EA5E9" },
  { name_he: "ש\"ס",            name_ru: "Шас",                  status: "active_25", note_he: "11 מנדטים, פעיל", note_ru: "11 мест, действует", color: "#C2410C" },
  { name_he: "יהדות התורה",     name_ru: "Яхадут ха-Тора",      status: "active_25", note_he: "7 מנדטים, פעיל", note_ru: "7 мест, действует",  color: "#7C3AED" },
  { name_he: "ישראל ביתנו",     name_ru: "Исраэль Бейтейну",    status: "active_25", note_he: "6 מנדטים, פעיל", note_ru: "6 мест, действует",  color: "#1E40AF" },
  { name_he: "חד\"ש-תע\"ל",     name_ru: "Хадаш-Тааль",         status: "active_25", note_he: "5 מנדטים, פעיל", note_ru: "5 мест, действует",  color: "#DC2626" },
  { name_he: "רע\"מ",           name_ru: "Раам",                 status: "active_25", note_he: "5 מנדטים, פעיל", note_ru: "5 мест, действует",  color: "#059669" },
  { name_he: "הדמוקרטים",       name_ru: "Демократы (Голан)",   status: "new_26",    note_he: "חדשה — מיזוג עבודה + מרץ בהנהגת יאיר גולן", note_ru: "Новая — слияние Авода + Мерец под руководством Яира Голана", color: "#0891B2" },
  { name_he: "עוצמה יהודית",    name_ru: "Евр. сила (Бен-Гвир)",status: "split_26",  note_he: "נפרדת מהציונות הדתית — ב-2022 רצו יחד", note_ru: "Отдельно от Религ. сионизма — в 2022 шли вместе", color: "#7F1D1D" },
  { name_he: "הציונות הדתית",   name_ru: "Религ. сионизм (Смотрич)", status: "split_26", note_he: "נפרדת מעוצמה יהודית — ב-2022 רצו יחד", note_ru: "Отдельно от Евр. силы — в 2022 шли вместе", color: "#B91C1C" },
];

const STATUS_LABELS: Record<string, { label_he: string; label_ru: string; cls: string }> = {
  active_25: { label_he: "פעילה בכנסת 25",  label_ru: "В 25-м Кнессете",   cls: "bg-emerald-100 text-emerald-700" },
  new_26:    { label_he: "מפלגה חדשה",       label_ru: "Новая партия",       cls: "bg-blue-100 text-blue-700" },
  split_26:  { label_he: "הפרדה מרשימה משולבת", label_ru: "Разделились",    cls: "bg-amber-100 text-amber-700" },
};

function PartyRegistrationPanel() {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50 rounded-xl transition-colors"
      >
        <span>🗳️ הרכב הרשימות לכנסת ה-26 — מי מתמודד ולמה</span>
        <span className="text-slate-400 text-xs">{open ? "▲ סגור" : "▼ הצג"}</span>
      </button>
      {open && (
        <div className="border-t border-slate-100 px-5 py-4 space-y-3">
          <p className="text-xs text-slate-500 leading-relaxed">
            הרשימה מבוססת על מידע ציבורי זמין נכון למאי 2026. יש לאמת מול מקורות עדכניים.
            <strong className="text-amber-700"> שינויים בהרכב הרשימות עלולים להשפיע על התוצאות.</strong>
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {FORECAST_PARTIES.map((p) => {
              const s = STATUS_LABELS[p.status];
              return (
                <div key={p.name_he} className="flex items-start gap-2.5 rounded-lg border border-slate-100 px-3 py-2">
                  <span className="w-3 h-3 rounded-sm shrink-0 mt-0.5 border border-black/10" style={{ backgroundColor: p.color }} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-xs font-semibold text-slate-800" dir="rtl">{p.name_he}</span>
                      <span className={`text-[10px] font-medium rounded-full px-1.5 py-0.5 leading-none ${s.cls}`}>{s.label_he}</span>
                    </div>
                    <p className="text-[10px] text-slate-400 mt-0.5 leading-snug" dir="rtl">{p.note_he}</p>
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-[10px] text-slate-400 border-t border-slate-100 pt-2">
            ⚠ נכון למאי 2026. מפלגות יכולות להתמזג, להתפצל או לשנות שם לפני הבחירות.
            מפלגות לא רשומות לא יכולות להתמודד. מקור חיצוני: ועדת הבחירות המרכזית.
          </p>
        </div>
      )}
    </div>
  );
}

// ── Tab component ─────────────────────────────────────────────────────────────

type Tab = "current" | "forecast" | "builder";

function TabBar({ active, onChange }: { active: Tab; onChange: (t: Tab) => void }) {
  const tabs: { id: Tab; label: string; badge?: string }[] = [
    { id: "current", label: "כנסת ה-25 (נוכחית)" },
    { id: "forecast", label: "כנסת ה-26 — תחזית", badge: "נתוני אמדן" },
    { id: "builder", label: "בניית קואליציה" },
  ];
  return (
    <div className="flex border-b border-slate-200 gap-0">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
            active === tab.id
              ? "border-brand-500 text-brand-700"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          {tab.label}
          {tab.badge && (
            <span className="rounded-full bg-amber-100 text-amber-700 text-[10px] font-semibold px-1.5 py-0.5 leading-none">
              {tab.badge}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function SimulationPage() {
  const t = useT();
  const s = t.simulation;
  const [activeTab, setActiveTab] = useState<Tab>("current");

  // Current Knesset data
  const [knesset, setKnesset] = useState<KnessetComposition | null>(null);
  const [knessetLoading, setKnessetLoading] = useState(true);
  const [knessetError, setKnessetError] = useState<string | null>(null);

  // Forecast/simulation data
  const [data, setData] = useState<SimulationRun | null>(null);
  const [simLoading, setSimLoading] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);

  // Polling refresh state
  const [refreshing, setRefreshing] = useState(false);
  const [refreshResult, setRefreshResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [adminPw, setAdminPw] = useState("");

  const handleRefreshPolls = async () => {
    if (!adminPw) { setRefreshResult({ ok: false, msg: "Введите пароль администратора" }); return; }
    setRefreshing(true);
    setRefreshResult(null);
    try {
      // Store temporarily so adminApiFetch picks it up
      if (typeof window !== "undefined") sessionStorage.setItem("sv_admin_pw", adminPw);
      const res = await adminRefreshPolling();
      if (res.polls_stored > 0) {
        setRefreshResult({ ok: true, msg: `✓ Загружено ${res.polls_stored} опросов (${res.parties_stored} результатов партий). Источник: ${res.source}` });
        // Reload simulation data
        setData(null);
        setSimLoading(true);
        getLatestSimulation().then(setData).catch(() => {}).finally(() => setSimLoading(false));
      } else {
        const warn = res.warnings.join(" | ");
        setRefreshResult({ ok: false, msg: warn || "Нет данных. Проверьте OPENAI_API_KEY." });
      }
    } catch (e: unknown) {
      setRefreshResult({ ok: false, msg: String(e) });
    } finally {
      setRefreshing(false);
    }
  };

  // Load current Knesset data on mount
  useEffect(() => {
    getKnessetCurrent()
      .then(setKnesset)
      .catch(() => setKnessetError("Failed to load Knesset composition. Ensure seed data is loaded."))
      .finally(() => setKnessetLoading(false));
  }, []);

  // Load forecast lazily when tab is first clicked
  useEffect(() => {
    if ((activeTab === "forecast" || activeTab === "builder") && !data && !simLoading) {
      setSimLoading(true);
      getLatestSimulation()
        .then(setData)
        .catch(() => setSimError(s.errorLoad))
        .finally(() => setSimLoading(false));
    }
  }, [activeTab, data, simLoading, s.errorLoad]);

  const sortedParties = [...(data?.parties ?? [])].sort(
    (a, b) => b.seats_mean - a.seats_mean
  );

  const semicircleParties = sortedParties
    .slice()
    .sort((a, b) => (a.left_right_score ?? 0) - (b.left_right_score ?? 0))
    .map((p) => ({
      name: p.name_he || p.party_name,
      seats: p.seats_median,
      color: p.color_hex,
      lr: p.left_right_score,
    }));

  const distributionParties = sortedParties.map((p) => ({
    name: p.name_he || p.party_name,
    seats_p10: p.seats_p10,
    seats_p25: p.seats_p25,
    seats_median: p.seats_median,
    seats_p75: p.seats_p75,
    seats_p90: p.seats_p90,
    color: p.color_hex || "#94a3b8",
  }));

  const maxSeats = Math.max(...sortedParties.map((p) => p.seats_p90), 45);

  // For the coalition builder, use knesset parties (real seats)

  return (
    <div className="space-y-6 pb-16">
      {/* ── Header ── */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold text-slate-900">{s.heading}</h1>
        <p className="text-slate-500 text-sm">{s.subheading}</p>
        {/* Epistemic disclaimer */}
        <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
          <p className="text-sm text-amber-800">
            ⚠&nbsp;
            <strong>{s.notPrediction}</strong>
            {" — "}
            {s.disclaimer}
          </p>
        </div>
      </div>

      {/* ── Tab navigation ── */}
      <TabBar active={activeTab} onChange={setActiveTab} />

      {/* ── TAB 1: Current Knesset ── */}
      {activeTab === "current" && (
        <div className="space-y-6">
          <section className="rounded-xl border border-slate-200 bg-white shadow-sm p-5 space-y-4">
            <div>
              <h2 className="text-base font-semibold text-slate-800">
                25th Knesset — Political Spectrum (November 2022)
              </h2>
              <p className="text-xs text-slate-500">
                Parties arranged left to right based on their political position score.
                Width of each segment represents actual seat count from the 2022 election.
                <span className="font-medium text-slate-600">
                  {" "}MK = Member of Knesset (חבר כנסת, ח&quot;כ).
                </span>
              </p>
            </div>

            {knessetLoading && (
              <div className="flex items-center gap-3 py-8 justify-center">
                <div className="h-6 w-6 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
                <span className="text-slate-400 text-sm">Loading Knesset data…</span>
              </div>
            )}

            {knessetError && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {knessetError}
              </div>
            )}

            {knesset && !knessetLoading && (
              <>
                <div className="text-xs text-slate-400">
                  Turnout: 70.9% · Threshold: {knesset.threshold_percent}% · Total: {knesset.total_seats} seats
                </div>
                <KnessetSpectrumBar parties={knesset.parties} />
              </>
            )}
          </section>
        </div>
      )}

      {/* ── TAB 2: Election Forecast ── */}
      {activeTab === "forecast" && (
        <div className="space-y-6">
          {/* Data-source notice */}
          <div className="rounded-lg bg-blue-50 border border-blue-200 px-4 py-3 text-sm text-blue-800 space-y-1">
            <p className="font-semibold">📊 תחזית כנסת ה-26 — לא הכנסת הנוכחית</p>
            <p className="text-xs leading-relaxed">
              לשונית זו מציגה <strong>תרחישי בחירות עתידיים לכנסת ה-26</strong>, לא את הרכב הכנסת ה-25 הנוכחית.
              הרכב הסיעות מבוסס על <strong>נתוני סקרי דעת קהל מוערכים</strong> (ינואר–אפריל 2026) שהוזנו ידנית.
              המערכת <strong>אינה מחוברת לסקרים בזמן אמת</strong> ממחברות סקרים.
              כל הנתונים הם תרחישים הסתברותיים בלבד, לא חיזוי בחירות.
            </p>
          </div>

          {/* Party registration status panel */}
          <PartyRegistrationPanel />

          {/* Polls source + refresh panel */}
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-4 space-y-3">
            {/* Source badge */}
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-sm font-medium text-slate-700">Источник данных опросов:</span>
              {data?.polls_meta ? (
                <span className={`text-xs font-semibold rounded-full px-2.5 py-1 ${
                  data.polls_meta.source === "live_web_search"
                    ? "bg-emerald-100 text-emerald-700"
                    : "bg-amber-100 text-amber-700"
                }`}>
                  {data.polls_meta.source === "live_web_search" ? "🌐 Живые данные (веб-поиск)" : "⚠ Расчётные данные (seed)"}
                </span>
              ) : (
                <span className="text-xs text-slate-400">загрузка…</span>
              )}
              {data?.polls_meta?.latest_date && (
                <span className="text-xs text-slate-400">актуально на {data.polls_meta.latest_date}</span>
              )}
            </div>

            {/* Refresh controls */}
            <details className="group">
              <summary className="cursor-pointer text-xs text-brand-600 font-medium select-none">
                🔄 Обновить опросы через OpenAI (требует admin-пароль)
              </summary>
              <div className="mt-3 space-y-2 p-3 bg-slate-50 rounded-lg border border-slate-200">
                <p className="text-xs text-slate-500">
                  Запускает веб-поиск через OpenAI Responses API (<code>gpt-4o</code>).
                  Находит актуальные опросы израильских социологических служб и обновляет базу.
                  Требует действующий <code>OPENAI_API_KEY</code>.
                </p>
                <div className="flex gap-2 flex-wrap">
                  <input
                    type="password"
                    placeholder="Пароль администратора"
                    value={adminPw}
                    onChange={(e) => setAdminPw(e.target.value)}
                    className="flex-1 min-w-0 rounded-lg border border-slate-300 px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-brand-400"
                  />
                  <button
                    onClick={handleRefreshPolls}
                    disabled={refreshing}
                    className="shrink-0 rounded-lg bg-brand-600 text-white px-4 py-1.5 text-xs font-medium hover:bg-brand-700 disabled:opacity-50 transition-colors"
                  >
                    {refreshing ? "Поиск…" : "Обновить опросы"}
                  </button>
                </div>
                {refreshResult && (
                  <p className={`text-xs font-medium ${refreshResult.ok ? "text-emerald-700" : "text-red-600"}`}>
                    {refreshResult.msg}
                  </p>
                )}
              </div>
            </details>
          </div>

          {data?.data_cutoff_date && (
            <p className="text-xs text-slate-400">{s.dataCutoff(data.data_cutoff_date)}</p>
          )}

          {simLoading && !data && (
            <div className="flex flex-col items-center gap-4 py-16">
              <div className="h-8 w-8 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
              <p className="text-slate-500 text-sm">{s.loadingSimulation}</p>
            </div>
          )}

          {simError && !data && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
              {simError}
            </div>
          )}

          {data && (
            <>
              <AssumptionsPanel run={data} s={s} />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <section className="rounded-xl border border-slate-200 bg-white shadow-sm p-5 space-y-3">
                  <div>
                    <h2 className="text-base font-semibold text-slate-800">{s.semicircleHeading}</h2>
                    <p className="text-xs text-slate-500">כנסת ה-26 (תחזית) — {s.semicircleDesc}</p>
                  </div>
                  <KnessetSemicircleChart parties={semicircleParties} />
                </section>

                <section className="rounded-xl border border-slate-200 bg-white shadow-sm p-5 space-y-3">
                  <div>
                    <h2 className="text-base font-semibold text-slate-800">{s.thresholdRiskHeading}</h2>
                    <p className="text-xs text-slate-500">{s.thresholdRiskDesc}</p>
                  </div>
                  <ThresholdRiskBars parties={data.parties} label={s.thresholdProbLabel} />
                </section>
              </div>

              <section className="rounded-xl border border-slate-200 bg-white shadow-sm p-5 space-y-3">
                <div>
                  <h2 className="text-base font-semibold text-slate-800">{s.seatDistributionHeading}</h2>
                  <p className="text-xs text-slate-500">{s.seatDistributionDesc}</p>
                </div>
                <SeatDistributionChart parties={distributionParties} maxSeats={maxSeats + 5} />
              </section>

              <section className="space-y-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-800">{s.coalitionScenariosHeading}</h2>
                  <p className="text-sm text-slate-500">{s.coalitionScenariosDesc}</p>
                </div>
                {data.coalitions.length === 0 ? (
                  <p className="text-slate-500 text-sm">{s.noScenarios}</p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {data.coalitions.slice(0, 8).map((sc) => (
                      <CoalitionCard key={sc.scenario_id} scenario={sc} s={s} />
                    ))}
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      )}

      {/* ── TAB 3: Coalition Builder ── */}
      {activeTab === "builder" && (
        <div className="space-y-4">
          <div>
            <h2 className="text-base font-semibold text-slate-800">בניית קואליציה</h2>
            <p className="text-sm text-slate-500">
              בנה קואליציה אפשרית וקבל ניתוח מיידי. מנדטים מבוססים על תחזית כנסת ה-26 (לא בחירות 2022).
              ניתן להוסיף מפלגות היפותטיות עם מספר מנדטים שרירותי.
            </p>
          </div>

          {/* Load simulation data if not loaded yet */}
          {!data && !simLoading && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-xs text-amber-800">
              <strong>⚠ טוען נתוני סימולציה...</strong> יש לטעון את לשונית &quot;כנסת ה-26 — תחזית&quot; תחילה, או לחכות.
            </div>
          )}

          {simLoading && (
            <div className="flex items-center gap-3 py-8 justify-center">
              <div className="h-6 w-6 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
              <span className="text-slate-400 text-sm">טוען נתוני תחזית…</span>
            </div>
          )}

          {/* Convert simulation parties → KnessetParty format for CoalitionBuilder */}
          {(() => {
            const forecastParties = (data?.parties ?? []).map((p) => ({
              official_name: p.party_name,
              name_en: p.party_name,
              name_he: p.name_he,
              seats: Math.round(p.seats_median),
              vote_share: p.vote_share_mean,
              left_right_score: p.left_right_score ?? 0,
              political_bloc: "",
              color_hex: p.color_hex || "#94a3b8",
              party_instance_id: p.party_instance_id ?? undefined,
            }));

            // Fallback to historical knesset if simulation not loaded
            const builderParties = forecastParties.length > 0
              ? forecastParties
              : (knesset?.parties ?? []);

            const usingForecast = forecastParties.length > 0;

            return builderParties.length > 0 ? (
              <CoalitionBuilder
                parties={builderParties}
                isForecast={usingForecast}
              />
            ) : (
              <div className="text-slate-400 text-sm text-center py-8">אין נתוני מפלגות זמינים</div>
            );
          })()}
        </div>
      )}

      {/* ── Footer link ── */}
      <div className="border-t border-slate-200 pt-6 flex items-center justify-between flex-wrap gap-3">
        <Link href="/methodology" className="text-sm text-brand-600 hover:underline">
          {t.results.viewMethodology}
        </Link>
        <Link href="/" className="text-sm text-slate-500 hover:text-slate-700">
          {t.results.backToStart}
        </Link>
      </div>
    </div>
  );
}

