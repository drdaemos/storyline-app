"""npc_simulation_tables

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create new simulation tables and modify existing ones."""

    # 1. Create rulesets table
    op.create_table('rulesets',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('rules_text', sa.Text(), nullable=False, server_default=''),
        sa.Column('state_schemas', sa.JSON(), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False, server_default='anonymous'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_ruleset_user', 'rulesets', ['user_id'], unique=False)

    # 2. Create world_lore table
    op.create_table('world_lore',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False, server_default=''),
        sa.Column('tags', sa.JSON(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False, server_default='anonymous'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_lore_user', 'world_lore', ['user_id'], unique=False)

    # 3. Create sessions table
    op.create_table('sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('scenario_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False, server_default='anonymous'),
        sa.Column('world_state', sa.JSON(), nullable=False),
        sa.Column('turn_counter', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('narration_history', sa.JSON(), nullable=False),
        sa.Column('location_history', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('snapshot', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'paused', 'completed')", name='check_session_status'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_session_user', 'sessions', ['user_id'], unique=False)
    op.create_index('idx_session_scenario', 'sessions', ['scenario_id'], unique=False)
    op.create_index('idx_session_status', 'sessions', ['status'], unique=False)

    # 4. Create character_states table
    op.create_table('character_states',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('character_id', sa.String(), nullable=False),
        sa.Column('drives', sa.JSON(), nullable=False),
        sa.Column('skills', sa.JSON(), nullable=False),
        sa.Column('emotional_state', sa.JSON(), nullable=False),
        sa.Column('active_intent', sa.JSON(), nullable=True),
        sa.Column('is_present', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('intended_destination', sa.String(), nullable=True),
        sa.Column('last_departure_tick', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_charstate_session', 'character_states', ['session_id'], unique=False)
    op.create_index('idx_charstate_session_character', 'character_states', ['session_id', 'character_id'], unique=True)

    # 5. Create events table
    op.create_table('events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('character_id', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('tick', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('subject', sa.JSON(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False, server_default=''),
        sa.Column('importance', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('decay_rate', sa.Float(), nullable=False, server_default='0.3'),
        sa.Column('initial_decay', sa.Float(), nullable=False, server_default='10.0'),
        sa.Column('source_refs', sa.JSON(), nullable=False),
        sa.Column('visibility', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("type IN ('observation', 'reflection')", name='check_event_type'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_event_session_character', 'events', ['session_id', 'character_id'], unique=False)
    op.create_index('idx_event_session_tick', 'events', ['session_id', 'tick'], unique=False)

    # 6. Modify scenarios table: add ruleset_id and character_ids columns
    op.add_column('scenarios', sa.Column('ruleset_id', sa.String(), nullable=True))
    op.add_column('scenarios', sa.Column('character_ids', sa.JSON(), nullable=True))
    op.create_index('idx_scenario_ruleset', 'scenarios', ['ruleset_id'], unique=False)

    # 7. Modify messages table: remove old columns, update constraints
    # Drop old indexes and constraints that reference removed columns
    op.drop_index('idx_character_session', table_name='messages')
    # Remove character_id and type columns
    op.drop_column('messages', 'character_id')
    op.drop_column('messages', 'type')
    # Update role check constraint
    op.drop_constraint('check_message_type', 'messages', type_='check')


def downgrade() -> None:
    """Reverse all changes."""
    # Re-add removed columns to messages
    op.add_column('messages', sa.Column('character_id', sa.String(), nullable=False, server_default='unknown'))
    op.add_column('messages', sa.Column('type', sa.String(), nullable=False, server_default='conversation'))
    op.create_index('idx_character_session', 'messages', ['character_id', 'session_id'], unique=False)
    op.create_check_constraint('check_message_type', 'messages', "type IN ('conversation', 'evaluation')")

    # Drop new columns from scenarios
    op.drop_index('idx_scenario_ruleset', table_name='scenarios')
    op.drop_column('scenarios', 'character_ids')
    op.drop_column('scenarios', 'ruleset_id')

    # Drop new tables
    op.drop_index('idx_event_session_tick', table_name='events')
    op.drop_index('idx_event_session_character', table_name='events')
    op.drop_table('events')

    op.drop_index('idx_charstate_session_character', table_name='character_states')
    op.drop_index('idx_charstate_session', table_name='character_states')
    op.drop_table('character_states')

    op.drop_index('idx_session_status', table_name='sessions')
    op.drop_index('idx_session_scenario', table_name='sessions')
    op.drop_index('idx_session_user', table_name='sessions')
    op.drop_table('sessions')

    op.drop_index('idx_lore_user', table_name='world_lore')
    op.drop_table('world_lore')

    op.drop_index('idx_ruleset_user', table_name='rulesets')
    op.drop_table('rulesets')
