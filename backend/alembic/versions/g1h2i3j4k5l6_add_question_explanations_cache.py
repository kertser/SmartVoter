"""add_question_explanations_cache

Revision ID: g1h2i3j4k5l6
Revises: d1e2f3a4b5c6
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "g1h2i3j4k5l6"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "question_explanations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("lang", sa.String(10), nullable=False),
        sa.Column("background", sa.Text(), nullable=True),
        sa.Column("why_relevant", sa.Text(), nullable=True),
        sa.Column("support_side", sa.Text(), nullable=True),
        sa.Column("oppose_side", sa.Text(), nullable=True),
        sa.Column("everyday_example", sa.Text(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="llm"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["question_id"], ["questions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "question_id", "lang", name="uq_question_explanation_lang"
        ),
    )
    op.create_index(
        "ix_question_explanations_question_id",
        "question_explanations",
        ["question_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_question_explanations_question_id", "question_explanations")
    op.drop_table("question_explanations")

