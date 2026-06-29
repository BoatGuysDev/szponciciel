"""rename tiktok post id

Revision ID: 8b22b7a6e3f4
Revises: 4e4b2c6d8e1a
Create Date: 2026-06-29 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b22b7a6e3f4"
down_revision: Union[str, Sequence[str], None] = "4e4b2c6d8e1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("persona_runs", "tiktok_post_id", new_column_name="zernio_post_id")


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("persona_runs", "zernio_post_id", new_column_name="tiktok_post_id")
