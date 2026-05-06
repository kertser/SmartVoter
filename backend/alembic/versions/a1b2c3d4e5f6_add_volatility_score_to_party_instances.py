"""add_volatility_score_to_party_instances

Revision ID: a1b2c3d4e5f6
Revises: 0c6f3edc9944
Create Date: 2026-05-06 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '0c6f3edc9944'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add volatility_score column to party_instances.
    # NULL = not yet computed; scoring engine falls back to live computation.
    op.add_column(
        'party_instances',
        sa.Column('volatility_score', sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('party_instances', 'volatility_score')

