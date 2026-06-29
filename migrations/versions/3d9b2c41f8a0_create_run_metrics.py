"""create run metrics

Revision ID: 3d9b2c41f8a0
Revises: 8b22b7a6e3f4
Create Date: 2026-06-29 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3d9b2c41f8a0"
down_revision: Union[str, Sequence[str], None] = "8b22b7a6e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "run_metrics",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("persona_run_id", sa.String(), nullable=False),
        sa.Column("persona_id", sa.String(), nullable=False),
        sa.Column("zernio_post_id", sa.String(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("platform_post_id", sa.String(), nullable=True),
        sa.Column("platform_post_url", sa.String(), nullable=True),
        sa.Column("account_id", sa.String(), nullable=True),
        sa.Column("account_username", sa.String(), nullable=True),
        sa.Column("post_status", sa.String(), nullable=True),
        sa.Column("sync_status", sa.String(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("metrics_last_updated_at", sa.DateTime(), nullable=True),
        sa.Column("post_age_hours", sa.Float(), nullable=True),
        sa.Column("views", sa.Integer(), nullable=True),
        sa.Column("likes", sa.Integer(), nullable=True),
        sa.Column("comments", sa.Integer(), nullable=True),
        sa.Column("shares", sa.Integer(), nullable=True),
        sa.Column("saves", sa.Integer(), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=True),
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("reach", sa.Integer(), nullable=True),
        sa.Column("engagement_rate", sa.Float(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["persona_id"], ["personas.id"]),
        sa.ForeignKeyConstraint(["persona_run_id"], ["persona_runs.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_run_metrics_account_id"), "run_metrics", ["account_id"], unique=False)
    op.create_index(op.f("ix_run_metrics_fetched_at"), "run_metrics", ["fetched_at"], unique=False)
    op.create_index(op.f("ix_run_metrics_persona_id"), "run_metrics", ["persona_id"], unique=False)
    op.create_index(op.f("ix_run_metrics_persona_run_id"), "run_metrics", ["persona_run_id"], unique=False)
    op.create_index(op.f("ix_run_metrics_platform"), "run_metrics", ["platform"], unique=False)
    op.create_index(op.f("ix_run_metrics_platform_post_id"), "run_metrics", ["platform_post_id"], unique=False)
    op.create_index(op.f("ix_run_metrics_run_id"), "run_metrics", ["run_id"], unique=False)
    op.create_index(op.f("ix_run_metrics_zernio_post_id"), "run_metrics", ["zernio_post_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_run_metrics_zernio_post_id"), table_name="run_metrics")
    op.drop_index(op.f("ix_run_metrics_run_id"), table_name="run_metrics")
    op.drop_index(op.f("ix_run_metrics_platform_post_id"), table_name="run_metrics")
    op.drop_index(op.f("ix_run_metrics_platform"), table_name="run_metrics")
    op.drop_index(op.f("ix_run_metrics_persona_run_id"), table_name="run_metrics")
    op.drop_index(op.f("ix_run_metrics_persona_id"), table_name="run_metrics")
    op.drop_index(op.f("ix_run_metrics_fetched_at"), table_name="run_metrics")
    op.drop_index(op.f("ix_run_metrics_account_id"), table_name="run_metrics")
    op.drop_table("run_metrics")
