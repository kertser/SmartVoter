"use client";

import type { PartyResult } from "@/lib/api";

// Evidence type display names and colors (ordered by reliability per AGENTS.MD §2.1)
const EVIDENCE_META: Record<string, { label: string; color: string }> = {
  vote:              { label: "Parliamentary vote", color: "#1d4ed8" },
  bill:              { label: "Sponsored bill",     color: "#2563eb" },
  candidate_history: { label: "Candidate history",  color: "#0d9488" },
  party_lineage:     { label: "Party lineage",      color: "#7c3aed" },
  party_platform:    { label: "Party platform",     color: "#d97706" },
  statement:         { label: "Public statement",   color: "#9ca3af" },
  coalition:         { label: "Coalition agmt.",    color: "#6b7280" },
};

const ORDER = ["vote", "bill", "candidate_history", "party_lineage", "party_platform", "statement", "coalition"];

interface Props {
  parties: PartyResult[];
  lang?: string;
}

function getLabel(type: string, lang?: string): string {
  const map: Record<string, { ru: string; he: string; en: string }> = {
    vote:              { en: "Vote",       ru: "Голосование",    he: "הצבעה"        },
    bill:              { en: "Bill",       ru: "Законопроект",   he: "חוק"           },
    candidate_history: { en: "Candidate",  ru: "Кандидат",       he: "מועמד"        },
    party_lineage:     { en: "Lineage",    ru: "Преемственность",he: "מוצא"         },
    party_platform:    { en: "Platform",   ru: "Программа",      he: "מצע"          },
    statement:         { en: "Statement",  ru: "Заявление",      he: "הצהרה"        },
    coalition:         { en: "Coalition",  ru: "Коалиция",       he: "קואליציה"     },
  };
  const entry = map[type];
  if (!entry) return EVIDENCE_META[type]?.label ?? type;
  return lang === "ru" ? entry.ru : lang === "he" ? entry.he : entry.en;
}

function getFootnote(lang?: string): string {
  if (lang === "ru") return "Шире база = больше доказательств. Голосования и законопроекты — наиболее надёжные источники.";
  if (lang === "he") return "בסיס רחב יותר = יותר עדות. הצבעות וחוקים הם המקורות האמינים ביותר.";
  return "Broader base = stronger evidence. Votes and bills are the most reliable sources.";
}

export function EvidenceCompositionBar({ parties, lang = "en" }: Props) {
  const topParties = parties.slice(0, 5);
  const getPartyName = (p: PartyResult) => p.name_he ?? p.name;

  const allTypes = new Set<string>();
  topParties.forEach((p) => Object.keys(p.evidence_by_type ?? {}).forEach((t) => allTypes.add(t)));
  const types = ORDER.filter((t) => allTypes.has(t));

  if (types.length === 0 || topParties.length === 0) {
    return (
      <div className="flex items-center justify-center h-24 text-slate-400 text-sm">
        {lang === "ru" ? "Нет данных о типах доказательств" : lang === "he" ? "אין נתונים על סוגי עדות" : "No evidence type data available"}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {topParties.map((party) => {
        const name = getPartyName(party);
        const evMap: Record<string, number> = party.evidence_by_type ?? {};
        const total = types.reduce((s, t) => s + (evMap[t] ?? 0), 0) || 1;

        return (
          <div key={party.party_id} className="space-y-0.5">
            <div className="flex justify-between items-center">
              <span className="text-xs font-medium text-slate-700 truncate" style={{ maxWidth: "60%" }}>{name}</span>
              <span className="text-[10px] text-slate-400 tabular-nums">
                {Math.round(party.evidence_strength * 100)}%
              </span>
            </div>
            {/* Stacked bar */}
            <div className="flex h-3 rounded-full overflow-hidden bg-slate-100">
              {types.map((t) => {
                const pct = ((evMap[t] ?? 0) / total) * 100;
                if (pct < 0.5) return null;
                return (
                  <div
                    key={t}
                    title={`${getLabel(t, lang)}: ${Math.round(pct)}%`}
                    style={{ width: `${pct}%`, backgroundColor: EVIDENCE_META[t]?.color ?? "#94a3b8" }}
                  />
                );
              })}
            </div>
          </div>
        );
      })}

      {/* Legend */}
      <div className="flex flex-wrap gap-x-3 gap-y-1 pt-1">
        {types.map((t) => (
          <div key={t} className="flex items-center gap-1">
            <div className="h-2 w-2 rounded-full flex-shrink-0" style={{ backgroundColor: EVIDENCE_META[t]?.color ?? "#94a3b8" }} />
            <span className="text-[10px] text-slate-500">{getLabel(t, lang)}</span>
          </div>
        ))}
      </div>

      <p className="text-xs text-slate-400">{getFootnote(lang)}</p>
    </div>
  );
}


