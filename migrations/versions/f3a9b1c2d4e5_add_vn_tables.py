"""add_vn_tables

Revision ID: f3a9b1c2d4e5
Revises: a1b2c3d4e5f6
Create Date: 2026-06-11

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f3a9b1c2d4e5'
down_revision: str | Sequence[str] | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('vn_scripts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('script_data', sa.JSON(), nullable=False),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('schema_version', sa.Integer(), nullable=False),
        sa.Column('validation_status', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("validation_status IN ('unvalidated', 'valid', 'invalid')", name='check_vn_validation_status'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_vn_script_user', 'vn_scripts', ['user_id'], unique=False)
    op.create_index('idx_vn_script_updated_at', 'vn_scripts', ['updated_at'], unique=False)

    op.create_table('vn_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('script_id', sa.String(), nullable=False),
        sa.Column('runtime_state', sa.JSON(), nullable=False),
        sa.Column('event_log', sa.JSON(), nullable=False),
        sa.Column('narration_log', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('running', 'ended')", name='check_vn_session_status'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_vn_session_user', 'vn_sessions', ['user_id'], unique=False)
    op.create_index('idx_vn_session_script', 'vn_sessions', ['script_id'], unique=False)
    op.create_index('idx_vn_session_updated_at', 'vn_sessions', ['updated_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_vn_session_updated_at', table_name='vn_sessions')
    op.drop_index('idx_vn_session_script', table_name='vn_sessions')
    op.drop_index('idx_vn_session_user', table_name='vn_sessions')
    op.drop_table('vn_sessions')

    op.drop_index('idx_vn_script_updated_at', table_name='vn_scripts')
    op.drop_index('idx_vn_script_user', table_name='vn_scripts')
    op.drop_table('vn_scripts')
