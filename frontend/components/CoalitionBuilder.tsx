"use client";

/**
 * CoalitionBuilder — interactive coalition assembly tool.
 *
 * Three zones: Available | Coalition | Opposition
 * Supports:
 * - Drag-and-drop (HTML5 native DnD)
 * - Custom parties added manually with arbitrary name + seat count
 *   → all other parties rescaled so total stays 120
 * - Uses forecast (simulation) seat counts, not 2022 election results
 *
 * Per AGENTS.MD 14B.10 — never presents as voting advice.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { KnessetParty, CoalitionEvaluation } from "@/lib/api";
import { evaluateCoalition } from "@/lib/api";

type Zone = "available" | "coalition" | "opposition";

// A colour palette for custom-added parties
const CUSTOM_COLORS = [
  "#6366f1", "#0ea5e9", "#14b8a6", "#f59e0b", "#8b5cf6",
  "#ec4899", "#10b981", "#f97316", "#06b6d4", "#84cc16",
];

interface CustomParty {
  key: string;          // unique identifier
  name: string;
  raw_seats: number;    // user-stated seat count
  color: string;
}

interface PartyChip extends KnessetParty {
  zone: Zone;
  /** Seats adjusted for custom-party rescaling */
  effective_seats: number;
  isCustom?: boolean;
}

interface Props {
  parties: KnessetParty[];
  /** If true, show "forecast" badge on seat counts */
  isForecast?: boolean;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function computeEffectiveSeats(
  parties: KnessetParty[],
  customs: CustomParty[],
): PartyChip[] {
  const customTotal = customs.reduce((s, c) => s + c.raw_seats, 0);
  const remaining   = Math.max(0, 120 - customTotal);
  const partyTotal  = parties.reduce((s, p) => s + (p.seats || 0), 0) || 1;
  const scale       = remaining / partyTotal;

  const chips: PartyChip[] = parties.map((p) => ({
    ...p,
    effective_seats: Math.round((p.seats || 0) * scale),
    zone: "available" as Zone,
  }));

  for (const c of customs) {
    chips.push({
      official_name: c.key,
      name_en: c.name,
      name_he: c.name,
      seats: c.raw_seats,
      effective_seats: c.raw_seats,
      color_hex: c.color,
      left_right_score: 0,
      political_bloc: "custom",
      zone: "available" as Zone,
      isCustom: true,
    });
  }
  return chips;
}

// ── Sub-components ─────────────────────────────────────────────────────────────

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

// ── Add Custom Party form ─────────────────────────────────────────────────────

function AddCustomPartyForm({
  onAdd,
  colorIndex,
}: {
  onAdd: (name: string, seats: number, color: string) => void;
  colorIndex: number;
}) {
  const [name, setName]   = useState("");
  const [seats, setSeats] = useState(8);
  const color = CUSTOM_COLORS[colorIndex % CUSTOM_COLORS.length];

  const handleAdd = () => {
    const trimmed = name.trim();
    if (!trimmed || seats < 1 || seats > 60) return;
    onAdd(trimmed, seats, color);
    setName("");
    setSeats(8);
  };

  return (
    <div className="rounded-xl border border-dashed border-indigo-200 bg-indigo-50/40 p-4 space-y-3">
      <div className="flex items-center gap-2">
        <span
          className="w-4 h-4 rounded-full border border-black/10 shrink-0"
          style={{ backgroundColor: color }}
        />
        <h3 className="text-xs font-semibold text-slate-700">הוסף מפלגה מותאמת</h3>
        <span className="text-xs text-slate-400">— Add custom party</span>
      </div>
      <p className="text-[11px] text-slate-500 leading-relaxed">
        הוסף מפלגה עם מספר מנדטים שרירותי. יתר המפלגות יוקטנו יחסית כך שהסכום יישאר 120.
      </p>
      <div className="flex flex-wrap gap-2">
        <input
          type="text"
          placeholder="שם המפלגה"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAdd()}
          className="flex-1 min-w-[140px] rounded-lg border border-slate-300 px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300"
          dir="rtl"
        />
        <div className="flex items-center gap-1.5">
          <input
            type="number"
            min={1}
            max={60}
            value={seats}
            onChange={(e) => setSeats(Math.min(60, Math.max(1, Number(e.target.value))))}
            className="w-16 rounded-lg border border-slate-300 px-2 py-1.5 text-xs text-center focus:outline-none focus:ring-2 focus:ring-indigo-300"
          />
          <span className="text-xs text-slate-500">מנדטים</span>
        </div>
        <button
          onClick={handleAdd}
          disabled={!name.trim() || seats < 1}
          className="shrink-0 rounded-lg bg-indigo-600 text-white px-4 py-1.5 text-xs font-semibold hover:bg-indigo-700 disabled:opacity-40 transition-colors"
        >
          + הוסף
        </button>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export function CoalitionBuilder({ parties, isForecast = false }: Props) {
  const [customs,     setCustoms]     = useState<CustomParty[]>([]);
  const [zones,       setZones]       = useState<Record<string, Zone>>({});
  const [draggedKey,  setDraggedKey]  = useState<string | null>(null);
  const [evaluation,  setEvaluation]  = useState<CoalitionEvaluation | null>(null);
  const [evaluating,  setEvaluating]  = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Rebuild chips when parties or customs change
  const chips: PartyChip[] = computeEffectiveSeats(parties, customs).map((c) => ({
    ...c,
    zone: zones[c.official_name] ?? "available",
  }));

  // Reset unknown zones
  useEffect(() => {
    setZones((z) => {
      const valid = new Set(chips.map((c) => c.official_name));
      const next = { ...z };
      let changed = false;
      for (const k of Object.keys(next)) {
        if (!valid.has(k)) { delete next[k]; changed = true; }
      }
      return changed ? next : z;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parties, customs]);

  const coalitionChips = chips.filter((c) => c.zone === "coalition");
  const coalitionSeats = coalitionChips.reduce((s, c) => s + c.effective_seats, 0);
  const hasMajority    = evaluation?.has_majority ?? coalitionSeats >= 61;

  const triggerEval = useCallback((nextZones: Record<string, Zone>, currentChips: PartyChip[]) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      const names = currentChips
        .filter((c) => (nextZones[c.official_name] ?? "available") === "coalition")
        .map((c) => c.official_name);
      if (names.length === 0) { setEvaluation(null); return; }
      setEvaluating(true);
      try {
        const res = await evaluateCoalition(names, false);
        setEvaluation(res);
      } catch {
        // silent
      } finally {
        setEvaluating(false);
      }
    }, 350);
  }, []);

  const moveChip = (key: string, zone: Zone) => {
    setZones((z) => {
      const next = { ...z, [key]: zone };
      triggerEval(next, chips);
      return next;
    });
  };

  const addCustom = (name: string, seats: number, color: string) => {
    const key = `custom_${Date.now()}`;
    setCustoms((c) => [...c, { key, name, raw_seats: seats, color }]);
  };

  const removeCustom = (key: string) => {
    setCustoms((c) => c.filter((x) => x.key !== key));
    setZones((z) => { const n = { ...z }; delete n[key]; return n; });
  };

  // DnD
  const handleDragStart = (e: React.DragEvent, key: string) => {
    setDraggedKey(key);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", key);
  };
  const handleDragOver  = (e: React.DragEvent) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; };
  const handleDrop      = (e: React.DragEvent, zone: Zone) => {
    e.preventDefault();
    const key = e.dataTransfer.getData("text/plain") || draggedKey;
    if (key) moveChip(key, zone);
    setDraggedKey(null);
  };
  const handleDragEnd   = () => setDraggedKey(null);

  const renderZone = (zone: Zone, label: string, bgClass: string, desc: string) => {
    const zoneChips = chips.filter((c) => c.zone === zone);
    return (
      <div className="flex flex-col min-h-0">
        <div className="mb-2">
          <h3 className="text-sm font-semibold text-slate-700">{label}</h3>
          <p className="text-xs text-slate-400">{desc}</p>
        </div>
        <div
          className={`flex-1 min-h-32 rounded-xl border-2 border-dashed p-3 flex flex-wrap gap-2 content-start transition-colors ${bgClass}`}
          onDragOver={handleDragOver}
          onDrop={(e) => handleDrop(e, zone)}
        >
          {zoneChips.length === 0 && (
            <p className="text-xs text-slate-300 italic w-full text-center pt-4">גרור לכאן</p>
          )}
          {zoneChips.map((chip) => (
            <div
              key={chip.official_name}
              draggable
              onDragStart={(e) => handleDragStart(e, chip.official_name)}
              onDragEnd={handleDragEnd}
              className={`group relative flex items-center gap-1.5 rounded-full px-3 py-1.5 cursor-grab active:cursor-grabbing select-none shadow-sm border border-black/10 transition-opacity text-white text-xs font-semibold ${
                draggedKey === chip.official_name ? "opacity-40" : "opacity-100"
              }`}
              style={{ backgroundColor: chip.color_hex || "#94a3b8" }}
              title={chip.name_he || chip.official_name}
            >
              <span className="max-w-[100px] truncate" dir="rtl">
                {chip.name_he || chip.name_en}
              </span>
              <span className="rounded-full bg-black/20 px-1.5 py-0.5 text-[10px] font-bold">
                {chip.effective_seats}
              </span>
              {isForecast && (
                <span className="text-[8px] opacity-70">~</span>
              )}
              {chip.isCustom && (
                <button
                  onClick={(e) => { e.stopPropagation(); removeCustom(chip.official_name); }}
                  className="ml-0.5 w-3.5 h-3.5 rounded-full bg-black/30 hover:bg-black/50 flex items-center justify-center text-white text-[9px] leading-none transition-colors"
                  title="הסר"
                >
                  ×
                </button>
              )}
            </div>
          ))}
        </div>
        {zone === "coalition" && (
          <div className="mt-2 flex items-center justify-between">
            <span className="text-xs text-slate-500">
              {coalitionChips.length} מפלגות · {coalitionSeats} מנדטים
            </span>
            <span
              className={`text-xs font-bold rounded-full px-2 py-0.5 ${
                hasMajority ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
              }`}
            >
              {hasMajority ? "✓ רוב" : `חסרים ${61 - coalitionSeats}`}
            </span>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Data source notice */}
      <div className="rounded-lg bg-blue-50 border border-blue-200 px-4 py-3 text-xs text-blue-800 space-y-1">
        <p>
          <strong>כלי תרחישים בלבד</strong> — גרור מפלגות לאזורים לניתוח קואליציה מיידי.
          {isForecast
            ? " מספרי המנדטים מבוססים על תחזית הסימולציה (ממוצע מדגמי)."
            : " מספרי המנדטים מבוססים על תחזית בחירות."}
          {" "}תוצאות הניתוח הן תרחישים תנאיים — לא תחזיות ולא המלצות.
        </p>
      </div>

      {/* Custom party form */}
      <AddCustomPartyForm onAdd={addCustom} colorIndex={customs.length} />

      {/* Custom-party rescaling notice */}
      {customs.length > 0 && (
        <div className="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800">
          <strong>⚖ שינוי יחסי:</strong> המפלגות המקוריות הוקטנו יחסית כדי שסכום כל המנדטים יישאר 120.
          (<strong>{customs.reduce((s, c) => s + c.raw_seats, 0)}</strong> מנדטים לפי מפלגות מותאמות,{" "}
          <strong>{120 - customs.reduce((s, c) => s + c.raw_seats, 0)}</strong> לשאר.)
        </div>
      )}

      {/* Three-zone layout */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {renderZone("coalition",  "קואליציה",   "border-emerald-300 bg-emerald-50/30", "מפלגות בממשלה")}
        {renderZone("opposition", "אופוזיציה",   "border-red-300 bg-red-50/30",         "מפלגות באופוזיציה")}
        {renderZone("available",  "לא מוגדר",   "border-slate-300 bg-slate-50/40",     "גרור לקואליציה או לאופוזיציה")}
      </div>

      {/* Evaluation panel */}
      {coalitionChips.length > 0 && (
        <div className={`rounded-xl border border-slate-200 bg-white shadow-sm p-5 space-y-4 transition-opacity ${evaluating ? "opacity-60" : "opacity-100"}`}>
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-800">ניתוח קואליציה</h3>
            {evaluating && <span className="text-xs text-slate-400 animate-pulse">מחשב…</span>}
          </div>

          {/* Seat bar */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs text-slate-600">
              <span className="font-medium">מנדטים ({coalitionSeats}/120)</span>
              <span className={`font-bold ${hasMajority ? "text-emerald-700" : "text-red-700"}`}>
                {hasMajority ? "✓ רוב (≥61)" : `אין רוב — חסרים ${61 - coalitionSeats}`}
              </span>
            </div>
            <div className="h-3 bg-slate-100 rounded-full overflow-hidden relative">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${(coalitionSeats / 120) * 100}%`,
                  background: hasMajority
                    ? "linear-gradient(90deg,#10b981,#059669)"
                    : "linear-gradient(90deg,#f87171,#ef4444)",
                }}
              />
              <div className="absolute top-0 bottom-0 w-0.5 bg-slate-600 opacity-40" style={{ left: `${(61 / 120) * 100}%` }} />
            </div>
            {/* chips breakdown */}
            <div className="flex flex-wrap gap-1.5 pt-1">
              {coalitionChips.map((c) => (
                <span
                  key={c.official_name}
                  className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium text-white"
                  style={{ backgroundColor: c.color_hex || "#94a3b8" }}
                  dir="rtl"
                >
                  {c.name_he || c.name_en} ({c.effective_seats})
                </span>
              ))}
            </div>
          </div>

          {evaluation && (
            <div className="space-y-3">
              <ScoreBar value={evaluation.feasibility_score}          label="ישימות (הכרזות אי-תאימות)"         color="#6366f1" />
              <ScoreBar value={evaluation.stability_score}            label="יציבות (שוליים ומרחק אידאולוגי)"   color="#0ea5e9" />
              <ScoreBar value={evaluation.ideological_coherence_score}label="קוהרנטיות אידאולוגית"              color="#f97316" />
            </div>
          )}

          {evaluation?.constraint_violations && evaluation.constraint_violations.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-700">הכרזות אי-תאימות</h4>
              {evaluation.constraint_violations.map((v, i) => (
                <div key={i} className={`rounded-lg px-3 py-2 text-xs ${
                  v.strength === "hard"
                    ? "bg-red-50 border border-red-200 text-red-800"
                    : "bg-amber-50 border border-amber-200 text-amber-800"
                }`}>
                  <strong>{v.strength === "hard" ? "⛔ חזק" : "⚠ רך"}:</strong> {v.description}
                </div>
              ))}
            </div>
          )}

          {evaluation?.constraint_violations?.length === 0 && (
            <p className="text-xs text-emerald-700 font-medium">
              ✓ אין הכרזות אי-תאימות בין חברי הקואליציה שנבחרו.
            </p>
          )}
        </div>
      )}

      {/* Disclaimer */}
      <p className="text-xs text-slate-400 border-t border-slate-100 pt-3">
        ⚠ ניתוח קואליציה הוא כלי תרחישים תנאיי — לא תחזית פוליטית.
        ציוני הישימות מבוססים על עמדות מוצהרות והתנהגות היסטורית.
        {isForecast && " מנדטים מבוססים על חציון הסימולציה המונטה-קרלו — ערכים הסתברותיים בלבד."}
      </p>
    </div>
  );
}
