from pydantic import BaseModel
import uuid


class TopicOut(BaseModel):
    id: uuid.UUID
    slug: str
    name_en: str
    name_he: str
    name_ru: str | None = None
    description: str | None = None

    model_config = {"from_attributes": True}

