"use client";

import { useT } from "@/lib/i18n";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { Tooltip } from "@/components/Tooltip";

/**
 * Client-side nav header so it can read the active language via useT().
 */
export function NavHeader() {
  const t = useT();
  const l = t.layout;
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto max-w-4xl px-4 py-4 flex items-center justify-between">
        <a href="/" className="font-semibold text-slate-800 text-lg tracking-tight">
          {l.siteTitle}
        </a>
        <nav className="flex items-center gap-5 text-sm text-slate-500 flex-wrap">
          <Tooltip content={l.navPartiesTitle} position="bottom">
            <a href="/parties" className="hover:text-slate-800 transition-colors">
              {l.navParties}
            </a>
          </Tooltip>
          <Tooltip content={l.navPersonsTitle} position="bottom">
            <a href="/persons" className="hover:text-slate-800 transition-colors">
              {l.navPersons}
            </a>
          </Tooltip>
          <Tooltip content={l.navVotesTitle} position="bottom">
            <a href="/votes" className="hover:text-slate-800 transition-colors">
              {l.navVotes}
            </a>
          </Tooltip>
          <Tooltip content={l.navBillsTitle} position="bottom">
            <a href="/bills" className="hover:text-slate-800 transition-colors">
              {l.navBills}
            </a>
          </Tooltip>
          <Tooltip content={l.navSimulationTitle} position="bottom">
            <a href="/simulation" className="hover:text-slate-800 transition-colors">
              {l.navSimulation}
            </a>
          </Tooltip>
          <Tooltip content={l.navMethodologyTitle} position="bottom">
            <a href="/methodology" className="hover:text-slate-800 transition-colors">
              {l.navMethodology}
            </a>
          </Tooltip>
          <Tooltip content={l.navAdminTitle} position="bottom">
            <a href="/admin" className="hover:text-slate-800 transition-colors text-orange-600 hover:text-orange-700">
              {l.navAdmin}
            </a>
          </Tooltip>
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

