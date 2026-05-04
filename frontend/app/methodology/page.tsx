import Link from "next/link";

const EVIDENCE_WEIGHTS = [
  { type: "Parliamentary vote", weight: "1.00", description: "Most reliable — direct observable behavior" },
  { type: "Sponsored bill", weight: "0.80", description: "Legislative initiative, slightly less definitive" },
  { type: "Committee behavior", weight: "0.70", description: "Committee participation and statements" },
  { type: "Candidate past votes", weight: "0.55", description: "Historical votes of current party members" },
  { type: "Party lineage", weight: "0.50", description: "Predecessor party behavior" },
  { type: "Coalition agreement", weight: "0.45", description: "Signed coalition deals" },
  { type: "Party platform", weight: "0.35", description: "Official declared platform" },
  { type: "Public statement", weight: "0.25", description: "Statements to press or public" },
  { type: "Media interview", weight: "0.20", description: "Least reliable — context-dependent" },
];

export default function MethodologyPage() {
  return (
    <div className="max-w-2xl mx-auto space-y-10">
      <div>
        <Link href="/" className="text-sm text-brand-600 hover:underline mb-4 inline-block">
          ← Back to home
        </Link>
        <h1 className="text-3xl font-bold text-slate-900">Methodology</h1>
        <p className="text-slate-500 mt-2">
          How SmartVoter scores are computed, what they mean, and what they cannot tell you.
        </p>
      </div>

      {/* Core principle */}
      <section className="rounded-xl border border-brand-100 bg-brand-50 p-6 space-y-2">
        <h2 className="font-semibold text-brand-900">Core principle</h2>
        <p className="text-sm text-brand-800">
          SmartVoter compares your stated preferences with parties&rsquo; observed behavior, not
          just their stated promises. Observed votes carry more weight than platform declarations.
          This is not voting advice — it is a similarity analysis.
        </p>
      </section>

      {/* Match score */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-slate-800">Match score</h2>
        <p className="text-sm text-slate-600">
          For each question you answer, we compute a similarity score between your position and
          the party&rsquo;s inferred position:
        </p>
        <div className="rounded-lg bg-slate-900 text-green-300 font-mono text-xs p-4 space-y-1">
          <p>distance = abs(your_position - party_position)</p>
          <p>similarity = 1 − distance / 2</p>
          <p>weighted = similarity × importance × evidence_strength</p>
          <p className="mt-2 text-slate-400">// Final score:</p>
          <p>match = Σ(weighted) / Σ(importance × evidence_strength)</p>
        </div>
        <p className="text-xs text-slate-400">
          Positions range from −1 (one pole) to +1 (opposite pole). The axis direction is
          defined per policy item.
        </p>
      </section>

      {/* Confidence score */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-slate-800">Confidence score</h2>
        <p className="text-sm text-slate-600">
          Confidence is computed separately from the match score and reflects how reliable
          the match score is:
        </p>
        <div className="rounded-lg bg-slate-900 text-green-300 font-mono text-xs p-4">
          <p>confidence = evidence_strength × coverage × (1 − volatility) × stability</p>
        </div>
        <div className="grid grid-cols-2 gap-3 text-xs text-slate-600">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <p className="font-medium text-slate-700">Coverage</p>
            <p>Fraction of your important issues that have evidence for this party</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <p className="font-medium text-slate-700">Stability</p>
            <p>Whether your ranking changes significantly when one answer is removed</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <p className="font-medium text-slate-700">Volatility penalty</p>
            <p>Parties that change frequently have higher uncertainty</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <p className="font-medium text-slate-700">Evidence strength</p>
            <p>Average reliability of sources used for this party&rsquo;s positions</p>
          </div>
        </div>
      </section>

      {/* Evidence priority */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-slate-800">Evidence priority</h2>
        <p className="text-sm text-slate-600">
          Not all sources are equally reliable. We weight evidence by type:
        </p>
        <div className="rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-slate-600 text-xs">Evidence type</th>
                <th className="text-right px-4 py-2 font-medium text-slate-600 text-xs">Weight</th>
                <th className="text-left px-4 py-2 font-medium text-slate-600 text-xs hidden sm:table-cell">Note</th>
              </tr>
            </thead>
            <tbody>
              {EVIDENCE_WEIGHTS.map((row, i) => (
                <tr key={row.type} className={i % 2 === 0 ? "bg-white" : "bg-slate-50/50"}>
                  <td className="px-4 py-2 text-slate-800 text-xs font-medium">{row.type}</td>
                  <td className="px-4 py-2 text-right">
                    <span className="font-mono text-xs bg-slate-100 rounded px-1.5 py-0.5 text-slate-700">
                      {row.weight}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-slate-500 text-xs hidden sm:table-cell">
                    {row.description}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* New party handling */}
      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-slate-800">New party handling</h2>
        <div className="rounded-xl border border-orange-200 bg-orange-50 p-4 text-sm text-orange-800">
          <p className="font-medium mb-1">New parties are not excluded — but confidence is lower.</p>
          <p>
            If a party has no parliamentary voting record, its position is inferred from
            candidate history (45%), lineage (25%), platform (20%), and statements (10%).
            These scores carry higher uncertainty and are shown with a warning.
          </p>
        </div>
      </section>

      {/* Limitations */}
      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-slate-800">Limitations</h2>
        <ul className="space-y-2 text-sm text-slate-600">
          <li className="flex gap-2">
            <span className="text-amber-500 shrink-0">⚠</span>
            This tool does not tell you whom to vote for.
          </li>
          <li className="flex gap-2">
            <span className="text-amber-500 shrink-0">⚠</span>
            Party positions may change over time; data has a cutoff date.
          </li>
          <li className="flex gap-2">
            <span className="text-amber-500 shrink-0">⚠</span>
            Absence from a vote is treated as low-information, not opposition.
          </li>
          <li className="flex gap-2">
            <span className="text-amber-500 shrink-0">⚠</span>
            Phase 1 uses mock data. Real Knesset data ingestion is planned for Phase 6.
          </li>
          <li className="flex gap-2">
            <span className="text-amber-500 shrink-0">⚠</span>
            LLM-generated content is reviewed by humans before it appears publicly.
          </li>
        </ul>
      </section>

      <div className="border-t border-slate-200 pt-6">
        <Link href="/" className="text-sm text-brand-600 hover:underline">← Back to home</Link>
      </div>
    </div>
  );
}

