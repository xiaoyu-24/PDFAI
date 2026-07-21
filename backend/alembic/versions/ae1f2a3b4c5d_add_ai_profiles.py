"""add_ai_profiles

Revision ID: ae1f2a3b4c5d
Revises: 9d0e1f2a3b4c
Create Date: 2026-07-20 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ae1f2a3b4c5d"
down_revision: Union[str, None] = "9d0e1f2a3b4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("base_url", sa.String(length=1024), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=256), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_pending", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_ai_profiles_name"),
    )
    op.add_column("compare_tasks", sa.Column("ai_profile_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_compare_tasks_ai_profile_id",
        "compare_tasks",
        "ai_profiles",
        ["ai_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_compare_tasks_ai_profile_id", "compare_tasks", ["ai_profile_id"])


def downgrade() -> None:
    op.drop_index("idx_compare_tasks_ai_profile_id", table_name="compare_tasks")
    op.drop_constraint("fk_compare_tasks_ai_profile_id", "compare_tasks", type_="foreignkey")
    op.drop_column("compare_tasks", "ai_profile_id")
    op.drop_table("ai_profiles")
