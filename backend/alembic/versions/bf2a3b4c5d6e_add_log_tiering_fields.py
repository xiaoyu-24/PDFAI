"""add_log_tiering_fields

Revision ID: bf2a3b4c5d6e
Revises: ae1f2a3b4c5d
Create Date: 2026-07-20 22:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "bf2a3b4c5d6e"
down_revision: Union[str, None] = "ae1f2a3b4c5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # task_logs 新增分层字段
    op.add_column("task_logs", sa.Column("is_timeline", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("task_logs", sa.Column("retention_until", sa.DateTime(), nullable=True))
    op.add_column("task_logs", sa.Column("detail_available_until", sa.DateTime(), nullable=True))

    # 新增索引
    op.create_index("idx_task_logs_timeline", "task_logs", ["task_id", "is_timeline", "created_at"])
    op.create_index("idx_task_logs_retention", "task_logs", ["level", "retention_until", "created_at"])

    # 新增 task_log_files 表
    op.create_table(
        "task_log_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("relative_path", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="writing"),
        sa.Column("line_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["compare_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "run_id", name="uq_task_log_files_task_run"),
    )
    op.create_index("idx_task_log_files_task_id", "task_log_files", ["task_id"])
    op.create_index("idx_task_log_files_expires", "task_log_files", ["expires_at", "status"])


def downgrade() -> None:
    op.drop_index("idx_task_log_files_expires", table_name="task_log_files")
    op.drop_index("idx_task_log_files_task_id", table_name="task_log_files")
    op.drop_table("task_log_files")
    op.drop_index("idx_task_logs_retention", table_name="task_logs")
    op.drop_index("idx_task_logs_timeline", table_name="task_logs")
    op.drop_column("task_logs", "detail_available_until")
    op.drop_column("task_logs", "retention_until")
    op.drop_column("task_logs", "is_timeline")
