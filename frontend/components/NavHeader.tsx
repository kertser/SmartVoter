"use client";

import { useT } from "@/lib/i18n";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

/**
 * Client-side nav header so it can read the active language via useT().
 */
export function NavHeader() {
  const t = useT();
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto max-w-4xl px-4 py-4 flex items-center justify-between">
        <a href="/" className="font-semibold text-slate-800 text-lg tracking-tight">
          {t.layout.siteTitle}
        </a>
        <nav className="flex items-center gap-6 text-sm text-slate-500">
          <a href="/methodology" className="hover:text-slate-800 transition-colors">
            {t.layout.navMethodology}
          </a>
          <a href="/admin" className="hover:text-slate-800 transition-colors text-orange-600 hover:text-orange-700">
            Admin
          </a>
          <LanguageSwitcher />
        </nav>
      </div>
    </header>
  );
}

/**
 * Client-side footer so it can read the active language via useT().
 */
export function NavFooter() {
  const t = useT();
  return (
    <footer className="border-t border-slate-200 mt-20 py-8 text-center text-xs text-slate-400">
      <p>{t.layout.footerDisclaimer}</p>
    </footer>
  );
}

