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
 * Requires admin password (X-Admin-Password header, configured in backend config.py).
 */

import { useEffect, useState, useCallback, useRef } from "react";
import {
  adminPing,
  adminGetReviewItems,
  adminApprove,
  adminReject,
  adminApproveAll,
  adminEditQuestion,
  adminGetLlmOutputs,
  adminTriggerIngestion,
  adminGetIngestionStatus,
  adminListIngestionJobs,
  adminTriggerFullPipeline,
  adminGetFullPipelineStatus,
  adminGetTopicsWithRootQuestions,
  adminCreateManualQuestion,
  adminDownloadBackup,
  adminRestoreBackup,
  adminGetAvailableKnessetData,
  adminGenerateQuestionBank,
  adminGetQuestionBankStatus,
  adminMarkStaleQuestions,
  adminListAllQuestions,
  adminDeleteQuestion,
  adminBulkDeleteQuestions,
  adminBatchGenerateExplanations,
  adminGetBatchExplainStatus,
  AdminQuestion,
  AdminQuestionBrowserItem,
  BatchExplainJob,
  LlmOutputRecord,
  IngestionJobStatus,
  FullPipelineJobStatus,
  FullPipelineKnessetResult,
  TopicWithRootQuestion,
  AvailableKnessetData,
  QuestionBankJobStatus,
  getStoredAdminPassword,
  storeAdminPassword,
  clearAdminPassword,
} from "@/lib/api";
import { useT } from "@/lib/i18n";

type Tab = "ingestion" | "generate" | "review" | "audit" | "backup" | "dedup";

// ── Password Gate ─────────────────────────────────────────────────────────────

function PasswordGate({ onAuth }: { onAuth: () => void }) {
  const t = useT();
  const a = t.admin;
  const [pw, setPw] = useState("");
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(false);
    // Probe the backend with a lightweight request
    try {
      storeAdminPassword(pw);
      await adminPing(); // lightweight auth check — just verifies the password
      onAuth();
    } catch (err) {
      clearAdminPassword();
      setError(true);
      console.error("[admin login]", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white shadow-lg p-8 space-y-6">
        <div className="space-y-1">
          <h1 className="text-xl font-bold text-slate-900">{a.passwordGateHeading}</h1>
          <p className="text-sm text-slate-500">{a.passwordGateSubtext}</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-slate-700">{a.passwordLabel}</label>
            <input
              type="password"
              value={pw}
              onChange={(e) => setPw(e.target.value)}
              placeholder={a.passwordPlaceholder}
              autoFocus
              required
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
            />
          </div>
          {error && (
            <p className="text-xs text-red-600 bg-red-50 rounded px-2 py-1">{a.passwordError}</p>
          )}
          <button
            type="submit"
            disabled={loading || !pw}
            className="w-full rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? "…" : a.passwordSubmit}
          </button>
        </form>
      </div>
    </div>
  );
}

// ── Main admin page ───────────────────────────────────────────────────────────

export default function AdminPage() {
  const t = useT();
  const a = t.admin;
  const [authed, setAuthed] = useState(false);
  const [tab, setTab] = useState<Tab>("ingestion");

  // Restore existing session on mount
  useEffect(() => {
    if (getStoredAdminPassword()) setAuthed(true);
  }, []);

  const handleLogout = () => {
    clearAdminPassword();
    setAuthed(false);
  };

  if (!authed) return <PasswordGate onAuth={() => setAuthed(true)} />;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold text-slate-900">{a.heading}</h1>
          <p className="text-sm text-slate-500">
            {a.subtext}{" "}
            <span className="text-orange-600 font-medium">{a.onlyApprovedNote}</span>
          </p>
        </div>
        <button
          onClick={handleLogout}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-500 hover:bg-slate-50"
        >
          {a.passwordLogout}
        </button>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-slate-200 flex-wrap">
        {(["ingestion", "generate", "review", "audit", "backup", "dedup"] as Tab[]).map((tabKey) => (
          <button
            key={tabKey}
            onClick={() => setTab(tabKey)}
            className={`px-4 py-2 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
              tab === tabKey
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            {tabKey === "ingestion" ? a.tabIngestion
              : tabKey === "generate" ? a.tabGenerate
              : tabKey === "review" ? a.tabReview
              : tabKey === "audit" ? a.tabAudit
              : tabKey === "dedup" ? "Deduplication"
              : a.tabBackup}
          </button>
        ))}
      </div>

      {tab === "ingestion" && <IngestionTab />}
      {tab === "generate" && <GenerateTab />}
      {tab === "review" && <ReviewTab />}
      {tab === "audit" && <AuditTab />}
      {tab === "backup" && <BackupTab />}
      {tab === "dedup" && <DedupTab />}
    </div>
  );
}

// ── Review Tab ────────────────────────────────────────────────────────────────

function ReviewTab() {
  const a = useT().admin;
  const [questions, setQuestions] = useState<AdminQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [editHe, setEditHe] = useState("");
  const [editRu, setEditRu] = useState("");
  const [approvingAll, setApprovingAll] = useState(false);
  const [approveAllMsg, setApproveAllMsg] = useState<{ ok: boolean; text: string } | null>(null);

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

  const handleApprove = async (id: string) => { await adminApprove(id); reload(); };
  const handleReject = async (id: string) => { await adminReject(id); reload(); };

  const handleApproveAll = async () => {
    if (!window.confirm(a.reviewApproveAllConfirm(questions.length))) return;
    setApprovingAll(true);
    setApproveAllMsg(null);
    try {
      const ids = questions.map(q => q.id);
      const res = await adminApproveAll({ ids });
      setApproveAllMsg({ ok: true, text: a.reviewApproveAllSuccess(res.approved) });
      reload();
    } catch {
      setApproveAllMsg({ ok: false, text: a.reviewApproveAllError });
    } finally {
      setApprovingAll(false);
    }
  };
  const handleEditSave = async (id: string) => {
    await adminEditQuestion(id, { question_text_en: editText, question_text_he: editHe, question_text_ru: editRu });
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
      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700"
          aria-label={a.reviewSelectFilter}
        >
          <option value="">{a.reviewFilterAll}</option>
          <option value="needs_review">{a.reviewFilterNeedsReview}</option>
          <option value="draft">{a.reviewFilterDraft}</option>
          <option value="llm_generated">{a.reviewFilterLlmGenerated}</option>
          <option value="rejected">{a.reviewFilterRejected}</option>
        </select>
        <button onClick={reload} className="text-xs text-brand-600 hover:underline">{a.reviewRefresh}</button>
        <span className="text-xs text-slate-400">{questions.length} items</span>

        {/* ── Approve All ─────────────────────────────────────────────── */}
        {questions.length > 0 && (
          <button
            onClick={handleApproveAll}
            disabled={approvingAll}
            className="ms-auto rounded-lg bg-green-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {approvingAll ? "…" : a.reviewApproveAll}
          </button>
        )}
      </div>

      {approveAllMsg && (
        <p className={`text-xs px-3 py-1.5 rounded-lg ${approveAllMsg.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-600"}`}>
          {approveAllMsg.text}
        </p>
      )}

      {loading ? (
        <p className="text-slate-400 text-sm py-10 text-center">Loading…</p>
      ) : questions.length === 0 ? (
        <div className="rounded-xl border border-slate-100 bg-slate-50 p-8 text-center text-slate-400 text-sm">
          {a.reviewNoItems}
        </div>
      ) : (
        <div className="space-y-3">
          {questions.map((q) => (
            <div key={q.id} className="rounded-xl border border-slate-200 bg-white shadow-sm p-5 space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${statusColors[q.status] ?? "bg-slate-100"}`}>
                  {q.status.replace("_", " ")}
                </span>
                {q.neutrality_score != null && (
                  <span className={`rounded-full px-2 py-0.5 text-xs ${
                    q.neutrality_score >= 0.75 ? "bg-green-50 text-green-700"
                    : q.neutrality_score >= 0.5 ? "bg-yellow-50 text-yellow-700"
                    : "bg-red-50 text-red-600"
                  }`}>
                    {a.reviewNeutrality}: {(q.neutrality_score * 100).toFixed(0)}%
                  </span>
                )}
                {q.llm_prompt_version && (
                  <span className="text-xs text-slate-400">{a.reviewPrompt} {q.llm_prompt_version}</span>
                )}
              </div>

              {editingId === q.id ? (
                <div className="space-y-2">
                  <label className="block text-xs font-medium text-slate-500">{a.reviewEnLabel}</label>
                  <textarea className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" rows={3} value={editText} onChange={(e) => setEditText(e.target.value)} />
                  <label className="block text-xs font-medium text-slate-500">{a.reviewHeLabel}</label>
                  <textarea dir="rtl" className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" rows={2} value={editHe} onChange={(e) => setEditHe(e.target.value)} />
                  <label className="block text-xs font-medium text-slate-500">{a.reviewRuLabel}</label>
                  <textarea className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" rows={2} value={editRu} onChange={(e) => setEditRu(e.target.value)} />
                  <div className="flex gap-2">
                    <button onClick={() => handleEditSave(q.id)} className="rounded-lg bg-brand-600 px-4 py-1.5 text-xs text-white font-medium hover:bg-brand-700">{a.reviewSave}</button>
                    <button onClick={() => setEditingId(null)} className="rounded-lg border border-slate-200 px-4 py-1.5 text-xs text-slate-600">{a.reviewCancel}</button>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-sm font-medium text-slate-800">{q.question_text_en}</p>
                  {q.question_text_he && <p dir="rtl" className="text-sm text-slate-500">{q.question_text_he}</p>}
                  {q.question_text_ru && <p className="text-sm text-slate-400">{q.question_text_ru}</p>}
                </div>
              )}

              {editingId !== q.id && (
                <div className="flex flex-wrap gap-2 pt-1">
                  <button onClick={() => handleApprove(q.id)} className="rounded-lg bg-green-600 px-3 py-1.5 text-xs text-white font-medium hover:bg-green-700">{a.reviewApprove}</button>
                  <button onClick={() => { setEditingId(q.id); setEditText(q.question_text_en); setEditHe(q.question_text_he ?? ""); setEditRu(q.question_text_ru ?? ""); }} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50">{a.reviewEdit}</button>
                  <button onClick={() => handleReject(q.id)} className="rounded-lg border border-red-200 px-3 py-1.5 text-xs text-red-600 hover:bg-red-50">{a.reviewReject}</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Manual Question Form ───────────────────────────────────────────────────────

function ManualQuestionForm({
  topics,
  onSaved,
}: {
  topics: TopicWithRootQuestion[];
  onSaved: () => void;
}) {
  const a = useT().admin;
  const [open, setOpen] = useState(false);
  const [topicId, setTopicId] = useState("");
  const [isRoot, setIsRoot] = useState(true);
  const [en, setEn] = useState("");
  const [he, setHe] = useState("");
  const [ru, setRu] = useState("");
  const [context, setContext] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reset = () => { setEn(""); setHe(""); setRu(""); setContext(""); setSuccess(null); setError(null); };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topicId || !en.trim()) return;
    setSubmitting(true);
    setSuccess(null);
    setError(null);
    try {
      const res = await adminCreateManualQuestion({
        topic_id: topicId,
        is_root_question: isRoot,
        question_text_en: en.trim(),
        question_text_he: he.trim(),
        question_text_ru: ru.trim(),
        context_note_en: context.trim(),
      });
      setSuccess(a.manualEntrySuccess(res.action));
      reset();
      onSaved();
    } catch (err) {
      setError(String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <button
        onClick={() => { setOpen(o => !o); setSuccess(null); setError(null); }}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
      >
        <span>✏️ {a.manualEntryHeading}</span>
        <span className="text-slate-400 text-xs">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <form onSubmit={handleSubmit} className="border-t border-slate-100 p-4 space-y-4">
          <p className="text-xs text-slate-500">{a.manualEntrySubtext}</p>

          {/* Topic + root checkbox */}
          <div className="flex flex-wrap gap-4 items-end">
            <div className="flex-1 min-w-[180px] space-y-1">
              <label className="block text-xs font-medium text-slate-600">{a.manualEntryTopicLabel} *</label>
              <select
                value={topicId}
                onChange={e => setTopicId(e.target.value)}
                required
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
              >
                <option value="">— select —</option>
                {topics.map(t => (
                  <option key={t.topic_id} value={t.topic_id}>{t.name_en}</option>
                ))}
              </select>
            </div>
            <label className="flex items-center gap-2 text-xs text-slate-700 pb-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isRoot}
                onChange={e => setIsRoot(e.target.checked)}
                className="rounded"
              />
              {a.manualEntryIsRoot}
            </label>
          </div>

          {/* Three language inputs */}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {/* English */}
            <div className="space-y-1">
              <label className="block text-xs font-medium text-slate-600">
                {a.manualEntryEnLabel} *
              </label>
              <textarea
                value={en}
                onChange={e => setEn(e.target.value)}
                required
                rows={3}
                placeholder={a.manualEntryEnPlaceholder}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-400"
              />
            </div>
            {/* Hebrew */}
            <div className="space-y-1">
              <label className="block text-xs font-medium text-slate-600">
                {a.manualEntryHeLabel}
              </label>
              <textarea
                value={he}
                onChange={e => setHe(e.target.value)}
                rows={3}
                dir="rtl"
                placeholder={a.manualEntryHePlaceholder}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-400 text-right"
              />
            </div>
            {/* Russian */}
            <div className="space-y-1">
              <label className="block text-xs font-medium text-slate-600">
                {a.manualEntryRuLabel}
              </label>
              <textarea
                value={ru}
                onChange={e => setRu(e.target.value)}
                rows={3}
                placeholder={a.manualEntryRuPlaceholder}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-brand-400"
              />
            </div>
          </div>

          {/* Context note */}
          <div className="space-y-1">
            <label className="block text-xs font-medium text-slate-600">{a.manualEntryContextLabel}</label>
            <input
              type="text"
              value={context}
              onChange={e => setContext(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
            />
          </div>

          {success && <p className="text-xs text-green-700 font-medium">{success}</p>}
          {error   && <p className="text-xs text-red-600">{error}</p>}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={submitting || !topicId || !en.trim()}
              className="rounded-lg bg-slate-800 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-900 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {submitting ? a.manualEntrySubmitting : a.manualEntrySubmitBtn}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

// ── Generate Tab ──────────────────────────────────────────────────────────────

function GenerateTab() {
  const a = useT().admin;
  // ManualQuestionForm needs a topics list; load it once
  const [topics, setTopics] = useState<TopicWithRootQuestion[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminGetTopicsWithRootQuestions()
      .then(setTopics)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      {/* Question Bank — primary generation path */}
      <QuestionBankPanel />

      {/* Manual entry */}
      {!loading && (
        <ManualQuestionForm topics={topics} onSaved={() => {}} />
      )}

      {/* Question browser — browse/edit/delete/explain all questions */}
      <QuestionBrowserSection />
    </div>
  );
}

// ── Question Browser Section ───────────────────────────────────────────────────

const PAGE_SIZE = 50;

const STATUS_COLORS: Record<string, string> = {
  approved: "bg-green-50 text-green-700 border-green-200",
  llm_generated: "bg-blue-50 text-blue-700 border-blue-200",
  needs_review: "bg-yellow-50 text-yellow-700 border-yellow-200",
  rejected: "bg-red-50 text-red-600 border-red-200",
  draft: "bg-slate-100 text-slate-600 border-slate-200",
};

function QuestionBrowserSection() {
  const a = useT().admin;
  const [open, setOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [items, setItems] = useState<AdminQuestionBrowserItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editEn, setEditEn] = useState("");
  const [editHe, setEditHe] = useState("");
  const [editRu, setEditRu] = useState("");
  const [explainJob, setExplainJob] = useState<BatchExplainJob | null>(null);
  const [explainMsg, setExplainMsg] = useState<string | null>(null);
  const explainPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 400);
    return () => clearTimeout(t);
  }, [search]);

  const load = useCallback(async (off = 0, reset = true) => {
    setLoading(true);
    try {
      const res = await adminListAllQuestions({
        status: statusFilter || undefined,
        search: debouncedSearch || undefined,
        limit: PAGE_SIZE,
        offset: off,
      });
      setTotal(res.total);
      if (reset) {
        setItems(res.items);
        setOffset(PAGE_SIZE);
      } else {
        setItems(prev => [...prev, ...res.items]);
        setOffset(off + PAGE_SIZE);
      }
    } finally {
      setLoading(false);
    }
  }, [statusFilter, debouncedSearch]);

  useEffect(() => {
    if (open) { load(0, true); setSelected(new Set()); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, statusFilter, debouncedSearch]);

  const stopExplainPoll = () => {
    if (explainPollRef.current) { clearInterval(explainPollRef.current); explainPollRef.current = null; }
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => () => stopExplainPoll(), []);

  /** Toggle one item selection */
  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  /** Select / deselect all visible */
  const toggleAll = () => {
    if (selected.size === items.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(items.map(i => i.id)));
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm(a.questionBrowserDeleteConfirm)) return;
    await adminDeleteQuestion(id);
    setItems(prev => prev.filter(i => i.id !== id));
    setTotal(prev => prev - 1);
    setSelected(prev => { const n = new Set(prev); n.delete(id); return n; });
  };

  const handleBulkDelete = async () => {
    const ids = Array.from(selected);
    if (!window.confirm(a.questionBrowserDeleteSelectedConfirm(ids.length))) return;
    await adminBulkDeleteQuestions(ids);
    setItems(prev => prev.filter(i => !selected.has(i.id)));
    setTotal(prev => prev - ids.length);
    setSelected(new Set());
  };

  const handleEditSave = async (id: string) => {
    await adminEditQuestion(id, { question_text_en: editEn, question_text_he: editHe, question_text_ru: editRu });
    setEditingId(null);
    load(0, true);
  };

  const handleGenerateExplanations = async () => {
    const ids = selected.size > 0 ? Array.from(selected) : items.map(i => i.id);
    if (ids.length === 0) return;
    setExplainMsg(null);
    stopExplainPoll();
    try {
      const job = await adminBatchGenerateExplanations({ question_ids: ids });
      setExplainJob(job);
      explainPollRef.current = setInterval(async () => {
        try {
          const status = await adminGetBatchExplainStatus(job.job_id);
          setExplainJob(status);
          if (status.status === "done" || status.status === "error") {
            stopExplainPoll();
            if (status.status === "done") {
              setExplainMsg(a.questionBrowserExplainDone(status.completed, status.errors));
            }
          }
        } catch { stopExplainPoll(); }
      }, 2000);
    } catch {
      setExplainMsg(a.questionBrowserExplainError);
    }
  };

  const handleGenerateAllExplanations = async () => {
    setExplainMsg(null);
    stopExplainPoll();
    try {
      const job = await adminBatchGenerateExplanations({ all_questions: true });
      setExplainJob(job);
      explainPollRef.current = setInterval(async () => {
        try {
          const status = await adminGetBatchExplainStatus(job.job_id);
          setExplainJob(status);
          if (status.status === "done" || status.status === "error") {
            stopExplainPoll();
            if (status.status === "done") {
              setExplainMsg(a.questionBrowserExplainDone(status.completed, status.errors));
            }
          }
        } catch { stopExplainPoll(); }
      }, 2000);
    } catch {
      setExplainMsg(a.questionBrowserExplainError);
    }
  };

  const isExplainRunning = explainJob?.status === "queued" || explainJob?.status === "running";

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
      >
        <span>{a.questionBrowserHeading}</span>
        <span className="text-slate-400 text-xs">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="border-t border-slate-100 p-4 space-y-4">
          <p className="text-xs text-slate-500">{a.questionBrowserSubtext}</p>

          {/* Filters */}
          <div className="flex flex-wrap gap-3 items-center">
            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700"
            >
              <option value="">{a.questionBrowserFilterAll}</option>
              <option value="approved">{a.questionBrowserFilterApproved}</option>
              <option value="llm_generated">{a.questionBrowserFilterLlmGenerated}</option>
              <option value="needs_review">{a.questionBrowserFilterNeedsReview}</option>
              <option value="rejected">{a.questionBrowserFilterRejected}</option>
              <option value="draft">{a.questionBrowserFilterDraft}</option>
            </select>
            <input
              type="search"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder={a.questionBrowserSearch}
              className="flex-1 min-w-[200px] rounded-lg border border-slate-200 px-3 py-1.5 text-sm"
            />
            <span className="text-xs text-slate-400">{a.questionBrowserCount(total)}</span>
          </div>

          {/* Bulk actions */}
          <div className="flex flex-wrap gap-2 items-center">
            <button
              onClick={toggleAll}
              className="text-xs text-brand-600 hover:underline"
            >
              {selected.size === items.length && items.length > 0 ? a.questionBrowserClearSelection : a.questionBrowserSelectAll}
            </button>
            {selected.size > 0 && (
              <button
                onClick={handleBulkDelete}
                className="rounded-lg border border-red-200 px-2.5 py-1 text-xs text-red-600 hover:bg-red-50"
              >
                {a.questionBrowserDeleteSelected(selected.size)}
              </button>
            )}
            <button
              onClick={handleGenerateExplanations}
              disabled={isExplainRunning}
              className="rounded-lg bg-blue-600 px-3 py-1 text-xs text-white font-medium hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed ms-auto"
            >
              {isExplainRunning
                ? a.questionBrowserExplainRunning(explainJob?.completed ?? 0, explainJob?.total ?? 1)
                : a.questionBrowserGenerateExplainBtn(selected.size)}
            </button>
            <button
              onClick={handleGenerateAllExplanations}
              disabled={isExplainRunning}
              title="Generate explanations for every question in the database (not just visible ones)"
              className="rounded-lg bg-indigo-600 px-3 py-1 text-xs text-white font-medium hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {isExplainRunning
                ? a.questionBrowserExplainRunning(explainJob?.completed ?? 0, explainJob?.total ?? 1)
                : a.questionBrowserGenerateAllExplainBtn}
            </button>
          </div>

          {explainMsg && (
            <p className="text-xs px-3 py-1.5 rounded-lg bg-blue-50 text-blue-700">{explainMsg}</p>
          )}

          {/* Question list */}
          {loading && items.length === 0 ? (
            <p className="text-slate-400 text-sm text-center py-8">Loading…</p>
          ) : items.length === 0 ? (
            <p className="text-slate-400 text-sm text-center py-8">{a.questionBrowserNoItems}</p>
          ) : (
            <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
              {items.map(item => (
                <div
                  key={item.id}
                  className={`rounded-lg border p-3 space-y-2 transition-colors ${
                    selected.has(item.id) ? "border-brand-300 bg-brand-50/40" : "border-slate-100 bg-white"
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      checked={selected.has(item.id)}
                      onChange={() => toggleSelect(item.id)}
                      className="mt-1 rounded shrink-0"
                    />
                    <div className="flex-1 min-w-0 space-y-1">
                      {/* Status + badges */}
                      <div className="flex flex-wrap gap-1.5 items-center">
                        <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[item.status] ?? "bg-slate-100 text-slate-600"}`}>
                          {item.status.replace("_", " ")}
                        </span>
                        {item.is_root_question && (
                          <span className="rounded-full bg-purple-50 border border-purple-200 px-2 py-0.5 text-xs text-purple-700">
                            {a.questionBrowserRootBadge}
                          </span>
                        )}
                        {item.is_stale && (
                          <span className="rounded-full bg-orange-50 border border-orange-200 px-2 py-0.5 text-xs text-orange-700">
                            {a.questionBrowserStaleBadge}
                          </span>
                        )}
                        {item.topic_name_en && (
                          <span className="text-xs text-slate-400">{item.topic_name_en}</span>
                        )}
                      </div>

                      {editingId === item.id ? (
                        <div className="space-y-2 mt-2">
                          <label className="block text-xs font-medium text-slate-500">English</label>
                          <textarea rows={2} value={editEn} onChange={e => setEditEn(e.target.value)}
                            className="w-full rounded border border-slate-200 px-2 py-1.5 text-sm resize-none" />
                          <label className="block text-xs font-medium text-slate-500">Hebrew</label>
                          <textarea rows={2} dir="rtl" value={editHe} onChange={e => setEditHe(e.target.value)}
                            className="w-full rounded border border-slate-200 px-2 py-1.5 text-sm resize-none" />
                          <label className="block text-xs font-medium text-slate-500">Russian</label>
                          <textarea rows={2} value={editRu} onChange={e => setEditRu(e.target.value)}
                            className="w-full rounded border border-slate-200 px-2 py-1.5 text-sm resize-none" />
                          <div className="flex gap-2">
                            <button onClick={() => handleEditSave(item.id)}
                              className="rounded bg-brand-600 px-3 py-1 text-xs text-white hover:bg-brand-700">
                              Save
                            </button>
                            <button onClick={() => setEditingId(null)}
                              className="rounded border border-slate-200 px-3 py-1 text-xs text-slate-600">
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="space-y-0.5">
                          <p className="text-sm text-slate-800 leading-snug">{item.question_text_en}</p>
                          {item.question_text_he && (
                            <p dir="rtl" className="text-xs text-slate-500 leading-snug">{item.question_text_he}</p>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Action buttons */}
                    {editingId !== item.id && (
                      <div className="flex gap-1 shrink-0">
                        <button
                          onClick={() => { setEditingId(item.id); setEditEn(item.question_text_en); setEditHe(item.question_text_he ?? ""); setEditRu(item.question_text_ru ?? ""); }}
                          className="rounded border border-slate-200 px-2 py-1 text-xs text-slate-500 hover:bg-slate-50"
                          title="Edit"
                        >✎</button>
                        <button
                          onClick={() => handleDelete(item.id)}
                          className="rounded border border-red-200 px-2 py-1 text-xs text-red-500 hover:bg-red-50"
                          title={a.questionBrowserDelete}
                        >✕</button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Load more */}
          {items.length < total && (
            <div className="text-center">
              <button
                onClick={() => load(offset, false)}
                disabled={loading}
                className="text-xs text-brand-600 hover:underline disabled:opacity-40"
              >
                {loading ? "Loading…" : a.questionBrowserLoadMore}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Question Bank Panel ───────────────────────────────────────────────────────

function QuestionBankPanel() {
  const a = useT().admin;
  const [maxQ, setMaxQ] = useState(300);
  const [depth, setDepth] = useState(2);
  const [workers, setWorkers] = useState(8);
  const [rootsPerTopic, setRootsPerTopic] = useState(3);
  const [force, setForce] = useState(false);
  const [generateExplanations, setGenerateExplanations] = useState(false);
  const [job, setJob] = useState<QuestionBankJobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [staleMsg, setStaleMsg] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => () => stopPoll(), []);

  const isRunning = job?.status === "queued" || job?.status === "running";

  const handleGenerate = async () => {
    setError(null);
    setJob(null);
    stopPoll();
    try {
      const res = await adminGenerateQuestionBank({
        max_questions: maxQ,
        depth_levels: depth,
        max_workers: workers,
        force_regenerate: force,
        root_questions_per_topic: rootsPerTopic,
        generate_explanations: generateExplanations,
      });
      setJob({ job_id: res.job_id, status: "queued", max_questions: maxQ, depth_levels: depth });
      pollRef.current = setInterval(async () => {
        try {
          const status = await adminGetQuestionBankStatus(res.job_id);
          setJob(status);
          if (status.status === "done" || status.status === "error") stopPoll();
        } catch { stopPoll(); }
      }, 3000);
    } catch (e) {
      setError(String(e));
    }
  };

  const handleMarkStale = async () => {
    setStaleMsg(null);
    try {
      const res = await adminMarkStaleQuestions();
      setStaleMsg(a.markStaleDone(res.marked_stale));
    } catch {
      setStaleMsg(a.markStaleError);
    }
  };

  return (
    <div className="rounded-xl border-2 border-amber-200 bg-amber-50/40 p-5 space-y-4 mt-6">
      <div className="space-y-1">
        <p className="text-sm font-semibold text-amber-900">{a.questionBankHeading}</p>
        <p className="text-xs text-slate-600">{a.questionBankSubtext}</p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:flex sm:flex-wrap sm:items-center sm:gap-4">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-slate-600">{a.questionBankMaxQuestionsLabel}</span>
          <input
            type="number" min={10} max={500} value={maxQ}
            onChange={e => setMaxQ(Math.max(10, Math.min(500, Number(e.target.value))))}
            disabled={isRunning}
            className="w-24 rounded-lg border border-slate-200 px-2 py-1 text-sm text-center"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-slate-600">{a.questionBankDepthLabel.split("(")[0].trim()}</span>
          <select
            value={depth}
            onChange={e => setDepth(Number(e.target.value))}
            disabled={isRunning}
            className="rounded-lg border border-slate-200 px-2 py-1 text-sm"
          >
            <option value={0}>0 — roots only</option>
            <option value={1}>1 — + policy items</option>
            <option value={2}>2 — full tree (recommended)</option>
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-slate-600">{a.questionBankWorkersLabel}</span>
          <input
            type="number" min={1} max={15} value={workers}
            onChange={e => setWorkers(Math.max(1, Math.min(15, Number(e.target.value))))}
            disabled={isRunning}
            className="w-16 rounded-lg border border-slate-200 px-2 py-1 text-sm text-center"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-slate-600">Корн. вопр. / тему</span>
          <input
            type="number" min={1} max={10} value={rootsPerTopic}
            onChange={e => setRootsPerTopic(Math.max(1, Math.min(10, Number(e.target.value))))}
            disabled={isRunning}
            className="w-16 rounded-lg border border-slate-200 px-2 py-1 text-sm text-center"
            title="Количество корневых вопросов (depth=0) на каждую тему. Все они идут в пул опросника."
          />
        </label>
        <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer pt-4">
          <input type="checkbox" checked={force} onChange={e => setForce(e.target.checked)} disabled={isRunning} className="rounded" />
          {a.questionBankForceLabel}
        </label>
        <label className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer pt-4">
          <input
            type="checkbox"
            checked={generateExplanations}
            onChange={e => setGenerateExplanations(e.target.checked)}
            disabled={isRunning}
            className="rounded"
          />
          <span className="flex flex-col gap-0.5">
            <span>{a.questionBankGenerateExplanationsLabel}</span>
            {generateExplanations && (
              <span className="text-amber-700 font-medium">
                ⚠️ Значительно увеличивает время генерации (×3 вызова LLM на вопрос)
              </span>
            )}
          </span>
        </label>
      </div>

      <div className="flex gap-3 flex-wrap items-center">
        <button
          onClick={handleGenerate}
          disabled={isRunning}
          className="rounded-lg bg-amber-700 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-800 disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
        >
          {isRunning ? "⏳ " + a.questionBankGenerating : a.questionBankGenerateBtn}
        </button>
      </div>

      {/* Progress */}
      {job && (
        <div className="space-y-1">
          {isRunning && (
            <>
              <div className="w-full bg-slate-200 rounded-full h-1.5">
                <div className="bg-amber-500 h-1.5 rounded-full transition-all animate-pulse" style={{ width: "60%" }} />
              </div>
              <p className="text-xs text-slate-600">
                {job.step
                  ? job.step === "generate_explanations"
                    ? `💬 Генерация объяснений: ${job.step_completed ?? 0} / ${job.step_total ?? 0}`
                    : a.questionBankRunning(job.step, job.step_completed ?? 0, job.step_total ?? 0)
                  : a.questionBankGenerating}
              </p>
            </>
          )}
          {job.status === "done" && (
            <div className="space-y-1">
              <p className="text-xs text-green-700 font-medium">
                ✅ {a.questionBankDone(job.created ?? 0, job.skipped ?? 0, job.errors ?? 0, job.stale_marked ?? 0)}
                {job.explanations_generated !== undefined && (
                  <span className="ms-2 text-slate-600">
                    · {job.explanations_generated} объяснений сгенерировано
                    {job.explanations_errors ? `, ${job.explanations_errors} ошибок` : ""}
                  </span>
                )}
              </p>
              {job.message && (
                <p className="text-xs text-slate-500 italic">{job.message}</p>
              )}
              {(job.created ?? 0) === 0 && (job.errors ?? 0) === 0 && (
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">
                  💡 0 questions created. Either all eligible policy items already have questions (try <strong>Force regenerate</strong>), or no policy items are in <em>approved / needs_review / llm_generated</em> status. Run the LLM policy-item pipeline first if you have a fresh data import.
                </p>
              )}
            </div>
          )}
          {job.status === "error" && (
            <p className="text-xs text-red-600">❌ {a.questionBankError} {job.error}</p>
          )}
        </div>
      )}

      {staleMsg && (
        <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-2 py-1">{staleMsg}</p>
      )}

      {error && (
        <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1">{error}</p>
      )}
    </div>
  );
}


// ── Full Pipeline Wizard ──────────────────────────────────────────────────────

function FullPipelineWizardSection() {
  const a = useT().admin;
  const [lastN, setLastN] = useState(4);
  const [noLlm, setNoLlm] = useState(true);
  const [currentKn, setCurrentKn] = useState(26);
  const [submitting, setSubmitting] = useState(false);
  const [job, setJob] = useState<FullPipelineJobStatus | null>(null);
  const ivRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Preview which Knessets would be imported based on lastN and currentKn.
  const previewKnessets = Array.from({ length: lastN }, (_, i) => currentKn - i);

  const stopPolling = () => {
    if (ivRef.current) { clearInterval(ivRef.current); ivRef.current = null; }
  };

  // Cleanup on unmount
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => () => stopPolling(), []);

  const startPolling = (jobId: string) => {
    stopPolling();
    ivRef.current = setInterval(async () => {
      try {
        const status = await adminGetFullPipelineStatus(jobId);
        setJob(status);
        if (status.status === "done" || status.status === "error") stopPolling();
      } catch {
        stopPolling();
        setJob((prev) => prev ? { ...prev, status: "error", error: "Polling failed." } : prev);
      }
    }, 2500);
  };

  const handleRun = async () => {
    setSubmitting(true);
    setJob(null);
    try {
      const res = await adminTriggerFullPipeline({ last_n_knessets: lastN, no_llm: noLlm, current_knesset: currentKn });
      const initial: FullPipelineJobStatus = {
        job_id: res.job_id,
        status: "queued",
        mode: "full_pipeline",
        knessets: res.knessets,
        no_llm: noLlm,
      };
      setJob(initial);
      startPolling(res.job_id);
    } catch (err) {
      setJob({ job_id: "—", status: "error", error: String(err) });
    } finally {
      setSubmitting(false);
    }
  };

  const isRunning = job?.status === "running" || job?.status === "queued";

  // ── Available data state ────────────────────────────────────────────────
  const [availData, setAvailData] = useState<AvailableKnessetData | null>(null);
  const [availDataLoading, setAvailDataLoading] = useState(true);
  const [availDataError, setAvailDataError] = useState(false);

  const loadAvailData = useCallback(() => {
    setAvailDataLoading(true);
    setAvailDataError(false);
    adminGetAvailableKnessetData()
      .then(setAvailData)
      .catch(() => setAvailDataError(true))
      .finally(() => setAvailDataLoading(false));
  }, []);

  useEffect(() => { loadAvailData(); }, [loadAvailData]);

  const statusColors: Record<string, string> = {
    queued:  "bg-slate-100 text-slate-700 border-slate-200",
    running: "bg-blue-50 text-blue-800 border-blue-200",
    done:    "bg-green-50 text-green-800 border-green-200",
    error:   "bg-red-50 text-red-700 border-red-200",
  };

  const knessetStatusBadge = (kr: FullPipelineKnessetResult) => {
    if (kr.status === "done") return <span className="text-xs text-green-700">✓ {a.pipelineWizardKnessetDone(kr.knesset_number)}</span>;
    if (kr.status === "running") return <span className="text-xs text-blue-700 animate-pulse">⟳ {a.pipelineWizardKnessetRunning(kr.knesset_number)}</span>;
    return <span className="text-xs text-slate-400">{a.pipelineWizardKnessetPending}</span>;
  };

  return (
    <div className="rounded-2xl border-2 border-brand-200 bg-brand-50/60 p-5 space-y-4">
      {/* ── Available data summary ───────────────────────────────────────── */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        {/* Header bar */}
        <div className="flex items-center justify-between px-4 py-2.5 bg-slate-50 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <span className="text-sm">🗄️</span>
            <p className="text-xs font-semibold text-slate-700 tracking-wide">
              {a.availableDataHeading}
            </p>
          </div>
          <button
            onClick={loadAvailData}
            disabled={availDataLoading}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-brand-700 disabled:opacity-40 transition-colors rounded px-1.5 py-0.5 hover:bg-slate-100"
          >
            <span className={availDataLoading ? "animate-spin inline-block" : ""}>↻</span>
            {a.availableDataRefresh}
          </button>
        </div>

        {/* Body */}
        <div className="px-4 py-3">
          {availDataLoading && (
            <div className="flex items-center gap-2 text-xs text-slate-400 py-1">
              <span className="inline-block h-3 w-3 rounded-full border-2 border-slate-300 border-t-brand-400 animate-spin" />
              {a.availableDataLoading}
            </div>
          )}
          {availDataError && (
            <p className="text-xs text-red-500 py-1">{a.availableDataError}</p>
          )}
          {!availDataLoading && !availDataError && availData && (
            availData.knessets.length === 0 ? (
              <p className="text-xs text-slate-400 py-1 italic">{a.availableDataEmpty}</p>
            ) : (
              <div className="space-y-3">
                {/* Knesset timeline pills */}
                <div className="space-y-1">
                  <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">{a.availableDataPerKnesset}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {(() => {
                      const maxVotes = Math.max(...availData.knessets.map((kn: number) => availData.vote_counts[String(kn)] ?? 0), 1);
                      return availData.knessets.map((kn: number) => {
                        const votes = availData.vote_counts[String(kn)] ?? 0;
                        const factions = availData.faction_counts[String(kn)] ?? 0;
                        const pct = Math.round((votes / maxVotes) * 100);
                        const hasVotes = votes > 0;
                        return (
                          <div
                            key={kn}
                            title={`${votes.toLocaleString()} votes · ${factions} factions`}
                            className="relative flex flex-col items-center rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 min-w-[52px] overflow-hidden group"
                          >
                            {/* Vote fill bar at bottom */}
                            {hasVotes && (
                              <div
                                className="absolute bottom-0 left-0 right-0 bg-brand-100 transition-all"
                                style={{ height: `${Math.max(pct * 0.4, 3)}%` }}
                              />
                            )}
                            <span className="relative text-xs font-bold text-slate-700 leading-none">{kn}</span>
                            {hasVotes && (
                              <span className="relative text-[9px] text-brand-600 font-medium mt-0.5 leading-none">
                                {votes >= 1000 ? `${(votes / 1000).toFixed(1)}k` : votes}
                              </span>
                            )}
                            {!hasVotes && factions > 0 && (
                              <span className="relative text-[9px] text-slate-400 mt-0.5 leading-none">{factions}f</span>
                            )}
                          </div>
                        );
                      });
                    })()}
                  </div>
                </div>

                {/* Global stat chips */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {[
                    { icon: "🗳️", value: availData.total_votes,        label: a.availableDataVotes(availData.total_votes) },
                    { icon: "📜", value: availData.total_bills,         label: a.availableDataBills(availData.total_bills) },
                    { icon: "👤", value: availData.total_persons,       label: a.availableDataPersons(availData.total_persons) },
                    { icon: "📊", value: availData.total_vote_results,  label: a.availableDataVoteResults(availData.total_vote_results) },
                  ].filter(s => s.value > 0).map(({ icon, value, label }) => (
                    <div key={icon} className="flex items-center gap-2 rounded-lg bg-slate-50 border border-slate-100 px-3 py-2">
                      <span className="text-base leading-none">{icon}</span>
                      <div className="min-w-0">
                        <p className="text-xs font-bold text-slate-800 tabular-nums">{value.toLocaleString()}</p>
                        <p className="text-[10px] text-slate-400 truncate">{label.replace(/^[\d,\.]+\s*/, "")}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )
          )}
        </div>
      </div>

      {/* ── Heading */}
      <div className="space-y-1">
        <h2 className="text-base font-semibold text-brand-800 flex items-center gap-2">
          <span className="text-lg">🚀</span>
          {a.pipelineWizardHeading}
        </h2>
        <p className="text-xs text-slate-600">{a.pipelineWizardSubtext}</p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-end gap-4">
        {/* Current Knesset input */}
        <div className="space-y-1">
          <label className="block text-xs font-medium text-slate-600">
            {a.pipelineWizardCurrentKnessetLabel}
          </label>
          <input
            type="number"
            min={1}
            max={40}
            value={currentKn}
            onChange={(e) => setCurrentKn(Math.max(1, Math.min(40, Number(e.target.value))))}
            className="w-20 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-center"
          />
        </div>

        {/* Last N input */}
        <div className="space-y-1">
          <label className="block text-xs font-medium text-slate-600">
            {a.pipelineWizardLastNLabel}
          </label>
          <input
            type="number"
            min={1}
            max={10}
            value={lastN}
            onChange={(e) => setLastN(Math.max(1, Math.min(10, Number(e.target.value))))}
            className="w-20 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-center"
          />
        </div>

        {/* No-LLM toggle */}
        <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer pb-1">
          <input
            type="checkbox"
            checked={noLlm}
            onChange={(e) => setNoLlm(e.target.checked)}
            className="accent-brand-600 h-4 w-4"
          />
          {a.pipelineWizardNoLlmLabel}
        </label>

        {/* Run button */}
        <button
          onClick={handleRun}
          disabled={submitting || isRunning}
          className="rounded-xl bg-brand-600 px-6 py-2.5 text-sm font-semibold text-white shadow hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
        >
          {isRunning ? (
            <span className="flex items-center gap-2">
              <span className="inline-block h-3 w-3 rounded-full border-2 border-white border-t-transparent animate-spin" />
              {a.ingestRunning}
            </span>
          ) : (
            a.pipelineWizardRunBtn
          )}
        </button>
      </div>

      {/* Notes */}
      <div className="space-y-1.5">
        <p className="text-xs text-slate-500">{a.pipelineWizardKnessetsLabel(previewKnessets)}</p>
        <p className="text-xs rounded-lg bg-sky-50 border border-sky-200 text-sky-800 px-3 py-2 leading-relaxed">
          {a.pipelineWizardCurrentKnessetNote(currentKn)}
        </p>
        {noLlm ? (
          <p className="text-xs text-slate-400">{a.pipelineWizardNoLlmNote}</p>
        ) : (
          <p className="text-xs rounded-lg bg-amber-50 border border-amber-300 text-amber-800 px-3 py-2 font-medium">
            {a.pipelineWizardLlmCostWarning}
          </p>
        )}
      </div>

      {/* Progress display */}
      {job && (
        <div className={`rounded-xl border p-4 space-y-3 text-sm ${statusColors[job.status] ?? "bg-slate-50 border-slate-200"}`}>
          {/* Header row */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-semibold">
              {job.status === "done" ? a.pipelineWizardDone
               : job.status === "error" ? a.pipelineWizardError
               : `${a.pipelineWizardStatusPrefix} ${job.status}`}
            </span>
            {isRunning && (
              <span className="inline-block h-3 w-3 rounded-full border-2 border-current border-t-transparent animate-spin" />
            )}
            {job.current_step && (
              <span className="text-xs opacity-75">{a.pipelineWizardCurrentStep(job.current_step)}</span>
            )}
            <span className="text-xs opacity-50 ms-auto">{a.ingestJobId}: {job.job_id}</span>
          </div>

          {/* Phase 1: per-Knesset results */}
          {job.knessets && job.knessets.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-semibold opacity-80">{a.pipelineWizardPhase1}</p>
              <div className="space-y-1 ps-3">
                {job.knessets.map((kn) => {
                  const kr = job.knesset_results?.[String(kn)];
                  return (
                    <div key={kn} className="text-xs space-y-0.5">
                      {kr ? knessetStatusBadge(kr) : (
                        <span className="text-slate-400">Knesset {kn}: {a.pipelineWizardKnessetPending}</span>
                      )}
                      {kr && kr.factions && (
                        <p className="ps-4 text-xs opacity-70">
                          ✓ {a.ingestResultFactions(
                            (kr.factions as Record<string, number>).inserted ?? 0,
                            (kr.factions as Record<string, number>).updated ?? 0
                          )}
                        </p>
                      )}
                      {kr && kr.votes && !("reason" in (kr.votes as Record<string, unknown>)) && (
                        <p className="ps-4 text-xs opacity-70">
                          ✓ {a.ingestResultVotes(
                            (kr.votes as Record<string, number>).inserted ?? 0,
                            (kr.votes as Record<string, number>).updated ?? 0,
                            (kr.votes as Record<string, number>).skipped ?? 0
                          )}
                        </p>
                      )}
                      {kr && kr.votes && "reason" in (kr.votes as Record<string, unknown>) && (
                        <p className="ps-4 text-xs opacity-60">⚠ {a.pipelineWizardVotesSkipped}</p>
                      )}
                      {kr && kr.bills && (
                        <p className="ps-4 text-xs opacity-70">
                          ✓ {a.ingestResultBills(
                            (kr.bills as Record<string, number>).inserted ?? 0,
                            (kr.bills as Record<string, number>).skipped ?? 0
                          )}
                        </p>
                      )}
                      {kr && kr.persons && (
                        <p className="ps-4 text-xs opacity-70">
                          ✓ {a.ingestResultPersons(
                            (kr.persons as Record<string, number>).inserted ?? 0,
                            (kr.persons as Record<string, number>).skipped ?? 0
                          )}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Phase 2: analysis pipeline results */}
          {(job.policy_items || job.party_positions || job.lineage || job.volatility) && (
            <div className="space-y-1">
              <p className="text-xs font-semibold opacity-80">{a.pipelineWizardPhase2}</p>
              <div className="space-y-0.5 ps-3">
                {job.policy_items && <p className="text-xs opacity-70">✓ {a.ingestResultPolicyItems((job.policy_items as Record<string, number>).created ?? 0, (job.policy_items as Record<string, number>).skipped ?? 0)}</p>}
                {job.party_positions && <p className="text-xs opacity-70">✓ {a.ingestResultPartyPositions((job.party_positions as Record<string, number>).positions_created ?? 0, (job.party_positions as Record<string, number>).positions_updated ?? 0)}</p>}
                {job.lineage && <p className="text-xs opacity-70">✓ {a.ingestResultLineage((job.lineage as Record<string, number>).edges_proposed ?? 0)}</p>}
                {job.volatility && <p className="text-xs opacity-70">✓ {a.ingestResultVolatility((job.volatility as Record<string, number>).candidates_updated ?? 0, (job.volatility as Record<string, number>).parties_updated ?? 0)}</p>}
              </div>
            </div>
          )}

          {job.error && (
            <p className="text-xs font-medium text-red-700 bg-red-50 rounded px-2 py-1">{job.error}</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Ingestion Tab ─────────────────────────────────────────────────────────────

/** Show detailed results for all steps that have completed. */
function JobStepDetails({ job, a }: {
  job: IngestionJobStatus;
  a: ReturnType<typeof useT>["admin"];
}) {
  const hasAny =
    job.factions || job.votes || job.bills || job.persons || job.vote_results ||
    job.policy_items || job.party_positions || job.questions || job.lineage ||
    job.volatility || job.error;
  if (!hasAny) return null;
  return (
    <div className="space-y-1 pt-2 mt-2 border-t border-current/10">
      {job.factions      && <p className="text-xs">✓ {a.ingestResultFactions(job.factions.inserted ?? 0, job.factions.updated ?? 0)}</p>}
      {job.votes         && <p className="text-xs">✓ {a.ingestResultVotes(job.votes.inserted ?? 0, job.votes.updated ?? 0, job.votes.skipped ?? 0)}</p>}
      {job.bills         && <p className="text-xs">✓ {a.ingestResultBills(job.bills.inserted ?? 0, job.bills.skipped ?? 0)}</p>}
      {job.persons       && <p className="text-xs">✓ {a.ingestResultPersons(job.persons.inserted ?? 0, job.persons.skipped ?? 0)}</p>}
      {job.vote_results  && <p className="text-xs">✓ {a.ingestResultVoteResults(job.vote_results.inserted ?? 0, job.vote_results.skipped ?? 0)}</p>}
      {job.policy_items  && <p className="text-xs">✓ {a.ingestResultPolicyItems(job.policy_items.created ?? 0, job.policy_items.skipped ?? 0)}</p>}
      {job.party_positions && <p className="text-xs">✓ {a.ingestResultPartyPositions(job.party_positions.positions_created ?? 0, job.party_positions.positions_updated ?? 0)}</p>}
      {job.questions     && <p className="text-xs">✓ {a.ingestResultQuestions(job.questions.created ?? 0, job.questions.skipped ?? 0)}</p>}
      {job.lineage       && <p className="text-xs">✓ {a.ingestResultLineage(job.lineage.edges_proposed ?? 0)}</p>}
      {job.volatility    && <p className="text-xs">✓ {a.ingestResultVolatility(job.volatility.candidates_updated ?? 0, job.volatility.parties_updated ?? 0)}</p>}
      {job.error         && <p className="text-xs text-red-600 font-medium">{job.error}</p>}
    </div>
  );
}

function IngestionTab() {
  const a = useT().admin;
  const [knessetNum, setKnessetNum] = useState(25);
  const [limit, setLimit] = useState(200);
  const [noLlm, setNoLlm] = useState(false);
  const [votesOnly, setVotesOnly] = useState(false);
  const [billsOnly, setBillsOnly] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [activeJob, setActiveJob] = useState<IngestionJobStatus | null>(null);
  const [jobs, setJobs] = useState<IngestionJobStatus[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [showManual, setShowManual] = useState(false);
  // Store the interval ID in a ref so polling callbacks always see the latest
  // value without creating circular useCallback dependencies.
  const ivRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    adminListIngestionJobs().then(setJobs).finally(() => setLoadingJobs(false));
  }, []);

  const stopPolling = useCallback(() => {
    if (ivRef.current) { clearInterval(ivRef.current); ivRef.current = null; }
  }, []);

  const startPolling = useCallback((jobId: string) => {
    stopPolling();
    ivRef.current = setInterval(async () => {
      try {
        const status = await adminGetIngestionStatus(jobId);
        setActiveJob(status);
        if (status.status === "done" || status.status === "error") {
          stopPolling();
          adminListIngestionJobs().then(setJobs);
        }
      } catch {
        // Polling failed (e.g. network error or 404 from a different Docker worker).
        // Reset to error so the Start button re-enables.
        stopPolling();
        setActiveJob((prev) =>
          prev ? { ...prev, status: "error", error: "Polling failed — job status unavailable." } : prev
        );
      }
    }, 2000);
  }, [stopPolling]);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const handleStart = async () => {
    setSubmitting(true);
    setActiveJob(null);
    try {
      const res = await adminTriggerIngestion({
        knesset_number: knessetNum, limit,
        no_llm: noLlm, votes_only: votesOnly, bills_only: billsOnly,
      });
      const job: IngestionJobStatus = {
        job_id: res.job_id, status: "queued",
        knesset_number: knessetNum, limit, no_llm: noLlm,
      };
      setActiveJob(job);
      startPolling(res.job_id);
    } catch (err) {
      setActiveJob({ job_id: "—", status: "error", error: String(err) });
    } finally {
      setSubmitting(false);
    }
  };

  const isRunning = activeJob?.status === "running" || activeJob?.status === "queued";

  const statusColors: Record<string, string> = {
    queued: "bg-slate-100 text-slate-600",
    running: "bg-blue-50 text-blue-700",
    done: "bg-green-50 text-green-700",
    error: "bg-red-50 text-red-600",
  };

  const statusLabel = (s: string) =>
    s === "queued" ? a.ingestQueued
    : s === "running" ? a.ingestRunning
    : s === "done" ? a.ingestDone
    : a.ingestError;

  return (
    <div className="space-y-6">
      {/* ── Full Pipeline Wizard ────────────────────────────────────────── */}
      <FullPipelineWizardSection />

      {/* ── Divider / Manual section toggle ────────────────────────────── */}
      <div className="border-t border-slate-200 pt-4">
        <button
          onClick={() => setShowManual((v) => !v)}
          className="flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors"
        >
          {showManual ? a.ingestManualHideBtn : a.ingestManualShowBtn}
        </button>
        {showManual && (
          <p className="text-xs text-slate-400 mt-1">{a.ingestManualSubtext}</p>
        )}
      </div>

      {showManual && (
        <>
          <div className="space-y-1">
            <p className="text-sm font-medium text-slate-700">{a.ingestManualTitle}</p>
            <p className="text-xs text-slate-400">{a.ingestSubtext}</p>
          </div>

          <div className="grid grid-cols-2 gap-4 max-w-sm">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">{a.ingestKnessetLabel}</label>
              <input
                type="number" min={1} max={30} value={knessetNum}
                onChange={(e) => setKnessetNum(Number(e.target.value))}
                className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-sm"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">{a.ingestLimitLabel}</label>
              <input
                type="number" min={10} max={5000} step={50} value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-sm"
              />
            </div>
          </div>

          {/* K25+ warning: official Votes.svc does not yet have data for Knesset 25+ */}
          {knessetNum >= 25 && (
            <p className="text-xs rounded-lg bg-amber-50 border border-amber-200 text-amber-800 px-3 py-2 leading-relaxed">
              {a.ingestKnesset25Warning}
            </p>
          )}

          <div className="flex flex-wrap gap-4 text-sm">
            {([
              [noLlm,      setNoLlm,      a.ingestNoLlmLabel],
              [votesOnly,  setVotesOnly,  a.ingestVotesOnlyLabel],
              [billsOnly,  setBillsOnly,  a.ingestBillsOnlyLabel],
            ] as [boolean, (v: boolean) => void, string][]).map(([val, setter, label], i) => (
              <label key={i} className="flex items-center gap-2 cursor-pointer text-slate-600">
                <input type="checkbox" checked={val} onChange={(e) => setter(e.target.checked)} className="accent-brand-600" />
                {label}
              </label>
            ))}
          </div>

          <button
            onClick={handleStart}
            disabled={submitting || isRunning}
            className="rounded-lg bg-brand-600 px-5 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {submitting ? a.ingestRunning : a.ingestRunBtn}
          </button>

          {activeJob && (
            <div className={`rounded-xl border p-4 space-y-1 text-sm ${statusColors[activeJob.status] ?? "bg-slate-50"}`}>
              <div className="flex items-center gap-3 flex-wrap">
                <span className="font-medium">{statusLabel(activeJob.status)}</span>
                {isRunning && (
                  <span className="inline-block h-3 w-3 rounded-full border-2 border-current border-t-transparent animate-spin" aria-hidden="true" />
                )}
                <span className="text-xs opacity-60">{a.ingestJobId}: {activeJob.job_id}</span>
                {!isRunning && (
                  <button
                    onClick={() => adminGetIngestionStatus(activeJob.job_id).then(setActiveJob).catch(() => {})}
                    className="text-xs underline opacity-70 hover:opacity-100"
                  >
                    {a.ingestPollBtn}
                  </button>
                )}
              </div>
              <JobStepDetails job={activeJob} a={a} />
            </div>
          )}

          {!loadingJobs && jobs.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Previous jobs (this session)</p>
              <div className="space-y-1">
                {jobs.slice().reverse().map((job) => (
                  <div key={job.job_id} className="rounded-lg border border-slate-100 bg-white px-3 py-2 text-xs text-slate-600">
                    <div className="flex flex-wrap items-center gap-3">
                      <span className={`rounded-full px-2 py-0.5 ${statusColors[job.status] ?? ""}`}>{statusLabel(job.status)}</span>
                      <span>Knesset {job.knesset_number} · limit {job.limit}</span>
                      <span className="text-slate-400">{job.job_id}</span>
                    </div>
                    <JobStepDetails job={job} a={a} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Backup Tab ────────────────────────────────────────────────────────────────

function BackupTab() {
  const a = useT().admin;
  const [downloading, setDownloading] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [skipExisting, setSkipExisting] = useState(true);
  const [restoreResult, setRestoreResult] = useState<{ total_inserted: number; total_skipped: number } | null>(null);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      await adminDownloadBackup();
    } finally {
      setDownloading(false);
    }
  };

  const handleRestore = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setRestoring(true);
    setRestoreResult(null);
    setRestoreError(null);
    try {
      const result = await adminRestoreBackup(file, skipExisting);
      setRestoreResult(result);
    } catch (e) {
      setRestoreError(String(e));
    } finally {
      setRestoring(false);
    }
  };

  return (
    <div className="space-y-8 max-w-lg">
      {/* Download */}
      <div className="space-y-3">
        <h2 className="text-base font-semibold text-slate-800">{a.backupHeading}</h2>
        <p className="text-xs text-slate-500">{a.backupSubtext}</p>
        <button
          onClick={handleDownload}
          disabled={downloading}
          className="rounded-lg bg-brand-600 px-5 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {downloading ? a.backupDownloading : a.backupDownloadBtn}
        </button>
      </div>

      <hr className="border-slate-200" />

      {/* Restore */}
      <div className="space-y-3">
        <h2 className="text-base font-semibold text-slate-800">{a.backupRestoreHeading}</h2>
        <p className="text-xs text-slate-500">{a.backupRestoreSubtext}</p>
        <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
          <input
            type="checkbox"
            checked={skipExisting}
            onChange={(e) => setSkipExisting(e.target.checked)}
            className="accent-brand-600 h-4 w-4"
          />
          {a.backupSkipExistingLabel}
        </label>
        <div className="flex items-center gap-3 flex-wrap">
          <input
            ref={fileRef}
            type="file"
            accept=".json,application/json"
            className="text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-brand-700 hover:file:bg-brand-100"
          />
          <button
            onClick={handleRestore}
            disabled={restoring}
            className="rounded-lg bg-slate-700 px-5 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {restoring ? a.backupRestoring : a.backupRestoreBtn}
          </button>
        </div>
        {restoreResult && (
          <p className="text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
            ✓ {a.backupRestoreSuccess(restoreResult.total_inserted, restoreResult.total_skipped)}
          </p>
        )}
        {restoreError && (
          <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            ✗ {a.backupRestoreError}
            <span className="block mt-1 text-slate-500 break-all">{restoreError}</span>
          </p>
        )}
      </div>
    </div>
  );
}

// ── Audit Tab ─────────────────────────────────────────────────────────────────

function AuditTab() {
  const a = useT().admin;
  const [outputs, setOutputs] = useState<LlmOutputRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { adminGetLlmOutputs(50).then(setOutputs).finally(() => setLoading(false)); }, []);

  const entityColors: Record<string, string> = {
    question: "bg-blue-50 text-blue-700",
    policy_item: "bg-purple-50 text-purple-700",
    party_position: "bg-green-50 text-green-700",
    bill_or_vote: "bg-orange-50 text-orange-700",
  };

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-500">{a.auditHeading}</p>
      {loading ? (
        <p className="text-slate-400 text-sm py-10 text-center">Loading…</p>
      ) : outputs.length === 0 ? (
        <div className="rounded-xl border border-slate-100 bg-slate-50 p-8 text-center text-slate-400 text-sm">{a.auditNoData}</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500">
                <th className="py-2 pe-4">{a.auditColWhen}</th>
                <th className="py-2 pe-4">{a.auditColProvider}</th>
                <th className="py-2 pe-4">{a.auditColType}</th>
                <th className="py-2 pe-4">{a.auditColConfidence}</th>
                <th className="py-2">{a.auditColSummary}</th>
              </tr>
            </thead>
            <tbody>
              {outputs.map((row) => (
                <tr key={row.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="py-2 pe-4 text-slate-400 whitespace-nowrap">{row.created_at ? new Date(row.created_at).toLocaleString() : "—"}</td>
                  <td className="py-2 pe-4 text-slate-600 whitespace-nowrap"><span className="font-medium">{row.provider}</span><br /><span className="text-slate-400">{row.model}</span></td>
                  <td className="py-2 pe-4">
                    {row.entity_type ? <span className={`rounded-full px-2 py-0.5 ${entityColors[row.entity_type] ?? "bg-slate-100 text-slate-600"}`}>{row.entity_type}</span> : "—"}
                  </td>
                  <td className="py-2 pe-4 text-slate-500">{row.confidence != null ? `${(row.confidence * 100).toFixed(0)}%` : "—"}</td>
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

// ── Deduplication Tab ─────────────────────────────────────────────────────────

interface DuplicateGroup {
  canonical_id: string;
  canonical_name: string;
  duplicate_ids: string[];
  duplicate_names: string[];
  reason: string;
}

function DedupTab() {
  const [groups, setGroups] = useState<DuplicateGroup[]>([]);
  const [source, setSource] = useState("");
  const [loading, setLoading] = useState(false);
  const [merging, setMerging] = useState<string | null>(null);
  const [done, setDone] = useState<string[]>([]);
  const [error, setError] = useState("");

  const findDuplicates = async () => {
    setLoading(true);
    setError("");
    setGroups([]);
    setDone([]);
    try {
      const data = await adminApiFetch<{ source: string; duplicate_groups: DuplicateGroup[] }>(
        "/api/admin/parties/find-duplicates",
        { method: "POST" }
      );
      setGroups(data.duplicate_groups ?? []);
      setSource(data.source ?? "");
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const merge = async (g: DuplicateGroup) => {
    setMerging(g.canonical_id);
    try {
      await adminApiFetch("/api/admin/parties/merge", {
        method: "POST",
        body: JSON.stringify({ canonical_id: g.canonical_id, duplicate_ids: g.duplicate_ids }),
      });
      setDone((d) => [...d, g.canonical_id]);
    } catch (e) {
      setError(String(e));
    } finally {
      setMerging(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold text-slate-900">Party Deduplication</h2>
        <p className="text-sm text-slate-500">
          Deduplication runs <strong>automatically</strong> after every faction import.
          Use the buttons below to run it manually or review what would be merged.
        </p>
      </div>

      <div className="flex gap-3 flex-wrap">
        <button
          onClick={async () => {
            setLoading(true); setError(""); setGroups([]); setDone([]);
            try {
              // Start background job — returns immediately
              const job = await adminApiFetch<{ job_id: string; status: string }>(
                "/api/admin/parties/deduplicate", { method: "POST" }
              );
              // Poll until done
              let attempts = 0;
              while (attempts < 120) {
                await new Promise(r => setTimeout(r, 2000));
                const status = await adminApiFetch<{ status: string; merged_count?: number; groups?: DuplicateGroup[]; error?: string }>(
                  `/api/admin/ingest/status/${job.job_id}`
                );
                if (status.status === "done") {
                  setSource("auto");
                  const g = (status.groups ?? []) as DuplicateGroup[];
                  setGroups(g);
                  setDone(g.map((x: DuplicateGroup) => x.canonical_id));
                  break;
                }
                if (status.status === "error") {
                  setError(status.error ?? "Unknown error");
                  break;
                }
                attempts++;
              }
            } catch (e) { setError(String(e)); }
            finally { setLoading(false); }
          }}
          disabled={loading}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-40"
        >
          {loading ? "Running…" : "▶ Run auto-deduplication now"}
        </button>
        <button
          onClick={findDuplicates}
          disabled={loading}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
        >
          {loading ? "Scanning…" : "🔍 Preview duplicates (review before merge)"}
        </button>
      </div>

      {source && (
        <p className="text-xs text-slate-400">Source: {source}</p>
      )}

      {error && (
        <p className="text-sm text-red-600 bg-red-50 rounded px-3 py-2">{error}</p>
      )}

      {!loading && groups.length === 0 && source && (
        <p className="text-sm text-green-700 bg-green-50 rounded px-3 py-2">
          ✓ No duplicate groups found.
        </p>
      )}

      <div className="space-y-4">
        {groups.map((g) => {
          const isDone = done.includes(g.canonical_id);
          return (
            <div
              key={g.canonical_id}
              className={`rounded-xl border p-4 space-y-3 ${
                isDone ? "border-green-200 bg-green-50 opacity-60" : "border-slate-200 bg-white"
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium uppercase text-slate-400">Keep</span>
                    <span className="font-semibold text-slate-900">{g.canonical_name}</span>
                    <span className="text-xs text-slate-400 font-mono">{g.canonical_id.slice(0, 8)}…</span>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="text-xs font-medium uppercase text-slate-400 mt-0.5">Merge</span>
                    <div className="flex flex-wrap gap-1">
                      {g.duplicate_names.map((n, i) => (
                        <span key={i} className="rounded-full bg-orange-100 text-orange-800 px-2 py-0.5 text-xs">
                          {n}
                        </span>
                      ))}
                    </div>
                  </div>
                  <p className="text-xs text-slate-500 italic">{g.reason}</p>
                </div>
                {isDone ? (
                  <span className="text-green-600 text-sm font-medium">✓ Merged</span>
                ) : (
                  <button
                    onClick={() => merge(g)}
                    disabled={merging === g.canonical_id}
                    className="shrink-0 rounded-lg bg-orange-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-orange-700 disabled:opacity-40"
                  >
                    {merging === g.canonical_id ? "Merging…" : "Merge"}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function adminApiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const pw = getStoredAdminPassword();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (pw) headers["X-Admin-Password"] = pw;
  return fetch(path, { ...options, headers }).then(async (r) => {
    if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
    return r.json();
  });
}
