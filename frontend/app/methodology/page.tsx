"use client";

import Link from "next/link";
import { useT } from "@/lib/i18n";

export default function MethodologyPage() {
  const t = useT();
  const m = t.methodology;

  return (
    <div className="max-w-2xl mx-auto space-y-10">
      <div>
        <Link href="/" className="text-sm text-brand-600 hover:underline mb-4 inline-block">
          {m.backHome}
        </Link>
        <h1 className="text-3xl font-bold text-slate-900">{m.heading}</h1>
        <p className="text-slate-500 mt-2">{m.subtext}</p>
      </div>

      {/* Core principle */}
      <section className="rounded-xl border border-brand-100 bg-brand-50 p-6 space-y-2">
        <h2 className="font-semibold text-brand-900">{m.corePrincipleHeading}</h2>
        <p className="text-sm text-brand-800">{m.corePrinciple}</p>
      </section>

      {/* Match score */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-slate-800">{m.matchScoreHeading}</h2>
        <p className="text-sm text-slate-600">{m.matchScoreDescription}</p>
        <div className="rounded-lg bg-slate-900 text-green-300 font-mono text-xs p-4 space-y-1">
          <p>distance = abs(your_position - party_position)</p>
          <p>similarity = 1 &minus; distance / 2</p>
          <p>weighted = similarity &times; importance &times; evidence_strength</p>
          <p className="mt-2 text-slate-400">// Final score:</p>
          <p>match = &Sigma;(weighted) / &Sigma;(importance &times; evidence_strength)</p>
        </div>
        <p className="text-xs text-slate-400">{m.notePositions}</p>
      </section>

      {/* Confidence score */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-slate-800">{m.confidenceScoreHeading}</h2>
        <p className="text-sm text-slate-600">{m.confidenceScoreDescription}</p>
        <div className="rounded-lg bg-slate-900 text-green-300 font-mono text-xs p-4">
          <p>confidence = evidence_strength &times; coverage &times; (1 &minus; volatility) &times; stability</p>
        </div>
        <div className="grid grid-cols-2 gap-3 text-xs text-slate-600">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <p className="font-medium text-slate-700">{m.coverageLabel}</p>
            <p>{m.coverageDescription}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <p className="font-medium text-slate-700">{m.stabilityLabel}</p>
            <p>{m.stabilityDescription}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <p className="font-medium text-slate-700">{m.volatilityLabel}</p>
            <p>{m.volatilityDescription}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <p className="font-medium text-slate-700">{m.evidenceStrengthLabel}</p>
            <p>{m.evidenceStrengthDescription}</p>
          </div>
        </div>
      </section>

      {/* Evidence priority */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-slate-800">{m.evidencePriorityHeading}</h2>
        <p className="text-sm text-slate-600">{m.evidencePriorityDescription}</p>
        <div className="rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-slate-600 text-xs">{m.tableEvidenceType}</th>
                <th className="text-right px-4 py-2 font-medium text-slate-600 text-xs">{m.tableWeight}</th>
                <th className="text-left px-4 py-2 font-medium text-slate-600 text-xs hidden sm:table-cell">{m.tableNote}</th>
              </tr>
            </thead>
            <tbody>
              {m.evidenceRows.map((row, i) => (
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
        <h2 className="text-xl font-semibold text-slate-800">{m.newPartyHeading}</h2>
        <div className="rounded-xl border border-orange-200 bg-orange-50 p-4 text-sm text-orange-800">
          <p className="font-medium mb-1">{m.newPartyWarningTitle}</p>
          <p>{m.newPartyWarningBody}</p>
        </div>
      </section>

      {/* Limitations */}
      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-slate-800">{m.limitationsHeading}</h2>
        <ul className="space-y-2 text-sm text-slate-600">
          {m.limitations.map((item, i) => (
            <li key={i} className="flex gap-2">
              <span className="text-amber-500 shrink-0">⚠</span>
              {item}
            </li>
          ))}
        </ul>
      </section>

      <div className="border-t border-slate-200 pt-6">
        <Link href="/" className="text-sm text-brand-600 hover:underline">{m.backHome}</Link>
      </div>
    </div>
  );
}

