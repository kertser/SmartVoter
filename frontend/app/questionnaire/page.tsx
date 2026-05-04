"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getOrCreateSessionId } from "@/lib/session";
import { createSession, getNextQuestion, submitAnswer, Question } from "@/lib/api";
import { useT, useLang } from "@/lib/i18n";
import { Tooltip } from "@/components/Tooltip";

/**
 * Questionnaire page (AGENTS.MD Sections 13, 14.3).
 * IMPORTANT: party names/scores MUST NOT appear during the questionnaire.
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

  const loadNextQuestion = useCallback(async (sid: string) => {
    setLoading(true);
    setSelectedAnswer(null);
    setSalience(1.0);
    setShowWhy(false);
    setError(null);
    try {
      const question = await getNextQuestion(sid);
      if (!question) {
        router.push(`/results?session_id=${sid}`);
        return;
      }
      setQuestion(question);
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
      if (newCount >= 15) {
        router.push(`/results?session_id=${sessionId}`);
        return;
      }
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

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Progress bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs text-slate-500">
          <span>{q.progressLabel(answeredCount + 1, 15)}</span>
          {answeredCount >= 8 && (
            <button
              onClick={handleViewResults}
              className="text-brand-600 hover:underline font-medium"
            >
              {q.showResultsNow}
            </button>
          )}
        </div>
        <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-brand-500 rounded-full transition-all duration-300"
            style={{ width: `${(answeredCount / 15) * 100}%` }}
          />
        </div>
      </div>

      {question && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-6 space-y-6">
          {/* Topic badge */}
          <span className="inline-block rounded-full bg-slate-100 px-3 py-0.5 text-xs font-medium text-slate-600 capitalize">
            {lang === "he" && question.topic_name_he
              ? question.topic_name_he
              : lang === "ru" && question.topic_name_ru
              ? question.topic_name_ru
              : question.topic_slug.replace("_", " ")}
          </span>

          {/* Question text — language-aware (AGENTS.MD Phase 8) */}
          <h2 className="text-xl font-semibold text-slate-900 leading-snug">
            {lang === "he" && question.question_text_he
              ? question.question_text_he
              : lang === "ru" && question.question_text_ru
              ? question.question_text_ru
              : question.question_text_en}
          </h2>

          {/* Likert scale */}
          <div className="space-y-2">
            <Tooltip content={q.positionTooltip} position="bottom">
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

          {/* Importance selector */}
          <div className="space-y-2">
            <Tooltip content={q.importanceTooltip} position="bottom">
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
                <p className="mt-2 text-xs text-slate-500 bg-slate-50 rounded-lg px-3 py-2 border border-slate-100">
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

