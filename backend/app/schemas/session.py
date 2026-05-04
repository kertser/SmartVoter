from pydantic import BaseModel
import uuid
import datetime


class SessionCreate(BaseModel):
    session_id: uuid.UUID | None = None


class SessionOut(BaseModel):
    session_id: uuid.UUID
    created_at: datetime.datetime

    model_config = {"from_attributes": True}

