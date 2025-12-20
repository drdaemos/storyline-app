"""add_scenarios_table

Revision ID: a1b2c3d4e5f6
Revises: d8e959f60e34
Create Date: 2025-12-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'd8e959f60e34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create scenarios table
    op.create_table('scenarios',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('character_id', sa.String(), nullable=False),
        sa.Column('scenario_data', sa.JSON(), nullable=False),
        sa.Column('schema_version', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_scenario_character', 'scenarios', ['character_id'], unique=False)
    op.create_index('idx_scenario_user', 'scenarios', ['user_id'], unique=False)
    op.create_index('idx_scenario_updated_at', 'scenarios', ['updated_at'], unique=False)

    # Add scenario_id column to messages table for session-scenario linking
    op.add_column('messages', sa.Column('scenario_id', sa.String(), nullable=True))
    op.create_index('idx_message_scenario', 'messages', ['scenario_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove scenario_id from messages
    op.drop_index('idx_message_scenario', table_name='messages')
    op.drop_column('messages', 'scenario_id')

    # Drop scenarios table
    op.drop_index('idx_scenario_updated_at', table_name='scenarios')
    op.drop_index('idx_scenario_user', table_name='scenarios')
    op.drop_index('idx_scenario_character', table_name='scenarios')
    op.drop_table('scenarios')
