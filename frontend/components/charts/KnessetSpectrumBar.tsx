"use client";

/**
 * KnessetSpectrumBar — horizontal political spectrum visualization.
 *
 * Renders parties from LEFT (−1) to RIGHT (+1) as colored rectangles.
 * Width of each rectangle is proportional to seat count.
 * Used in the "Current Knesset" tab of the Simulation page.
 */

import { useState } from "react";
import type { KnessetParty } from "@/lib/api";

interface Props {
  parties: KnessetParty[];  // already sorted left → right
}

const BLOC_BG: Record<string, string> = {
  "far-right":    "#B91C1C",
  "right":        "#DC2626",
  "center-right": "#F97316",
  "center-left":  "#6366F1",
  "left":         "#3B82F6",
  "arab-left":    "#22C55E",
};

function BlocSeats({ parties }: { parties: KnessetParty[] }) {
  const blocs: Record<string, number> = {};
  for (const p of parties) {
    blocs[p.political_bloc] = (blocs[p.political_bloc] || 0) + p.seats;
  }

  const rightBloc = (blocs["far-right"] || 0) + (blocs["right"] || 0) + (blocs["center-right"] || 0);
  const leftBloc = (blocs["center-left"] || 0) + (blocs["left"] || 0) + (blocs["arab-left"] || 0);
  const hasRight = rightBloc >= 61;
  const hasLeft = leftBloc >= 61;

  return (
    <div className="flex items-center gap-6 text-xs flex-wrap pt-1">
      <span className={`font-medium ${hasRight ? "text-emerald-700" : "text-slate-500"}`}>
        Right bloc: {rightBloc} seats{hasRight ? " ✓ majority" : ""}
      </span>
      <span className={`font-medium ${hasLeft ? "text-emerald-700" : "text-slate-500"}`}>
        Center-Left / Arab bloc: {leftBloc} seats{hasLeft ? " ✓ majority" : ""}
      </span>
    </div>
  );
}

export function KnessetSpectrumBar({ parties }: Props) {
  const [hovered, setHovered] = useState<string | null>(null);

  if (parties.length === 0) {
    return (
      <div className="h-16 bg-slate-100 rounded-xl flex items-center justify-center text-xs text-slate-400">
        No data available
      </div>
    );
  }

  const seatsInChart = parties.reduce((s, p) => s + p.seats, 0);

  return (
    <div className="space-y-3">
      {/* Axis labels */}
      <div className="flex justify-between text-xs text-slate-400 font-medium px-1">
        <span>◀ Left</span>
        <span>Center</span>
        <span>Right ▶</span>
      </div>

      {/* Main bar */}
      <div className="relative">
        <div className="flex h-12 rounded-xl overflow-hidden border border-slate-200 shadow-sm">
          {parties.map((party) => {
            const widthPct = (party.seats / seatsInChart) * 100;
            const isHovered = hovered === party.official_name;
            return (
              <div
                key={party.official_name}
                className="relative flex items-center justify-center transition-all duration-150 cursor-pointer"
                style={{
                  width: `${widthPct}%`,
                  backgroundColor: party.color_hex,
                  opacity: hovered && !isHovered ? 0.55 : 1,
                  flexShrink: 0,
                }}
                onMouseEnter={() => setHovered(party.official_name)}
                onMouseLeave={() => setHovered(null)}
                title={`${party.name_he || party.official_name}: ${party.seats} מנדטים`}
              >
                {/* Show label only if wide enough */}
                {widthPct >= 7 && (
                  <span className="text-white text-xs font-bold select-none leading-none px-0.5 truncate">
                    {party.seats}
                  </span>
                )}
              </div>
            );
          })}
        </div>

        {/* Majority line at 50.83% */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-slate-800 opacity-40 pointer-events-none"
          style={{ left: "50%" }}
          title="61 seats majority line"
        />
        <div
          className="absolute -top-4 text-xs text-slate-500 font-medium"
          style={{ left: "50%", transform: "translateX(-50%)" }}
        >
          61 (majority)
        </div>
      </div>

      {/* Party legend grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 pt-1">
        {parties.map((party) => (
          <div
            key={party.official_name}
            className={`flex items-center gap-2 rounded-lg px-2 py-1.5 transition-colors cursor-default ${
              hovered === party.official_name ? "bg-slate-100" : ""
            }`}
            onMouseEnter={() => setHovered(party.official_name)}
            onMouseLeave={() => setHovered(null)}
          >
            <span
              className="w-3 h-3 rounded-sm shrink-0 border border-black/10"
              style={{ backgroundColor: party.color_hex }}
            />
            <span className="text-xs font-medium text-slate-700 truncate" dir="rtl">
              {party.name_he || party.official_name}
            </span>
            <span className="ms-auto text-xs font-bold text-slate-600 shrink-0">
              {party.seats}
            </span>
          </div>
        ))}
      </div>

      {/* Bloc totals */}
      <BlocSeats parties={parties} />

      {/* Explanation footnote */}
      <p className="text-xs text-slate-400 pt-2 border-t border-slate-100">
        Each row above represents a party that passed the 3.25% electoral threshold in the November 2022 elections.
        Seat counts are actual official results.
      </p>
    </div>
  );
}


