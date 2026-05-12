"""add_party_poll_aliases

Revision ID: i1j2k3l4m5n6
Revises: g1h2i3j4k5l6
Create Date: 2026-05-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'i1j2k3l4m5n6'
down_revision = 'g1h2i3j4k5l6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'party_poll_aliases',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('alias_text', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('official_name', sa.String(255), nullable=False),
        sa.Column('party_instance_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('party_instances.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('language', sa.String(10), nullable=False, server_default='any'),
        sa.Column('auto_created', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_party_poll_aliases_official_name', 'party_poll_aliases', ['official_name'])
    op.create_index('ix_party_poll_aliases_party_instance_id', 'party_poll_aliases', ['party_instance_id'])


def downgrade() -> None:
    op.drop_table('party_poll_aliases')

