"""add_color_hex_and_left_right_score

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-05-07 10:00:00.000000

Adds:
  political_brands.color_hex    — party brand display color (CSS hex, e.g. "#1E3A8A")
  party_instances.left_right_score — pre-computed L–R political axis score (-1..+1)
  party_instances.political_bloc   — high-level bloc label (right/center-right/center/left/arab)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'political_brands',
        sa.Column('color_hex', sa.String(7), nullable=True),
    )
    op.add_column(
        'party_instances',
        sa.Column('left_right_score', sa.Float(), nullable=True),
    )
    op.add_column(
        'party_instances',
        sa.Column('political_bloc', sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('party_instances', 'political_bloc')
    op.drop_column('party_instances', 'left_right_score')
    op.drop_column('political_brands', 'color_hex')

