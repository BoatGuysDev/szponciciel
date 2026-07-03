"""unique run metrics persona run

Revision ID: 5f4a1b0c8e92
Revises: 3d9b2c41f8a0
Create Date: 2026-06-29 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5f4a1b0c8e92"
down_revision: Union[str, Sequence[str], None] = "3d9b2c41f8a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f("ix_run_metrics_persona_run_id"), table_name="run_metrics")
    op.create_index("ux_run_metrics_persona_run_id", "run_metrics", ["persona_run_id"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ux_run_metrics_persona_run_id", table_name="run_metrics")
    op.create_index(op.f("ix_run_metrics_persona_run_id"), "run_metrics", ["persona_run_id"], unique=False)
