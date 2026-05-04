import Link from "next/link";

/**
 * Onboarding / Home page (AGENTS.MD Section 14.2).
 * Must contain the exact disclaimer text specified in AGENTS.MD.
 * Must NOT promise to tell users whom to vote for.
 */
export default function HomePage() {
  return (
    <div className="flex flex-col items-center text-center gap-10 py-12">
      {/* Hero */}
      <div className="max-w-2xl space-y-4">
        <div className="inline-block rounded-full bg-brand-50 border border-brand-100 px-4 py-1 text-xs font-medium text-brand-700 mb-2">
          Evidence-based · Transparent · Non-partisan
        </div>
        <h1 className="text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
          How closely do parties match<br className="hidden sm:block" /> your{" "}
          <span className="text-brand-600">policy preferences</span>?
        </h1>
        <p className="text-lg text-slate-600 leading-relaxed">
          This tool compares your policy preferences with parties&rsquo; observed
          parliamentary behavior and declared positions.{" "}
          <strong>It does not tell you whom to vote for.</strong> It shows
          similarity, disagreement, evidence, and uncertainty.
        </p>
      </div>

      {/* Disclaimer (AGENTS.MD Section 14.2 required text) */}
      <div className="max-w-xl rounded-xl border border-slate-200 bg-white p-6 text-left shadow-sm space-y-2">
        <p className="text-sm font-semibold text-slate-700">Before you begin</p>
        <ul className="text-sm text-slate-600 space-y-1 list-disc list-inside">
          <li>Your answers are anonymous. No login is required.</li>
          <li>Results show <em>similarity scores</em>, not recommendations.</li>
          <li>
            Confidence is lower for new parties without parliamentary voting
            records.
          </li>
          <li>
            Evidence sources and confidence levels are shown for every result.
          </li>
        </ul>
      </div>

      {/* CTAs */}
      <div className="flex flex-wrap gap-4 justify-center">
        <Link
          href="/questionnaire"
          className="rounded-lg bg-brand-600 px-8 py-3 text-white font-medium hover:bg-brand-700 transition-colors shadow-sm"
        >
          Start quick test
        </Link>
        <Link
          href="/methodology"
          className="rounded-lg border border-slate-300 bg-white px-8 py-3 text-slate-700 font-medium hover:bg-slate-50 transition-colors"
        >
          View methodology
        </Link>
      </div>

      {/* Trust indicators */}
      <div className="flex flex-wrap gap-8 justify-center text-sm text-slate-500">
        <div className="flex items-center gap-2">
          <span className="text-green-600">✓</span> Evidence-first scoring
        </div>
        <div className="flex items-center gap-2">
          <span className="text-green-600">✓</span> Explicit uncertainty
        </div>
        <div className="flex items-center gap-2">
          <span className="text-green-600">✓</span> No voting advice
        </div>
        <div className="flex items-center gap-2">
          <span className="text-green-600">✓</span> Open methodology
        </div>
      </div>
    </div>
  );
}

