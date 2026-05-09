"""create_user_skipped_questions

Revision ID: h1i2j3k4l5m6
Revises: 9bfbadd706ed
Create Date: 2026-05-09 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'h1i2j3k4l5m6'
down_revision: Union[str, None] = '9bfbadd706ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table was already partially created; use IF NOT EXISTS style via checkfirst
    # The table itself was created by a previous partial run; indexes were also created.
    # This migration is now a no-op for the table/indexes that already exist.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'user_skipped_questions' not in tables:
        op.create_table(
            'user_skipped_questions',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('user_sessions.id'), nullable=False),
            sa.Column('question_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('questions.id'), nullable=False),
            sa.Column('reason', sa.String(50), nullable=False, server_default='outdated'),
            sa.Column('skipped_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index('ix_user_skipped_questions_session_id', 'user_skipped_questions', ['session_id'])
        op.create_index('ix_user_skipped_questions_question_id', 'user_skipped_questions', ['question_id'])


def downgrade() -> None:
    op.drop_index('ix_user_skipped_questions_question_id', table_name='user_skipped_questions')
    op.drop_index('ix_user_skipped_questions_session_id', table_name='user_skipped_questions')
    op.drop_table('user_skipped_questions')


