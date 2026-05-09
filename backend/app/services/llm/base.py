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

    def explain_question_context(self, input_data: dict) -> dict:
        """
        Generate a detailed, language-specific background explanation of an Israeli
        political question for a general voter.

        input_data keys:
            question_text, topic_name, policy_description, directional_axis, language_name

        Returns: background, why_relevant, support_side, oppose_side, everyday_example
        All values in the requested language.
        """
        raise NotImplementedError("explain_question_context not implemented by this provider.")

    def generate_discovery_question(self, input_data: dict) -> dict:
        """
        Generate a question for a niche policy item where a non-mainstream party
        has a strong, evidence-backed legislative position.  Uses the
        'discovery_question_from_niche' prompt which explicitly frames questions
        as revealing unexpected policy areas users may not have considered.

        Default: falls back to generate_question. Override in concrete providers
        to use the dedicated discovery prompt.

        input_data keys:
            title, description, directional_axis, evidence_context
        Returns: question_en, question_he, question_ru, context_note_en,
                 everyday_life_hook, answer_scale, discovery_rationale,
                 neutrality_risk, neutrality_score, is_loaded, etc.
        """
        return self.generate_question(input_data)

    def generate_question_bank_item(self, input_data: dict) -> dict:
        """
        Generate a single question for the pre-built question bank.
        Awareness of current date (May 2026) is injected via input_data['current_context'].

        Unlike generate_question_with_critique (which targets a single policy item
        without date context), this method uses the 'generate_question_bank_item'
        prompt that explicitly knows what is and isn't currently relevant
        in Israeli politics.

        input_data keys (in addition to standard policy-item fields):
            title, description, directional_axis
            current_context: str  — CURRENT_DATE_CONTEXT injected by the pipeline
            direction_hint: str (optional) — for depth-2 directional follow-ups

        Returns: question_en, question_he, question_ru, context_note_en,
                 answer_scale, neutrality_risk, subtopic_tag, is_loaded, etc.

        Default: falls back to generate_question (ignores current_context).
        Override in concrete providers to use the dedicated prompt.
        """
        return self.generate_question(input_data)

    @abstractmethod
    def infer_party_position(self, input_data: dict) -> dict:
        """Returns: party_position_mean, uncertainty, evidence_strength,
        evidence_sources, explanation"""

    @abstractmethod
    def infer_party_lineage(self, input_data: dict) -> dict:
        """Returns: relation_type, continuity_weight, explanation, confidence"""

    def check_question_relevance(self, input_data: dict) -> dict:
        """
        Check whether a question is still relevant/current as of today's date.

        Uses the LLM (optionally with web search) to assess if the question
        references outdated events, resolved controversies, or expired legislation.

        input_data keys:
            question_en: str        — question text in English
            question_he: str        — question text in Hebrew
            policy_description: str — policy item description
            directional_axis: str   — policy axis label
            current_date: str       — ISO date string "YYYY-MM-DD"

        Returns:
            is_relevant: bool       — True if the question is still current/active
            is_stale: bool          — True if the question refers to outdated content
            relevance_score: float  — 0.0 (fully stale) .. 1.0 (highly current)
            staleness_reason: str   — short explanation if stale
            confidence: float       — confidence in the relevance assessment
        """
        # Default: assume relevant (conservative — avoids false stale marking)
        return {
            "is_relevant": True,
            "is_stale": False,
            "relevance_score": 0.8,
            "staleness_reason": "",
            "confidence": 0.5,
        }

