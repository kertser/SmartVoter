"""fix vote_value enum for_ -> for

Revision ID: j0k1l2m3n4o5
Revises: i1j2k3l4m5n6
Create Date: 2026-05-12

The PostgreSQL vote_value ENUM was created with 'for_' (Python enum member name)
instead of 'for' (the intended value). This migration renames the enum value to
match the Python model's VoteValue.for_ = "for".

PostgreSQL 10+ ALTER TYPE ... RENAME VALUE also atomically updates all existing
rows that reference the enum value, so no data-patching step is needed.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'j0k1l2m3n4o5'
down_revision = 'i1j2k3l4m5n6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE vote_value RENAME VALUE 'for_' TO 'for'")


def downgrade() -> None:
    op.execute("ALTER TYPE vote_value RENAME VALUE 'for' TO 'for_'")

