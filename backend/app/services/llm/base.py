from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract interface for all LLM providers. Every method returns a validated dict.

    Every concrete subclass MUST define both class-level attributes:
        provider: str   — e.g. "openai", "mock", "fallback"
        model:    str   — e.g. "gpt-4o-mini", "mock-v1"

    They are declared here with empty defaults so that AuditedLLMService can always
    read them without an AttributeError, even if a subclass omits them.
    """

    provider: str = ""   # overridden by each concrete provider
    model: str = ""      # overridden by each concrete provider

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

    def classify_and_extract(self, input_data: dict) -> dict:
        """
        OPTIMISATION: Combined classify_policy_item + extract_policy_axis in a single LLM call.
        Saves one HTTP round-trip per vote/bill processed.
        Returns the merged output of both methods under a single prompt.
        Default: calls both methods separately (2 calls). Override in concrete providers.
        """
        cls = self.classify_policy_item(input_data)
        axis = self.extract_policy_axis(input_data)
        return {**cls, **axis}

    @abstractmethod
    def generate_question(self, input_data: dict) -> dict:
        """Returns: question, answer_scale, neutrality_risk, loaded_terms, source_refs"""

    @abstractmethod
    def critique_question(self, input_data: dict) -> dict:
        """Returns: is_loaded, bias_direction, suggested_revision, reading_level,
        requires_context, context_note"""

    @abstractmethod
    def generate_question_with_critique(self, input_data: dict) -> dict:
        """
        OPTIMISATION: Combined generate + critique in a single LLM call.
        Returns merged output including a computed neutrality_score (float 0–1).
        Default: calls both methods separately (2 calls). Override in concrete providers.
        """

    @abstractmethod
    def generate_root_question(self, input_data: dict) -> dict:
        """
        Generate a BROAD TOPIC-LEVEL opening question for the questionnaire.
        Uses a dedicated VALUES-FIRST prompt — NOT the same as generate_question_with_critique.

        The goal is to discover what the user genuinely values in this policy area,
        starting from everyday-life experience rather than abstract policy positions.

        input_data keys:
            topic_name_en, topic_name_he, topic_name_ru, topic_description

        Returns: question_en, question_he, question_ru, context_note_en,
                 answer_scale, neutrality_risk, neutrality_score, is_loaded,
                 bias_direction, suggested_revision, requires_context, context_note,
                 everyday_life_hook
        """

    def generate_follow_up_from_salience(self, input_data: dict) -> dict:
        """
        Generate a targeted follow-up question for a topic the user rated as
        highly important (high salience). Helps discover WHICH SPECIFIC ASPECT
        of the topic the user cares about.

        Default: raises NotImplementedError. Override in concrete providers.

        input_data keys:
            topic_name_en, topic_description, policy_items_summary (list of dicts)
        """
        raise NotImplementedError(
            "generate_follow_up_from_salience not implemented by this provider."
        )

    @abstractmethod
    def infer_party_position(self, input_data: dict) -> dict:
        """Returns: party_position_mean, uncertainty, evidence_strength,
        evidence_sources, explanation"""

    @abstractmethod
    def infer_party_lineage(self, input_data: dict) -> dict:
        """Returns: relation_type, continuity_weight, explanation, confidence"""

