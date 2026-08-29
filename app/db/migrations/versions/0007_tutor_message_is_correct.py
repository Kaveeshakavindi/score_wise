"""Add tutor_messages.is_correct: whether the student's recorded answer for
this question was correct (true also for accept_all-voided questions, since
every response was accepted). The tutor now auto-generates one feedback
message per (question, user) covering all three outcomes -- correct, wrong,
missed -- not just wrong ones, so dashboard analytics that used to assume
"has a tutor message" == "reviewed a mistake" need this to keep scoping
follow-through-rate/top-cited-topics to actual mistakes rather than every
question the student happened to view feedback for. Nullable for the
handful of pre-existing rows created before this column existed (open
chat turns, not tied to a single outcome); new rows always set it. Additive
only.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tutor_messages", sa.Column("is_correct", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("tutor_messages", "is_correct")
