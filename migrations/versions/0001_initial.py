"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-08 00:00:00

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("affiliate_code", sa.String(length=32), nullable=True),
        sa.Column("referred_by", sa.Integer(), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("customer_email", sa.String(length=255), nullable=True),
        sa.Column("customer_phone", sa.String(length=32), nullable=True),
        sa.Column("customer_document_type", sa.String(length=8), nullable=True),
        sa.Column("customer_document_number", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["referred_by"],
            ["users.id"],
            name="fk_users_referred_by_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)
    op.create_index("ix_users_affiliate_code", "users", ["affiliate_code"], unique=True)
    op.create_index("ix_users_referred_by", "users", ["referred_by"])

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_products_name", "products", ["name"])

    op.create_table(
        "purchases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_purchases_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], name="fk_purchases_product_id_products", ondelete="RESTRICT"),
        sa.UniqueConstraint("user_id", "product_id", name="uq_purchases_user_id_product_id"),
    )
    op.create_index("ix_purchases_user_id", "purchases", ["user_id"])
    op.create_index("ix_purchases_product_id", "purchases", ["product_id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_transactions_user_id_users", ondelete="CASCADE"),
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
    op.create_index("ix_transactions_type", "transactions", ["type"])
    op.create_index("ix_transactions_user_created", "transactions", ["user_id", "created_at"])
    op.create_index(
        "uq_transactions_deposit_ref",
        "transactions",
        ["type", "reference_id"],
        unique=True,
        postgresql_where=sa.text("type = 'DEPOSIT' AND reference_id IS NOT NULL"),
    )

    op.create_table(
        "affiliates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("affiliate_id", sa.Integer(), nullable=False),
        sa.Column("referred_id", sa.Integer(), nullable=False),
        sa.Column("purchase_id", sa.Integer(), nullable=False),
        sa.Column("commission", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="paid"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["affiliate_id"], ["users.id"], name="fk_affiliates_affiliate_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["referred_id"], ["users.id"], name="fk_affiliates_referred_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"], name="fk_affiliates_purchase_id_purchases", ondelete="CASCADE"),
        sa.UniqueConstraint("purchase_id", name="uq_affiliates_purchase_id"),
    )
    op.create_index("ix_affiliates_affiliate_id", "affiliates", ["affiliate_id"])
    op.create_index("ix_affiliates_referred_id", "affiliates", ["referred_id"])

    op.create_table(
        "pix_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=128), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("qr_code", sa.Text(), nullable=True),
        sa.Column("pix_copy_paste", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_pix_payments_user_id_users", ondelete="CASCADE"),
    )
    op.create_index("ix_pix_payments_user_id", "pix_payments", ["user_id"])
    op.create_index("ix_pix_payments_external_id", "pix_payments", ["external_id"], unique=True)
    op.create_index("ix_pix_payments_provider_payment_id", "pix_payments", ["provider_payment_id"], unique=True)
    op.create_index("ix_pix_payments_status", "pix_payments", ["status"])

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="freepay"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_webhook_events_event_id", "webhook_events", ["event_id"], unique=True)
    op.create_index("ix_webhook_events_processed", "webhook_events", ["processed"])


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_table("pix_payments")
    op.drop_table("affiliates")
    op.drop_table("transactions")
    op.drop_table("purchases")
    op.drop_table("products")
    op.drop_table("users")
