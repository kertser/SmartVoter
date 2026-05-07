"use client";

import type { PartyResult } from "@/lib/api";

interface Props {
  party: PartyResult;
  lang?: string;
}

interface Component {
  key: string;
  label: string;
  description: string;
  color: string;
}

function getComponents(lang?: string): Component[] {
  const isRu = lang === "ru";
  const isHe = lang === "he";
  return [
    {
      key: "evidence_strength",
      label: isRu ? "Сила доказательств" : isHe ? "חוזק עדות" : "Evidence strength",
      description: isRu
        ? "Надёжность источников: голосования > законопроекты > программа"
        : isHe
        ? "אמינות המקורות: הצבעות > חוקים > מצע"
        : "Source reliability: votes > bills > platform",
      color: "#2563eb",
    },
    {
      key: "coverage",
      label: isRu ? "Охват тем" : isHe ? "כיסוי נושאים" : "Topic coverage",
      description: isRu
        ? "Доля важных для вас тем, по которым есть данные"
        : isHe
        ? "חלק מהנושאים החשובים שיש להם עדות"
        : "Fraction of your important topics with evidence",
      color: "#0d9488",
    },
    {
      key: "answer_stability",
      label: isRu ? "Стабильность" : isHe ? "יציבות תשובות" : "Answer stability",
      description: isRu
        ? "Меняется ли рейтинг при удалении одного ответа"
        : isHe
        ? "האם הדירוג משתנה אם תשובה אחת מוסרת"
        : "Whether ranking changes when one answer is removed",
      color: "#7c3aed",
    },
    {
      key: "volatility_inv",
      label: isRu ? "Без волатильности" : isHe ? "ללא תנודתיות" : "Party stability",
      description: isRu
        ? "1 − волатильность: выше для стабильных партий"
        : isHe
        ? "1 − תנודתיות: גבוה יותר עבור מפלגות יציבות"
        : "1 − volatility: higher for stable parties",
      color: "#d97706",
    },
  ];
}

export function ConfidenceBreakdownBar({ party, lang }: Props) {
  const components = getComponents(lang);
  const overallPct = Math.round(party.confidence * 100);

  const items = components.map((c) => {
    const raw =
      c.key === "volatility_inv"
        ? 1 - (party.volatility ?? 0)
        : ((party[c.key as keyof PartyResult] as number) ?? 0);
    return { ...c, pct: Math.round(raw * 100) };
  });

  const overallLabel =
    lang === "ru" ? `Итого: ${overallPct}%`
    : lang === "he" ? `סה"כ: ${overallPct}%`
    : `Overall: ${overallPct}%`;

  const noteLabel =
    lang === "ru" ? "Каждый компонент вносит вклад в итоговый уровень доверия."
    : lang === "he" ? "כל רכיב תורם לציון הביטחון הכולל."
    : "Each component contributes to the overall confidence score.";

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">{noteLabel}</p>
        <span className="text-xs font-semibold text-slate-700">{overallLabel}</span>
      </div>

      <div className="space-y-2.5">
        {items.map((item) => (
          <div key={item.key} className="space-y-0.5">
            <div className="flex justify-between text-xs">
              <span className="text-slate-600 font-medium" title={item.description}>
                {item.label}
              </span>
              <span className="text-slate-500 tabular-nums">{item.pct}%</span>
            </div>
            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${item.pct}%`, backgroundColor: item.color }}
              />
            </div>
            <p className="text-[10px] text-slate-400 leading-tight">{item.description}</p>
          </div>
        ))}
      </div>

      {/* Overall reference line as a summary row */}
      <div className="border-t border-slate-100 pt-2">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-slate-500">
            {lang === "ru" ? "Итоговый уровень доверия" : lang === "he" ? "ציון ביטחון כולל" : "Final confidence score"}
          </span>
          <span className="font-semibold text-slate-700">{overallPct}%</span>
        </div>
        <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${overallPct}%`,
              background: `linear-gradient(90deg, #2563eb, #0d9488)`,
            }}
          />
        </div>
      </div>
    </div>
  );
}
