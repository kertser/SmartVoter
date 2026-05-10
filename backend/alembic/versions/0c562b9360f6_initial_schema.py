"""initial_schema

Revision ID: 0c562b9360f6
Revises:
Create Date: 2026-05-05 00:00:00.000000

Creates the base database schema for SmartVoter: all core tables
before any additive migrations (simulation, question-tree, etc.).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0c562b9360f6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enum types ────────────────────────────────────────────────────────────
    op.execute(
        "CREATE TYPE party_status AS ENUM "
        "('active', 'dissolved', 'merged', 'split', 'renamed')"
    )
    op.execute(
        "CREATE TYPE lineage_relation_type AS ENUM "
        "('rename', 'split', 'merger', 'successor', 'alliance', 'rebrand')"
    )
    op.execute(
        "CREATE TYPE lineage_review_status AS ENUM "
        "('draft', 'needs_review', 'approved', 'rejected')"
    )
    op.execute(
        "CREATE TYPE membership_role AS ENUM "
        "('mk', 'candidate', 'minister', 'leader', 'founder')"
    )
    op.execute(
        "CREATE TYPE vote_value AS ENUM "
        "('for', 'against', 'abstain', 'absent', 'unknown')"
    )
    op.execute(
        "CREATE TYPE policy_source_type AS ENUM "
        "('vote', 'bill', 'platform', 'statement', 'candidate_history')"
    )
    op.execute(
        "CREATE TYPE policy_review_status AS ENUM "
        "('draft', 'llm_generated', 'needs_review', 'approved', 'rejected', 'deprecated')"
    )
    op.execute(
        "CREATE TYPE answer_scale_type AS ENUM "
        "('likert_5', 'binary', 'tradeoff')"
    )
    op.execute(
        "CREATE TYPE question_review_status AS ENUM "
        "('draft', 'llm_generated', 'needs_review', 'approved', 'rejected', 'deprecated')"
    )

    # ── Core reference tables ─────────────────────────────────────────────────
    op.create_table(
        'topics',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('name_he', sa.String(255), nullable=False),
        sa.Column('name_en', sa.String(255), nullable=False),
        sa.Column('name_ru', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_topics_slug', 'topics', ['slug'], unique=True)

    op.create_table(
        'political_brands',
        # Note: color_hex is NOT included here; added by b3c4d5e6f7a8.
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('canonical_name', sa.String(255), nullable=False),
        sa.Column('names_json', sa.JSON(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'party_instances',
        # Note: volatility_score added by a1b2c3d4e5f6.
        # Note: left_right_score, political_bloc added by b3c4d5e6f7a8.
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('political_brand_id', sa.UUID(), nullable=False),
        sa.Column('official_name', sa.String(255), nullable=False),
        sa.Column('election_cycle', sa.String(50), nullable=True),
        sa.Column('knesset_number', sa.Integer(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column(
            'status',
            sa.Enum(
                'active', 'dissolved', 'merged', 'split', 'renamed',
                name='party_status',
                create_type=False,
            ),
            nullable=False,
            server_default='active',
        ),
        sa.Column('source_url', sa.String(2048), nullable=True),
        sa.ForeignKeyConstraint(['political_brand_id'], ['political_brands.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_party_instances_political_brand_id',
        'party_instances',
        ['political_brand_id'],
    )

    op.create_table(
        'party_lineage_edges',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('from_party_instance_id', sa.UUID(), nullable=False),
        sa.Column('to_party_instance_id', sa.UUID(), nullable=False),
        sa.Column(
            'relation_type',
            sa.Enum(
                'rename', 'split', 'merger', 'successor', 'alliance', 'rebrand',
                name='lineage_relation_type',
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column('continuity_weight', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('llm_explanation', sa.Text(), nullable=True),
        sa.Column(
            'human_review_status',
            sa.Enum(
                'draft', 'needs_review', 'approved', 'rejected',
                name='lineage_review_status',
                create_type=False,
            ),
            nullable=False,
            server_default='draft',
        ),
        sa.Column('source_url', sa.String(2048), nullable=True),
        sa.ForeignKeyConstraint(
            ['from_party_instance_id'], ['party_instances.id']
        ),
        sa.ForeignKeyConstraint(
            ['to_party_instance_id'], ['party_instances.id']
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_party_lineage_edges_from_party_instance_id',
        'party_lineage_edges',
        ['from_party_instance_id'],
    )
    op.create_index(
        'ix_party_lineage_edges_to_party_instance_id',
        'party_lineage_edges',
        ['to_party_instance_id'],
    )

    # ── Person / membership ───────────────────────────────────────────────────
    op.create_table(
        'persons',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name_he', sa.String(255), nullable=False),
        sa.Column('name_en', sa.String(255), nullable=False),
        sa.Column('external_ids_json', sa.JSON(), nullable=True),
        sa.Column('birth_year', sa.Integer(), nullable=True),
        sa.Column('public_profile_url', sa.String(2048), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'person_party_memberships',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('person_id', sa.UUID(), nullable=False),
        sa.Column('party_instance_id', sa.UUID(), nullable=False),
        sa.Column(
            'role',
            sa.Enum(
                'mk', 'candidate', 'minister', 'leader', 'founder',
                name='membership_role',
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('source_url', sa.String(2048), nullable=True),
        sa.ForeignKeyConstraint(['party_instance_id'], ['party_instances.id']),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_person_party_memberships_person_id',
        'person_party_memberships',
        ['person_id'],
    )
    op.create_index(
        'ix_person_party_memberships_party_instance_id',
        'person_party_memberships',
        ['party_instance_id'],
    )

    # ── Bills and votes ───────────────────────────────────────────────────────
    op.create_table(
        'bills',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('external_id', sa.String(100), nullable=True),
        sa.Column('title_he', sa.String(500), nullable=False),
        sa.Column('title_en', sa.String(500), nullable=True),
        sa.Column('summary_he', sa.Text(), nullable=True),
        sa.Column('summary_en', sa.Text(), nullable=True),
        sa.Column('full_text_url', sa.String(2048), nullable=True),
        sa.Column('date_submitted', sa.Date(), nullable=True),
        sa.Column('status', sa.String(100), nullable=True),
        sa.Column('source_url', sa.String(2048), nullable=True),
        sa.Column('raw_json', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id'),
    )

    op.create_table(
        'votes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('external_id', sa.String(100), nullable=True),
        sa.Column('bill_id', sa.UUID(), nullable=True),
        sa.Column('title_he', sa.String(500), nullable=False),
        sa.Column('title_en', sa.String(500), nullable=True),
        sa.Column('date', sa.Date(), nullable=True),
        sa.Column('knesset_number', sa.Integer(), nullable=True),
        sa.Column('vote_type', sa.String(100), nullable=True),
        sa.Column('is_procedural_estimate', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('importance_score', sa.Float(), nullable=True),
        sa.Column('signal_quality_score', sa.Float(), nullable=True),
        sa.Column('source_url', sa.String(2048), nullable=True),
        sa.Column('raw_json', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['bill_id'], ['bills.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id'),
    )
    op.create_index('ix_votes_bill_id', 'votes', ['bill_id'])

    op.create_table(
        'vote_results',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('vote_id', sa.UUID(), nullable=False),
        sa.Column('person_id', sa.UUID(), nullable=False),
        sa.Column('party_instance_id_at_time', sa.UUID(), nullable=True),
        sa.Column(
            'vote_value',
            sa.Enum(
                'for', 'against', 'abstain', 'absent', 'unknown',
                name='vote_value',
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column('source_url', sa.String(2048), nullable=True),
        sa.ForeignKeyConstraint(['party_instance_id_at_time'], ['party_instances.id']),
        sa.ForeignKeyConstraint(['person_id'], ['persons.id']),
        sa.ForeignKeyConstraint(['vote_id'], ['votes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_vote_results_vote_id', 'vote_results', ['vote_id'])
    op.create_index('ix_vote_results_person_id', 'vote_results', ['person_id'])
    op.create_index(
        'ix_vote_results_party_instance_id_at_time',
        'vote_results',
        ['party_instance_id_at_time'],
    )

    # ── Policy items and party positions ──────────────────────────────────────
    op.create_table(
        'policy_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('topic_id', sa.UUID(), nullable=False),
        sa.Column('directional_axis', sa.String(500), nullable=True),
        sa.Column(
            'source_type',
            sa.Enum(
                'vote', 'bill', 'platform', 'statement', 'candidate_history',
                name='policy_source_type',
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column('source_refs_json', sa.JSON(), nullable=True),
        sa.Column('llm_confidence', sa.Float(), nullable=True),
        sa.Column(
            'human_review_status',
            sa.Enum(
                'draft', 'llm_generated', 'needs_review', 'approved', 'rejected', 'deprecated',
                name='policy_review_status',
                create_type=False,
            ),
            nullable=False,
            server_default='draft',
        ),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_policy_items_topic_id', 'policy_items', ['topic_id'])

    op.create_table(
        'party_positions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('party_instance_id', sa.UUID(), nullable=False),
        sa.Column('policy_item_id', sa.UUID(), nullable=False),
        sa.Column('position_mean', sa.Float(), nullable=False),
        sa.Column('position_uncertainty', sa.Float(), nullable=False, server_default='0.2'),
        sa.Column('evidence_strength', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('evidence_type', sa.String(100), nullable=True),
        sa.Column('source_refs_json', sa.JSON(), nullable=True),
        sa.Column('llm_explanation', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['party_instance_id'], ['party_instances.id']),
        sa.ForeignKeyConstraint(['policy_item_id'], ['policy_items.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_party_positions_party_instance_id',
        'party_positions',
        ['party_instance_id'],
    )
    op.create_index(
        'ix_party_positions_policy_item_id',
        'party_positions',
        ['policy_item_id'],
    )

    # ── Questions ─────────────────────────────────────────────────────────────
    # Initial state: policy_item_id NOT NULL, no is_root_question/topic_id/
    # answer_polarity/parent_question_id/tree_depth/subtopic_tag/generation_date/is_stale.
    # Those are all added by subsequent migrations.
    op.create_table(
        'questions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('policy_item_id', sa.UUID(), nullable=False),
        sa.Column('question_text_he', sa.Text(), nullable=False),
        sa.Column('question_text_en', sa.Text(), nullable=False),
        sa.Column('question_text_ru', sa.Text(), nullable=True),
        sa.Column(
            'answer_scale_type',
            sa.Enum(
                'likert_5', 'binary', 'tradeoff',
                name='answer_scale_type',
                create_type=False,
            ),
            nullable=False,
            server_default='likert_5',
        ),
        sa.Column('neutrality_score', sa.Float(), nullable=True),
        sa.Column('complexity_score', sa.Float(), nullable=True),
        sa.Column('llm_prompt_version', sa.String(50), nullable=True),
        sa.Column(
            'human_review_status',
            sa.Enum(
                'draft', 'llm_generated', 'needs_review', 'approved', 'rejected', 'deprecated',
                name='question_review_status',
                create_type=False,
            ),
            nullable=False,
            server_default='draft',
        ),
        sa.ForeignKeyConstraint(['policy_item_id'], ['policy_items.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_questions_policy_item_id', 'questions', ['policy_item_id'])

    # ── User sessions and answers ─────────────────────────────────────────────
    op.create_table(
        'user_sessions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'last_active_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'user_answers',
        # Note: policy_item_id is NOT NULL here; made nullable by d1e2f3a4b5c6.
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column('question_id', sa.UUID(), nullable=False),
        sa.Column('policy_item_id', sa.UUID(), nullable=False),
        sa.Column('answer_value', sa.Float(), nullable=False),
        sa.Column('salience', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column(
            'answered_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['policy_item_id'], ['policy_items.id']),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id']),
        sa.ForeignKeyConstraint(['session_id'], ['user_sessions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_user_answers_session_id', 'user_answers', ['session_id'])
    op.create_index('ix_user_answers_question_id', 'user_answers', ['question_id'])
    op.create_index('ix_user_answers_policy_item_id', 'user_answers', ['policy_item_id'])

    op.create_table(
        'recommendation_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('scoring_config_json', sa.JSON(), nullable=True),
        sa.Column('result_json', sa.JSON(), nullable=True),
        sa.Column(
            'methodology_version',
            sa.String(50),
            nullable=False,
            server_default='0.1.0',
        ),
        sa.ForeignKeyConstraint(['session_id'], ['user_sessions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_recommendation_runs_session_id',
        'recommendation_runs',
        ['session_id'],
    )

    # ── LLM audit tables ──────────────────────────────────────────────────────
    op.create_table(
        'llm_prompt_versions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('prompt_name', sa.String(255), nullable=False),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('prompt_template', sa.Text(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'llm_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('provider', sa.String(100), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('prompt_version_id', sa.UUID(), nullable=True),
        sa.Column('input_hash', sa.String(64), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['prompt_version_id'], ['llm_prompt_versions.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'llm_outputs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('llm_run_id', sa.UUID(), nullable=False),
        sa.Column('output_json', sa.JSON(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('entity_type', sa.String(100), nullable=True),
        sa.Column('entity_id', sa.UUID(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['llm_run_id'], ['llm_runs.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_llm_outputs_llm_run_id', 'llm_outputs', ['llm_run_id'])


def downgrade() -> None:
    op.drop_index('ix_llm_outputs_llm_run_id', table_name='llm_outputs')
    op.drop_table('llm_outputs')
    op.drop_table('llm_runs')
    op.drop_table('llm_prompt_versions')
    op.drop_index('ix_recommendation_runs_session_id', table_name='recommendation_runs')
    op.drop_table('recommendation_runs')
    op.drop_index('ix_user_answers_policy_item_id', table_name='user_answers')
    op.drop_index('ix_user_answers_question_id', table_name='user_answers')
    op.drop_index('ix_user_answers_session_id', table_name='user_answers')
    op.drop_table('user_answers')
    op.drop_table('user_sessions')
    op.drop_index('ix_questions_policy_item_id', table_name='questions')
    op.drop_table('questions')
    op.drop_index('ix_party_positions_policy_item_id', table_name='party_positions')
    op.drop_index('ix_party_positions_party_instance_id', table_name='party_positions')
    op.drop_table('party_positions')
    op.drop_index('ix_policy_items_topic_id', table_name='policy_items')
    op.drop_table('policy_items')
    op.drop_index(
        'ix_vote_results_party_instance_id_at_time', table_name='vote_results'
    )
    op.drop_index('ix_vote_results_person_id', table_name='vote_results')
    op.drop_index('ix_vote_results_vote_id', table_name='vote_results')
    op.drop_table('vote_results')
    op.drop_index('ix_votes_bill_id', table_name='votes')
    op.drop_table('votes')
    op.drop_table('bills')
    op.drop_index(
        'ix_person_party_memberships_party_instance_id',
        table_name='person_party_memberships',
    )
    op.drop_index(
        'ix_person_party_memberships_person_id',
        table_name='person_party_memberships',
    )
    op.drop_table('person_party_memberships')
    op.drop_table('persons')
    op.drop_index(
        'ix_party_lineage_edges_to_party_instance_id',
        table_name='party_lineage_edges',
    )
    op.drop_index(
        'ix_party_lineage_edges_from_party_instance_id',
        table_name='party_lineage_edges',
    )
    op.drop_table('party_lineage_edges')
    op.drop_index(
        'ix_party_instances_political_brand_id', table_name='party_instances'
    )
    op.drop_table('party_instances')
    op.drop_table('political_brands')
    op.drop_index('ix_topics_slug', table_name='topics')
    op.drop_table('topics')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS question_review_status")
    op.execute("DROP TYPE IF EXISTS answer_scale_type")
    op.execute("DROP TYPE IF EXISTS policy_review_status")
    op.execute("DROP TYPE IF EXISTS policy_source_type")
    op.execute("DROP TYPE IF EXISTS vote_value")
    op.execute("DROP TYPE IF EXISTS membership_role")
    op.execute("DROP TYPE IF EXISTS lineage_review_status")
    op.execute("DROP TYPE IF EXISTS lineage_relation_type")
    op.execute("DROP TYPE IF EXISTS party_status")
