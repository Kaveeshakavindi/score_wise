"""Add tutor_messages.citations: the retrieved syllabus chunks that grounded
an assistant reply (document/topic/snippet), so the tutor UI can show
citations proving the answer isn't unsourced. Additive only.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tutor_messages", sa.Column("citations", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("tutor_messages", "citations")
