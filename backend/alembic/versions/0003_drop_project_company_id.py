"""drop company_id from projects

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('projects', 'company_id')


def downgrade() -> None:
    op.add_column('projects', sa.Column(
        'company_id', sa.String(255), nullable=True
    ))