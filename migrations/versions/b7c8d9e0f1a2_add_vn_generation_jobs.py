"""add_vn_generation_jobs

Revision ID: b7c8d9e0f1a2
Revises: f3a9b1c2d4e5
Create Date: 2026-06-11

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: str | Sequence[str] | None = 'f3a9b1c2d4e5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('vn_generation_jobs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('input_data', sa.JSON(), nullable=False),
        sa.Column('processor_type', sa.String(), nullable=False),
        sa.Column('checkpoint', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('error', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('running', 'failed')", name='check_vn_generation_job_status'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_vn_generation_job_user', 'vn_generation_jobs', ['user_id'], unique=False)
    op.create_index('idx_vn_generation_job_updated_at', 'vn_generation_jobs', ['updated_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_vn_generation_job_updated_at', table_name='vn_generation_jobs')
    op.drop_index('idx_vn_generation_job_user', table_name='vn_generation_jobs')
    op.drop_table('vn_generation_jobs')
