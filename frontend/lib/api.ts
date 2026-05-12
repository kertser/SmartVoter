/**
 * Typed API client for SmartVoter backend.
 * Base URL comes from NEXT_PUBLIC_API_URL environment variable.
 */

// Use an explicit API URL only when provided (e.g. for local dev outside Docker).
// In production the Next.js rewrite proxies /api/* → backend internally, so an
// empty base URL (relative paths) is correct and avoids hitting the unexposed port.
const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "";

// ── Admin password (stored in sessionStorage, never sent to analytics) ────────

const ADMIN_PW_KEY = "sv_admin_pw";

export function getStoredAdminPassword(): string {
  if (typeof window === "undefined") return "";
  return sessionStorage.getItem(ADMIN_PW_KEY) ?? "";
}

export function storeAdminPassword(pw: string): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(ADMIN_PW_KEY, pw);
}

export function clearAdminPassword(): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(ADMIN_PW_KEY);
}

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
  question_text_ru?: string;
  answer_scale_type: string;
  policy_item_id: string;
  topic_slug: string;
  topic_name_he?: string;
  topic_name_ru?: string;
  context_note?: string;
  why_selected?: string;
  is_root_question?: boolean;
  // answer_polarity: +1 means "Strongly support" = positive axis; -1 means it's inverted.
  // The backend handles the arithmetic automatically. Frontend uses this ONLY to optionally
  // flip the Likert label display so labels always make intuitive sense to the user.
  answer_polarity?: number;
  // Convergence metadata
  can_show_results?: boolean;
  phase?: "survey" | "depth";
  topics_covered?: number;
  topics_total?: number;
  answered_count?: number;
  ranking_stability?: number;
  // Discovery metadata — set when the question was selected to surface a
  // non-top party with a niche/unexpected distinctive position
  is_discovery_question?: boolean;
  outsider_signal_strength?: number;
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
  name_he?: string;
  name_ru?: string;
  match_score: number;
  confidence: number;
  evidence_strength: number;
  volatility: number;
  coverage: number;
  answer_stability: number;
  is_new_party: boolean;
  explanation: string;
  explanation_he?: string;
  explanation_ru?: string;
  top_agreements: string[];
  top_agreements_he?: string[];
  top_agreements_ru?: string[];
  top_disagreements: string[];
  top_disagreements_he?: string[];
  top_disagreements_ru?: string[];
  weak_evidence_topics: string[];
  /** topic_name_en → 0..1 similarity */
  topic_scores: Record<string, number>;
  /** evidence_type → proportion 0..1 */
  evidence_by_type: Record<string, number>;
  /** Confidence component breakdown for UI decomposition display */
  confidence_breakdown: {
    evidence_quality: number;
    coverage: number;
    answer_stability: number;
    volatility_penalty: number;
    high_salience_coverage: number;
  };
}

export interface BestPartyByTopic {
  topic: string;
  topic_he?: string;
  topic_ru?: string;
  party: string;
  party_he?: string;
}

export interface RepresentationGap {
  has_gap: boolean;
  explanation: string;
  explanation_he?: string;
  explanation_ru?: string;
  best_party_by_topic: BestPartyByTopic[];
}

export interface DiscoveryMatch {
  topic: string;
  topic_he?: string;
  topic_ru?: string;
  party: string;
  party_he?: string;
  party_ru?: string;
  party_id: string;
  similarity: number;
  top3_best_similarity: number;
}

export interface ResultsOut {
  session_id: string;
  run_id: string;
  parties: PartyResult[];
  representation_gap: RepresentationGap;
  discovery_matches?: DiscoveryMatch[];
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

/** Like apiFetch but automatically attaches the stored admin password header. */
async function adminApiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const pw = getStoredAdminPassword();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (pw) headers["X-Admin-Password"] = pw;
  return apiFetch<T>(path, { ...options, headers });
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

export async function getQuestionContext(
  questionId: string,
  lang: string = "en",
): Promise<{ question_id: string; context_note: string | null; topic_name: string | null; lang: string }> {
  return apiFetch(`/api/questions/${questionId}/context?lang=${lang}`);
}

export interface QuestionExplanation {
  question_id: string;
  lang: string;
  topic_name: string;
  background: string;
  why_relevant: string;
  support_side: string;
  oppose_side: string;
  everyday_example: string;
  source: "llm" | "stored";
}

export async function explainQuestion(
  questionId: string,
  lang: string = "en",
): Promise<QuestionExplanation> {
  return apiFetch(`/api/questions/${questionId}/explain?lang=${lang}`);
}

export async function getMethodology(): Promise<object> {
  return apiFetch<object>("/api/methodology");
}

// ── Admin API ─────────────────────────────────────────────────────────────────

export interface AdminQuestion {
  id: string;
  policy_item_id: string;
  question_text_en: string;
  question_text_he: string;
  question_text_ru?: string;
  status: string;
  answer_scale_type: string;
  neutrality_score?: number;
  complexity_score?: number;
  llm_prompt_version?: string;
}

export interface PolicyItemAdmin {
  id: string;
  title: string;
  description?: string;
  directional_axis?: string;
  source_type: string;
  llm_confidence?: number;
  human_review_status: string;
}

export interface LlmOutputRecord {
  id: string;
  run_id: string;
  provider: string;
  model: string;
  entity_type?: string;
  entity_id?: string;
  confidence?: number;
  output_summary: string;
  created_at?: string;
}

export async function adminGetReviewItems(status?: string): Promise<AdminQuestion[]> {
  const qs = status ? `?status=${status}` : "";
  return adminApiFetch<AdminQuestion[]>(`/api/admin/review/items${qs}`);
}

export async function adminApprove(id: string): Promise<{ status: string }> {
  return adminApiFetch(`/api/admin/review/${id}/approve`, { method: "POST" });
}

export async function adminReject(id: string): Promise<{ status: string }> {
  return adminApiFetch(`/api/admin/review/${id}/reject`, { method: "POST" });
}

export async function adminApproveAll(params?: {
  ids?: string[];
  status_filter?: string;
}): Promise<{ approved: number; status: string }> {
  return adminApiFetch("/api/admin/review/bulk-approve", {
    method: "POST",
    body: JSON.stringify(params ?? {}),
  });
}

export async function adminEditQuestion(
  id: string,
  body: { question_text_en?: string; question_text_he?: string; question_text_ru?: string; neutrality_score?: number }
): Promise<{ status: string }> {
  return adminApiFetch(`/api/admin/review/${id}/edit`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function adminGetPolicyItems(): Promise<PolicyItemAdmin[]> {
  return adminApiFetch<PolicyItemAdmin[]>("/api/admin/policy-items");
}

export async function adminGenerateQuestions(policy_item_ids: string[]): Promise<object> {
  return adminApiFetch("/api/admin/llm/generate-questions", {
    method: "POST",
    body: JSON.stringify({ policy_item_ids }),
  });
}

export async function adminClassifyPolicy(policy_item_id: string): Promise<object> {
  return adminApiFetch("/api/admin/llm/classify", {
    method: "POST",
    body: JSON.stringify({ policy_item_id }),
  });
}

export async function adminGetLlmOutputs(limit = 50): Promise<LlmOutputRecord[]> {
  return adminApiFetch<LlmOutputRecord[]>(`/api/admin/llm/outputs?limit=${limit}`);
}

// ── Lineage & Evidence ────────────────────────────────────────────────────────

export interface LineageNode {
  id: string;
  name: string;
  name_he?: string;
  name_ru?: string;
  official_name: string;
  election_cycle?: string;
  knesset_number?: number;
  status: string;
  start_date?: string;
  end_date?: string;
}

export interface LineageEdge {
  id: string;
  from_id: string;
  to_id: string;
  relation_type: string;
  continuity_weight: number;
  llm_explanation?: string;
  human_review_status: string;
  source_url?: string;
}

export interface LineageGraph {
  nodes: LineageNode[];
  edges: LineageEdge[];
}

export interface PartyEvidenceItem {
  position_id: string;
  policy_item_id: string;
  policy_item_title: string;
  policy_item_description?: string;
  directional_axis?: string;
  topic_slug?: string;
  topic_name_en?: string;
  topic_name_he?: string;
  topic_name_ru?: string;
  position_mean: number;
  position_uncertainty: number;
  evidence_strength: number;
  evidence_type: string;
  source_refs_json: unknown[];
  llm_explanation?: string;
}

export async function getLineage(): Promise<LineageGraph> {
  return apiFetch<LineageGraph>("/api/lineage");
}

export async function getPartyEvidence(partyId: string): Promise<PartyEvidenceItem[]> {
  return apiFetch<PartyEvidenceItem[]>(`/api/parties/${partyId}/evidence`);
}

// ── Simulation API (Phase 14B) ────────────────────────────────────────────────

export interface SimulationPartyResult {
  party_name: string;
  /** Hebrew name from political_brands.names_json['he'] */
  name_he?: string;
  party_instance_id: string | null;
  seats_mean: number;
  seats_median: number;
  seats_p10: number;
  seats_p25: number;
  seats_p75: number;
  seats_p90: number;
  threshold_pass_probability: number;
  vote_share_mean: number;
  color_hex?: string;
  left_right_score?: number | null;
}

export interface CoalitionScenarioMember {
  party_name: string;
  /** Hebrew name from political_brands.names_json['he'] */
  name_he?: string;
  expected_seats: number;
  role?: string;
  color_hex?: string;
}

export interface CoalitionScenario {
  scenario_id: string;
  scenario_name: string;
  probability_estimate: number;
  seat_mean: number;
  seat_p10: number;
  seat_p90: number;
  feasibility_score: number;
  stability_score: number;
  ideological_coherence_score: number;
  explanation: string;
  members: CoalitionScenarioMember[];
}

export interface SimulationRun {
  run_id: string;
  created_at: string | null;
  model_version: string;
  data_cutoff_date: string | null;
  n_iterations: number;
  assumptions: Record<string, string>;
  parties: SimulationPartyResult[];
  coalitions: CoalitionScenario[];
  polls_meta?: {
    count: number;
    latest_date: string | null;
    source: "live_web_search" | "seed_estimate" | "none";
    source_label_he?: string;
    source_label_ru?: string;
  };
}

// Current Knesset (25th, real election results sorted left-to-right)
export interface KnessetParty {
  official_name: string;
  name_en: string;
  name_he?: string;
  name_ru?: string;
  seats: number;
  vote_share?: number;
  left_right_score: number;
  political_bloc: string;
  color_hex: string;
  party_instance_id?: string;
}

export interface KnessetComposition {
  knesset_number: number;
  election_date: string;
  election_cycle: string;
  total_seats: number;
  threshold_percent: number;
  parties: KnessetParty[];  // sorted left → right
}

// Coalition evaluation (user-built coalition)
export interface CoalitionViolation {
  source: string;
  target: string;
  strength: "hard" | "soft";
  description: string;
}

export interface CoalitionEvaluation {
  party_names: string[];
  seats: number;
  has_majority: boolean;
  seat_breakdown: Record<string, number>;
  feasibility_score: number;
  stability_score: number;
  ideological_coherence_score: number;
  constraint_violations: CoalitionViolation[];
  hard_violations: number;
  soft_violations: number;
}

export async function getLatestSimulation(): Promise<SimulationRun> {
  return apiFetch<SimulationRun>("/api/simulation/latest");
}

export async function triggerSimulation(n_iterations = 5000): Promise<SimulationRun> {
  return apiFetch<SimulationRun>(`/api/simulation/run?n_iterations=${n_iterations}`, {
    method: "POST",
  });
}

export interface PollingRefreshResult {
  source: string;
  polls_stored: number;
  parties_stored: number;
  warnings: string[];
  notes: string;
  refreshed_at: string | null;
  model_used: string | null;
}

export async function adminRefreshPolling(model = "gpt-4o"): Promise<PollingRefreshResult> {
  return adminApiFetch<PollingRefreshResult>(`/api/admin/polling/refresh?model=${encodeURIComponent(model)}`, {
    method: "POST",
  });
}

export async function getKnessetCurrent(): Promise<KnessetComposition> {
  return apiFetch<KnessetComposition>("/api/simulation/knesset/current");
}

export async function evaluateCoalition(
  partyNames: string[],
  useForecastSeats = false,
): Promise<CoalitionEvaluation> {
  const params = new URLSearchParams({ use_forecast_seats: String(useForecastSeats) });
  return apiFetch<CoalitionEvaluation>(`/api/simulation/coalition/evaluate?${params}`, {
    method: "POST",
    body: JSON.stringify(partyNames),
  });
}

// ── Privacy ───────────────────────────────────────────────────────────────────

export async function deleteSession(sessionId: string): Promise<{ deleted: boolean }> {
  return apiFetch<{ deleted: boolean }>(`/api/sessions/${sessionId}`, { method: "DELETE" });
}

export async function undoLastAnswer(
  sessionId: string
): Promise<{ deleted: boolean; question_id: string | null }> {
  return apiFetch<{ deleted: boolean; question_id: string | null }>(
    `/api/sessions/${sessionId}/answers/last`,
    { method: "DELETE" }
  );
}

export async function skipQuestion(
  questionId: string,
  sessionId: string,
  reason: "outdated" | "not_relevant" | "other" = "outdated"
): Promise<{ skipped: boolean; question_id: string; reason: string }> {
  const params = new URLSearchParams({ session_id: sessionId, reason });
  return apiFetch(`/api/questions/${questionId}/skip?${params}`, { method: "POST" });
}

// ── Public evidence browser ───────────────────────────────────────────────────

export interface PartyListItem {
  id: string;
  name: string;
  name_he?: string;
  name_ru?: string;
  official_name: string;
  election_cycle?: string;
  knesset_number?: number;
  status: string;
  start_date?: string;
  end_date?: string;
}

export interface PartyPositionRecord {
  policy_item_id: string;
  policy_item_title: string;
  directional_axis?: string;
  topic_slug?: string;
  topic_name_en?: string;
  topic_name_he?: string;
  topic_name_ru?: string;
  position_mean: number;
  position_uncertainty: number;
  evidence_strength: number;
  evidence_type: string;
  llm_explanation?: string;
}

export interface MemberRecord {
  person_id: string;
  name_en?: string;
  name_he?: string;
  role: string;
  start_date?: string;
  end_date?: string;
  confidence?: number;
}

export interface PartyDetail extends PartyListItem {
  positions: PartyPositionRecord[];
  members: MemberRecord[];
  lineage: LineageEdge[];
}

export interface PersonDetail {
  id: string;
  name_en: string;
  name_he: string;
  birth_year?: number;
  public_profile_url?: string;
  memberships: Array<{
    party_instance_id: string;
    party_name: string;
    party_name_he?: string;
    party_name_ru?: string;
    role: string;
    start_date?: string;
    end_date?: string;
    confidence?: number;
    is_current: boolean;
  }>;
}

export interface VoteDetail {
  id: string;
  external_id?: string;
  title_he: string;
  title_en?: string;
  date?: string;
  knesset_number?: number;
  vote_type?: string;
  is_procedural_estimate: boolean;
  importance_score?: number;
  source_url?: string;
  results: Array<{
    person_id: string;
    name_en?: string;
    name_he?: string;
    vote_value: string;
    party_instance_id_at_time?: string;
  }>;
}

export interface VoteListItem {
  id: string;
  external_id?: string;
  title_he: string;
  title_en?: string;
  date?: string;
  knesset_number?: number;
  importance_score?: number;
  is_procedural_estimate?: boolean;
  source_url?: string;
}

export interface BillDetail {
  id: string;
  external_id?: string;
  title_he: string;
  title_en?: string;
  summary_he?: string;
  summary_en?: string;
  full_text_url?: string;
  date_submitted?: string;
  status?: string;
  source_url?: string;
}

export interface PersonListItem {
  id: string;
  name_en: string;
  name_he: string;
  birth_year?: number;
  current_party_name?: string;
  current_party_name_he?: string;
  current_party_name_ru?: string;
  current_party_instance_id?: string;
}

export async function getParties(groupByBrand = true): Promise<PartyListItem[]> {
  return apiFetch<PartyListItem[]>(`/api/parties?group_by_brand=${groupByBrand}`);
}

export async function getParty(id: string): Promise<PartyDetail> {
  return apiFetch<PartyDetail>(`/api/parties/${id}`);
}

export async function getPerson(id: string): Promise<PersonDetail> {
  return apiFetch<PersonDetail>(`/api/persons/${id}`);
}

export async function getPersons(currentOnly = false): Promise<PersonListItem[]> {
  return apiFetch<PersonListItem[]>(`/api/persons?current_only=${currentOnly}&limit=500`);
}

export async function getVote(id: string): Promise<VoteDetail> {
  return apiFetch<VoteDetail>(`/api/votes/${id}`);
}

export async function getVotes(knesset_number?: number, hide_procedural = false): Promise<VoteListItem[]> {
  const params = new URLSearchParams();
  if (knesset_number) params.set("knesset_number", String(knesset_number));
  if (hide_procedural) params.set("hide_procedural", "true");
  const qs = params.toString() ? `?${params}` : "";
  return apiFetch<VoteListItem[]>(`/api/votes${qs}`);
}

export async function getBill(id: string): Promise<BillDetail> {
  return apiFetch<BillDetail>(`/api/bills/${id}`);
}

export async function getBills(): Promise<BillDetail[]> {
  return apiFetch<BillDetail[]>("/api/bills");
}

// ── Admin Knesset Ingestion (Phase 6) ─────────────────────────────────────────

export interface IngestionStepResult {
  inserted?: number;
  updated?: number;
  skipped?: number;
  created?: number;
  edges_proposed?: number;
  candidates_evaluated?: number;
  positions_created?: number;
  positions_updated?: number;
  skipped_no_evidence?: number;
  candidates_updated?: number;
  parties_updated?: number;
  processed?: number;
  errors?: number;
  error?: string;
  [key: string]: number | string | undefined;
}

export interface IngestionJobStatus {
  job_id: string;
  status: "queued" | "running" | "done" | "error";
  knesset_number?: number;
  limit?: number;
  no_llm?: boolean;
  // per-step results (set once each step completes)
  factions?: IngestionStepResult;
  votes?: IngestionStepResult;
  bills?: IngestionStepResult;
  persons?: IngestionStepResult;
  vote_results?: IngestionStepResult;
  policy_items?: IngestionStepResult;
  party_positions?: IngestionStepResult;
  questions?: IngestionStepResult;
  lineage?: IngestionStepResult;
  volatility?: IngestionStepResult;
  error?: string;
  results?: Record<string, IngestionStepResult>;
}

export async function adminTriggerIngestion(params: {
  knesset_number: number;
  limit: number;
  votes_only: boolean;
  bills_only: boolean;
  no_llm: boolean;
}): Promise<{ job_id: string; status: string; message: string }> {
  return adminApiFetch("/api/admin/ingest/knesset", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function adminGetIngestionStatus(jobId: string): Promise<IngestionJobStatus> {
  return adminApiFetch<IngestionJobStatus>(`/api/admin/ingest/status/${jobId}`);
}

export async function adminListIngestionJobs(): Promise<IngestionJobStatus[]> {
  return adminApiFetch<IngestionJobStatus[]>("/api/admin/ingest/jobs");
}

export interface AvailableKnessetData {
  /** All Knesset numbers that have any data in the DB */
  knessets: number[];
  knessets_with_votes: number[];
  knessets_with_factions: number[];
  /** Knesset number (as string) → vote count */
  vote_counts: Record<string, number>;
  faction_counts: Record<string, number>;
  total_votes: number;
  total_bills: number;
  total_persons: number;
  total_vote_results: number;
  /** Human-readable short summary, e.g. "Кнессет 22–25" or null if empty */
  summary: string | null;
}

export async function adminGetAvailableKnessetData(): Promise<AvailableKnessetData> {
  return adminApiFetch<AvailableKnessetData>("/api/admin/ingest/available-data");
}

// ── Full Multi-Knesset Pipeline ───────────────────────────────────────────────

export interface FullPipelineKnessetResult {
  knesset_number: number;
  status: "pending" | "running" | "done" | "error";
  factions?: IngestionStepResult;
  votes?: IngestionStepResult;
  bills?: IngestionStepResult;
  persons?: IngestionStepResult;
  vote_results?: IngestionStepResult;
  [key: string]: unknown;
}

export interface FullPipelineJobStatus extends IngestionJobStatus {
  mode?: "full_pipeline";
  /** list of Knesset numbers being processed, e.g. [25, 24] */
  knessets?: number[];
  /** Knesset number currently being processed in Phase 1 */
  current_knesset?: number | null;
  /** current step name within the active Knesset or analysis phase */
  current_step?: string | null;
  /** per-Knesset step results, keyed by Knesset number as string */
  knesset_results?: Record<string, FullPipelineKnessetResult>;
}

export async function adminTriggerFullPipeline(params: {
  last_n_knessets: number;
  no_llm: boolean;
  current_knesset?: number;
}): Promise<{ job_id: string; status: string; knessets: number[]; message: string }> {
  return adminApiFetch("/api/admin/ingest/full-pipeline", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function adminGetFullPipelineStatus(jobId: string): Promise<FullPipelineJobStatus> {
  return adminApiFetch<FullPipelineJobStatus>(`/api/admin/ingest/status/${jobId}`);
}

// ── Root question generation (question tree) ───────────────────────────────

export interface TopicWithRootQuestion {
  topic_id: string;
  slug: string;
  name_en: string;
  name_he: string;
  name_ru?: string;
  description?: string;
  policy_item_count: number;
  followup_question_count: number;
  root_question: {
    id: string;
    question_text_en: string;
    question_text_he: string;
    question_text_ru?: string;
    status: string;
    neutrality_score?: number;
  } | null;
}

export async function adminGetTopicsWithRootQuestions(): Promise<TopicWithRootQuestion[]> {
  return adminApiFetch<TopicWithRootQuestion[]>("/api/admin/topics/with-root-questions");
}

export async function adminGenerateRootQuestion(
  topicId: string,
  forceRegenerate = false,
): Promise<{
  action: string;
  question_id: string;
  topic_id: string;
  topic_name_en: string;
  question_en: string;
  question_he: string;
  question_ru?: string;
  neutrality_score: number;
  status: string;
  provider: string;
}> {
  return adminApiFetch("/api/admin/llm/generate-root-question", {
    method: "POST",
    body: JSON.stringify({
      topic_id: topicId,
      force_regenerate: forceRegenerate,
    }),
  });
}

// ── Batch root question generation ────────────────────────────────────────────

export interface GenerateAllRootQuestionsJob {
  job_id: string;
  status: "queued" | "running" | "done" | "error";
  total: number;
  completed: number;
  errors: number;
  current_topic: string | null;
  results: Array<{
    topic_slug: string;
    topic_name_en: string;
    action: "created" | "updated" | "skipped_approved" | "error";
    error?: string;
    question_en?: string;
    neutrality_score?: number;
  }>;
  error?: string;
}

export async function adminGenerateAllRootQuestions(params: {
  force_regenerate: boolean;
  skip_existing: boolean;
  max_workers?: number;
}): Promise<{ job_id: string; status: string }> {
  return adminApiFetch("/api/admin/llm/generate-all-root-questions", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function adminGetGenerateAllRootQuestionsStatus(
  jobId: string,
): Promise<GenerateAllRootQuestionsJob> {
  return adminApiFetch<GenerateAllRootQuestionsJob>(
    `/api/admin/llm/generate-all-root-questions/status/${jobId}`,
  );
}

// ── Manual question creation ───────────────────────────────────────────────

export interface ManualQuestionResult {
  action: "created" | "updated";
  question_id: string;
  topic_id: string;
  topic_name_en: string;
  question_text_en: string;
}

export async function adminCreateManualQuestion(params: {
  topic_id: string;
  is_root_question: boolean;
  policy_item_id?: string;
  question_text_en: string;
  question_text_he: string;
  question_text_ru: string;
  answer_scale_type?: string;
  context_note_en?: string;
}): Promise<ManualQuestionResult> {
  return adminApiFetch("/api/admin/questions/manual", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

// ── Database backup and restore ────────────────────────────────────────────

export async function adminDownloadBackup(): Promise<void> {
  const pw = getStoredAdminPassword();
  const resp = await fetch(`${BASE_URL}/api/admin/db/backup`, {
    headers: { "X-Admin-Password": pw },
  });
  if (!resp.ok) throw new Error(`Backup failed: ${resp.status}`);
  const blob = await resp.blob();
  const cd = resp.headers.get("Content-Disposition") ?? "";
  const match = cd.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : "smartvoter_backup.json";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function adminRestoreBackup(
  file: File,
  skipExisting: boolean = true,
): Promise<{
  status: string;
  total_inserted: number;
  total_skipped: number;
  backup_created_at?: string;
  tables: Record<string, { inserted: number; skipped: number }>;
}> {
  const pw = getStoredAdminPassword();
  const form = new FormData();
  form.append("file", file);
  const resp = await fetch(
    `${BASE_URL}/api/admin/db/restore?skip_existing=${skipExisting}`,
    { method: "POST", headers: { "X-Admin-Password": pw }, body: form }
  );
  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`Restore failed ${resp.status}: ${err}`);
  }
  return resp.json();
}

// ── Question Bank bulk generation ──────────────────────────────────────────────

export interface QuestionBankJobStatus {
  job_id: string;
  status: "queued" | "running" | "done" | "error";
  max_questions: number;
  depth_levels: number;
  created?: number;
  skipped?: number;
  errors?: number;
  stale_marked?: number;
  explanations_generated?: number;
  explanations_errors?: number;
  step?: string;
  step_completed?: number;
  step_total?: number;
  message?: string;
  error?: string;
}

export async function adminGenerateQuestionBank(params: {
  max_questions?: number;
  depth_levels?: number;
  max_workers?: number;
  topics?: string[];
  force_regenerate?: boolean;
  root_questions_per_topic?: number;
  generate_explanations?: boolean;
}): Promise<{ job_id: string; status: string; max_questions: number; message: string }> {
  return adminApiFetch("/api/admin/llm/generate-question-bank", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function adminGetQuestionBankStatus(
  jobId: string,
): Promise<QuestionBankJobStatus> {
  return adminApiFetch<QuestionBankJobStatus>(
    `/api/admin/llm/question-bank-status/${jobId}`,
  );
}

export async function adminMarkStaleQuestions(): Promise<{
  marked_stale: number;
  message: string;
}> {
  return adminApiFetch("/api/admin/llm/mark-stale-questions", { method: "POST" });
}

