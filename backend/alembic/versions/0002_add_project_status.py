"""add status and business_rules to projects

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Créer le type enum PostgreSQL
    project_status = sa.Enum(
        'CREATED', 'DATA_UPLOADED', 'METADATA_CONFIGURED',
        'TRAINING', 'READY', 'FAILED', 'ARCHIVED',
        name='projectstatus'
    )
    project_status.create(op.get_bind(), checkfirst=True)

    # Ajouter les colonnes
    op.add_column('projects', sa.Column(
        'status',
        sa.Enum('CREATED', 'DATA_UPLOADED', 'METADATA_CONFIGURED',
                'TRAINING', 'READY', 'FAILED', 'ARCHIVED',
                name='projectstatus'),
        nullable=False,
        server_default='CREATED',
    ))
    op.add_column('projects', sa.Column(
        'business_rules',
        sa.Text(),
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column('projects', 'business_rules')
    op.drop_column('projects', 'status')
    op.execute("DROP TYPE IF EXISTS projectstatus")