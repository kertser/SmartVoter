from pydantic import BaseModel, field_validator
import uuid
import datetime


class QuestionOut(BaseModel):
    id: uuid.UUID
    question_text_en: str
    question_text_he: str
    question_text_ru: str | None = None
    answer_scale_type: str
    policy_item_id: uuid.UUID | None = None  # null for root (topic-level) questions
    topic_slug: str
    topic_name_he: str | None = None
    topic_name_ru: str | None = None
    context_note: str | None = None
    why_selected: str | None = None
    is_root_question: bool = False

    # Convergence metadata — used by the frontend to decide when to offer results
    can_show_results: bool = False          # ranking stable + topics covered
    phase: str = "survey"                   # "survey" | "depth"
    topics_covered: int = 0                 # how many distinct topics answered so far
    topics_total: int = 0                   # total topics in the pool
    answered_count: int = 0                 # questions answered before this one
    ranking_stability: float = 0.0          # Kendall-τ [0..1]

    model_config = {"from_attributes": True}


class AnswerIn(BaseModel):
    session_id: uuid.UUID
    question_id: uuid.UUID
    policy_item_id: uuid.UUID | None = None  # null for root questions
    answer_value: float  # -1.0 to +1.0
    salience: float = 1.0  # 0.5 | 1.0 | 2.0

    @field_validator("answer_value")
    @classmethod
    def validate_answer_value(cls, v: float) -> float:
        if not -1.0 <= v <= 1.0:
            raise ValueError("answer_value must be between -1.0 and 1.0")
        return v

    @field_validator("salience")
    @classmethod
    def validate_salience(cls, v: float) -> float:
        if v not in (0.5, 1.0, 2.0):
            raise ValueError("salience must be 0.5, 1.0, or 2.0")
        return v


class AnswerOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    answered_at: datetime.datetime

    model_config = {"from_attributes": True}

