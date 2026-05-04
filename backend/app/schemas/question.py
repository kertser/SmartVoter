from pydantic import BaseModel, field_validator
import uuid
import datetime


class QuestionOut(BaseModel):
    id: uuid.UUID
    question_text_en: str
    question_text_he: str
    answer_scale_type: str
    policy_item_id: uuid.UUID
    topic_slug: str
    context_note: str | None = None
    why_selected: str | None = None

    model_config = {"from_attributes": True}


class AnswerIn(BaseModel):
    session_id: uuid.UUID
    question_id: uuid.UUID
    policy_item_id: uuid.UUID
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

