"""Token usage tracking (see software.md's token-usage-management proposal).

Two additive pieces:
1. tutor_messages gains nullable input_tokens/output_tokens -- lets a single
   explanation show its own token cost with no join, same pattern as 0007's
   is_correct. Nullable for the same reason: existing rows predate this and
   are never backfilled with a number we didn't actually measure.
2. A new llm_usage_events table -- the append-only ledger for every LLM call
   in the app (tutor, chat, title generation), independent of any one
   feature's own tables. Feeds the per-user daily token budget check and any
   future cross-feature usage view. user_id is nullable to allow future
   system/background calls with no attributable user.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tutor_messages", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("tutor_messages", sa.Column("output_tokens", sa.Integer(), nullable=True))

    op.create_table(
        "llm_usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("feature", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_llm_usage_events_user_created", "llm_usage_events", ["user_id", sa.text("created_at DESC")])
    op.create_index("idx_llm_usage_events_feature", "llm_usage_events", ["feature"])


def downgrade() -> None:
    op.drop_index("idx_llm_usage_events_feature", table_name="llm_usage_events")
    op.drop_index("idx_llm_usage_events_user_created", table_name="llm_usage_events")
    op.drop_table("llm_usage_events")
    op.drop_column("tutor_messages", "output_tokens")
    op.drop_column("tutor_messages", "input_tokens")
