"""rename story mode ratio

Revision ID: 4e4b2c6d8e1a
Revises: 9e18d0fc1759
Create Date: 2026-06-13 19:30:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4e4b2c6d8e1a"
down_revision: Union[str, Sequence[str], None] = "9e18d0fc1759"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("personas", "real_news_ratio", new_column_name="fictional_news_ratio")
    op.execute("UPDATE personas SET fictional_news_ratio = 1.0 - fictional_news_ratio")
    op.execute(
        "UPDATE personas SET style = 'fictional news documentary', "
        "tone = 'confident, straight-faced' WHERE id = 'ground_truth_media'"
    )
    op.alter_column("persona_runs", "content_type", new_column_name="story_mode")
    op.execute("UPDATE persona_runs SET story_mode = 'real_news' WHERE story_mode = 'real'")
    op.execute("UPDATE persona_runs SET story_mode = 'fictional_news' WHERE story_mode = 'fake'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE persona_runs SET story_mode = 'real' WHERE story_mode = 'real_news'")
    op.execute("UPDATE persona_runs SET story_mode = 'fake' WHERE story_mode = 'fictional_news'")
    op.alter_column("persona_runs", "story_mode", new_column_name="content_type")
    op.execute("UPDATE personas SET style = 'neutral, factual', tone = 'informative' WHERE id = 'ground_truth_media'")
    op.execute("UPDATE personas SET fictional_news_ratio = 1.0 - fictional_news_ratio")
    op.alter_column("personas", "fictional_news_ratio", new_column_name="real_news_ratio")
