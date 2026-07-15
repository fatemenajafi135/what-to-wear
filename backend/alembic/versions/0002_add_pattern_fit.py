"""add_pattern_fit

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema. Additive only — nullable pattern/fit on wardrobe_items,
    mirroring how fabric/source were added in 0001. catalog_items is
    untouched: catalog items predate these fields."""
    op.add_column('wardrobe_items', sa.Column('pattern', sa.String(), nullable=True))
    op.add_column('wardrobe_items', sa.Column('fit', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('wardrobe_items', 'fit')
    op.drop_column('wardrobe_items', 'pattern')
