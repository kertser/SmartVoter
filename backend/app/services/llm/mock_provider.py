import hashlib
import random
from backend.app.services.llm.base import LLMProvider


# Topic-aware mock questions keyed by topic slug / keyword in the title.
# Each entry: (question_en, question_he, question_ru)
_TOPIC_QUESTIONS: dict[str, tuple[str, str, str]] = {
    "security": (
        "Should Israel prioritize diplomatic negotiations over military operations when addressing threats from neighboring territories?",
        "האם ישראל צריכה לתעדף משא ומתן דיפלומטי על פני פעולות צבאיות כשמתמודדת עם איומים מהשטחים השכנים?",
        "Должен ли Израиль отдавать приоритет дипломатическим переговорам, а не военным операциям при угрозах со стороны соседних территорий?",
    ),
    "judiciary": (
        "Should the Knesset have greater power to limit the Supreme Court's ability to strike down laws?",
        "האם לכנסת צריכה להיות סמכות רבה יותר להגביל את בית המשפט העליון?",
        "Должен ли Кнессет иметь больше полномочий для ограничения Верховного суда?",
    ),
    "religion_state": (
        "Should civil marriage be legally recognized in Israel alongside religious marriage?",
        "האם יש להכיר בנישואים אזרחיים כחוקיים בישראל לצד נישואים דתיים?",
        "Должны ли гражданские браки быть юридически признаны в Израиле наряду с религиозными?",
    ),
    "settlements": (
        "Should Israel continue building civilian settlements in the West Bank?",
        "האם ישראל צריכה להמשיך בבניית התנחלויות אזרחיות בגדה המערבית?",
        "Должен ли Израиль продолжать строительство гражданских поселений на Западном берегу?",
    ),
    "economy_taxes": (
        "Should the government raise taxes on high earners to fund expanded public services?",
        "האם הממשלה צריכה להעלות מסים על בעלי הכנסות גבוהות כדי לממן שירותים ציבוריים מורחבים?",
        "Должно ли правительство повысить налоги на высокодоходных граждан для финансирования расширения государственных услуг?",
    ),
    "healthcare": (
        "Should the government fully fund a universal public healthcare system without requiring supplemental private insurance?",
        "האם הממשלה צריכה לממן במלואה מערכת בריאות ציבורית אוניברסלית ללא ביטוח פרטי משלים?",
        "Должно ли правительство полностью финансировать универсальную государственную систему здравоохранения без дополнительного частного страхования?",
    ),
    "education": (
        "Should the government fund independent ultra-Orthodox school systems that do not teach the core national curriculum?",
        "האם הממשלה צריכה לממן מערכות חינוך חרדיות עצמאיות שאינן מלמדות את תכנית הלימודים הלאומית?",
        "Должно ли правительство финансировать независимые ультраортодоксальные школы, не преподающие национальную учебную программу?",
    ),
    "civil_rights": (
        "Should anti-discrimination protections be extended to cover sexual orientation and gender identity in all areas of public life?",
        "האם יש להרחיב את ההגנות מפני אפליה כך שיכסו נטייה מינית וזהות מגדרית בכל תחומי החיים הציבוריים?",
        "Следует ли расширить защиту от дискриминации на сексуальную ориентацию и гендерную идентичность во всех сферах общественной жизни?",
    ),
    "housing": (
        "Should the government build large amounts of public housing to address the housing affordability crisis?",
        "האם הממשלה צריכה לבנות כמויות גדולות של דיור ציבורי כדי להתמודד עם משבר הדיור?",
        "Должно ли правительство строить большое количество социального жилья для решения кризиса доступности жилья?",
    ),
    "welfare": (
        "Should welfare benefits be conditional on recipients fulfilling work or community service obligations?",
        "האם קצבאות רווחה צריכות להיות מותנות בקיום התחייבויות עבודה או שירות קהילתי?",
        "Должно ли получение социальных пособий быть условием выполнения трудовых или общественных обязательств?",
    ),
    "military_service": (
        "Should ultra-Orthodox men be required to serve in the Israeli military or perform equivalent national service?",
        "האם גברים חרדים צריכים להיות מחויבים לשרת בצבא הישראלי או לבצע שירות לאומי שווה ערך?",
        "Должны ли ультраортодоксальные мужчины быть обязаны служить в израильской армии или проходить эквивалентную национальную службу?",
    ),
    "governance_corruption": (
        "Should there be stronger independent oversight of elected officials to prevent conflicts of interest and corruption?",
        "האם צריך להיות פיקוח עצמאי חזק יותר על נבחרי ציבור כדי למנוע ניגוד עניינים ושחיתות?",
        "Следует ли усилить независимый надзор за выборными должностными лицами для предотвращения конфликта интересов и коррупции?",
    ),
    "environment": (
        "Should Israel adopt legally binding carbon reduction targets even if it raises energy costs for households?",
        "האם ישראל צריכה לאמץ יעדים מחייבים להפחתת פחמן גם אם הדבר יעלה את עלויות האנרגיה לבתי אב?",
        "Должен ли Израиль принять юридически обязательные цели по сокращению углерода, даже если это повысит расходы домохозяйств на энергию?",
    ),
    "transport": (
        "Should the government prioritize heavy investment in public transportation over expanding road infrastructure?",
        "האם הממשלה צריכה לתעדף השקעה כבדה בתחבורה ציבורית על פני הרחבת תשתיות כביש?",
        "Должно ли правительство отдавать приоритет крупным инвестициям в общественный транспорт над расширением дорожной инфраструктуры?",
    ),
    "cost_of_living": (
        "Should the government break up large monopolies and cartels to reduce consumer prices?",
        "האם הממשלה צריכה לפרק מונופולים וקרטלים גדולים כדי להוריד מחירים לצרכן?",
        "Должно ли правительство разрушить крупные монополии и картели для снижения потребительских цен?",
    ),
}

# Context notes corresponding to each topic (English only — used for the question card)
_TOPIC_CONTEXT: dict[str, str] = {
    "security": "Relates to the balance between military deterrence and diplomatic resolution of security challenges.",
    "judiciary": "Judicial review allows courts to strike down laws that conflict with basic laws.",
    "religion_state": "Israel currently has no civil marriage; only religious marriages are recognised by the state.",
    "settlements": "Israeli settlements in the West Bank are considered illegal under international law by most countries.",
    "economy_taxes": "Relates to the balance between tax burden and the scope of government services.",
    "healthcare": "Israel has a universal health insurance law (1994) but also a large supplemental private insurance market.",
    "education": "Ultra-Orthodox schools receive state funding but are exempt from parts of the national curriculum.",
    "civil_rights": "Israeli law prohibits some discrimination but does not have comprehensive LGBTQ+ equality legislation.",
    "housing": "Israel has experienced a severe housing affordability crisis over the past decade.",
    "welfare": "Relates to conditions and obligations attached to receiving government welfare benefits.",
    "military_service": "Ultra-Orthodox men have a historical exemption from mandatory IDF service.",
    "governance_corruption": "Relates to mechanisms for preventing and investigating corruption among elected officials.",
    "environment": "Israel has made voluntary climate pledges but lacks binding domestic carbon legislation.",
    "transport": "Israeli public transport coverage outside major cities is limited compared to Western Europe.",
    "cost_of_living": "Israel consistently ranks among OECD countries with the highest cost of living relative to wages.",
}


def _topic_key(input_data: dict) -> str:
    """
    Extract a topic keyword from the input_data title/description.
    Returns the best matching key from _TOPIC_QUESTIONS, or 'judiciary' as fallback.
    """
    text = " ".join([
        input_data.get("title", ""),
        input_data.get("description", ""),
    ]).lower()

    # Prefer exact slug matches
    for key in _TOPIC_QUESTIONS:
        if key.replace("_", " ") in text or key in text:
            return key

    # Keyword aliases
    aliases = {
        "civil right": "civil_rights",
        "cost of living": "cost_of_living",
        "military": "military_service",
        "religious": "religion_state",
        "religion": "religion_state",
        "settlement": "settlements",
        "economy": "economy_taxes",
        "tax": "economy_taxes",
        "health": "healthcare",
        "govern": "governance_corruption",
        "corrupt": "governance_corruption",
        "transpor": "transport",
        "environ": "environment",
        "welfare": "welfare",
        "education": "education",
        "housing": "housing",
        "security": "security",
    }
    for alias, key in aliases.items():
        if alias in text:
            return key
    return "judiciary"  # fallback


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
        topic = _topic_key(input_data)
        return {
            "topics": [
                {"topic": topic, "confidence": 0.87},
                {"topic": "governance_corruption", "confidence": 0.54},
            ],
            "primary_topic": topic,
            "classification_confidence": 0.87,
        }

    def extract_policy_axis(self, input_data: dict) -> dict:
        topic = _topic_key(input_data)
        axes = {
            "security": ("military_deterrence", "stronger military deterrence", "diplomatic resolution"),
            "judiciary": ("judicial_review_scope", "broader judicial review and court independence", "greater parliamentary control over judicial review"),
            "religion_state": ("religion_state_separation", "strict separation of religion and state", "religious law has formal role in state affairs"),
            "economy_taxes": ("redistribution", "stronger redistribution and higher taxes", "lower taxes and market-led economy"),
            "civil_rights": ("civil_rights_scope", "stronger universal civil rights protections", "more limited or community-based rights frameworks"),
            "military_service": ("draft_equality", "equal mandatory service for all citizens", "continued exemptions for ultra-Orthodox"),
            "governance_corruption": ("oversight_strength", "stronger independent oversight", "less regulatory oversight of officials"),
            "environment": ("climate_policy", "binding climate targets and green investment", "voluntary or market-based environmental policy"),
        }
        axis = axes.get(topic, ("policy_scope", "broader government role", "smaller government role"))
        return {
            "axis_name": axis[0],
            "negative_pole": axis[1],
            "positive_pole": axis[2],
            "direction_explanation": f"Positive values indicate support for {axis[2]}.",
        }

    def classify_and_extract(self, input_data: dict) -> dict:
        """Optimised combined mock: single call returns both classification and axis."""
        topic = _topic_key(input_data)
        cls = self.classify_policy_item(input_data)
        axis = self.extract_policy_axis(input_data)
        return {**cls, **axis, "_prompt_version": "v1.0"}

    def generate_question(self, input_data: dict) -> dict:
        topic = _topic_key(input_data)
        q_en, q_he, q_ru = _TOPIC_QUESTIONS[topic]
        context = _TOPIC_CONTEXT.get(topic, "")
        return {
            "question": q_en,
            "question_en": q_en,
            "question_he": q_he,
            "question_ru": q_ru,
            "context_note_en": context,
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
            "_prompt_version": "v1.0",
        }

    def critique_question(self, input_data: dict) -> dict:
        return {
            "is_loaded": False,
            "bias_direction": None,
            "suggested_revision": None,
            "reading_level": "general public",
            "requires_context": True,
            "context_note": "Provides context for the policy area.",
        }

    def generate_question_with_critique(self, input_data: dict) -> dict:
        """Optimised combined mock: single call returns question + critique + neutrality_score."""
        q = self.generate_question(input_data)
        return {
            **q,
            "neutrality_score": 0.7,
            "is_loaded": False,
            "bias_direction": None,
            "suggested_revision": None,
            "reading_level": "general public",
            "requires_context": True,
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

