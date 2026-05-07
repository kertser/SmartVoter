"""
Question format validation for SmartVoter.

Every question served to users MUST be a CLOSED PROPOSITION answerable on the
Strongly Oppose → Strongly Support scale. This module provides:

1. `is_closed_question(text)` — fast heuristic check (no LLM needed)
2. `fix_open_question(text)` — attempts to rephrase an open question into a closed one
3. `QuestionFormatError` — raised when a question fails format validation

Design rule (AGENTS.MD v1.3):
    A question is VALID if and only if a user can clearly say
    "I support this" or "I oppose this" — with degrees in between.

    FORBIDDEN question types:
    - Open-ended: "What should...?", "How do you think...?", "Which approach...?"
    - Salience-only: "How important is it to you that...?"
    - Priority lists: "What priorities should determine...?"

    VALID question types:
    - Propositions: "Should the government [do X]?"
    - Yes/No: "Do you support [policy]?"
    - Agreement statements: "The state should [policy]."
"""
from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)


# ── Forbidden opening patterns ─────────────────────────────────────────────────

_FORBIDDEN_OPENINGS_EN: list[re.Pattern] = [
    # Open-ended "what" questions
    re.compile(r"^\s*what\s+(priorities|approach|policy|should|do|is|are|kind)", re.IGNORECASE),
    re.compile(r"^\s*what\s+\w+\s+should\b", re.IGNORECASE),
    re.compile(r"^\s*what\s+do\s+you\s+think\b", re.IGNORECASE),
    # "Which approach" — choice, not proposition
    re.compile(r"^\s*which\s+(approach|option|policy|method|solution|way|is\s+better)", re.IGNORECASE),
    # Open-ended "how" questions
    re.compile(r"^\s*how\s+(do\s+you|should\s+the|should\s+Israel|should\s+government|should\s+policy)", re.IGNORECASE),
    re.compile(r"^\s*how\s+should\b", re.IGNORECASE),
    # Salience questions — these reveal no directional preference
    re.compile(r"^\s*how\s+important\s+is\s+it\s+(to\s+you\s+that|for)", re.IGNORECASE),
    re.compile(r"^\s*how\s+important\s+(is|are|do)\b", re.IGNORECASE),
    # Priority questions
    re.compile(r"^\s*what\s+priorities\b", re.IGNORECASE),
    re.compile(r"^\s*in\s+your\s+opinion\b", re.IGNORECASE),
    # "To what extent" is borderline — only allowed if followed by "should [institution] have"
    # otherwise it's open-ended
    re.compile(r"^\s*to\s+what\s+extent\s+do\s+you\s+(think|believe|feel)\b", re.IGNORECASE),
]

# Hebrew forbidden patterns (common open-ended prefixes)
_FORBIDDEN_OPENINGS_HE: list[re.Pattern] = [
    re.compile(r"^\s*מה\s+(הם\s+הסדר|צריכות?\s+להיות|לדעתך|אתה\s+חושב)", re.UNICODE),
    re.compile(r"^\s*כמה\s+חשוב\b", re.UNICODE),
    re.compile(r"^\s*כיצד\s+(לדעתך|לדעתכם|אתה\s+מרגיש)\b", re.UNICODE),
    re.compile(r"^\s*אילו\s+עדיפויות?\b", re.UNICODE),
]

# Russian forbidden patterns
_FORBIDDEN_OPENINGS_RU: list[re.Pattern] = [
    re.compile(r"^\s*какие\s+приоритеты\b", re.IGNORECASE | re.UNICODE),
    re.compile(r"^\s*как\s+(вы\s+думаете|вы\s+считаете|по-вашему)\b", re.IGNORECASE | re.UNICODE),
    re.compile(r"^\s*насколько\s+важно\b", re.IGNORECASE | re.UNICODE),
    re.compile(r"^\s*что\s+(должно|следует|нужно|правительство)\b", re.IGNORECASE | re.UNICODE),
    re.compile(r"^\s*по\s+вашему\s+мнению\b", re.IGNORECASE | re.UNICODE),
    re.compile(r"^\s*какой\s+подход\b", re.IGNORECASE | re.UNICODE),
]

# Patterns that strongly suggest a VALID closed question (positive indicators)
_VALID_OPENINGS_EN: list[re.Pattern] = [
    re.compile(r"^\s*should\b", re.IGNORECASE),
    re.compile(r"^\s*do\s+you\s+(support|believe|think\s+that)\b", re.IGNORECASE),
    re.compile(r"^\s*does\s+(the|israel|government)\b", re.IGNORECASE),
    re.compile(r"^\s*is\s+it\s+(right|appropriate|acceptable)\b", re.IGNORECASE),
    re.compile(r"^\s*the\s+(government|state|knesset|court)\s+should\b", re.IGNORECASE),
    re.compile(r"^\s*would\s+you\s+support\b", re.IGNORECASE),
]


class QuestionFormatError(ValueError):
    """Raised when a generated question is open-ended and not usable."""

    def __init__(self, question: str, language: str = "en", reason: str = ""):
        self.question = question
        self.language = language
        self.reason = reason
        super().__init__(
            f"[{language}] Open-ended question detected: {question!r}. "
            f"Reason: {reason or 'matched forbidden pattern'}. "
            "Questions must be closed propositions answerable on Strongly Oppose → Strongly Support."
        )


def is_closed_question(text: str, language: str = "en") -> bool:
    """
    Heuristic check: returns True if `text` appears to be a closed proposition
    (answerable on Strongly Oppose → Strongly Support), False if it looks open-ended.

    This is a fast regex-based check — not a perfect classifier.
    False positives (valid questions flagged as open) are possible for unusual phrasings.

    Args:
        text: The question text to check.
        language: "en", "he", or "ru" (selects the right pattern set).

    Returns:
        True = likely a closed question (OK to use).
        False = likely open-ended (should be rewritten).
    """
    if not text or not text.strip():
        return False

    text = text.strip()

    if language == "he":
        forbidden = _FORBIDDEN_OPENINGS_HE
    elif language == "ru":
        forbidden = _FORBIDDEN_OPENINGS_RU
    else:
        forbidden = _FORBIDDEN_OPENINGS_EN

    # Check forbidden patterns first
    for pattern in forbidden:
        if pattern.match(text):
            logger.debug("Question failed closed-form check (matched forbidden pattern %s): %r", pattern.pattern, text[:80])
            return False

    # For English, also check positive indicators as confirmation
    if language == "en":
        for pattern in _VALID_OPENINGS_EN:
            if pattern.match(text):
                return True

        # If no positive indicator found but no forbidden pattern matched,
        # treat it as potentially OK (we don't want to block unknown valid forms)
        return True

    # For Hebrew and Russian: if no forbidden pattern matched, accept
    return True


def validate_question_or_raise(
    question_en: str,
    question_he: str = "",
    question_ru: str = "",
) -> None:
    """
    Validate that a generated question is a closed proposition in all provided languages.
    Raises QuestionFormatError for the first language that fails.

    Use this after receiving LLM output to catch open-ended questions before
    they reach the database or the user.
    """
    if question_en and not is_closed_question(question_en, "en"):
        raise QuestionFormatError(question_en, "en")
    if question_he and not is_closed_question(question_he, "he"):
        raise QuestionFormatError(question_he, "he")
    if question_ru and not is_closed_question(question_ru, "ru"):
        raise QuestionFormatError(question_ru, "ru")


def check_question_format(
    question_en: str,
    question_he: str = "",
    question_ru: str = "",
) -> dict[str, bool | str | None]:
    """
    Non-raising version of validate_question_or_raise.
    Returns a dict with format check results for each language.

    Returns:
        {
          "is_valid": bool,
          "en_ok": bool,
          "he_ok": bool,
          "ru_ok": bool,
          "issue": str | None  — human-readable problem description if is_valid=False
        }
    """
    en_ok = is_closed_question(question_en, "en") if question_en else True
    he_ok = is_closed_question(question_he, "he") if question_he else True
    ru_ok = is_closed_question(question_ru, "ru") if question_ru else True

    is_valid = en_ok and he_ok and ru_ok
    issue: str | None = None
    if not en_ok:
        issue = f"English question appears open-ended: {question_en[:80]!r}"
    elif not he_ok:
        issue = f"Hebrew question appears open-ended: {question_he[:60]!r}"
    elif not ru_ok:
        issue = f"Russian question appears open-ended: {question_ru[:80]!r}"

    return {
        "is_valid": is_valid,
        "en_ok": en_ok,
        "he_ok": he_ok,
        "ru_ok": ru_ok,
        "issue": issue,
    }

