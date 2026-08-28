"""Add tutor_messages.selected_answer: which option the student had selected
when this turn happened. Needed so a later tutor turn only replays history
from turns made under the *same* selected answer — if the student re-attempts
a question and picks a different wrong option, prior turns explaining the
old wrong option are no longer valid grounding and must not be fed back to
the model. Additive only.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tutor_messages", sa.Column("selected_answer", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("tutor_messages", "selected_answer")
