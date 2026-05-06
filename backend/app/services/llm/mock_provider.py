import hashlib
import random
from backend.app.services.llm.base import LLMProvider


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for development/testing. Returns plausible-looking fake outputs.
    No real API calls are made. All outputs are stored for audit purposes."""

    provider = "mock"
    model = "mock-v1"

    def _input_hash(self, input_data: dict) -> str:
        return hashlib.sha256(str(sorted(input_data.items())).encode()).hexdigest()

    def summarize_bill_or_vote(self, input_data: dict) -> dict:
        return {
            "plain_summary": "This bill proposes changes to the legislative framework.",
            "main_policy_change": "Modifies oversight mechanisms.",
            "affected_groups": ["general public", "government institutions"],
            "is_procedural": False,
            "importance_score": round(random.uniform(0.4, 0.9), 2),
            "reasoning_summary": "Mock summary generated for development purposes.",
        }

    def classify_policy_item(self, input_data: dict) -> dict:
        return {
            "topics": [
                {"topic": "judiciary", "confidence": 0.87},
                {"topic": "governance_corruption", "confidence": 0.54},
            ],
            "primary_topic": "judiciary",
            "classification_confidence": 0.87,
        }

    def extract_policy_axis(self, input_data: dict) -> dict:
        return {
            "axis_name": "judicial_review_scope",
            "negative_pole": "broader judicial review and stronger court independence",
            "positive_pole": "greater parliamentary control over judicial review",
            "direction_explanation": "Positive values indicate support for limiting judicial review.",
        }

    def classify_and_extract(self, input_data: dict) -> dict:
        """Optimised combined mock: single call returns both classification and axis."""
        return {
            "topics": [
                {"topic": "judiciary", "confidence": 0.87},
                {"topic": "governance_corruption", "confidence": 0.54},
            ],
            "primary_topic": "judiciary",
            "classification_confidence": 0.87,
            "axis_name": "judicial_review_scope",
            "negative_pole": "broader judicial review and stronger court independence",
            "positive_pole": "greater parliamentary control over judicial review",
            "direction_explanation": "Positive values indicate support for limiting judicial review.",
            "_prompt_version": "v1.0",
        }

    def generate_question(self, input_data: dict) -> dict:
        return {
            "question": "Should the Knesset have greater power to limit the Supreme Court's ability to strike down laws?",
            "question_en": "Should the Knesset have greater power to limit the Supreme Court's ability to strike down laws?",
            "question_he": "האם לכנסת צריכה להיות סמכות רבה יותר להגביל את בית המשפט העליון?",
            "question_ru": "Должен ли Кнессет иметь больше полномочий для ограничения Верховного суда?",
            "answer_scale": [
                "Strongly oppose",
                "Somewhat oppose",
                "Neutral / unsure",
                "Somewhat support",
                "Strongly support",
            ],
            "neutrality_risk": "medium",
            "loaded_terms": [],
            "source_refs": [],
        }

    def critique_question(self, input_data: dict) -> dict:
        return {
            "is_loaded": False,
            "bias_direction": None,
            "suggested_revision": None,
            "reading_level": "general public",
            "requires_context": True,
            "context_note": "Explain what judicial review means.",
        }

    def generate_question_with_critique(self, input_data: dict) -> dict:
        """Optimised combined mock: single call returns question + critique + neutrality_score."""
        return {
            "question": "Should the Knesset have greater power to limit the Supreme Court's ability to strike down laws?",
            "question_en": "Should the Knesset have greater power to limit the Supreme Court's ability to strike down laws?",
            "question_he": "האם לכנסת צריכה להיות סמכות רבה יותר להגביל את בית המשפט העליון?",
            "question_ru": "Должен ли Кнессет иметь больше полномочий для ограничения Верховного суда?",
            "context_note_en": "Judicial review allows courts to strike down laws that conflict with basic laws.",
            "answer_scale": [
                "Strongly oppose",
                "Somewhat oppose",
                "Neutral / unsure",
                "Somewhat support",
                "Strongly support",
            ],
            "neutrality_risk": "medium",
            "loaded_terms": [],
            "source_refs": [],
            "is_loaded": False,
            "bias_direction": None,
            "suggested_revision": None,
            "reading_level": "general public",
            "requires_context": True,
            "context_note": "Explain what judicial review means.",
            "neutrality_score": 0.7,
            "_prompt_version": "v1.0",
        }

    def infer_party_position(self, input_data: dict) -> dict:
        position = round(random.uniform(-0.8, 0.8), 2)
        return {
            "party_position_mean": position,
            "uncertainty": round(random.uniform(0.1, 0.3), 2),
            "evidence_strength": round(random.uniform(0.6, 0.95), 2),
            "evidence_sources": [],
            "explanation": "Mock party position inferred from available evidence.",
        }

    def infer_party_lineage(self, input_data: dict) -> dict:
        return {
            "relation_type": "rename",
            "continuity_weight": 0.85,
            "explanation": "The party rebranded without significant structural change.",
            "confidence": 0.80,
        }

