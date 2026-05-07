"use client";

/**
 * CoalitionBuilder — interactive drag-and-drop coalition assembly tool.
 *
 * Three zones: Available | Coalition | Opposition
 * Uses HTML5 native DnD (no external library needed).
 * Calls /api/simulation/coalition/evaluate after each change (debounced).
 *
 * Per AGENTS.MD 14B.10 and coding rules:
 * - Never presents coalition as voting advice
 * - Shows constraint violations explicitly
 * - Uses "scenario" and "conditional simulation" language
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { KnessetParty, CoalitionEvaluation } from "@/lib/api";
import { evaluateCoalition } from "@/lib/api";

type Zone = "available" | "coalition" | "opposition";

interface PartyChip extends KnessetParty {
  zone: Zone;
}

interface Props {
  parties: KnessetParty[];
  useForecastSeats?: boolean;
}

function ScoreBar({ value, label, color }: { value: number; label: string; color: string }) {
  const pct = Math.round(value * 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-slate-600 font-medium">{label}</span>
        <span className={`font-bold ${pct >= 65 ? "text-emerald-700" : pct >= 40 ? "text-amber-700" : "text-red-700"}`}>
          {pct}%
        </span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

export function CoalitionBuilder({ parties, useForecastSeats = false }: Props) {
  const [chips, setChips] = useState<PartyChip[]>(() =>
    parties.map((p) => ({ ...p, zone: "available" as Zone }))
  );
  const [draggedName, setDraggedName] = useState<string | null>(null);
  const [evaluation, setEvaluation] = useState<CoalitionEvaluation | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Update chips when parties prop changes
  useEffect(() => {
    setChips(parties.map((p) => {
      const existing = chips.find((c) => c.official_name === p.official_name);
      return { ...p, zone: existing?.zone ?? "available" };
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parties]);

  const coalitionParties = chips.filter((c) => c.zone === "coalition");

  const triggerEvaluation = useCallback((currentChips: PartyChip[]) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      const names = currentChips.filter((c) => c.zone === "coalition").map((c) => c.official_name);
      if (names.length === 0) {
        setEvaluation(null);
        return;
      }
      setEvaluating(true);
      try {
        const result = await evaluateCoalition(names, useForecastSeats);
        setEvaluation(result);
      } catch {
        // silent — UI still works with last evaluation
      } finally {
        setEvaluating(false);
      }
    }, 350);
  }, [useForecastSeats]);

  const moveChip = (name: string, zone: Zone) => {
    setChips((prev) => {
      const next = prev.map((c) => c.official_name === name ? { ...c, zone } : c);
      triggerEvaluation(next);
      return next;
    });
  };

  const handleDragStart = (e: React.DragEvent, name: string) => {
    setDraggedName(name);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", name);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const handleDrop = (e: React.DragEvent, zone: Zone) => {
    e.preventDefault();
    const name = e.dataTransfer.getData("text/plain") || draggedName;
    if (name) moveChip(name, zone);
    setDraggedName(null);
  };

  const handleDragEnd = () => setDraggedName(null);

  const coalitionSeats = coalitionParties.reduce((s, p) => s + (p.seats || 0), 0);
  const hasMajority = (evaluation?.has_majority) ?? (coalitionSeats >= 61);

  const renderZone = (zone: Zone, label: string, bgClass: string, description: string) => {
    const zoneChips = chips.filter((c) => c.zone === zone);
    return (
      <div className="flex flex-col min-h-0">
        <div className="mb-2">
          <h3 className="text-sm font-semibold text-slate-700">{label}</h3>
          <p className="text-xs text-slate-400">{description}</p>
        </div>
        <div
          className={`flex-1 min-h-32 rounded-xl border-2 border-dashed p-3 flex flex-wrap gap-2 content-start transition-colors ${bgClass}`}
          onDragOver={handleDragOver}
          onDrop={(e) => handleDrop(e, zone)}
        >
          {zoneChips.length === 0 && (
            <p className="text-xs text-slate-300 italic w-full text-center pt-4">
              Drop parties here
            </p>
          )}
          {zoneChips.map((chip) => (
            <div
              key={chip.official_name}
              draggable
              onDragStart={(e) => handleDragStart(e, chip.official_name)}
              onDragEnd={handleDragEnd}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 cursor-grab active:cursor-grabbing select-none shadow-sm border border-black/10 transition-opacity text-white text-xs font-semibold ${
                draggedName === chip.official_name ? "opacity-40" : "opacity-100"
              }`}
              style={{ backgroundColor: chip.color_hex }}
              title={`${chip.name_he || chip.official_name} — ${chip.seats} מנדטים (שמאל/ימין: ${chip.left_right_score?.toFixed(2)})`}
            >
              <span className="max-w-[100px] truncate" dir="rtl">{chip.name_he || chip.name_en}</span>
              <span className="rounded-full bg-black/20 px-1.5 py-0.5 text-[10px] font-bold">
                {chip.seats || "—"}
              </span>
            </div>
          ))}
        </div>
        {zone === "coalition" && (
          <div className="mt-2 flex items-center justify-between">
            <span className="text-xs text-slate-500">
              {coalitionParties.length} parties · {coalitionSeats} seats
            </span>
            <span
              className={`text-xs font-bold rounded-full px-2 py-0.5 ${
                hasMajority
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-red-100 text-red-700"
              }`}
            >
              {hasMajority ? "✓ Majority" : `${61 - coalitionSeats} more needed`}
            </span>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Instruction */}
      <div className="rounded-lg bg-blue-50 border border-blue-200 px-4 py-3 text-xs text-blue-800">
        <strong>How to use:</strong> Drag parties between the three zones to build a coalition.
        Results update automatically. Coalition scenarios are conditional simulations — not predictions.
        Seat counts are from the November 2022 election.
      </div>

      {/* Three-column layout */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {renderZone(
          "coalition",
          "Coalition",
          "border-emerald-300 bg-emerald-50/30",
          "Parties forming the government"
        )}
        {renderZone(
          "opposition",
          "Opposition",
          "border-red-300 bg-red-50/30",
          "Parties in opposition"
        )}
        {renderZone(
          "available",
          "Unassigned",
          "border-slate-300 bg-slate-50/40",
          "Drag to coalition or opposition"
        )}
      </div>

      {/* Evaluation panel */}
      {coalitionParties.length > 0 && (
        <div className={`rounded-xl border border-slate-200 bg-white shadow-sm p-5 space-y-4 transition-opacity ${evaluating ? "opacity-60" : "opacity-100"}`}>
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-800">Coalition analysis</h3>
            {evaluating && (
              <span className="text-xs text-slate-400 animate-pulse">Evaluating…</span>
            )}
          </div>

          {evaluation && (
            <>
              {/* Seat bar */}
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-slate-600">
                  <span className="font-medium">Seats ({evaluation.seats}/120)</span>
                  <span className={`font-bold ${evaluation.has_majority ? "text-emerald-700" : "text-red-700"}`}>
                    {evaluation.has_majority ? "✓ Has majority (≥61)" : `No majority — ${61 - evaluation.seats} short`}
                  </span>
                </div>
                <div className="h-3 bg-slate-100 rounded-full overflow-hidden relative">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${(evaluation.seats / 120) * 100}%`,
                      background: evaluation.has_majority
                        ? "linear-gradient(90deg, #10b981, #059669)"
                        : "linear-gradient(90deg, #f87171, #ef4444)",
                    }}
                  />
                  {/* 61-seat mark */}
                  <div
                    className="absolute top-0 bottom-0 w-0.5 bg-slate-600 opacity-50"
                    style={{ left: `${(61 / 120) * 100}%` }}
                  />
                </div>
                {/* Seat breakdown */}
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {Object.entries(evaluation.seat_breakdown).map(([name, seats]) => {
                    const chip = chips.find((c) => c.official_name === name);
                    return (
                      <span
                        key={name}
                        className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-white"
                        style={{ backgroundColor: chip?.color_hex || "#94a3b8" }}
                        dir="rtl"
                      >
                        {chip?.name_he || chip?.name_en || name} ({seats})
                      </span>
                    );
                  })}
                </div>
              </div>

              {/* Score bars */}
              <div className="space-y-3">
                <ScoreBar
                  value={evaluation.feasibility_score}
                  label="Feasibility (based on declared incompatibilities)"
                  color="#6366f1"
                />
                <ScoreBar
                  value={evaluation.stability_score}
                  label="Stability (seat margin and ideological spread)"
                  color="#0ea5e9"
                />
                <ScoreBar
                  value={evaluation.ideological_coherence_score}
                  label="Ideological coherence"
                  color="#f97316"
                />
              </div>

              {/* Constraint violations */}
              {evaluation.constraint_violations.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-slate-700">Declared incompatibilities</h4>
                  {evaluation.constraint_violations.map((v, i) => (
                    <div
                      key={i}
                      className={`rounded-lg px-3 py-2 text-xs ${
                        v.strength === "hard"
                          ? "bg-red-50 border border-red-200 text-red-800"
                          : "bg-amber-50 border border-amber-200 text-amber-800"
                      }`}
                    >
                      <strong>{v.strength === "hard" ? "⛔ Hard" : "⚠ Soft"} conflict:</strong>{" "}
                      {v.description}
                    </div>
                  ))}
                </div>
              )}

              {evaluation.constraint_violations.length === 0 && (
                <p className="text-xs text-emerald-700 font-medium">
                  ✓ No declared incompatibilities between selected coalition members.
                </p>
              )}
            </>
          )}

          {!evaluation && !evaluating && (
            <p className="text-xs text-slate-400">
              Add at least one party to the coalition to see analysis.
            </p>
          )}
        </div>
      )}

      {/* Epistemic disclaimer */}
      <p className="text-xs text-slate-400 border-t border-slate-100 pt-3">
        ⚠ Coalition analysis is a conditional scenario tool, not a political prediction.
        Feasibility scores are estimates based on declared positions and historical behavior.
        Seat counts are from the 2022 election — use the &quot;Election Forecast&quot; tab for projected seats.
      </p>
    </div>
  );
}

