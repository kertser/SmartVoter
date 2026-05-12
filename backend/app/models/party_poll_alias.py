"""
PartyPollAlias — maps raw poll name strings to canonical party names.

Replaces the hardcoded PARTY_ALIASES list in web_polling.py.
Aliases can be managed via the admin API and are auto-seeded on first run.
Unknown parties seen in polls are auto-inserted with auto_created=True so
an admin can later link them to a party instance.
"""
import uuid
import datetime
from sqlalchemy import String, DateTime, ForeignKey, Boolean, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.base import Base


class PartyPollAlias(Base):
    __tablename__ = "party_poll_aliases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Cleaned, lowercased alias text used for matching (e.g. "הליכוד", "likud")
    alias_text: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    # Canonical name that maps to party_instances.official_name
    # Also used as reported_name in poll_party_results when no party_instance is linked.
    official_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Optional direct link to a party instance (NULL = unlinked / new party)
    party_instance_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("party_instances.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Language hint: 'he' | 'en' | 'translit' | 'any'
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="any")

    # True = inserted automatically from an unrecognised poll entry; needs admin review
    auto_created: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

