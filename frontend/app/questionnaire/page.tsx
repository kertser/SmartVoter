"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getOrCreateSessionId } from "@/lib/session";
import { createSession, getNextQuestion, submitAnswer, explainQuestion, QuestionExplanation, Question } from "@/lib/api";
import { useT, useLang } from "@/lib/i18n";
import { Tooltip } from "@/components/Tooltip";

/**
 * Questionnaire page (AGENTS.MD Sections 13, 14.3).
 * IMPORTANT: party names/scores MUST NOT appear during the questionnaire.
 *
 * Stopping logic (backend-driven, not hardcoded):
 * - When the API returns null → redirect to results immediately.
 * - When question.can_show_results === true AND answeredCount >= 20 → show convergence banner
 *   (user may view results now or keep going).
 * - Hard max is enforced server-side (HARD_MAX = 40).
 *
 * Questions are pre-generated in background on session creation so the user
 * never waits for LLM calls. On-the-fly auto-generation covers gaps.
 */
export default function QuestionnairePage() {
  const router = useRouter();
  const t = useT();
  const lang = useLang().lang;
  const q = t.questionnaire;
  const [sessionId, setSessionId] = useState<string>("");
  const [question, setQuestion] = useState<Question | null>(null);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<number | null>(null);
  const [salience, setSalience] = useState<number>(1.0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showWhy, setShowWhy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Convergence banner state — only shown after 20+ answers
  const [showConvergenceBanner, setShowConvergenceBanner] = useState(false);
  // Explain-question state
  const [showExplain, setShowExplain] = useState(false);
  const [explainData, setExplainData] = useState<QuestionExplanation | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);

  const loadNextQuestion = useCallback(async (sid: string) => {
    setLoading(true);
    setSelectedAnswer(null);
    setSalience(1.0);
    setShowWhy(false);
    setShowExplain(false);
    setExplainData(null);
    setError(null);
    setShowConvergenceBanner(false);
    try {
      const nextQuestion = await getNextQuestion(sid);
      if (!nextQuestion) {
        router.push(`/results?session_id=${sid}`);
        return;
      }
      setQuestion(nextQuestion);
      // Show convergence banner only after 20 answers to encourage more questions
      if (nextQuestion.can_show_results && (nextQuestion.answered_count ?? 0) >= 20) {
        setShowConvergenceBanner(true);
      }
    } catch {
      setError(q.errorLoad);
    } finally {
      setLoading(false);
    }
  }, [router, q]);

  useEffect(() => {
    const init = async () => {
      const sid = getOrCreateSessionId();
      setSessionId(sid);
      try {
        await createSession(sid);
      } catch {
        // session may already exist
      }
      await loadNextQuestion(sid);
    };
    init();
  }, [loadNextQuestion]);

  const handleSubmit = async () => {
    if (selectedAnswer === null || !question || !sessionId) return;
    setSubmitting(true);
    try {
      await submitAnswer({
        session_id: sessionId,
        question_id: question.id,
        policy_item_id: question.policy_item_id,
        answer_value: selectedAnswer,
        salience,
      });
      const newCount = answeredCount + 1;
      setAnsweredCount(newCount);
      // Backend enforces HARD_MAX; just load next (null → auto-redirect)
      await loadNextQuestion(sessionId);
    } catch {
      setError(q.errorSubmit);
    } finally {
      setSubmitting(false);
    }
  };

  const handleViewResults = () => {
    router.push(`/results?session_id=${sessionId}`);
  };

  /** Explain this question — calls the /explain endpoint for rich, language-aware background. */
  const handleExplain = async () => {
    if (showExplain) {
      setShowExplain(false);
      return;
    }
    if (explainData !== null) {
      // Already fetched — just toggle
      setShowExplain(true);
      return;
    }
    setExplainLoading(true);
    setShowExplain(true);
    try {
      const data = await explainQuestion(question!.id, lang);
      setExplainData(data);
    } catch {
      setExplainData(null);
    } finally {
      setExplainLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center gap-4 py-20">
        <div className="h-8 w-8 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
        <p className="text-slate-500 text-sm">{q.loadingQuestion}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-xl mx-auto text-center py-20 space-y-4">
        <p className="text-red-600">{error}</p>
        <button onClick={() => loadNextQuestion(sessionId)} className="btn-primary">
          {q.tryAgain}
        </button>
      </div>
    );
  }

  const LIKERT_OPTIONS = [
    { label: q.likert.stronglyOppose, value: -1.0 },
    { label: q.likert.somewhatOppose, value: -0.5 },
    { label: q.likert.neutral, value: 0.0 },
    { label: q.likert.somewhatSupport, value: 0.5 },
    { label: q.likert.stronglySupport, value: 1.0 },
  ];

  const SALIENCE_OPTIONS = [
    { label: q.salience.notImportant, value: 0.5 },
    { label: q.salience.important, value: 1.0 },
    { label: q.salience.veryImportant, value: 2.0 },
  ];

  // Progress — simple linear: answered / 40
  const HARD_MAX = 40;
  const progressPct = Math.min((answeredCount / HARD_MAX) * 100, 100);

  const topicsCovered = question?.topics_covered ?? 0;
  const topicsTotal = question?.topics_total ?? 15;
  const topicsLeftCount = topicsTotal - topicsCovered;

  // Topic coverage dots (filled = covered)
  const maxDots = Math.min(topicsTotal, 15);
  const coveredDots = Math.min(topicsCovered, maxDots);

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* ── Progress section ── */}
      <div className="space-y-2">
        {/* Row: question counter + optional early-exit */}
        <div className="flex justify-between items-center text-sm">
          <span className="font-semibold text-slate-700">
            {q.progressLabel(answeredCount + 1)}
          </span>
          <span className="flex items-center gap-3 text-xs text-slate-500">
            {/* Show results only after 20 questions */}
            {answeredCount >= 20 && (
              <button
                onClick={handleViewResults}
                className="text-brand-600 hover:underline font-medium"
              >
                {q.showResultsNow}
              </button>
            )}
          </span>
        </div>

        {/* Main progress bar — linear 0–40 */}
        <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500 bg-brand-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>

        {/* Topic coverage row */}
        <div className="flex items-center justify-between text-xs text-slate-400">
          {/* Mini dot-grid for topic coverage */}
          <span className="flex items-center gap-1.5">
            <span className="flex gap-0.5">
              {Array.from({ length: maxDots }).map((_, i) => (
                <span
                  key={i}
                  className={`inline-block h-1.5 w-1.5 rounded-full transition-colors ${
                    i < coveredDots ? "bg-brand-400" : "bg-slate-200"
                  }`}
                />
              ))}
            </span>
            <span className={topicsCovered >= topicsTotal ? "text-green-600 font-medium" : ""}>
              {q.topicsCoveredLabel(topicsCovered, topicsTotal)}
            </span>
          </span>

          {topicsLeftCount > 0 && (
            <span className="text-slate-400">
              {q.convergenceTopicsLeft(topicsLeftCount)}
            </span>
          )}
        </div>
      </div>

      {/* Convergence banner — shown when ranking is stable AND ≥20 answers */}
      {showConvergenceBanner && (
        <div className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 flex flex-wrap items-center gap-3 text-sm">
          <span className="text-green-800 flex-1">{q.convergenceOfferResults}</span>
          <div className="flex gap-2">
            <button
              onClick={handleViewResults}
              className="rounded-lg bg-green-600 px-4 py-1.5 text-white font-medium hover:bg-green-700 text-xs transition-colors"
            >
              {q.showResultsNow}
            </button>
            <button
              onClick={() => setShowConvergenceBanner(false)}
              className="rounded-lg border border-green-300 px-4 py-1.5 text-green-800 font-medium hover:bg-green-100 text-xs transition-colors"
            >
              {q.convergenceKeepGoing}
            </button>
          </div>
        </div>
      )}

      {question && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-6 space-y-6">
          {/* Topic badge + discovery badge */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-block rounded-full bg-slate-100 px-3 py-0.5 text-xs font-medium text-slate-600 capitalize">
              {lang === "he" && question.topic_name_he
                ? question.topic_name_he
                : lang === "ru" && question.topic_name_ru
                ? question.topic_name_ru
                : question.topic_slug.replace("_", " ")}
            </span>
            {question.is_discovery_question && (
              <span
                title={q.discoveryTooltip}
                className="inline-flex items-center rounded-full bg-amber-50 border border-amber-200 px-3 py-0.5 text-xs font-medium text-amber-700 cursor-help"
              >
                {q.discoveryBadge}
              </span>
            )}
          </div>

          {/* Question text — language-aware (AGENTS.MD Phase 8) */}
          <h2 className="text-xl font-semibold text-slate-900 leading-snug">
            {lang === "he" && question.question_text_he
              ? question.question_text_he
              : lang === "ru" && question.question_text_ru
              ? question.question_text_ru
              : question.question_text_en}
          </h2>

          {/* ── Explain this question button ── */}
          <div>
            <button
              onClick={handleExplain}
              className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-1 transition-colors"
            >
              {showExplain ? q.explainHide : q.explainBtn}
            </button>
            {showExplain && (
              <div className="mt-2 rounded-lg border border-blue-100 bg-blue-50 px-3 py-3 text-xs text-blue-900 leading-relaxed space-y-3">
                {explainLoading ? (
                  <span className="text-slate-400 italic">{q.explainLoading}</span>
                ) : explainData && (explainData.background || explainData.why_relevant) ? (
                  <>
                    {explainData.background && (
                      <div>
                        <p className="font-semibold text-blue-700 mb-0.5">{q.explainBackground}</p>
                        <p>{explainData.background}</p>
                      </div>
                    )}
                    {explainData.why_relevant && (
                      <div>
                        <p className="font-semibold text-blue-700 mb-0.5">{q.explainWhyRelevant}</p>
                        <p>{explainData.why_relevant}</p>
                      </div>
                    )}
                    {(explainData.support_side || explainData.oppose_side) && (
                      <div className="grid grid-cols-2 gap-2">
                        {explainData.support_side && (
                          <div className="rounded bg-green-50 border border-green-100 px-2 py-1.5">
                            <p className="font-semibold text-green-700 mb-0.5">{q.explainSupportSide}</p>
                            <p className="text-green-800">{explainData.support_side}</p>
                          </div>
                        )}
                        {explainData.oppose_side && (
                          <div className="rounded bg-red-50 border border-red-100 px-2 py-1.5">
                            <p className="font-semibold text-red-700 mb-0.5">{q.explainOpposeSide}</p>
                            <p className="text-red-800">{explainData.oppose_side}</p>
                          </div>
                        )}
                      </div>
                    )}
                    {explainData.everyday_example && (
                      <div className="border-t border-blue-100 pt-2">
                        <p className="font-semibold text-blue-700 mb-0.5">💡 {q.explainEverydayExample}</p>
                        <p className="italic">{explainData.everyday_example}</p>
                      </div>
                    )}
                  </>
                ) : (
                  <span className="text-slate-400 italic">{q.explainNoData}</span>
                )}
              </div>
            )}
          </div>

          {/* Likert scale */}
          <div className="space-y-2">
            <Tooltip content={q.positionTooltip} position="bottom" wide>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide cursor-help">
                {q.positionLabel} ⓘ
              </p>
            </Tooltip>
            <div className="flex flex-col gap-2">
              {LIKERT_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setSelectedAnswer(opt.value)}
                  className={`rounded-lg border px-4 py-3 text-sm text-left transition-all ${
                    selectedAnswer === opt.value
                      ? "border-brand-500 bg-brand-50 text-brand-800 font-medium"
                      : "border-slate-200 hover:border-slate-300 hover:bg-slate-50 text-slate-700"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Importance selector — wide tooltip to prevent clipping */}
          <div className="space-y-2">
            <Tooltip content={q.importanceTooltip} position="bottom" wide>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide cursor-help">
                {q.importanceLabel} ⓘ
              </p>
            </Tooltip>
            <div className="flex gap-2">
              {SALIENCE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setSalience(opt.value)}
                  className={`flex-1 rounded-lg border px-3 py-2 text-xs transition-all ${
                    salience === opt.value
                      ? "border-slate-700 bg-slate-900 text-white font-medium"
                      : "border-slate-200 hover:border-slate-300 text-slate-600"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Why selected (expandable, AGENTS.MD Section 14A.10) */}
          {question.why_selected && (
            <div>
              <button
                onClick={() => setShowWhy(!showWhy)}
                className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-1"
              >
                {showWhy ? q.whyAskedHide : q.whyAskedShow}
              </button>
              {showWhy && (
                <p className={`mt-2 text-xs rounded-lg px-3 py-2 border ${
                  question.is_discovery_question
                    ? "text-amber-700 bg-amber-50 border-amber-100"
                    : "text-slate-500 bg-slate-50 border-slate-100"
                }`}>
                  {question.why_selected}
                </p>
              )}
            </div>
          )}

          {/* Submit */}
          <button
            onClick={handleSubmit}
            disabled={selectedAnswer === null || submitting}
            className="w-full rounded-lg bg-brand-600 py-3 text-white font-medium hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? q.submitting : q.submitNext}
          </button>
        </div>
      )}
    </div>
  );
}

