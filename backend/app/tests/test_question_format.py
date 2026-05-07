"""
Tests for question format validation (AGENTS.MD v1.3).

Core rule being tested:
    Every question served to users must be a CLOSED PROPOSITION answerable on
    the Strongly Oppose → Strongly Support scale.

    FORBIDDEN: "What priorities should determine...?", "How important is it...?",
               "How do you think...?", "Which approach is better...?"
    VALID:     "Should the government [do X]?", "Do you support [Y]?",
               "The state should [Z]."

The LLM may still occasionally generate open-ended questions despite the prompt.
This validator provides a fast defence layer before questions reach the DB.
"""
import pytest
from backend.app.services.llm.question_format import (
    is_closed_question,
    check_question_format,
    validate_question_or_raise,
    QuestionFormatError,
)


# ── Valid closed questions (should return True) ────────────────────────────────

class TestValidClosedQuestionsEN:
    """These are the correct format — all must pass validation."""

    def test_should_the_government(self):
        assert is_closed_question(
            "Should the government significantly increase funding for public hospitals?"
        )

    def test_should_military_service(self):
        assert is_closed_question(
            "Should military service be mandatory and equal for ALL citizens, "
            "regardless of their religious background or group affiliation?"
        )

    def test_should_supreme_court(self):
        assert is_closed_question(
            "Should the Supreme Court have the authority to strike down laws "
            "passed by an elected parliamentary majority?"
        )

    def test_do_you_support(self):
        assert is_closed_question(
            "Do you support requiring all Israeli citizens, including ultra-Orthodox men, "
            "to serve in the military?"
        )

    def test_should_state_control_prices(self):
        assert is_closed_question(
            "Should the state directly control the prices of essential food products "
            "to make them more affordable for ordinary families?"
        )

    def test_should_civil_marriage(self):
        assert is_closed_question(
            "Should civil marriage — without a rabbi or religious authority — "
            "be legally recognized in Israel?"
        )

    def test_do_you_believe_courts(self):
        assert is_closed_question(
            "Do you believe courts should be independent of government influence "
            "when appointing judges?"
        )

    def test_should_religious_schools(self):
        assert is_closed_question(
            "Should religious schools that receive public funding be required "
            "to teach a core secular curriculum?"
        )

    def test_should_pm_resign_on_indictment(self):
        assert is_closed_question(
            "Should a sitting Prime Minister who has been formally charged "
            "with criminal offences temporarily step down from office?"
        )

    def test_should_rent_increases_be_capped(self):
        assert is_closed_question(
            "Should annual apartment rent increases be limited by law to protect "
            "tenants from sharp price hikes?"
        )


# ── Invalid open-ended questions (should return False) ────────────────────────

class TestInvalidOpenQuestionsEN:
    """These must be detected as open-ended and rejected."""

    def test_what_priorities_healthcare(self):
        """The exact example from the user's bug report (healthcare variant)."""
        assert not is_closed_question(
            "What priorities should determine the government's approach to healthcare "
            "in Israel, including the public health system, insurance, hospital "
            "funding, and drug costs?"
        )

    def test_what_should_be_done(self):
        assert not is_closed_question(
            "What should be done about the high cost of living?"
        )

    def test_how_important_is_it(self):
        """Salience question — reveals no directional preference."""
        assert not is_closed_question(
            "How important is it to you that the government actively works "
            "to make everyday goods affordable for ordinary families?"
        )

    def test_how_important_are_courts(self):
        assert not is_closed_question(
            "How important is judicial independence to you?"
        )

    def test_how_do_you_think(self):
        assert not is_closed_question(
            "How do you think the burden of military service should be distributed "
            "among Israeli citizens?"
        )

    def test_how_should_the_government(self):
        assert not is_closed_question(
            "How should the government approach the issue of housing affordability?"
        )

    def test_which_approach_is_better(self):
        assert not is_closed_question(
            "Which approach is better for solving Israel's housing shortage: "
            "government construction or private development incentives?"
        )

    def test_what_do_you_think(self):
        assert not is_closed_question(
            "What do you think about the current balance between religious "
            "and secular authorities in Israel?"
        )

    def test_in_your_opinion(self):
        assert not is_closed_question(
            "In your opinion, what approach should Israel take to reduce "
            "the cost of living?"
        )

    def test_what_kind_of_healthcare(self):
        assert not is_closed_question(
            "What kind of healthcare system do you think Israel should have?"
        )

    def test_what_is_the_best_approach(self):
        assert not is_closed_question(
            "What is the best approach to balancing economic growth and "
            "environmental protection in Israel?"
        )

    def test_how_should_the_knesset(self):
        assert not is_closed_question(
            "How should the Knesset approach judicial appointments?"
        )


# ── Hebrew questions ───────────────────────────────────────────────────────────

class TestHebrew:
    def test_valid_hebrew_should_question(self):
        assert is_closed_question(
            "האם על הממשלה להגדיל משמעותית את התקציב לבתי חולים ציבוריים?",
            language="he"
        )

    def test_valid_hebrew_support_question(self):
        assert is_closed_question(
            "האם אתה תומך בחיוב שירות צבאי שווה לכל אזרחי ישראל ללא קשר לדתיות?",
            language="he"
        )

    def test_invalid_hebrew_salience(self):
        assert not is_closed_question(
            "כמה חשוב לך שהממשלה תטפל ביוקר המחיה?",
            language="he"
        )

    def test_invalid_hebrew_what(self):
        assert not is_closed_question(
            "מה לדעתך צריכות להיות עדיפויות הממשלה בתחום הבריאות?",
            language="he"
        )


# ── Russian questions ──────────────────────────────────────────────────────────

class TestRussian:
    def test_valid_russian_should_question(self):
        assert is_closed_question(
            "Должно ли правительство значительно увеличить финансирование государственных больниц?",
            language="ru"
        )

    def test_invalid_russian_priorities(self):
        """The exact user-reported bug: Russian version of the healthcare question."""
        assert not is_closed_question(
            "Какие приоритеты должны определять подход правительства к здравоохранению "
            "в Израиле, включая систему общественного здравоохранения, страхование, "
            "финансирование больниц и стоимость лекарств?",
            language="ru"
        )

    def test_invalid_russian_how_do_you_think(self):
        assert not is_closed_question(
            "Как вы думаете, каким должен быть подход правительства к жилищной политике?",
            language="ru"
        )

    def test_invalid_russian_importance(self):
        assert not is_closed_question(
            "Насколько важно для вас равенство воинской обязанности?",
            language="ru"
        )

    def test_invalid_russian_in_your_opinion(self):
        assert not is_closed_question(
            "По вашему мнению, что должно делать правительство для снижения стоимости жизни?",
            language="ru"
        )


# ── check_question_format helper ──────────────────────────────────────────────

class TestCheckQuestionFormat:
    def test_all_valid(self):
        result = check_question_format(
            question_en="Should the government increase healthcare funding?",
            question_he="האם על הממשלה להגדיל את תקציב הבריאות?",
            question_ru="Должно ли правительство увеличить финансирование здравоохранения?",
        )
        assert result["is_valid"] is True
        assert result["en_ok"] is True
        assert result["he_ok"] is True
        assert result["ru_ok"] is True
        assert result["issue"] is None

    def test_english_fails(self):
        result = check_question_format(
            question_en="What priorities should determine healthcare policy?",
            question_he="האם על הממשלה להגדיל את תקציב הבריאות?",
            question_ru="Должно ли правительство увеличить финансирование?",
        )
        assert result["is_valid"] is False
        assert result["en_ok"] is False
        assert result["issue"] is not None
        assert "English" in result["issue"]

    def test_russian_fails(self):
        result = check_question_format(
            question_en="Should the government increase healthcare funding?",
            question_he="האם על הממשלה להגדיל את תקציב הבריאות?",
            question_ru="Какие приоритеты должны определять подход правительства к здравоохранению?",
        )
        assert result["is_valid"] is False
        assert result["ru_ok"] is False
        assert result["issue"] is not None

    def test_empty_he_and_ru_not_flagged(self):
        """Empty strings for optional languages should not fail validation."""
        result = check_question_format(
            question_en="Should the state fund public housing?",
            question_he="",
            question_ru="",
        )
        assert result["is_valid"] is True

    def test_exact_bug_report_russian(self):
        """The EXACT question from the user's bug report must fail validation."""
        result = check_question_format(
            question_en="What priorities should determine the government's approach to healthcare?",
            question_ru="Какие приоритеты должны определять подход правительства к здравоохранению "
                        "в Израиле, включая систему общественного здравоохранения, страхование, "
                        "финансирование больниц и стоимость лекарств?",
        )
        assert result["is_valid"] is False
        assert result["en_ok"] is False
        assert result["ru_ok"] is False


# ── validate_question_or_raise ────────────────────────────────────────────────

class TestValidateOrRaise:
    def test_valid_question_does_not_raise(self):
        validate_question_or_raise(
            question_en="Should the government cap rental prices to protect tenants?",
            question_he="האם על הממשלה לקבוע תקרת שכר דירה?",
            question_ru="Должно ли правительство ограничить рост цен на аренду?",
        )

    def test_open_english_raises(self):
        with pytest.raises(QuestionFormatError) as exc_info:
            validate_question_or_raise(
                question_en="What priorities should determine housing policy?",
                question_he="האם על הממשלה לבנות דיור ציבורי?",
            )
        assert exc_info.value.language == "en"
        assert "Open-ended" in str(exc_info.value)

    def test_open_russian_raises(self):
        with pytest.raises(QuestionFormatError) as exc_info:
            validate_question_or_raise(
                question_en="Should the government build public housing?",
                question_ru="Какие приоритеты должны определять жилищную политику?",
            )
        assert exc_info.value.language == "ru"

    def test_open_hebrew_raises(self):
        with pytest.raises(QuestionFormatError) as exc_info:
            validate_question_or_raise(
                question_en="Should the government build public housing?",
                question_he="כמה חשוב לך שהממשלה תבנה דיור ציבורי?",
            )
        assert exc_info.value.language == "he"

    def test_error_message_includes_question_text(self):
        bad_question = "How important is it to you that courts are independent?"
        with pytest.raises(QuestionFormatError) as exc_info:
            validate_question_or_raise(question_en=bad_question)
        assert "courts are independent" in str(exc_info.value)


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_string_returns_false(self):
        assert not is_closed_question("")

    def test_whitespace_only_returns_false(self):
        assert not is_closed_question("   ")

    def test_case_insensitive_forbidden_what(self):
        assert not is_closed_question("WHAT PRIORITIES SHOULD DETERMINE POLICY?")

    def test_case_insensitive_forbidden_how_important(self):
        assert not is_closed_question("HOW IMPORTANT IS IT TO YOU THAT courts are independent?")

    def test_leading_whitespace_handled(self):
        assert not is_closed_question("  What priorities should determine education policy?")

    def test_valid_with_leading_whitespace(self):
        assert is_closed_question("  Should the government increase the education budget?")

