"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getOrCreateSessionId } from "@/lib/session";
import { createSession, getNextQuestion, submitAnswer, Question } from "@/lib/api";

const LIKERT_OPTIONS = [
  { label: "Strongly oppose", value: -1.0 },
  { label: "Somewhat oppose", value: -0.5 },
  { label: "Neutral / unsure", value: 0.0 },
  { label: "Somewhat support", value: 0.5 },
  { label: "Strongly support", value: 1.0 },
];

const SALIENCE_OPTIONS = [
  { label: "Not important", value: 0.5 },
  { label: "Important", value: 1.0 },
  { label: "Very important", value: 2.0 },
];

/**
 * Questionnaire page (AGENTS.MD Sections 13, 14.3).
 * IMPORTANT: party names/scores MUST NOT appear during the questionnaire.
 */
export default function QuestionnairePage() {
  const router = useRouter();
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
      const q = await getNextQuestion(sid);
      if (!q) {
        router.push(`/results?session_id=${sid}`);
        return;
      }
      setQuestion(q);
    } catch (e) {
      setError("Failed to load next question. Please refresh.");
    } finally {
      setLoading(false);
    }
  }, [router]);

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
    } catch (e) {
      setError("Failed to submit answer. Please try again.");
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
        <p className="text-slate-500 text-sm">Loading question…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-xl mx-auto text-center py-20 space-y-4">
        <p className="text-red-600">{error}</p>
        <button onClick={() => loadNextQuestion(sessionId)} className="btn-primary">
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Progress bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs text-slate-500">
          <span>Question {answeredCount + 1} of up to 15</span>
          {answeredCount >= 8 && (
            <button
              onClick={handleViewResults}
              className="text-brand-600 hover:underline font-medium"
            >
              Show results now →
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
            {question.topic_slug.replace("_", " ")}
          </span>

          {/* Question text */}
          <h2 className="text-xl font-semibold text-slate-900 leading-snug">
            {question.question_text_en}
          </h2>

          {/* Likert scale */}
          <div className="space-y-2">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
              Your position
            </p>
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
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
              How important is this to you?
            </p>
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
                <span>{showWhy ? "▲" : "▼"}</span>
                Why am I being asked this?
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
            {submitting ? "Saving…" : "Next question →"}
          </button>
        </div>
      )}
    </div>
  );
}

