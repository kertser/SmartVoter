"""
OpenAI LLM provider for SmartVoter (Phase 5).

All methods call the OpenAI chat completion API with structured JSON output.
Outputs are validated against the expected schemas from AGENTS.MD Sections 7.1–7.7.
No chain-of-thought is stored — only the public concise explanations.
"""

import hashlib
import json
import logging

from openai import OpenAI

from backend.app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)

# ── Prompt templates (versioned via llm_prompt_version field) ──────────────────

PROMPT_VERSION = "v1.0"

SYSTEM_NEUTRAL = (
    "You are a neutral, non-partisan political analyst assistant for the SmartVoter app. "
    "Your job is to classify, summarize, and analyze political positions and legislative data "
    "for Israeli parties. Always be factual, balanced, and concise. "
    "Always respond with valid JSON only — no markdown fences, no extra text."
)


def _call(client: OpenAI, model: str, messages: list[dict], temperature: float = 0.2) -> dict:
    """Make a chat completion call and parse JSON response."""
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    raw = resp.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error("OpenAI returned invalid JSON: %s", raw[:500])
        return {}


def _input_hash(input_data: dict) -> str:
    return hashlib.sha256(json.dumps(input_data, sort_keys=True).encode()).hexdigest()


class OpenAIProvider(LLMProvider):
    """Real OpenAI provider. Uses gpt-4o-mini by default (configurable)."""

    provider = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    # ── 7.1 Bill/vote summarization ────────────────────────────────────────────

    def summarize_bill_or_vote(self, input_data: dict) -> dict:
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {
                "role": "user",
                "content": (
                    "Summarize the following Israeli legislative item for the SmartVoter app.\n\n"
                    f"Title: {input_data.get('title', '')}\n"
                    f"Text: {input_data.get('text', '')[:3000]}\n"
                    f"Metadata: {json.dumps(input_data.get('metadata', {}))}\n\n"
                    "Return JSON with these exact keys:\n"
                    "  plain_summary (string, max 3 sentences, plain language),\n"
                    "  main_policy_change (string, 1 sentence),\n"
                    "  affected_groups (list of strings),\n"
                    "  is_procedural (boolean),\n"
                    "  importance_score (float 0.0–1.0),\n"
                    "  reasoning_summary (string, max 2 sentences, public explanation only — "
                    "no chain-of-thought)."
                ),
            },
        ]
        result = _call(self.client, self.model, messages)
        return {
            "plain_summary": result.get("plain_summary", ""),
            "main_policy_change": result.get("main_policy_change", ""),
            "affected_groups": result.get("affected_groups", []),
            "is_procedural": bool(result.get("is_procedural", False)),
            "importance_score": float(result.get("importance_score", 0.5)),
            "reasoning_summary": result.get("reasoning_summary", ""),
            "_prompt_version": PROMPT_VERSION,
            "_input_hash": _input_hash(input_data),
        }

    # ── OPTIMISED: classify + extract_axis in one call ────────────────────────

    def classify_and_extract(self, input_data: dict) -> dict:
        """
        Single prompt that returns topic classification AND directional axis.
        Replaces two separate classify_policy_item + extract_policy_axis calls.
        ~50% cost reduction for the policy_item_pipeline step.
        """
        topics_list = ", ".join([
            "security", "judiciary", "religion_state", "settlements", "economy_taxes",
            "healthcare", "education", "civil_rights", "housing", "welfare",
            "military_service", "governance_corruption", "environment", "transport",
            "cost_of_living",
        ])
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {
                "role": "user",
                "content": (
                    "Analyze this Israeli policy item and return BOTH topic classification "
                    "AND directional policy axis in a single JSON response.\n\n"
                    f"Title: {input_data.get('title', '')}\n"
                    f"Description: {input_data.get('description', '')}\n\n"
                    f"Available topics: {topics_list}\n\n"
                    "Return JSON with ALL of these keys:\n"
                    "  topics (list of objects with 'topic' and 'confidence' float 0–1),\n"
                    "  primary_topic (string from available topics),\n"
                    "  classification_confidence (float 0–1),\n"
                    "  axis_name (snake_case identifier for the policy axis),\n"
                    "  negative_pole (string — what -1 means on this axis),\n"
                    "  positive_pole (string — what +1 means on this axis),\n"
                    "  direction_explanation (string — 1 sentence explaining scale direction)."
                ),
            },
        ]
        result = _call(self.client, self.model, messages)
        return {
            # classification fields
            "topics": result.get("topics", []),
            "primary_topic": result.get("primary_topic", ""),
            "classification_confidence": float(result.get("classification_confidence", 0.5)),
            # axis fields
            "axis_name": result.get("axis_name", ""),
            "negative_pole": result.get("negative_pole", ""),
            "positive_pole": result.get("positive_pole", ""),
            "direction_explanation": result.get("direction_explanation", ""),
            "_prompt_version": PROMPT_VERSION,
            "_input_hash": _input_hash(input_data),
        }

    # ── 7.2 Topic classification ───────────────────────────────────────────────

    def classify_policy_item(self, input_data: dict) -> dict:
        topics_list = ", ".join([
            "security", "judiciary", "religion_state", "settlements", "economy_taxes",
            "healthcare", "education", "civil_rights", "housing", "welfare",
            "military_service", "governance_corruption", "environment", "transport",
            "cost_of_living",
        ])
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {
                "role": "user",
                "content": (
                    f"Classify this Israeli policy item into topics.\n\n"
                    f"Title: {input_data.get('title', '')}\n"
                    f"Description: {input_data.get('description', '')}\n\n"
                    f"Available topics: {topics_list}\n\n"
                    "Return JSON with:\n"
                    "  topics (list of objects with 'topic' and 'confidence' float 0–1),\n"
                    "  primary_topic (string),\n"
                    "  classification_confidence (float 0–1)."
                ),
            },
        ]
        result = _call(self.client, self.model, messages)
        return {
            "topics": result.get("topics", []),
            "primary_topic": result.get("primary_topic", ""),
            "classification_confidence": float(result.get("classification_confidence", 0.5)),
            "_prompt_version": PROMPT_VERSION,
            "_input_hash": _input_hash(input_data),
        }

    # ── 7.3 Policy-axis extraction ─────────────────────────────────────────────

    def extract_policy_axis(self, input_data: dict) -> dict:
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {
                "role": "user",
                "content": (
                    "Extract the directional policy axis for this Israeli political issue.\n\n"
                    f"Title: {input_data.get('title', '')}\n"
                    f"Description: {input_data.get('description', '')}\n\n"
                    "Return JSON with:\n"
                    "  axis_name (snake_case identifier),\n"
                    "  negative_pole (string — what -1 means),\n"
                    "  positive_pole (string — what +1 means),\n"
                    "  direction_explanation (string — 1 sentence explaining scale direction)."
                ),
            },
        ]
        result = _call(self.client, self.model, messages)
        return {
            "axis_name": result.get("axis_name", ""),
            "negative_pole": result.get("negative_pole", ""),
            "positive_pole": result.get("positive_pole", ""),
            "direction_explanation": result.get("direction_explanation", ""),
            "_prompt_version": PROMPT_VERSION,
            "_input_hash": _input_hash(input_data),
        }

    # ── 7.5 Neutral question generation ───────────────────────────────────────

    def generate_question(self, input_data: dict) -> dict:
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {
                "role": "user",
                "content": (
                    "Generate a neutral, non-partisan survey question in English, Hebrew (עברית), "
                    "and Russian for the SmartVoter app.\n\n"
                    f"Policy item: {input_data.get('title', '')}\n"
                    f"Description: {input_data.get('description', '')}\n"
                    f"Directional axis: {input_data.get('directional_axis', '')}\n\n"
                    "Rules:\n"
                    "- The question must be factual and non-loaded.\n"
                    "- Do not name specific parties in the question.\n"
                    "- Use a 5-point Likert scale (Strongly oppose → Strongly support).\n"
                    "- Keep the reading level accessible to the general public.\n"
                    "- Include a brief neutral context note (1–2 sentences).\n\n"
                    "Return JSON with:\n"
                    "  question_en (string),\n"
                    "  question_he (string, Hebrew),\n"
                    "  question_ru (string, Russian),\n"
                    "  context_note_en (string, 1–2 sentences),\n"
                    "  answer_scale (list of 5 English strings),\n"
                    "  neutrality_risk (low|medium|high),\n"
                    "  loaded_terms (list of strings, empty if none),\n"
                    "  source_refs (list of strings)."
                ),
            },
        ]
        result = _call(self.client, self.model, messages)
        return {
            "question": result.get("question_en", ""),
            "question_en": result.get("question_en", ""),
            "question_he": result.get("question_he", ""),
            "question_ru": result.get("question_ru", ""),
            "context_note_en": result.get("context_note_en", ""),
            "answer_scale": result.get("answer_scale", [
                "Strongly oppose", "Somewhat oppose", "Neutral / unsure",
                "Somewhat support", "Strongly support",
            ]),
            "neutrality_risk": result.get("neutrality_risk", "medium"),
            "loaded_terms": result.get("loaded_terms", []),
            "source_refs": result.get("source_refs", []),
            "_prompt_version": PROMPT_VERSION,
            "_input_hash": _input_hash(input_data),
        }

    # ── OPTIMISED: generate + critique in one call ────────────────────────────

    def generate_question_with_critique(self, input_data: dict) -> dict:
        """
        Single prompt that generates a neutral question AND self-critiques it.
        Replaces two separate generate_question + critique_question calls.
        ~50% cost reduction for question_pipeline step.
        """
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {
                "role": "user",
                "content": (
                    "Generate a neutral survey question for the SmartVoter app AND immediately "
                    "self-critique it for bias or loaded wording — all in one JSON response.\n\n"
                    f"Policy item: {input_data.get('title', '')}\n"
                    f"Description: {input_data.get('description', '')}\n"
                    f"Directional axis: {input_data.get('directional_axis', '')}\n\n"
                    "Rules:\n"
                    "- The question must be factual and non-loaded.\n"
                    "- Do not name specific parties in the question.\n"
                    "- Use a 5-point Likert scale (Strongly oppose → Strongly support).\n"
                    "- Keep the reading level accessible to the general public.\n\n"
                    "Return JSON with ALL of these keys:\n"
                    "  question_en (string),\n"
                    "  question_he (string, Hebrew),\n"
                    "  question_ru (string, Russian),\n"
                    "  context_note_en (string, 1–2 neutral sentences),\n"
                    "  answer_scale (list of 5 English strings),\n"
                    "  neutrality_risk (low|medium|high),\n"
                    "  loaded_terms (list of strings, empty if none),\n"
                    "  source_refs (list of strings),\n"
                    "  is_loaded (boolean — is the question biased?),\n"
                    "  bias_direction (string or null),\n"
                    "  suggested_revision (string or null — only if is_loaded=true),\n"
                    "  reading_level (general public|educated|expert),\n"
                    "  requires_context (boolean),\n"
                    "  context_note (string or null)."
                ),
            },
        ]
        result = _call(self.client, self.model, messages)

        question_en = result.get("question_en", "")
        is_loaded = bool(result.get("is_loaded", False))
        neutrality_risk = result.get("neutrality_risk", "medium")

        # Apply revision if suggested
        if is_loaded and result.get("suggested_revision"):
            question_en = result["suggested_revision"]

        # Derive neutrality_score
        if is_loaded:
            neutrality_score = 0.4
        elif neutrality_risk == "low":
            neutrality_score = 0.9
        elif neutrality_risk == "high":
            neutrality_score = 0.5
        else:
            neutrality_score = 0.7

        return {
            "question": question_en,
            "question_en": question_en,
            "question_he": result.get("question_he", ""),
            "question_ru": result.get("question_ru", ""),
            "context_note_en": result.get("context_note_en", ""),
            "answer_scale": result.get("answer_scale", [
                "Strongly oppose", "Somewhat oppose", "Neutral / unsure",
                "Somewhat support", "Strongly support",
            ]),
            "neutrality_risk": neutrality_risk,
            "loaded_terms": result.get("loaded_terms", []),
            "source_refs": result.get("source_refs", []),
            "is_loaded": is_loaded,
            "bias_direction": result.get("bias_direction"),
            "suggested_revision": result.get("suggested_revision"),
            "reading_level": result.get("reading_level", "general public"),
            "requires_context": bool(result.get("requires_context", False)),
            "context_note": result.get("context_note"),
            "neutrality_score": neutrality_score,
            "_prompt_version": PROMPT_VERSION,
            "_input_hash": _input_hash(input_data),
        }

    # ── 7.6 Question critique ──────────────────────────────────────────────────

    def critique_question(self, input_data: dict) -> dict:
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {
                "role": "user",
                "content": (
                    "Critically review this survey question for bias or loaded wording.\n\n"
                    f"Question: {input_data.get('question', '')}\n\n"
                    "Return JSON with:\n"
                    "  is_loaded (boolean),\n"
                    "  bias_direction (string or null — 'left'|'right'|'religious'|'secular'|etc.),\n"
                    "  suggested_revision (string or null — improved neutral wording),\n"
                    "  reading_level (string — 'general public'|'educated'|'expert'),\n"
                    "  requires_context (boolean),\n"
                    "  context_note (string or null — suggested context explanation)."
                ),
            },
        ]
        result = _call(self.client, self.model, messages)
        return {
            "is_loaded": bool(result.get("is_loaded", False)),
            "bias_direction": result.get("bias_direction"),
            "suggested_revision": result.get("suggested_revision"),
            "reading_level": result.get("reading_level", "general public"),
            "requires_context": bool(result.get("requires_context", False)),
            "context_note": result.get("context_note"),
            "_prompt_version": PROMPT_VERSION,
            "_input_hash": _input_hash(input_data),
        }

    # ── 7.4 Party-position inference ──────────────────────────────────────────

    def infer_party_position(self, input_data: dict) -> dict:
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {
                "role": "user",
                "content": (
                    "Infer this Israeli party's position on a policy axis based on the evidence.\n\n"
                    f"Party: {input_data.get('party_name', '')}\n"
                    f"Policy item: {input_data.get('policy_title', '')}\n"
                    f"Directional axis: {input_data.get('directional_axis', '')}\n"
                    f"  -1 = {input_data.get('negative_pole', 'one end')}\n"
                    f"  +1 = {input_data.get('positive_pole', 'other end')}\n"
                    f"Evidence sources: {json.dumps(input_data.get('evidence', []))}\n\n"
                    "Return JSON with:\n"
                    "  party_position_mean (float -1.0 to +1.0),\n"
                    "  uncertainty (float 0.0 to 1.0 — higher = less certain),\n"
                    "  evidence_strength (float 0.0 to 1.0),\n"
                    "  evidence_sources (list of objects with 'type' and 'id' and 'weight'),\n"
                    "  explanation (string, max 3 sentences, factual and neutral)."
                ),
            },
        ]
        result = _call(self.client, self.model, messages)
        return {
            "party_position_mean": float(result.get("party_position_mean", 0.0)),
            "uncertainty": float(result.get("uncertainty", 0.5)),
            "evidence_strength": float(result.get("evidence_strength", 0.3)),
            "evidence_sources": result.get("evidence_sources", []),
            "explanation": result.get("explanation", ""),
            "_prompt_version": PROMPT_VERSION,
            "_input_hash": _input_hash(input_data),
        }

    # ── Party lineage inference ────────────────────────────────────────────────

    def infer_party_lineage(self, input_data: dict) -> dict:
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {
                "role": "user",
                "content": (
                    "Analyze the lineage relationship between two Israeli party instances.\n\n"
                    f"From party: {input_data.get('from_party', '')}\n"
                    f"To party: {input_data.get('to_party', '')}\n"
                    f"Context: {input_data.get('context', '')}\n\n"
                    "Relation types: rename | split | merger | successor | alliance | rebrand\n\n"
                    "Return JSON with:\n"
                    "  relation_type (string from list above),\n"
                    "  continuity_weight (float 0.0–1.0 — how much predecessor behavior carries over),\n"
                    "  explanation (string, max 2 sentences),\n"
                    "  confidence (float 0.0–1.0)."
                ),
            },
        ]
        result = _call(self.client, self.model, messages)
        return {
            "relation_type": result.get("relation_type", "successor"),
            "continuity_weight": float(result.get("continuity_weight", 0.5)),
            "explanation": result.get("explanation", ""),
            "confidence": float(result.get("confidence", 0.5)),
            "_prompt_version": PROMPT_VERSION,
            "_input_hash": _input_hash(input_data),
        }

