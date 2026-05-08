"""add_question_tree_fields

Adds question-tree / question-bank columns to the questions table:
  - parent_question_id  : self-referential FK for tree structure
  - tree_depth          : 0=root, 1=policy-item, 2=deep follow-up
  - trigger_answer_min  : optional lower answer threshold for follow-ups
  - trigger_answer_max  : optional upper answer threshold for follow-ups
  - subtopic_tag        : finer-grained topic label
  - generation_date     : timestamp when the question was LLM-generated
  - is_stale            : hidden from live questionnaire when True

Revision ID: c1d2e3f4a5b6
Revises: f1a2b3c4d5e6
Create Date: 2026-05-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Self-referential FK: parent_question_id → questions.id
    op.add_column("questions", sa.Column("parent_question_id", sa.Uuid(), nullable=True))
    op.create_index("ix_questions_parent_question_id", "questions", ["parent_question_id"])
    op.create_foreign_key(
        "fk_questions_parent_question_id",
        "questions", "questions",
        ["parent_question_id"], ["id"],
        ondelete="SET NULL",
    )

    # Tree depth (0 = root/topic, 1 = policy-item, 2 = deep)
    op.add_column("questions", sa.Column("tree_depth", sa.Integer(), nullable=True))
    op.execute("UPDATE questions SET tree_depth = 0 WHERE tree_depth IS NULL")
    op.alter_column("questions", "tree_depth", nullable=False)

    # Directional trigger thresholds for follow-up activation
    op.add_column("questions", sa.Column("trigger_answer_min", sa.Float(), nullable=True))
    op.add_column("questions", sa.Column("trigger_answer_max", sa.Float(), nullable=True))

    # Fine-grained subtopic tag within the main topic
    op.add_column("questions", sa.Column("subtopic_tag", sa.String(100), nullable=True))

    # Generation timestamp (for staleness tracking)
    op.add_column("questions", sa.Column("generation_date", sa.DateTime(), nullable=True))

    # Stale flag — hides question from live questionnaire
    op.add_column("questions", sa.Column("is_stale", sa.Boolean(), nullable=True))
    op.execute("UPDATE questions SET is_stale = FALSE WHERE is_stale IS NULL")
    op.alter_column("questions", "is_stale", nullable=False)


def downgrade() -> None:
    op.drop_column("questions", "is_stale")
    op.drop_column("questions", "generation_date")
    op.drop_column("questions", "subtopic_tag")
    op.drop_column("questions", "trigger_answer_max")
    op.drop_column("questions", "trigger_answer_min")
    op.drop_column("questions", "tree_depth")
    op.drop_constraint("fk_questions_parent_question_id", "questions", type_="foreignkey")
    op.drop_index("ix_questions_parent_question_id", table_name="questions")
    op.drop_column("questions", "parent_question_id")

