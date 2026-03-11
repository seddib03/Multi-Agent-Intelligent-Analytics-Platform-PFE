"""replace minio_key with file_path in datasets

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remplacer minio_key par file_path
    op.add_column('datasets', sa.Column('file_path', sa.String(500), nullable=True))
    op.add_column('datasets', sa.Column('processed_path', sa.String(500), nullable=True))

    # Copier les valeurs existantes
    op.execute("UPDATE datasets SET file_path = minio_key WHERE file_path IS NULL")

    # Rendre file_path NOT NULL
    op.alter_column('datasets', 'file_path', nullable=False)

    # Supprimer les anciennes colonnes MinIO
    op.drop_column('datasets', 'minio_key')
    op.drop_column('datasets', 'minio_processed_key')


def downgrade() -> None:
    op.add_column('datasets', sa.Column('minio_key', sa.String(500), nullable=True))
    op.add_column('datasets', sa.Column('minio_processed_key', sa.String(500), nullable=True))
    op.execute("UPDATE datasets SET minio_key = file_path WHERE minio_key IS NULL")
    op.alter_column('datasets', 'minio_key', nullable=False)
    op.drop_column('datasets', 'file_path')
    op.drop_column('datasets', 'processed_path')