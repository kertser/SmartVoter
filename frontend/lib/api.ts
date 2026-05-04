/**
 * Typed API client for SmartVoter backend.
 * Base URL comes from NEXT_PUBLIC_API_URL environment variable.
 */

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Topic {
  id: string;
  slug: string;
  name_en: string;
  name_he: string;
  name_ru?: string;
  description?: string;
}

export interface Question {
  id: string;
  question_text_en: string;
  question_text_he: string;
  answer_scale_type: string;
  policy_item_id: string;
  topic_slug: string;
  context_note?: string;
  why_selected?: string;
}

export interface AnswerIn {
  session_id: string;
  question_id: string;
  policy_item_id: string;
  answer_value: number; // -1.0 to +1.0
  salience: number; // 0.5 | 1.0 | 2.0
}

export interface AnswerOut {
  id: string;
  session_id: string;
  answered_at: string;
}

export interface PartyResult {
  party_id: string;
  name: string;
  match_score: number;
  confidence: number;
  evidence_strength: number;
  volatility: number;
  coverage: number;
  is_new_party: boolean;
  explanation: string;
  top_agreements: string[];
  top_disagreements: string[];
  weak_evidence_topics: string[];
}

export interface BestPartyByTopic {
  topic: string;
  party: string;
}

export interface RepresentationGap {
  has_gap: boolean;
  explanation: string;
  best_party_by_topic: BestPartyByTopic[];
}

export interface ResultsOut {
  session_id: string;
  run_id: string;
  parties: PartyResult[];
  representation_gap: RepresentationGap;
}

async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export async function getTopics(): Promise<Topic[]> {
  return apiFetch<Topic[]>("/api/topics");
}

export async function createSession(sessionId: string): Promise<{ session_id: string; created_at: string }> {
  return apiFetch("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export async function getNextQuestion(
  sessionId: string
): Promise<Question | null> {
  return apiFetch<Question | null>(
    `/api/questions/next?session_id=${sessionId}`
  );
}

export async function submitAnswer(answer: AnswerIn): Promise<AnswerOut> {
  return apiFetch<AnswerOut>("/api/answers", {
    method: "POST",
    body: JSON.stringify(answer),
  });
}

export async function getResults(sessionId: string): Promise<ResultsOut> {
  return apiFetch<ResultsOut>(`/api/results/${sessionId}`);
}

export async function getMethodology(): Promise<object> {
  return apiFetch<object>("/api/methodology");
}

