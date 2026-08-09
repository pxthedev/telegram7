from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.transaction import Transaction
from app.utils.formatting import fmt_datetime, fmt_money, transaction_type_label


async def list_user_transactions(
    session: AsyncSession,
    user_id: int,
    page: int,
    per_page: int = 5,
    tx_type: str | None = None,
) -> tuple[list, int]:
    conditions = [Transaction.user_id == user_id]
    if tx_type is not None:
        conditions.append(Transaction.type == tx_type)
    total = await session.scalar(
        select(func.count(Transaction.id)).where(*conditions)
    )
    result = await session.execute(
        select(Transaction)
        .where(*conditions)
        .order_by(Transaction.created_at.desc())
        .limit(per_page)
        .offset((page - 1) * per_page)
    )
    rows = result.scalars().all()
    return rows, total or 0


def format_transaction(tx: Transaction) -> str:
    amount = Decimal(tx.amount or 0)
    sign = "+" if amount >= 0 else "-"
    return (
        f"#{tx.id} {transaction_type_label(tx.type)}\n"
        f"Valor: {fmt_money(abs(amount))} ({sign})\n"
        f"Data: {fmt_datetime(tx.created_at)}"
    )


async def sum_by_type(
    session: AsyncSession, tx_type: str, since: datetime | None = None
) -> Decimal:
    conditions = [Transaction.type == tx_type]
    if since is not None:
        conditions.append(Transaction.created_at >= since)
    value = await session.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(*conditions)
    )
    return Decimal(value or 0)


async def count_by_type(
    session: AsyncSession, tx_type: str, since: datetime | None = None
) -> int:
    conditions = [Transaction.type == tx_type]
    if since is not None:
        conditions.append(Transaction.created_at >= since)
    value = await session.scalar(
        select(func.count(Transaction.id)).where(*conditions)
    )
    return value or 0
