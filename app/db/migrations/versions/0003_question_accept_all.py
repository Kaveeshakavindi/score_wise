"""Questions: support voided/all-responses-accepted answer keys.

Some official AL past-paper marking schemes mark a question "All" instead of
a specific option number (an examiner-voided question — every submitted
answer, including none, is accepted as correct). `correct_answer` alone
can't represent that, so it becomes nullable and a new `accept_all` flag
carries the voided-question meaning; AttemptService scores any selection as
correct when it's set.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("questions", "correct_answer", existing_type=sa.Integer(), nullable=True)
    op.add_column(
        "questions",
        sa.Column("accept_all", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("questions", "accept_all")
    op.alter_column("questions", "correct_answer", existing_type=sa.Integer(), nullable=False)
