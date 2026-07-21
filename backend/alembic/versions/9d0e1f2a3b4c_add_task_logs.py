"""add_task_logs

Revision ID: 9d0e1f2a3b4c
Revises: 8c9d0e1f2a3b
Create Date: 2026-07-20 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9d0e1f2a3b4c"
down_revision: Union[str, None] = "8c9d0e1f2a3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("component", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_category", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("attempt_no", sa.Integer(), nullable=True),
        sa.Column("max_attempts", sa.Integer(), nullable=True),
        sa.Column("timeout_ms", sa.Integer(), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("is_degraded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fallback_action", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["compare_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_task_logs_task_created", "task_logs", ["task_id", "created_at"])
    op.create_index("idx_task_logs_level_created", "task_logs", ["level", "created_at"])
    op.create_index("idx_task_logs_category_created", "task_logs", ["error_category", "created_at"])
    op.create_index("idx_task_logs_stage_status", "task_logs", ["stage", "status"])
    op.create_index("idx_task_logs_run_created", "task_logs", ["run_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_task_logs_run_created", table_name="task_logs")
    op.drop_index("idx_task_logs_stage_status", table_name="task_logs")
    op.drop_index("idx_task_logs_category_created", table_name="task_logs")
    op.drop_index("idx_task_logs_level_created", table_name="task_logs")
    op.drop_index("idx_task_logs_task_created", table_name="task_logs")
    op.drop_table("task_logs")
