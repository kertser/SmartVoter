"use client";

/**
 * KnessetSemicircleChart — SVG hemicycle showing 120 seats grouped by party.
 * Per AGENTS.MD Section 14B.10: Knesset semicircle chart.
 *
 * Seats are arranged in 6 concentric arcs (innermost = 10, outermost = 30).
 * Party seats are colored and sorted by party index for visual grouping.
 */

const PARTY_COLORS = [
  "#2563eb", // blue-600
  "#16a34a", // green-600
  "#9333ea", // purple-600
  "#ea580c", // orange-600
  "#0891b2", // cyan-600
  "#dc2626", // red-600
  "#65a30d", // lime-600
  "#d97706", // amber-600
];

const ROW_LAYOUT: Array<{ radius: number; seats: number }> = [
  { radius: 42, seats: 10 },
  { radius: 57, seats: 14 },
  { radius: 72, seats: 18 },
  { radius: 87, seats: 22 },
  { radius: 102, seats: 26 },
  { radius: 118, seats: 30 },
];
// Total = 120

const CX = 140;
const CY = 138;
const SEAT_RADIUS = 5;
const ANGLE_MIN = Math.PI * 0.05; // 9° from right (leave buffer)
const ANGLE_MAX = Math.PI * 0.95; // 171° from right (leave buffer)

interface PartyEntry {
  name: string;
  seats: number;
  color?: string;  // optional override from DB
}

interface Props {
  parties: PartyEntry[];
  /** Optional: highlight a party name */
  highlight?: string;
}

function layoutSeats(parties: PartyEntry[]): string[] {
  // Build a flat list of party labels for 120 seats (sorted by party index, large→small)
  const labels: string[] = [];
  const sorted = [...parties].sort((a, b) => b.seats - a.seats);
  for (const p of sorted) {
    for (let i = 0; i < Math.round(p.seats); i++) {
      labels.push(p.name);
    }
  }
  // Pad or trim to exactly 120
  while (labels.length < 120) labels.push("__empty__");
  return labels.slice(0, 120);
}

export function KnessetSemicircleChart({ parties, highlight }: Props) {
  const seatLabels = layoutSeats(parties);
  const colorMap: Record<string, string> = {};
  parties.forEach((p, i) => {
    // Use DB color if available, otherwise fallback to palette
    colorMap[p.name] = p.color || PARTY_COLORS[i % PARTY_COLORS.length];
  });

  const seats: Array<{ x: number; y: number; label: string; color: string }> = [];
  let seatIdx = 0;

  for (const row of ROW_LAYOUT) {
    const { radius, seats: count } = row;
    for (let i = 0; i < count; i++) {
      const angle = ANGLE_MAX - (i / (count - 1)) * (ANGLE_MAX - ANGLE_MIN);
      const x = CX + radius * Math.cos(angle);
      const y = CY - radius * Math.sin(angle);
      const label = seatLabels[seatIdx] ?? "__empty__";
      const color = label === "__empty__" ? "#e2e8f0" : (colorMap[label] ?? "#94a3b8");
      seats.push({ x, y, label, color });
      seatIdx++;
    }
  }

  // Build legend
  const legendParties = [...parties].sort((a, b) => b.seats - a.seats);

  return (
    <div className="space-y-3">
      <svg
        viewBox="0 0 280 145"
        width="100%"
        aria-label="Knesset seat distribution semicircle"
        className="max-w-md mx-auto block"
      >
        {/* Base arc line */}
        <path
          d={`M ${CX - 125} ${CY} A 125 125 0 0 1 ${CX + 125} ${CY}`}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth="1"
        />
        {/* Seats */}
        {seats.map((s, i) => (
          <circle
            key={i}
            cx={s.x}
            cy={s.y}
            r={SEAT_RADIUS}
            fill={s.color}
            opacity={highlight && s.label !== "__empty__" && s.label !== highlight ? 0.3 : 1}
            aria-label={s.label !== "__empty__" ? `${s.label} seat` : undefined}
          />
        ))}
      </svg>

      {/* Legend */}
      <div className="flex flex-wrap justify-center gap-x-4 gap-y-1">
        {legendParties.map((p, i) => (
          <div key={p.name} className="flex items-center gap-1.5 text-xs text-slate-600">
            <span
              className="inline-block w-3 h-3 rounded-full"
              style={{ backgroundColor: PARTY_COLORS[i % PARTY_COLORS.length] }}
            />
            <span className="font-medium">{p.name}</span>
            <span className="text-slate-400">{Math.round(p.seats)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

