"""add_photo_path

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-16 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema. Additive only — nullable photo_path on wardrobe_items,
    same pattern as pattern/fit in 0002. catalog_items is untouched: catalog
    items never have a photo."""
    op.add_column("wardrobe_items", sa.Column("photo_path", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("wardrobe_items", "photo_path")
