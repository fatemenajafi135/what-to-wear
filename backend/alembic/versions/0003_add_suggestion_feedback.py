"""add_suggestion_feedback

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-16 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema. Additive only -- two new tables, no changes to
    existing ones (Feature 004: preference-memory). See
    specs/004-preference-memory/data-model.md."""
    op.create_table(
        "suggestion_feedback",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("verdict", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("item_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("item_ids_key", sa.String(), nullable=False),
        sa.Column("item_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("verdict IN ('liked','rejected')", name="ck_suggestion_feedback_verdict"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "item_ids_key", name="uq_suggestion_feedback_user_items"),
    )
    op.create_index(op.f("ix_suggestion_feedback_user_id"), "suggestion_feedback", ["user_id"], unique=False)

    op.create_table(
        "preference_signal_dismissal",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("signal_key", sa.String(), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "signal_key", name="uq_pref_dismissal_user_signal"),
    )
    op.create_index(
        op.f("ix_preference_signal_dismissal_user_id"), "preference_signal_dismissal", ["user_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_preference_signal_dismissal_user_id"), table_name="preference_signal_dismissal")
    op.drop_table("preference_signal_dismissal")
    op.drop_index(op.f("ix_suggestion_feedback_user_id"), table_name="suggestion_feedback")
    op.drop_table("suggestion_feedback")
