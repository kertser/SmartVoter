"use client";

/** MatchScoreRing — SVG circular progress showing match percentage. */

interface Props {
  score: number; // 0..1
  size?: number;
  strokeWidth?: number;
}

export function MatchScoreRing({ score, size = 80, strokeWidth = 7 }: Props) {
  const R = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * R;
  const pct = Math.max(0, Math.min(1, score));
  const dash = pct * circumference;
  const displayPct = Math.round(pct * 100);

  // Neutral color scale: slate → brand
  const color =
    pct >= 0.7 ? "#2563eb" : pct >= 0.5 ? "#64748b" : "#94a3b8";

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-label={`${displayPct}% match`}>
      {/* Background ring */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={R}
        fill="none"
        stroke="#e2e8f0"
        strokeWidth={strokeWidth}
      />
      {/* Progress arc */}
      <circle
        cx={size / 2}
        cy={size / 2}
        r={R}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={`${dash} ${circumference - dash}`}
        strokeDashoffset={circumference / 4}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: "stroke-dasharray 0.5s ease" }}
      />
      {/* Center text */}
      <text
        x={size / 2}
        y={size / 2 + 1}
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize={size * 0.22}
        fontWeight="700"
        fill="#1e293b"
      >
        {displayPct}%
      </text>
    </svg>
  );
}

