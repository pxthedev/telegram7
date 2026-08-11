"""enable row level security on public tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-11 00:00:00

"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_TABLES = (
    "users",
    "products",
    "purchases",
    "transactions",
    "affiliates",
    "pix_payments",
    "webhook_events",
    "alembic_version",
)


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY;")
