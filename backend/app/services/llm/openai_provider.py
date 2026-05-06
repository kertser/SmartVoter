"""
OpenAI LLM provider for SmartVoter (Phase 5).

All methods call the OpenAI chat completion API with structured JSON output.
Outputs are validated against the expected schemas from AGENTS.MD Sections 7.1–7.7.
No chain-of-thought is stored — only the public concise explanations.
"""

import hashlib
import json
import logging
import re
from pathlib import Path

from openai import OpenAI, BadRequestError

from backend.app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)

# ── Load prompts from prompts.json ─────────────────────────────────────────────
# Prompts are stored in prompts.json next to this file so they can be edited
# without touching Python source. Each template uses {variable} placeholders
# that are filled via str.format_map() at call time.

_PROMPTS_PATH = Path(__file__).parent / "prompts.json"

def _load_prompts() -> dict:
    try:
        with open(_PROMPTS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to load prompts.json: %s", exc)
        return {}

_PROMPTS: dict = _load_prompts()

def _get_template(name: str) -> tuple[str, str]:
    """Return (user_message_template, prompt_version) for a named prompt."""
    tmpl = _PROMPTS.get("templates", {}).get(name, {})
    return tmpl.get("user_message", ""), tmpl.get("version", "v1.0")

SYSTEM_NEUTRAL: str = _PROMPTS.get(
    "system_neutral",
    "You are a neutral, non-partisan political analyst assistant for the SmartVoter app. "
    "Your job is to classify, summarize, and analyze political positions and legislative data "
    "for Israeli parties. Always be factual, balanced, and concise. "
    "Always respond with valid JSON only — no markdown fences, no extra text.",
)

# Fallback version if JSON is unavailable
PROMPT_VERSION = _PROMPTS.get("_meta", {}).get("version", "v1.0")


# Runtime cache: models discovered to not support custom temperature.
# Pre-populated with known reasoning/next-gen models; grows automatically
# when the API returns an "unsupported_value" error for temperature.
_no_temperature_models: set[str] = {
    # o1 / o3 / o4 reasoning family
    "o1", "o1-mini", "o1-preview",
    "o3", "o3-mini",
    "o4", "o4-mini",
    # GPT-5 generation (confirmed via API error)
    "gpt-5-mini", "gpt-5-nano",
}


def _model_key(model: str) -> str:
    """Normalise model name: strip version suffix for cache lookup.

    'gpt-5-nano-2025-12-01' → 'gpt-5-nano'
    'o3-mini-2025-01-31'   → 'o3-mini'
    """
    # Strip trailing date-like suffixes (-YYYY-MM-DD or -YYYYMMDD)
    return re.sub(r"-\d{4}[-\d]*$", "", model.lower())


def _supports_temperature(model: str) -> bool:
    """Return False if this model is known to reject custom temperature."""
    key = _model_key(model)
    return key not in _no_temperature_models


def _call(client: OpenAI, model: str, messages: list[dict], temperature: float = 0.2) -> dict:
    """Make a chat completion call and parse JSON response.

    Automatically retries without ``temperature`` if the model returns an
    ``unsupported_value`` error for that parameter, and caches the result so
    subsequent calls skip the parameter without an extra round-trip.
    """
    def _run(with_temperature: bool) -> dict:
        kwargs: dict = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        if with_temperature:
            kwargs["temperature"] = temperature
        resp = client.chat.completions.create(**kwargs)
        raw = resp.choices[0].message.content or "{}"
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error("OpenAI returned invalid JSON: %s", raw[:500])
            return {}

    if not _supports_temperature(model):
        return _run(with_temperature=False)

    try:
        return _run(with_temperature=True)
    except BadRequestError as exc:
        # Detect "temperature not supported" and auto-learn for this model
        err_body = exc.body or {}
        if (
            isinstance(err_body, dict)
            and err_body.get("error", {}).get("code") == "unsupported_value"
            and "temperature" in err_body.get("error", {}).get("message", "")
        ):
            key = _model_key(model)
            _no_temperature_models.add(key)
            logger.info(
                "Model '%s' does not support custom temperature — "
                "retrying without it (cached for this session).", model
            )
            return _run(with_temperature=False)
        raise


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
        tmpl, pv = _get_template("summarize_bill_or_vote")
        user_msg = tmpl.format_map({
            "title": input_data.get("title", ""),
            "text": input_data.get("text", "")[:3000],
            "metadata": json.dumps(input_data.get("metadata", {})),
        })
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {"role": "user", "content": user_msg},
        ]
        result = _call(self.client, self.model, messages)
        return {
            "plain_summary": result.get("plain_summary", ""),
            "main_policy_change": result.get("main_policy_change", ""),
            "affected_groups": result.get("affected_groups", []),
            "is_procedural": bool(result.get("is_procedural", False)),
            "importance_score": float(result.get("importance_score", 0.5)),
            "reasoning_summary": result.get("reasoning_summary", ""),
            "_prompt_version": pv,
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
        tmpl, pv = _get_template("classify_and_extract")
        user_msg = tmpl.format_map({
            "title": input_data.get("title", ""),
            "description": input_data.get("description", ""),
            "topics_list": topics_list,
        })
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {"role": "user", "content": user_msg},
        ]
        result = _call(self.client, self.model, messages)
        return {
            "topics": result.get("topics", []),
            "primary_topic": result.get("primary_topic", ""),
            "classification_confidence": float(result.get("classification_confidence", 0.5)),
            "axis_name": result.get("axis_name", ""),
            "negative_pole": result.get("negative_pole", ""),
            "positive_pole": result.get("positive_pole", ""),
            "direction_explanation": result.get("direction_explanation", ""),
            "_prompt_version": pv,
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
        tmpl, pv = _get_template("classify_policy_item")
        user_msg = tmpl.format_map({
            "title": input_data.get("title", ""),
            "description": input_data.get("description", ""),
            "topics_list": topics_list,
        })
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {"role": "user", "content": user_msg},
        ]
        result = _call(self.client, self.model, messages)
        return {
            "topics": result.get("topics", []),
            "primary_topic": result.get("primary_topic", ""),
            "classification_confidence": float(result.get("classification_confidence", 0.5)),
            "_prompt_version": pv,
            "_input_hash": _input_hash(input_data),
        }

    # ── 7.3 Policy-axis extraction ─────────────────────────────────────────────

    def extract_policy_axis(self, input_data: dict) -> dict:
        tmpl, pv = _get_template("extract_policy_axis")
        user_msg = tmpl.format_map({
            "title": input_data.get("title", ""),
            "description": input_data.get("description", ""),
        })
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {"role": "user", "content": user_msg},
        ]
        result = _call(self.client, self.model, messages)
        return {
            "axis_name": result.get("axis_name", ""),
            "negative_pole": result.get("negative_pole", ""),
            "positive_pole": result.get("positive_pole", ""),
            "direction_explanation": result.get("direction_explanation", ""),
            "_prompt_version": pv,
            "_input_hash": _input_hash(input_data),
        }

    # ── 7.5 Neutral question generation ───────────────────────────────────────

    def generate_question(self, input_data: dict) -> dict:
        tmpl, pv = _get_template("generate_question")
        user_msg = tmpl.format_map({
            "title": input_data.get("title", ""),
            "description": input_data.get("description", ""),
            "directional_axis": input_data.get("directional_axis", ""),
        })
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {"role": "user", "content": user_msg},
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
            "_prompt_version": pv,
            "_input_hash": _input_hash(input_data),
        }

    # ── OPTIMISED: generate + critique in one call ────────────────────────────

    def generate_question_with_critique(self, input_data: dict) -> dict:
        """
        Single prompt that generates a neutral question AND self-critiques it.
        Replaces two separate generate_question + critique_question calls.
        ~50% cost reduction for question_pipeline step.
        """
        tmpl, pv = _get_template("generate_question_with_critique")
        user_msg = tmpl.format_map({
            "title": input_data.get("title", ""),
            "description": input_data.get("description", ""),
            "directional_axis": input_data.get("directional_axis", ""),
        })
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {"role": "user", "content": user_msg},
        ]
        result = _call(self.client, self.model, messages)

        question_en = result.get("question_en", "")
        is_loaded = bool(result.get("is_loaded", False))
        neutrality_risk = result.get("neutrality_risk", "medium")

        if is_loaded and result.get("suggested_revision"):
            question_en = result["suggested_revision"]

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
            "_prompt_version": pv,
            "_input_hash": _input_hash(input_data),
        }

    # ── Root question generation (topic-level) ────────────────────────────────

    def generate_root_question(self, input_data: dict) -> dict:
        """
        Generate a broad topic-level opening question for the questionnaire.
        Uses a dedicated prompt optimised for root questions — NOT the same
        as policy-item question generation.

        input_data keys:
            topic_name_en   – English topic name
            topic_name_he   – Hebrew topic name
            topic_name_ru   – Russian topic name (or empty string)
            topic_description – plain-language topic description
        """
        tmpl, pv = _get_template("root_question")
        user_msg = tmpl.format_map({
            "topic_name_en": input_data.get("topic_name_en", ""),
            "topic_name_he": input_data.get("topic_name_he", ""),
            "topic_name_ru": input_data.get("topic_name_ru", ""),
            "topic_description": input_data.get("topic_description", ""),
        })
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {"role": "user", "content": user_msg},
        ]
        result = _call(self.client, self.model, messages)

        question_en = result.get("question_en", "")
        is_loaded = bool(result.get("is_loaded", False))
        neutrality_risk = result.get("neutrality_risk", "medium")

        # Auto-apply suggested revision when the model flags bias
        if is_loaded and result.get("suggested_revision"):
            question_en = result["suggested_revision"]

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
            "is_loaded": is_loaded,
            "bias_direction": result.get("bias_direction"),
            "suggested_revision": result.get("suggested_revision"),
            "reading_level": result.get("reading_level", "general public"),
            "requires_context": bool(result.get("requires_context", False)),
            "context_note": result.get("context_note"),
            "neutrality_score": neutrality_score,
            "_prompt_version": pv,
            "_input_hash": _input_hash(input_data),
        }

    # ── 7.6 Question critique ──────────────────────────────────────────────────

    def critique_question(self, input_data: dict) -> dict:
        tmpl, pv = _get_template("critique_question")
        user_msg = tmpl.format_map({"question": input_data.get("question", "")})
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {"role": "user", "content": user_msg},
        ]
        result = _call(self.client, self.model, messages)
        return {
            "is_loaded": bool(result.get("is_loaded", False)),
            "bias_direction": result.get("bias_direction"),
            "suggested_revision": result.get("suggested_revision"),
            "reading_level": result.get("reading_level", "general public"),
            "requires_context": bool(result.get("requires_context", False)),
            "context_note": result.get("context_note"),
            "_prompt_version": pv,
            "_input_hash": _input_hash(input_data),
        }

    # ── 7.4 Party-position inference ──────────────────────────────────────────

    def infer_party_position(self, input_data: dict) -> dict:
        tmpl, pv = _get_template("infer_party_position")
        user_msg = tmpl.format_map({
            "party_name": input_data.get("party_name", ""),
            "policy_title": input_data.get("policy_title", ""),
            "directional_axis": input_data.get("directional_axis", ""),
            "negative_pole": input_data.get("negative_pole", "one end"),
            "positive_pole": input_data.get("positive_pole", "other end"),
            "evidence": json.dumps(input_data.get("evidence", [])),
        })
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {"role": "user", "content": user_msg},
        ]
        result = _call(self.client, self.model, messages)
        return {
            "party_position_mean": float(result.get("party_position_mean", 0.0)),
            "uncertainty": float(result.get("uncertainty", 0.5)),
            "evidence_strength": float(result.get("evidence_strength", 0.3)),
            "evidence_sources": result.get("evidence_sources", []),
            "explanation": result.get("explanation", ""),
            "_prompt_version": pv,
            "_input_hash": _input_hash(input_data),
        }

    # ── Party lineage inference ────────────────────────────────────────────────

    def infer_party_lineage(self, input_data: dict) -> dict:
        tmpl, pv = _get_template("infer_party_lineage")
        user_msg = tmpl.format_map({
            "from_party": input_data.get("from_party", ""),
            "to_party": input_data.get("to_party", ""),
            "context": input_data.get("context", ""),
        })
        messages = [
            {"role": "system", "content": SYSTEM_NEUTRAL},
            {"role": "user", "content": user_msg},
        ]
        result = _call(self.client, self.model, messages)
        return {
            "relation_type": result.get("relation_type", "successor"),
            "continuity_weight": float(result.get("continuity_weight", 0.5)),
            "explanation": result.get("explanation", ""),
            "confidence": float(result.get("confidence", 0.5)),
            "_prompt_version": pv,
            "_input_hash": _input_hash(input_data),
        }

