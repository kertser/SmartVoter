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
  triggerSimulation,
  getKnessetCurrent,
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
        const riskLevel =
          pct >= 90 ? "text-emerald-700" : pct >= 50 ? "text-amber-700" : "text-red-700";
        return (
          <div key={p.party_name} className="flex items-center gap-3">
            <span className="w-28 text-xs font-semibold text-slate-700 text-right truncate shrink-0">
              {p.party_name}
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
            .map((p) => p.party_name)
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
        <h3 className="text-sm font-semibold text-slate-800 leading-snug">
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
          >
            {m.party_name}
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

// ── Tab component ─────────────────────────────────────────────────────────────

type Tab = "current" | "forecast" | "builder";

function TabBar({ active, onChange }: { active: Tab; onChange: (t: Tab) => void }) {
  const tabs: { id: Tab; label: string }[] = [
    { id: "current", label: "Current Knesset (25th)" },
    { id: "forecast", label: "Election Forecast" },
    { id: "builder", label: "Coalition Builder" },
  ];
  return (
    <div className="flex border-b border-slate-200 gap-0">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={`px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
            active === tab.id
              ? "border-brand-500 text-brand-700"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          {tab.label}
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
  const [triggering, setTriggering] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);

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

  const handleRunNew = async () => {
    setTriggering(true);
    setSimError(null);
    try {
      const result = await triggerSimulation(5000);
      setData(result);
    } catch {
      setSimError(s.errorLoad);
    } finally {
      setTriggering(false);
    }
  };

  const sortedParties = [...(data?.parties ?? [])].sort(
    (a, b) => b.seats_mean - a.seats_mean
  );

  const semicircleParties = sortedParties
    .slice()
    .sort((a, b) => (a.left_right_score ?? 0) - (b.left_right_score ?? 0))
    .map((p) => ({
      name: p.party_name,
      seats: p.seats_median,
      color: p.color_hex,
    }));

  const distributionParties = sortedParties.map((p) => ({
    name: p.party_name,
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
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              {data?.data_cutoff_date && (
                <p className="text-xs text-slate-400">{s.dataCutoff(data.data_cutoff_date)}</p>
              )}
            </div>
            <button
              onClick={handleRunNew}
              disabled={triggering}
              className="shrink-0 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 transition-colors"
            >
              {triggering ? s.running : s.runNewSimulation}
            </button>
          </div>

          {(simLoading || triggering) && !data && (
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
                    <p className="text-xs text-slate-500">{s.semicircleDesc}</p>
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
            <h2 className="text-base font-semibold text-slate-800">Interactive Coalition Builder</h2>
            <p className="text-sm text-slate-500">
              Assemble parties into a coalition and see instant feasibility analysis.
              This is a scenario exploration tool — not a prediction or voting recommendation.
            </p>
          </div>

          {knessetLoading && (
            <div className="flex items-center gap-3 py-8 justify-center">
              <div className="h-6 w-6 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
              <span className="text-slate-400 text-sm">Loading party data…</span>
            </div>
          )}

          {knesset && !knessetLoading && (
            <CoalitionBuilder parties={knesset.parties} useForecastSeats={false} />
          )}
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

