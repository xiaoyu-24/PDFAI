"""add_task_observability_fields

Revision ID: 7b8c9d0e1f2a
Revises: d2135e58fd8a
Create Date: 2026-06-16 09:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7b8c9d0e1f2a"
down_revision: Union[str, None] = "d2135e58fd8a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_extraction_runs", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.add_column("ai_extraction_runs", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("ai_extraction_runs", sa.Column("finished_at", sa.DateTime(), nullable=True))
    op.add_column("ai_extraction_runs", sa.Column("attempt_count", sa.Integer(), nullable=True))

    op.add_column("compare_tasks", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("compare_tasks", sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True))
    op.add_column("compare_tasks", sa.Column("failed_stage", sa.String(length=64), nullable=True))
    op.add_column("compare_tasks", sa.Column("last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("compare_tasks", "last_error")
    op.drop_column("compare_tasks", "failed_stage")
    op.drop_column("compare_tasks", "updated_at")
    op.drop_column("compare_tasks", "started_at")

    op.drop_column("ai_extraction_runs", "attempt_count")
    op.drop_column("ai_extraction_runs", "finished_at")
    op.drop_column("ai_extraction_runs", "started_at")
    op.drop_column("ai_extraction_runs", "duration_ms")
