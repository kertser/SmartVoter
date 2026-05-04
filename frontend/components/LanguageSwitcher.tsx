"use client";

import { useLang, useT, type Lang } from "@/lib/i18n";
import { Tooltip } from "@/components/Tooltip";

export function LanguageSwitcher() {
  const { lang, setLang } = useLang();
  const t = useT();
  const ls = t.langSwitcher;

  const options: { code: Lang; label: string; tooltip: string }[] = [
    { code: "en", label: ls.en, tooltip: ls.enTooltip },
    { code: "he", label: ls.he, tooltip: ls.heTooltip },
    { code: "ru", label: ls.ru, tooltip: ls.ruTooltip },
  ];

  return (
    <div className="flex items-center gap-1" aria-label={ls.label}>
      {options.map(({ code, label, tooltip }) => (
        <Tooltip key={code} content={tooltip}>
          <button
            onClick={() => setLang(code)}
            aria-pressed={lang === code}
            className={`px-2 py-0.5 rounded text-xs font-mono font-medium transition-colors ${
              lang === code
                ? "bg-slate-800 text-white"
                : "text-slate-400 hover:text-slate-700 hover:bg-slate-100"
            }`}
          >
            {label}
          </button>
        </Tooltip>
      ))}
    </div>
  );
}
