"""Persist payment events and LangGraph resume delivery.

Revision ID: 8c31b147d92a
Revises: 5a0d16241cc1
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "8c31b147d92a"
down_revision: Union[str, Sequence[str], None] = "5a0d16241cc1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("graph_thread_id", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("razorpay_payment_id", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("payment_status", sa.String(24), server_default="pending", nullable=False))
    op.add_column("orders", sa.Column("currency", sa.String(3), server_default="INR", nullable=False))
    op.create_index("ix_orders_graph_thread_id", "orders", ["graph_thread_id"])
    op.create_table(
        "payment_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("razorpay_event_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("razorpay_order_id", sa.Text(), nullable=False),
        sa.Column("razorpay_payment_id", sa.Text()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("razorpay_event_id", name="uq_payment_event_razorpay_id"),
    )
    op.create_index("ix_payment_events_razorpay_order_id", "payment_events", ["razorpay_order_id"])
    op.create_table(
        "payment_resume_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("payment_event_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_status", sa.String(24), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_resume_outbox_status", "payment_resume_outbox", ["status"])


def downgrade() -> None:
    op.drop_index("ix_payment_resume_outbox_status", table_name="payment_resume_outbox")
    op.drop_table("payment_resume_outbox")
    op.drop_index("ix_payment_events_razorpay_order_id", table_name="payment_events")
    op.drop_table("payment_events")
    op.drop_index("ix_orders_graph_thread_id", table_name="orders")
    op.drop_column("orders", "currency")
    op.drop_column("orders", "payment_status")
    op.drop_column("orders", "razorpay_payment_id")
    op.drop_column("orders", "graph_thread_id")
