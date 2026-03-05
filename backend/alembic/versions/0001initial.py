"""initial schema

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision:       str                         = "0001"
down_revision:  Union[str, None]            = None
branch_labels:  Union[str, Sequence[str], None] = None
depends_on:     Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # ── users ──────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id",              postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email",           sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name",       sa.String(255), nullable=False),
        sa.Column("company_id",      sa.String(255), nullable=False),
        sa.Column("is_active",       sa.Boolean(),   nullable=False, server_default="true"),
        sa.Column("preferences",     sa.Text(),      nullable=True),
        sa.Column("created_at",      sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",      sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email",      "users", ["email"],      unique=True)
    op.create_index("ix_users_company_id", "users", ["company_id"], unique=False)

    # ── projects ───────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id",                 postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name",               sa.String(255), nullable=False),
        sa.Column("description",        sa.Text(),      nullable=True),
        sa.Column("use_case",           sa.Text(),      nullable=True),
        sa.Column("detected_sector",    sa.String(100), nullable=True),
        sa.Column("visual_preferences", sa.Text(),      nullable=True),
        sa.Column("owner_id",           postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("company_id",         sa.String(255), nullable=False),
        sa.Column("created_at",         sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",         sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_projects_company_id", "projects", ["company_id"], unique=False)

    # ── datasets ───────────────────────────────────────────
    op.create_table(
        "datasets",
        sa.Column("id",                  postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id",          postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("original_filename",   sa.String(255), nullable=False),
        sa.Column("minio_key",           sa.String(500), nullable=False),
        sa.Column("minio_processed_key", sa.String(500), nullable=True),
        sa.Column("file_format",         sa.String(20),  nullable=False),
        sa.Column("file_size_bytes",     sa.Integer(),   nullable=False),
        sa.Column("row_count",           sa.Integer(),   nullable=True),
        sa.Column("column_count",        sa.Integer(),   nullable=True),
        sa.Column("quality_score",       sa.Float(),     nullable=True),
        sa.Column("quality_report",      postgresql.JSONB(), nullable=True),
        sa.Column("created_at",          sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",          sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── dataset_columns ────────────────────────────────────
    op.create_table(
        "dataset_columns",
        sa.Column("id",             postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_id",     postgresql.UUID(as_uuid=True), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("original_name",  sa.String(255), nullable=False),
        sa.Column("business_name",  sa.String(255), nullable=True),
        sa.Column("detected_type",  sa.String(50),  nullable=False),
        sa.Column("business_type",  sa.String(50),  nullable=True),
        sa.Column("null_percent",   sa.Float(),     nullable=True),
        sa.Column("unique_count",   sa.Integer(),   nullable=True),
        sa.Column("sample_values",  postgresql.JSONB(), nullable=True),
        sa.Column("stats",          postgresql.JSONB(), nullable=True),
        sa.Column("column_order",   sa.Integer(),   nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("dataset_columns")
    op.drop_table("datasets")
    op.drop_index("ix_projects_company_id", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_users_company_id", table_name="users")
    op.drop_index("ix_users_email",      table_name="users")
    op.drop_table("users")