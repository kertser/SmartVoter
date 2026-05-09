"""nullable policy_item_id in user_answers

Root questions (topic-level) have no policy_item_id; making the column nullable
lets their answers be stored without a DB constraint violation.

Revision ID: d1e2f3a4b5c6
Revises: f1a2b3c4d5e6
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d1e2f3a4b5c6"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "user_answers",
        "policy_item_id",
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    # First delete any rows where policy_item_id is NULL so the constraint can
    # be re-applied (those rows are root-question answers with no policy item).
    op.execute(
        "DELETE FROM user_answers WHERE policy_item_id IS NULL"
    )
    op.alter_column(
        "user_answers",
        "policy_item_id",
        existing_type=sa.UUID(),
        nullable=False,
    )


