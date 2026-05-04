"use client";

/**
 * i18n context — provides en / he / ru translations and RTL support.
 *
 * Usage:
 *   const t = useT();
 *   <p>{t.home.ctaStart}</p>
 *
 * Language is persisted to localStorage under the key "sv_lang".
 * The <html> element's lang + dir attributes are updated automatically.
 */

import React, { createContext, useContext, useEffect, useState } from "react";
import en from "@/locales/en";
import he from "@/locales/he";
import ru from "@/locales/ru";
import type { Translations } from "@/locales/types";

export type Lang = "en" | "he" | "ru";

const LOCALES: Record<Lang, Translations> = { en, he, ru };
const STORAGE_KEY = "sv_lang";

interface I18nContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: Translations;
}

const I18nContext = createContext<I18nContextValue>({
  lang: "en",
  setLang: () => {},
  t: en,
});

function detectBrowserLang(): Lang {
  if (typeof navigator === "undefined") return "en";
  const pref = navigator.language?.toLowerCase() ?? "";
  if (pref.startsWith("he") || pref.startsWith("iw")) return "he";
  if (pref.startsWith("ru")) return "ru";
  return "en";
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");

  // Hydrate from localStorage (or browser preference) on mount
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as Lang | null;
    const chosen =
      stored && LOCALES[stored] ? stored : detectBrowserLang();
    setLangState(chosen);
  }, []);

  // Apply lang + dir to <html> whenever language changes
  useEffect(() => {
    const t = LOCALES[lang];
    document.documentElement.lang = lang;
    document.documentElement.dir = t.dir;
  }, [lang]);

  const setLang = (next: Lang) => {
    setLangState(next);
    localStorage.setItem(STORAGE_KEY, next);
  };

  return (
    <I18nContext.Provider value={{ lang, setLang, t: LOCALES[lang] }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useT(): Translations {
  return useContext(I18nContext).t;
}

export function useLang(): { lang: Lang; setLang: (l: Lang) => void } {
  const { lang, setLang } = useContext(I18nContext);
  return { lang, setLang };
}

