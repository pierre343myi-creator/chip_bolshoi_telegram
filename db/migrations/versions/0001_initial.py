"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("scene", sa.String(length=100), nullable=True),
        sa.Column("show_dates", sa.JSON(), nullable=True),
        sa.Column("program_type", sa.String(length=200), nullable=True),
        sa.Column("ticket_price", sa.String(length=200), nullable=True),
        sa.Column("sale_opens_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ticket_url", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("notified_advance", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notified_today", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_url"),
    )
    op.create_index("ix_events_source_url", "events", ["source_url"])

    op.create_table(
        "subscribers",
        # Telegram user/chat IDs can exceed the 32-bit range → BigInteger.
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "subscribed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("telegram_user_id"),
    )


def downgrade() -> None:
    op.drop_table("subscribers")
    op.drop_index("ix_events_source_url", table_name="events")
    op.drop_table("events")
