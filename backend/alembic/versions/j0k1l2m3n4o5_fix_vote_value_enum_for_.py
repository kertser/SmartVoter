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
    # Only rename if 'for_' actually exists in the enum (some DBs were created
    # with the correct 'for' label already; renaming a non-existent label errors).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'vote_value' AND e.enumlabel = 'for_'
            ) THEN
                ALTER TYPE vote_value RENAME VALUE 'for_' TO 'for';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # Only rename back if 'for' exists (i.e. the upgrade ran successfully).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'vote_value' AND e.enumlabel = 'for'
            ) AND NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'vote_value' AND e.enumlabel = 'for_'
            ) THEN
                ALTER TYPE vote_value RENAME VALUE 'for' TO 'for_';
            END IF;
        END
        $$;
        """
    )

