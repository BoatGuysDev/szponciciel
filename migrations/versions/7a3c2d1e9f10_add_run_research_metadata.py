"""add run research metadata

Revision ID: 7a3c2d1e9f10
Revises: 5f4a1b0c8e92
Create Date: 2026-07-03 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7a3c2d1e9f10"
down_revision: Union[str, Sequence[str], None] = "5f4a1b0c8e92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("runs", sa.Column("topic", sa.String(), nullable=True))
    op.add_column("runs", sa.Column("news_category", sa.String(), nullable=True))
    op.add_column("runs", sa.Column("research_query", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("runs", "research_query")
    op.drop_column("runs", "news_category")
    op.drop_column("runs", "topic")
