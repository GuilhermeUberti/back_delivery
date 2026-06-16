"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # restaurants
    op.create_table(
        "restaurants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("whatsapp_number", sa.Text, nullable=False),
        sa.Column("pix_key", sa.Text),
        sa.Column("delivery_fee", sa.Numeric(8, 2)),
        sa.Column("delivery_radius", sa.Integer),
        sa.Column("open_time", sa.Time),
        sa.Column("close_time", sa.Time),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("whatsapp_number", name="uq_restaurants_whatsapp_number"),
    )

    # users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=False, server_default=sa.text("'owner'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_restaurant_id", "users", ["restaurant_id"])

    # categories
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("position", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_categories_restaurant_id", "categories", ["restaurant_id"])

    # menu_items
    op.create_table(
        "menu_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("price", sa.Numeric(8, 2), nullable=False),
        sa.Column("image_url", sa.Text),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("position", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_menu_items_restaurant_active", "menu_items", ["restaurant_id", "active"])
    op.create_index("ix_menu_items_category_id", "menu_items", ["category_id"])

    # customers
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("whatsapp", sa.Text, nullable=False),
        sa.Column("name", sa.Text),
        sa.Column("address", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("restaurant_id", "whatsapp", name="uq_customers_restaurant_whatsapp"),
    )
    op.create_index("ix_customers_restaurant_id", "customers", ["restaurant_id"])

    # orders
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("payment_method", sa.Text),
        sa.Column("payment_status", sa.Text, nullable=False, server_default=sa.text("'awaiting'")),
        sa.Column("payment_ref", sa.Text),
        sa.Column("subtotal", sa.Numeric(8, 2)),
        sa.Column("delivery_fee", sa.Numeric(8, 2)),
        sa.Column("total", sa.Numeric(8, 2)),
        sa.Column("address", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_orders_restaurant_status", "orders", ["restaurant_id", "status"])
    op.create_index("ix_orders_restaurant_created_at", "orders", ["restaurant_id", "created_at"])

    # order_items
    op.create_table(
        "order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("menu_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("menu_items.id")),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("price", sa.Numeric(8, 2), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])

    # conversation_state
    op.create_table(
        "conversation_state",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("whatsapp", sa.Text, nullable=False),
        sa.Column("step", sa.Text, nullable=False),
        sa.Column("cart", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("data", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("restaurant_id", "whatsapp", name="uq_conversation_state_restaurant_whatsapp"),
    )
    op.create_index("ix_conversation_state_updated_at", "conversation_state", ["updated_at"])


def downgrade() -> None:
    op.drop_table("conversation_state")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("customers")
    op.drop_table("menu_items")
    op.drop_table("categories")
    op.drop_table("users")
    op.drop_table("restaurants")
