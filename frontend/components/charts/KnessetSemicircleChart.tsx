"use client";

/**
 * KnessetSemicircleChart — elegant interactive SVG hemicycle.
 *
 * Visual rules:
 * - Left-wing parties appear on the LEFT side of the semicircle.
 * - Right-wing parties appear on the RIGHT side.
 * - Hovering a party highlights its seats; all others dim.
 * - Clicking or hovering a legend entry triggers the same effect.
 * - Info panel appears in the centre of the arc on hover.
 */

import { useState, useCallback } from "react";

// ── Layout constants ──────────────────────────────────────────────────────────

const ROW_LAYOUT: { radius: number; count: number }[] = [
  { radius: 44,  count: 10 },
  { radius: 60,  count: 14 },
  { radius: 76,  count: 18 },
  { radius: 92,  count: 22 },
  { radius: 108, count: 26 },
  { radius: 124, count: 30 },
];

const CX = 160;
const CY = 155;
const R_SEAT = 5.0;
const R_HOVER = 6.8;
const ANGLE_MIN = Math.PI * 0.02;
const ANGLE_MAX = Math.PI * 0.98;
const TOTAL_SEATS = 120;

// ── Types ─────────────────────────────────────────────────────────────────────

export interface PartyEntry {
  name: string;
  seats: number;
  color?: string;
  lr?: number | null;
}

interface SeatDot {
  x: number;
  y: number;
  party: string;
  color: string;
  isEmpty: boolean;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function buildSeatList(parties: PartyEntry[]): { party: string; color: string }[] {
  const sorted = [...parties].sort((a, b) => (a.lr ?? 0) - (b.lr ?? 0));
  const list: { party: string; color: string }[] = [];
  for (const p of sorted) {
    const seats = Math.max(0, Math.round(p.seats));
    for (let i = 0; i < seats; i++) {
      list.push({ party: p.name, color: p.color || "#94a3b8" });
    }
  }
  while (list.length < TOTAL_SEATS) list.push({ party: "__empty__", color: "#e8edf2" });
  return list.slice(0, TOTAL_SEATS);
}

function buildDots(seatList: { party: string; color: string }[]): SeatDot[] {
  const dots: SeatDot[] = [];
  let idx = 0;
  for (const row of ROW_LAYOUT) {
    for (let i = 0; i < row.count; i++) {
      const t = row.count > 1 ? i / (row.count - 1) : 0.5;
      // t=0 → leftmost (ANGLE_MAX ≈ π), t=1 → rightmost (ANGLE_MIN ≈ 0)
      const angle = ANGLE_MAX - t * (ANGLE_MAX - ANGLE_MIN);
      const x = CX + row.radius * Math.cos(angle);
      const y = CY - row.radius * Math.sin(angle);
      const { party, color } = seatList[idx] ?? { party: "__empty__", color: "#e8edf2" };
      dots.push({ x, y, party, color, isEmpty: party === "__empty__" });
      idx++;
    }
  }
  return dots;
}

// ── Component ─────────────────────────────────────────────────────────────────

interface Props {
  parties: PartyEntry[];
}

export function KnessetSemicircleChart({ parties }: Props) {
  const [hovered, setHovered] = useState<string | null>(null);

  const onEnter  = useCallback((p: string) => setHovered(p), []);
  const onLeave  = useCallback(() => setHovered(null), []);
  const onToggle = useCallback((p: string) => setHovered((h) => (h === p ? null : p)), []);

  const seatList = buildSeatList(parties);
  const dots     = buildDots(seatList);

  const activeParty = hovered ? parties.find((p) => p.name === hovered) : null;
  const legendParties = [...parties]
    .filter((p) => p.seats > 0)
    .sort((a, b) => (a.lr ?? 0) - (b.lr ?? 0));

  return (
    <div className="select-none space-y-3">
      <svg
        viewBox="0 0 320 170"
        width="100%"
        aria-label="Knesset seat distribution hemicycle"
        className="block overflow-visible"
        style={{ filter: "drop-shadow(0 4px 14px rgba(0,0,0,0.07))" }}
      >
        {/* Background arc */}
        <path
          d={`M ${CX - 138} ${CY} A 138 138 0 0 1 ${CX + 138} ${CY}`}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth="1.5"
        />

        {/* Axis labels */}
        <text x="6"   y={CY + 14} fontSize="8.5" fill="#94a3b8" fontWeight="500" textAnchor="start">◄ שמאל</text>
        <text x="314" y={CY + 14} fontSize="8.5" fill="#94a3b8" fontWeight="500" textAnchor="end">ימין ►</text>
        <text x={CX}  y={CY + 14} fontSize="8"   fill="#cbd5e1" textAnchor="middle">מרכז</text>

        {/* Seat dots */}
        {dots.map((d, i) => {
          const isActive = !d.isEmpty && d.party === hovered;
          const isDimmed = !d.isEmpty && !!hovered && d.party !== hovered;
          return (
            <circle
              key={i}
              cx={d.x}
              cy={d.y}
              r={isActive ? R_HOVER : R_SEAT}
              fill={d.isEmpty ? "#e8edf2" : d.color}
              opacity={d.isEmpty ? 0.35 : isDimmed ? 0.10 : 1}
              style={{
                transition: "r 0.10s ease, opacity 0.14s ease",
                cursor: d.isEmpty ? "default" : "pointer",
              }}
              onMouseEnter={() => !d.isEmpty && onEnter(d.party)}
              onMouseLeave={onLeave}
              onClick={() => !d.isEmpty && onToggle(d.party)}
            >
              {!d.isEmpty && <title>{d.party}</title>}
            </circle>
          );
        })}

        {/* Central hover info — shows in the empty interior of the arc */}
        {activeParty ? (
          <g>
            <circle cx={CX} cy={CY - 42} r="22" fill={activeParty.color || "#94a3b8"} opacity="0.10" />
            <circle cx={CX} cy={CY - 42} r="13" fill={activeParty.color || "#94a3b8"} opacity="0.22" />
            <text
              x={CX} y={CY - 37}
              textAnchor="middle" dominantBaseline="middle"
              fontSize="15" fontWeight="800"
              fill={activeParty.color || "#1e293b"}
            >
              {Math.round(activeParty.seats)}
            </text>
            <text
              x={CX} y={CY - 19}
              textAnchor="middle" dominantBaseline="middle"
              fontSize="7.5" fontWeight="600"
              fill="#334155"
            >
              {activeParty.name}
            </text>
          </g>
        ) : (
          /* Default: show total and majority line hints */
          <g>
            <text x={CX} y={CY - 38} textAnchor="middle" fontSize="8" fill="#cbd5e1">120 מנדטים</text>
            <text x={CX} y={CY - 26} textAnchor="middle" fontSize="7" fill="#e2e8f0">רוב = 61</text>
          </g>
        )}
      </svg>

      {/* Legend — left to right */}
      <div className="flex flex-wrap justify-center gap-1.5 px-2">
        {legendParties.map((p) => {
          const isActive = hovered === p.name;
          return (
            <button
              key={p.name}
              onMouseEnter={() => onEnter(p.name)}
              onMouseLeave={onLeave}
              onClick={() => onToggle(p.name)}
              className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium border transition-all duration-150 ${
                isActive
                  ? "border-slate-300 bg-white shadow scale-105"
                  : "border-transparent bg-slate-50 hover:bg-white hover:border-slate-200"
              }`}
              style={{ color: isActive ? (p.color || "#1e293b") : "#64748b" }}
            >
              <span
                className="inline-block w-2.5 h-2.5 rounded-full shrink-0 border border-black/10"
                style={{ backgroundColor: p.color || "#94a3b8" }}
              />
              <span dir="rtl">{p.name}</span>
              <span
                className="text-[10px] font-bold"
                style={{ color: isActive ? (p.color || "#64748b") : "#94a3b8" }}
              >
                {Math.round(p.seats)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
