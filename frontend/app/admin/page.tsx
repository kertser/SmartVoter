"use client";

/**
 * Admin Review & LLM Generation Panel (AGENTS.MD Section 15).
 *
 * Tabs:
 *  1. Review Queue  — approve / reject / edit LLM-generated questions
 *  2. Generate      — select policy items, trigger LLM question generation
 *  3. LLM Audit     — browse stored LLM outputs
 *
 * No question goes public until status = approved.
 */

import { useEffect, useState, useCallback } from "react";
import {
  adminGetReviewItems,
  adminApprove,
  adminReject,
  adminEditQuestion,
  adminGetPolicyItems,
  adminGenerateQuestions,
  adminGetLlmOutputs,
  AdminQuestion,
  PolicyItemAdmin,
  LlmOutputRecord,
} from "@/lib/api";

type Tab = "review" | "generate" | "audit";

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("review");

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-bold text-slate-900">Admin Panel</h1>
        <p className="text-sm text-slate-500">
          Review LLM-generated questions · Generate new questions · Audit LLM outputs.{" "}
          <span className="text-orange-600 font-medium">
            Questions are only shown to users after approval.
          </span>
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-slate-200">
        {(["review", "generate", "audit"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
              tab === t
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {t === "review" ? "Review Queue" : t === "generate" ? "Generate Questions" : "LLM Audit"}
          </button>
        ))}
      </div>

      {tab === "review" && <ReviewTab />}
      {tab === "generate" && <GenerateTab />}
      {tab === "audit" && <AuditTab />}
    </div>
  );
}

// ── Review Tab ────────────────────────────────────────────────────────────────

function ReviewTab() {
  const [questions, setQuestions] = useState<AdminQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [editHe, setEditHe] = useState("");
  const [editRu, setEditRu] = useState("");

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const items = await adminGetReviewItems(statusFilter || undefined);
      setQuestions(items);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { reload(); }, [reload]);

  const handleApprove = async (id: string) => {
    await adminApprove(id);
    reload();
  };

  const handleReject = async (id: string) => {
    await adminReject(id);
    reload();
  };

  const handleEditSave = async (id: string) => {
    await adminEditQuestion(id, {
      question_text_en: editText,
      question_text_he: editHe,
      question_text_ru: editRu,
    });
    setEditingId(null);
    reload();
  };

  const statusColors: Record<string, string> = {
    needs_review: "bg-yellow-50 text-yellow-700 border-yellow-200",
    draft: "bg-slate-100 text-slate-600",
    llm_generated: "bg-blue-50 text-blue-700 border-blue-200",
    approved: "bg-green-50 text-green-700 border-green-200",
    rejected: "bg-red-50 text-red-600 border-red-200",
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700"
        >
          <option value="">All pending</option>
          <option value="needs_review">Needs review</option>
          <option value="draft">Draft</option>
          <option value="llm_generated">LLM generated</option>
          <option value="rejected">Rejected</option>
        </select>
        <button onClick={reload} className="text-xs text-brand-600 hover:underline">↻ Refresh</button>
        <span className="text-xs text-slate-400">{questions.length} items</span>
      </div>

      {loading ? (
        <p className="text-slate-400 text-sm py-10 text-center">Loading…</p>
      ) : questions.length === 0 ? (
        <div className="rounded-xl border border-slate-100 bg-slate-50 p-8 text-center text-slate-400 text-sm">
          No items pending review.
        </div>
      ) : (
        <div className="space-y-3">
          {questions.map((q) => (
            <div key={q.id} className="rounded-xl border border-slate-200 bg-white shadow-sm p-5 space-y-3">
              {/* Status + neutrality */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${statusColors[q.status] ?? "bg-slate-100"}`}>
                  {q.status.replace("_", " ")}
                </span>
                {q.neutrality_score != null && (
                  <span className={`rounded-full px-2 py-0.5 text-xs ${
                    q.neutrality_score >= 0.75
                      ? "bg-green-50 text-green-700"
                      : q.neutrality_score >= 0.5
                      ? "bg-yellow-50 text-yellow-700"
                      : "bg-red-50 text-red-600"
                  }`}>
                    Neutrality: {(q.neutrality_score * 100).toFixed(0)}%
                  </span>
                )}
                {q.llm_prompt_version && (
                  <span className="text-xs text-slate-400">prompt {q.llm_prompt_version}</span>
                )}
              </div>

              {editingId === q.id ? (
                /* Edit mode */
                <div className="space-y-2">
                  <label className="block text-xs font-medium text-slate-500">English</label>
                  <textarea
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    rows={3}
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                  />
                  <label className="block text-xs font-medium text-slate-500">Hebrew (עברית)</label>
                  <textarea
                    dir="rtl"
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    rows={2}
                    value={editHe}
                    onChange={(e) => setEditHe(e.target.value)}
                  />
                  <label className="block text-xs font-medium text-slate-500">Russian (Русский)</label>
                  <textarea
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    rows={2}
                    value={editRu}
                    onChange={(e) => setEditRu(e.target.value)}
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleEditSave(q.id)}
                      className="rounded-lg bg-brand-600 px-4 py-1.5 text-xs text-white font-medium hover:bg-brand-700"
                    >
                      Save & mark needs-review
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="rounded-lg border border-slate-200 px-4 py-1.5 text-xs text-slate-600"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                /* View mode */
                <div className="space-y-2">
                  <p className="text-sm font-medium text-slate-800">{q.question_text_en}</p>
                  {q.question_text_he && (
                    <p dir="rtl" className="text-sm text-slate-500">{q.question_text_he}</p>
                  )}
                  {q.question_text_ru && (
                    <p className="text-sm text-slate-400">{q.question_text_ru}</p>
                  )}
                </div>
              )}

              {editingId !== q.id && (
                <div className="flex flex-wrap gap-2 pt-1">
                  <button
                    onClick={() => handleApprove(q.id)}
                    className="rounded-lg bg-green-600 px-3 py-1.5 text-xs text-white font-medium hover:bg-green-700"
                  >
                    ✓ Approve
                  </button>
                  <button
                    onClick={() => {
                      setEditingId(q.id);
                      setEditText(q.question_text_en);
                      setEditHe(q.question_text_he ?? "");
                      setEditRu(q.question_text_ru ?? "");
                    }}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                  >
                    ✎ Edit
                  </button>
                  <button
                    onClick={() => handleReject(q.id)}
                    className="rounded-lg border border-red-200 px-3 py-1.5 text-xs text-red-600 hover:bg-red-50"
                  >
                    ✗ Reject
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Generate Tab ──────────────────────────────────────────────────────────────

function GenerateTab() {
  const [policyItems, setPolicyItems] = useState<PolicyItemAdmin[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<{ generated: { question_en?: string; question_id?: string; error?: string; policy_item_id: string; neutrality_score?: number; is_loaded?: boolean; provider?: string }[] } | null>(null);

  useEffect(() => {
    adminGetPolicyItems().then(setPolicyItems).finally(() => setLoading(false));
  }, []);

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const handleGenerate = async () => {
    if (selected.size === 0) return;
    setGenerating(true);
    setResult(null);
    try {
      const res = await adminGenerateQuestions([...selected]) as { generated: { question_en?: string; question_id?: string; error?: string; policy_item_id: string; neutrality_score?: number; is_loaded?: boolean; provider?: string }[] };
      setResult(res);
    } finally {
      setGenerating(false);
    }
  };

  const sourceColors: Record<string, string> = {
    vote: "bg-green-50 text-green-700",
    bill: "bg-blue-50 text-blue-700",
    platform: "bg-purple-50 text-purple-700",
    statement: "bg-orange-50 text-orange-700",
    candidate_history: "bg-teal-50 text-teal-700",
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <p className="text-sm text-slate-600 flex-1">
          Select policy items and click Generate. The LLM will produce questions in EN/HE/RU.
          All outputs are stored for audit and placed in <em>needs_review</em> status.
        </p>
        <button
          onClick={handleGenerate}
          disabled={selected.size === 0 || generating}
          className="rounded-lg bg-brand-600 px-5 py-2 text-sm text-white font-medium hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
        >
          {generating ? "Generating…" : `Generate (${selected.size} selected)`}
        </button>
      </div>

      {result && (
        <div className="rounded-xl border border-brand-100 bg-brand-50 p-4 space-y-2">
          <p className="text-sm font-medium text-brand-700">
            Generated {result.generated.length} question(s). Go to Review Queue to approve them.
          </p>
          {result.generated.map((r, i) => (
            <div key={i} className="text-xs text-slate-600">
              {r.error ? (
                <span className="text-red-600">✗ {r.policy_item_id}: {r.error}</span>
              ) : (
                <span>
                  ✓ [{r.provider}] neutrality={((r.neutrality_score ?? 0) * 100).toFixed(0)}%
                  {r.is_loaded ? " ⚠ loaded" : ""} — {r.question_en?.slice(0, 80)}…
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {loading ? (
        <p className="text-slate-400 text-sm py-10 text-center">Loading policy items…</p>
      ) : (
        <div className="space-y-2">
          <div className="flex gap-2 text-xs text-slate-500">
            <button onClick={() => setSelected(new Set(policyItems.map((p) => p.id)))} className="hover:underline">
              Select all
            </button>
            <span>·</span>
            <button onClick={() => setSelected(new Set())} className="hover:underline">
              Clear
            </button>
          </div>
          {policyItems.map((pi) => (
            <label
              key={pi.id}
              className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                selected.has(pi.id) ? "border-brand-400 bg-brand-50" : "border-slate-200 bg-white hover:bg-slate-50"
              }`}
            >
              <input
                type="checkbox"
                checked={selected.has(pi.id)}
                onChange={() => toggle(pi.id)}
                className="mt-0.5 accent-brand-600"
              />
              <div className="flex-1 space-y-0.5">
                <p className="text-sm font-medium text-slate-800">{pi.title}</p>
                {pi.directional_axis && (
                  <p className="text-xs text-slate-400">{pi.directional_axis}</p>
                )}
                <div className="flex gap-2 flex-wrap">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${sourceColors[pi.source_type] ?? "bg-slate-100 text-slate-600"}`}>
                    {pi.source_type}
                  </span>
                  {pi.llm_confidence != null && (
                    <span className="text-xs text-slate-400">
                      conf {(pi.llm_confidence * 100).toFixed(0)}%
                    </span>
                  )}
                  <span className={`text-xs ${pi.human_review_status === "approved" ? "text-green-600" : "text-slate-400"}`}>
                    {pi.human_review_status}
                  </span>
                </div>
              </div>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Audit Tab ─────────────────────────────────────────────────────────────────

function AuditTab() {
  const [outputs, setOutputs] = useState<LlmOutputRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminGetLlmOutputs(50).then(setOutputs).finally(() => setLoading(false));
  }, []);

  const entityColors: Record<string, string> = {
    question: "bg-blue-50 text-blue-700",
    policy_item: "bg-purple-50 text-purple-700",
    party_position: "bg-green-50 text-green-700",
    bill_or_vote: "bg-orange-50 text-orange-700",
  };

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-500">
        Every LLM call is stored here with provider, model, input hash, and confidence.
        Double-click a row to see full output (coming soon).
      </p>
      {loading ? (
        <p className="text-slate-400 text-sm py-10 text-center">Loading…</p>
      ) : outputs.length === 0 ? (
        <div className="rounded-xl border border-slate-100 bg-slate-50 p-8 text-center text-slate-400 text-sm">
          No LLM outputs recorded yet. Generate questions to see audit entries here.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500">
                <th className="py-2 pr-4">When</th>
                <th className="py-2 pr-4">Provider / Model</th>
                <th className="py-2 pr-4">Type</th>
                <th className="py-2 pr-4">Confidence</th>
                <th className="py-2">Summary</th>
              </tr>
            </thead>
            <tbody>
              {outputs.map((row) => (
                <tr key={row.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-2 pr-4 text-slate-400 whitespace-nowrap">
                    {row.created_at ? new Date(row.created_at).toLocaleString() : "—"}
                  </td>
                  <td className="py-2 pr-4 text-slate-600 whitespace-nowrap">
                    <span className="font-medium">{row.provider}</span>
                    <br />
                    <span className="text-slate-400">{row.model}</span>
                  </td>
                  <td className="py-2 pr-4">
                    {row.entity_type ? (
                      <span className={`rounded-full px-2 py-0.5 ${entityColors[row.entity_type] ?? "bg-slate-100 text-slate-600"}`}>
                        {row.entity_type}
                      </span>
                    ) : "—"}
                  </td>
                  <td className="py-2 pr-4 text-slate-500">
                    {row.confidence != null ? `${(row.confidence * 100).toFixed(0)}%` : "—"}
                  </td>
                  <td className="py-2 text-slate-600 max-w-sm truncate">{row.output_summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

