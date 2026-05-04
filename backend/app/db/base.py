from sqlalchemy.orm import DeclarativeBase
import datetime
import uuid
from sqlalchemy import DateTime, func
from sqlalchemy.orm import mapped_column, Mapped


class Base(DeclarativeBase):
    pass

