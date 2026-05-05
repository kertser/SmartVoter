"use client";

/**
 * Knesset Simulator page — Phase 14B.
 * Per AGENTS.MD Sections 14B.10, 14B.11, 14B.14.
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
  SimulationRun,
  SimulationPartyResult,
  CoalitionScenario,
} from "@/lib/api";
import { KnessetSemicircleChart } from "@/components/charts/KnessetSemicircleChart";
import { SeatDistributionChart } from "@/components/charts/SeatDistributionChart";
import Link from "next/link";

// Muted, colorblind-safer party color palette
const PARTY_COLORS = [
  "#2563eb", // blue
  "#16a34a", // green
  "#9333ea", // purple
  "#ea580c", // orange
  "#0891b2", // cyan
  "#dc2626", // red
];

function colorForIndex(i: number) {
  return PARTY_COLORS[i % PARTY_COLORS.length];
}

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
      {sorted.map((p, i) => {
        const pct = Math.round(p.threshold_pass_probability * 100);
        const color = colorForIndex(
          parties.findIndex((x) => x.party_name === p.party_name)
        );
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
                style={{
                  width: `${pct}%`,
                  backgroundColor: color,
                  opacity: 0.8,
                }}
              />
            </div>
            <span className={`w-12 text-xs font-bold text-right ${riskLevel}`}>
              {pct}%
            </span>
          </div>
        );
      })}
      <p className="text-xs text-slate-400 pt-1">
        {label}
      </p>
    </div>
  );
}

// ── Coalition Scenario Card ───────────────────────────────────────────────────

function CoalitionCard({
  scenario,
  partyColorMap,
  s,
}: {
  scenario: CoalitionScenario;
  partyColorMap: Record<string, string>;
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
      {/* Probability badge */}
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-800 leading-snug">
          {scenario.scenario_name}
        </h3>
        <span className="shrink-0 rounded-full bg-brand-50 border border-brand-200 text-brand-700 text-xs font-bold px-2 py-0.5">
          {probPct > 0 ? `~${probPct}%` : "—"}
        </span>
      </div>

      {/* Seat count */}
      <p className="text-xs text-slate-500">
        {s.coalSeats(scenario.seat_mean, scenario.seat_p10, scenario.seat_p90)}
      </p>

      {/* Scores */}
      <div className="flex gap-4 text-xs">
        <span className={`font-medium ${feasColor}`}>
          {s.feasibilityLabel}: {feasPct}%
        </span>
        <span className={`font-medium ${stabColor}`}>
          {s.stabilityLabel}: {stabPct}%
        </span>
      </div>

      {/* Members */}
      <div className="flex flex-wrap gap-1.5">
        {scenario.members.map((m) => (
          <span
            key={m.party_name}
            className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-white"
            style={{ backgroundColor: partyColorMap[m.party_name] ?? "#94a3b8" }}
          >
            {m.party_name}
            <span className="opacity-80">({Math.round(m.expected_seats)})</span>
          </span>
        ))}
      </div>

      {/* Explanation */}
      {scenario.explanation && (
        <p className="text-xs text-slate-500 leading-relaxed">
          {scenario.explanation}
        </p>
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
                <span className="font-medium">{s.dataCutoff("").replace(": ", "")}</span>
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
          <p className="pt-2 text-amber-700 font-medium border-t border-slate-200 mt-2">
            ⚠ {s.dataNote}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function SimulationPage() {
  const t = useT();
  const s = t.simulation;
  const [data, setData] = useState<SimulationRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getLatestSimulation()
      .then(setData)
      .catch(() => setError(s.errorLoad))
      .finally(() => setLoading(false));
  }, [s.errorLoad]);

  const handleRunNew = async () => {
    setTriggering(true);
    setError(null);
    try {
      const result = await triggerSimulation(5000);
      setData(result);
    } catch {
      setError(s.errorLoad);
    } finally {
      setTriggering(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center gap-4 py-20">
        <div className="h-8 w-8 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
        <p className="text-slate-500 text-sm">{s.loadingSimulation}</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="text-center py-20 space-y-4">
        <p className="text-red-600">{error}</p>
        <button onClick={handleRunNew} className="btn-primary">
          {s.runNewSimulation}
        </button>
      </div>
    );
  }

  // Build color map
  const partyColorMap: Record<string, string> = {};
  (data?.parties ?? []).forEach((p, i) => {
    partyColorMap[p.party_name] = colorForIndex(i);
  });

  const sortedParties = [...(data?.parties ?? [])].sort(
    (a, b) => b.seats_mean - a.seats_mean
  );

  const semicircleParties = sortedParties.map((p) => ({
    name: p.party_name,
    seats: p.seats_median,
  }));

  const distributionParties = sortedParties.map((p, i) => ({
    name: p.party_name,
    seats_p10: p.seats_p10,
    seats_p25: p.seats_p25,
    seats_median: p.seats_median,
    seats_p75: p.seats_p75,
    seats_p90: p.seats_p90,
    color: colorForIndex(i),
  }));

  const maxSeats = Math.max(...sortedParties.map((p) => p.seats_p90), 45);

  return (
    <div className="space-y-10 pb-16">
      {/* ── Header ── */}
      <div className="space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
              {s.dataNote}
            </p>
            <h1 className="text-3xl font-bold text-slate-900">{s.heading}</h1>
            <p className="text-slate-500 text-sm mt-1">{s.subheading}</p>
          </div>
          <button
            onClick={handleRunNew}
            disabled={triggering}
            className="shrink-0 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 transition-colors"
          >
            {triggering ? s.running : s.runNewSimulation}
          </button>
        </div>

        {/* Epistemic disclaimer — prominently displayed */}
        <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3">
          <p className="text-sm text-amber-800">
            ⚠&nbsp;
            <strong>{s.notPrediction}</strong>
            {" — "}
            {s.disclaimer}
          </p>
        </div>

        {data?.data_cutoff_date && (
          <p className="text-xs text-slate-400">{s.dataCutoff(data.data_cutoff_date)}</p>
        )}
      </div>

      {/* ── Assumptions ── */}
      {data && <AssumptionsPanel run={data} s={s} />}

      {/* ── Semicircle + Threshold side-by-side ── */}
      {data && (
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
      )}

      {/* ── Seat Distribution Intervals ── */}
      {data && (
        <section className="rounded-xl border border-slate-200 bg-white shadow-sm p-5 space-y-3">
          <div>
            <h2 className="text-base font-semibold text-slate-800">
              {s.seatDistributionHeading}
            </h2>
            <p className="text-xs text-slate-500">{s.seatDistributionDesc}</p>
          </div>
          <SeatDistributionChart
            parties={distributionParties}
            maxSeats={maxSeats + 5}
          />
          <div className="flex items-center gap-4 pt-1 text-xs text-slate-500">
            <div className="flex items-center gap-1.5">
              <span className="inline-block w-8 h-3 bg-brand-500 rounded opacity-75" />
              <span>50% interval (p25–p75)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block w-8 h-0.5 bg-brand-500 border-t border-dashed border-brand-300" />
              <span>80% interval (p10–p90)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block w-1.5 h-4 bg-brand-600 rounded" />
              <span>{s.seatsMedianLabel}</span>
            </div>
          </div>
        </section>
      )}

      {/* ── Coalition Scenarios ── */}
      {data && (
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-800">
              {s.coalitionScenariosHeading}
            </h2>
            <p className="text-sm text-slate-500">{s.coalitionScenariosDesc}</p>
          </div>

          {data.coalitions.length === 0 ? (
            <p className="text-slate-500 text-sm">{s.noScenarios}</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {data.coalitions.slice(0, 8).map((sc) => (
                <CoalitionCard
                  key={sc.scenario_id}
                  scenario={sc}
                  partyColorMap={partyColorMap}
                  s={s}
                />
              ))}
            </div>
          )}
        </section>
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

