"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useT } from "@/lib/i18n";
import { Tooltip } from "@/components/Tooltip";
import {
  clearSession,
  getCompletedSessionId,
  clearCompletedSession,
} from "@/lib/session";

/**
 * Onboarding / Home page (AGENTS.MD Section 14.2).
 * Must contain the exact disclaimer text specified in AGENTS.MD.
 * Must NOT promise to tell users whom to vote for.
 */
export default function HomePage() {
  const t = useT();
  const h = t.home;
  const router = useRouter();
  const [prevSessionId, setPrevSessionId] = useState<string | null>(null);

  useEffect(() => {
    const completedId = getCompletedSessionId();
    if (!completedId) return;
    // Verify the session still exists on the server. If the container was
    // restarted / data wiped, the server will return 404/422 and we clear
    // the stale reference so the "View previous results" button disappears.
    fetch(`/api/results/${completedId}`)
      .then((res) => {
        if (res.status === 404 || res.status === 422) {
          clearCompletedSession();
        } else {
          setPrevSessionId(completedId);
        }
      })
      .catch(() => {
        // Network error — don't clear; might be a transient startup delay.
        setPrevSessionId(completedId);
      });
  }, []);

  /** Start a brand-new questionnaire, discarding any in-progress session. */
  const handleStartFresh = () => {
    clearSession(); // force a new session ID to be generated in the questionnaire
    router.push("/questionnaire");
  };

  return (
    <div className="flex flex-col items-center text-center gap-10 py-12">
      {/* Hero */}
      <div className="max-w-2xl space-y-4">
        <div className="inline-block rounded-full bg-brand-50 border border-brand-100 px-4 py-1 text-xs font-medium text-brand-700 mb-2">
          {h.badge}
        </div>
        <h1 className="text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
          {h.headline1}
          <br className="hidden sm:block" /> {h.headline2}{" "}
          <span className="text-brand-600">{h.headlineEmphasis}</span>
          {h.headlineEnd}
        </h1>
        <p className="text-lg text-slate-600 leading-relaxed">
          {h.subtext}{" "}
          <strong>{h.subtextStrong}</strong>
          {h.subtextEnd}
        </p>
      </div>

      {/* Disclaimer (AGENTS.MD Section 14.2 required text) */}
      <div className="max-w-xl rounded-xl border border-slate-200 bg-white p-6 text-left shadow-sm space-y-2">
        <p className="text-sm font-semibold text-slate-700">
          {h.beforeYouBegin}
        </p>
        <ul className="text-sm text-slate-600 space-y-1 list-disc list-inside">
          {h.disclaimer.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      </div>

      {/* CTAs */}
      <div className="flex flex-wrap gap-4 justify-center">
        <button
          onClick={handleStartFresh}
          className="rounded-lg bg-brand-600 px-8 py-3 text-white font-medium hover:bg-brand-700 transition-colors shadow-sm"
        >
          {h.ctaStart}
        </button>
        <Link
          href="/methodology"
          className="rounded-lg border border-slate-300 bg-white px-8 py-3 text-slate-700 font-medium hover:bg-slate-50 transition-colors"
        >
          {h.ctaMethodology}
        </Link>
        {prevSessionId && (
          <Link
            href={`/results?session_id=${prevSessionId}`}
            className="rounded-lg border border-brand-200 bg-brand-50 px-8 py-3 text-brand-700 font-medium hover:bg-brand-100 transition-colors"
          >
            {h.ctaViewPrevResults}
          </Link>
        )}
      </div>

      {/* Trust indicators */}
      <div className="flex flex-wrap gap-8 justify-center text-sm text-slate-500">
        {([
          [h.trust1, h.trust1Tooltip],
          [h.trust2, h.trust2Tooltip],
          [h.trust3, h.trust3Tooltip],
          [h.trust4, h.trust4Tooltip],
        ] as [string, string][]).map(([label, tip]) => (
          <Tooltip key={label} content={tip} position="top">
            <div className="flex items-center gap-2 cursor-help">
              <span className="text-green-600">✓</span> {label}
            </div>
          </Tooltip>
        ))}
      </div>
    </div>
  );
}
