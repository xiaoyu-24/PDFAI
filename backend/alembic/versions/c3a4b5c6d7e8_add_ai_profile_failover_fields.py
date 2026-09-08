"""add_ai_profile_failover_fields

Revision ID: c3a4b5c6d7e8
Revises: bf2a3b4c5d6e
Create Date: 2026-08-26 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3a4b5c6d7e8"
down_revision: Union[str, None] = "bf2a3b4c5d6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_profiles", sa.Column("priority", sa.Integer(), nullable=False, server_default="100"))
    op.add_column(
        "ai_profiles",
        sa.Column("health_status", sa.String(length=16), nullable=False, server_default="unknown"),
    )
    op.add_column("ai_profiles", sa.Column("cooldown_until", sa.DateTime(), nullable=True))
    op.add_column("ai_profiles", sa.Column("last_health_error", sa.Text(), nullable=True))
    op.add_column("ai_profiles", sa.Column("last_health_checked_at", sa.DateTime(), nullable=True))
    op.create_index("idx_ai_profiles_priority", "ai_profiles", ["is_enabled", "priority", "id"])


def downgrade() -> None:
    op.drop_index("idx_ai_profiles_priority", table_name="ai_profiles")
    op.drop_column("ai_profiles", "last_health_checked_at")
    op.drop_column("ai_profiles", "last_health_error")
    op.drop_column("ai_profiles", "cooldown_until")
    op.drop_column("ai_profiles", "health_status")
    op.drop_column("ai_profiles", "priority")
