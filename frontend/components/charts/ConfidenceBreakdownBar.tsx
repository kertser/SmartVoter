"use client";

import type { PartyResult } from "@/lib/api";

interface Props {
  party: PartyResult;
  lang?: string;
}

interface ComponentDef {
  key: string;
  label: string;
  description: string;
  color: string;
  weight: number;
  /** if true, value is 1-raw (e.g. volatility_penalty → party stability) */
  invert?: boolean;
}

function getComponents(lang?: string): ComponentDef[] {
  const isRu = lang === "ru";
  const isHe = lang === "he";
  return [
    {
      key: "evidence_quality",
      weight: 0.4,
      label: isRu ? "Качество доказательств" : isHe ? "איכות עדות" : "Evidence quality",
      description: isRu
        ? "Надёжность источников (голосования > законопроекты > программа). Вес: 40%"
        : isHe
        ? "אמינות המקורות (הצבעות > חוקים > מצע). משקל: 40%"
        : "Source reliability: votes > bills > platform. Weight: 40%",
      color: "#2563eb",
    },
    {
      key: "coverage",
      weight: 0.25,
      label: isRu ? "Охват вопросов" : isHe ? "כיסוי שאלות" : "Question coverage",
      description: isRu
        ? "Доля ваших ответов, по которым у партии есть данные. Вес: 25%"
        : isHe
        ? "חלק מתשובותיך שיש עליהן נתונים אצל המפלגה. משקל: 25%"
        : "Fraction of your answers the party has positions for. Weight: 25%",
      color: "#0d9488",
    },
    {
      key: "answer_stability",
      weight: 0.15,
      label: isRu ? "Стабильность рейтинга" : isHe ? "יציבות הדירוג" : "Ranking stability",
      description: isRu
        ? "Насколько рейтинг меняется при удалении одного ответа. Вес: 15%"
        : isHe
        ? "עד כמה הדירוג משתנה עם הסרת תשובה אחת. משקל: 15%"
        : "How much ranking changes when one answer is removed. Weight: 15%",
      color: "#7c3aed",
    },
    {
      key: "volatility_penalty",
      weight: 0.1,
      invert: true,
      label: isRu ? "Стабильность партии" : isHe ? "יציבות מפלגה" : "Party stability",
      description: isRu
        ? "1 − волатильность: выше для устойчивых партий. Вес: 10%"
        : isHe
        ? "1 − תנודתיות: גבוה יותר עבור מפלגות יציבות. משקל: 10%"
        : "1 − volatility: higher for stable parties. Weight: 10%",
      color: "#d97706",
    },
    {
      key: "high_salience_coverage",
      weight: 0.1,
      label: isRu ? "Важные темы" : isHe ? "נושאים חשובים" : "Priority topics",
      description: isRu
        ? "Покрытие тем, которые вы отметили как очень важные. Вес: 10%"
        : isHe
        ? "כיסוי נושאים שסימנת כחשובים מאוד. משקל: 10%"
        : "Coverage of topics you rated as very important. Weight: 10%",
      color: "#059669",
    },
  ];
}

export function ConfidenceBreakdownBar({ party, lang }: Props) {
  const components = getComponents(lang);
  const overallPct = Math.round(party.confidence * 100);
  const bd = party.confidence_breakdown ?? {};

  // Get raw value for each component
  const items = components.map((c) => {
    let raw: number;
    if (Object.keys(bd).length > 0) {
      // Use structured breakdown when available
      raw = (bd[c.key as keyof typeof bd] as number) ?? 0;
    } else {
      // Fallback to legacy party fields
      raw = c.key === "evidence_quality" ? (party.evidence_strength ?? 0)
          : c.key === "volatility_penalty" ? (party.volatility ?? 0)
          : ((party[c.key as keyof PartyResult] as number) ?? 0);
    }
    const displayValue = c.invert ? Math.max(0, 1 - raw) : raw;
    const weightedContrib = displayValue * c.weight;
    return {
      ...c,
      raw,
      pct: Math.round(displayValue * 100),
      contribution: Math.round(weightedContrib * 100),
    };
  });

  const overallLabel =
    lang === "ru" ? `Итоговый балл: ${overallPct}%`
    : lang === "he" ? `ציון סופי: ${overallPct}%`
    : `Overall: ${overallPct}%`;

  const noteLabel =
    lang === "ru" ? "Вклад каждого компонента в итоговый балл (взвешенная сумма)"
    : lang === "he" ? "תרומת כל רכיב לציון הסופי (סכום משוקלל)"
    : "Each component's weighted contribution to the final confidence score";

  const methodLabel =
    lang === "ru" ? "Формула: 40% × качество + 25% × охват + 15% × стабильность + 10% × партия + 10% × темы"
    : lang === "he" ? "נוסחה: 40% × איכות + 25% × כיסוי + 15% × יציבות + 10% × מפלגה + 10% × נושאים"
    : "Formula: 40%×quality + 25%×coverage + 15%×stability + 10%×party + 10%×priority";

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs text-slate-400 leading-tight flex-1">{noteLabel}</p>
        <span className="text-xs font-semibold text-slate-700 whitespace-nowrap">{overallLabel}</span>
      </div>

      <div className="space-y-2">
        {items.map((item) => (
          <div key={item.key} className="space-y-0.5">
            <div className="flex justify-between items-center text-xs">
              <span className="text-slate-600 font-medium truncate max-w-[60%]" title={item.description}>
                {item.label}
              </span>
              <span className="flex items-center gap-2 text-slate-500 tabular-nums">
                <span className="text-[10px] text-slate-400">×{Math.round(item.weight * 100)}%</span>
                <span className="font-medium text-slate-700">{item.pct}%</span>
              </span>
            </div>
            {/* Track: full bar = raw component value; darker fill = weighted contribution */}
            <div className="relative h-2 bg-slate-100 rounded-full overflow-hidden">
              {/* Full component value (lighter) */}
              <div
                className="absolute inset-y-0 left-0 rounded-full opacity-25"
                style={{ width: `${item.pct}%`, backgroundColor: item.color }}
              />
              {/* Weighted contribution (darker) */}
              <div
                className="absolute inset-y-0 left-0 rounded-full transition-all duration-500"
                style={{ width: `${Math.min(item.contribution * (100 / (item.weight * 100)), 100)}%`, backgroundColor: item.color }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Overall bar */}
      <div className="border-t border-slate-100 pt-2 space-y-1">
        <div className="flex justify-between text-xs">
          <span className="text-slate-500 font-medium">
            {lang === "ru" ? "Итоговый уровень доверия" : lang === "he" ? "ציון ביטחון כולל" : "Final confidence score"}
          </span>
          <span className="font-bold text-slate-800">{overallPct}%</span>
        </div>
        <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{
              width: `${overallPct}%`,
              background: `linear-gradient(90deg, #2563eb 0%, #0d9488 50%, #059669 100%)`,
            }}
          />
        </div>
        <p className="text-[9px] text-slate-300 leading-tight">{methodLabel}</p>
      </div>
    </div>
  );
}
