"use client";

/**
 * SeatDistributionChart — interval/range bar chart for party seat distributions.
 * Shows p25–p75 as a solid bar + p10–p90 as a thin whisker + a median marker.
 * Per AGENTS.MD Section 14B.10.
 *
 * Uses a custom SVG-based approach for clear, accessible rendering.
 */

interface PartyInterval {
  name: string;
  seats_p10: number;
  seats_p25: number;
  seats_median: number;
  seats_p75: number;
  seats_p90: number;
  color: string;
}

interface Props {
  parties: PartyInterval[];
  maxSeats?: number;
  /** Height per row in px */
  rowHeight?: number;
}

const LABEL_WIDTH = 110;
const BAR_AREA_WIDTH = 260;
const PADDING_RIGHT = 30;

export function SeatDistributionChart({
  parties,
  maxSeats = 50,
  rowHeight = 36,
}: Props) {
  const scale = (seats: number) => (seats / maxSeats) * BAR_AREA_WIDTH;
  const totalWidth = LABEL_WIDTH + BAR_AREA_WIDTH + PADDING_RIGHT;
  const totalHeight = parties.length * rowHeight + 30; // 30px for x-axis

  // Grid lines every 10 seats
  const gridLines: number[] = [];
  for (let s = 0; s <= maxSeats; s += 10) {
    gridLines.push(s);
  }

  return (
    <svg
      viewBox={`0 0 ${totalWidth} ${totalHeight}`}
      width="100%"
      aria-label="Seat distribution intervals by party"
    >
      {/* X-axis grid lines */}
      {gridLines.map((s) => {
        const x = LABEL_WIDTH + scale(s);
        return (
          <g key={s}>
            <line
              x1={x}
              y1={0}
              x2={x}
              y2={totalHeight - 14}
              stroke="#f1f5f9"
              strokeWidth="1"
            />
            <text
              x={x}
              y={totalHeight - 2}
              textAnchor="middle"
              fontSize="9"
              fill="#94a3b8"
            >
              {s}
            </text>
          </g>
        );
      })}

      {/* Rows */}
      {parties.map((p, i) => {
        const y = i * rowHeight;
        const barY = y + rowHeight * 0.3;
        const barH = rowHeight * 0.4;
        const whiskerY = y + rowHeight * 0.5;

        const x_p10 = LABEL_WIDTH + scale(p.seats_p10);
        const x_p25 = LABEL_WIDTH + scale(p.seats_p25);
        const x_p75 = LABEL_WIDTH + scale(p.seats_p75);
        const x_p90 = LABEL_WIDTH + scale(p.seats_p90);
        const x_med = LABEL_WIDTH + scale(p.seats_median);

        return (
          <g key={p.name}>
            {/* Party label */}
            <text
              x={LABEL_WIDTH - 8}
              y={y + rowHeight * 0.55}
              textAnchor="end"
              dominantBaseline="middle"
              fontSize="11"
              fontWeight="600"
              fill="#334155"
            >
              {p.name}
            </text>

            {/* 80% interval whisker (p10–p90) */}
            <line
              x1={x_p10}
              y1={whiskerY}
              x2={x_p90}
              y2={whiskerY}
              stroke={p.color}
              strokeWidth="1.5"
              opacity="0.4"
            />
            {/* Whisker end caps */}
            <line x1={x_p10} y1={barY + 1} x2={x_p10} y2={barY + barH - 1} stroke={p.color} strokeWidth="1.5" opacity="0.4" />
            <line x1={x_p90} y1={barY + 1} x2={x_p90} y2={barY + barH - 1} stroke={p.color} strokeWidth="1.5" opacity="0.4" />

            {/* 50% interval bar (p25–p75) */}
            <rect
              x={x_p25}
              y={barY}
              width={x_p75 - x_p25}
              height={barH}
              fill={p.color}
              opacity="0.75"
              rx="2"
            />

            {/* Median marker */}
            <line
              x1={x_med}
              y1={barY - 1}
              x2={x_med}
              y2={barY + barH + 1}
              stroke={p.color}
              strokeWidth="2.5"
            />

            {/* Median label */}
            <text
              x={x_med}
              y={barY - 4}
              textAnchor="middle"
              fontSize="9"
              fontWeight="700"
              fill={p.color}
            >
              {p.seats_median}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

