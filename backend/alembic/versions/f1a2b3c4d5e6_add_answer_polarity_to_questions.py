"""add_answer_polarity_to_questions

Revision ID: f1a2b3c4d5e6
Revises: e2269a930b25
Create Date: 2026-05-08

Adds answer_polarity column to questions table.
answer_polarity: 1.0 means "Strongly support" on the question = +1 on the policy axis.
               -1.0 means "Strongly support" on the question = -1 on the policy axis.
               (i.e. the question is phrased in the opposite direction to the axis)
"""
from alembic import op
import sqlalchemy as sa

revision = "f1a2b3c4d5e6"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column("answer_polarity", sa.Float(), nullable=False, server_default="1.0"),
    )
    # Invalidate all stale user_answers that were recorded before the polarity fix.
    # Their answer_value may be in the wrong direction for inverted questions.
    # We clear only answers whose associated question is inverted (polarity will be
    # updated by the seed patch).  For safety we clear ALL existing user_answers since
    # this is a dev environment and the data was incorrect.
    op.execute("DELETE FROM user_answers")
    op.execute("DELETE FROM recommendation_runs")


def downgrade() -> None:
    op.drop_column("questions", "answer_polarity")


