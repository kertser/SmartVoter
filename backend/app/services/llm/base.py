from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract interface for all LLM providers. Every method returns a validated dict."""

    @abstractmethod
    def summarize_bill_or_vote(self, input_data: dict) -> dict:
        """Returns: plain_summary, main_policy_change, affected_groups, is_procedural,
        importance_score, reasoning_summary"""

    @abstractmethod
    def classify_policy_item(self, input_data: dict) -> dict:
        """Returns: topics (list of {topic, confidence}), primary_topic, classification_confidence"""

    @abstractmethod
    def extract_policy_axis(self, input_data: dict) -> dict:
        """Returns: axis_name, negative_pole, positive_pole, direction_explanation"""

    @abstractmethod
    def generate_question(self, input_data: dict) -> dict:
        """Returns: question, answer_scale, neutrality_risk, loaded_terms, source_refs"""

    @abstractmethod
    def critique_question(self, input_data: dict) -> dict:
        """Returns: is_loaded, bias_direction, suggested_revision, reading_level,
        requires_context, context_note"""

    @abstractmethod
    def infer_party_position(self, input_data: dict) -> dict:
        """Returns: party_position_mean, uncertainty, evidence_strength,
        evidence_sources, explanation"""

    @abstractmethod
    def infer_party_lineage(self, input_data: dict) -> dict:
        """Returns: relation_type, continuity_weight, explanation, confidence"""

