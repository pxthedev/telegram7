from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.purchase import Purchase
from app.database.models.transaction import Transaction
from app.database.models.user import User
from app.exceptions import InsufficientBalance, UserNotFound


async def _generate_unique_affiliate_code(session: AsyncSession) -> str:
    for _ in range(5):
        code = uuid4().hex[:8]
        exists = await session.scalar(
            select(User.id).where(User.affiliate_code == code)
        )
        if not exists:
            return code
    return uuid4().hex[:12]


async def _resolve_referrer(
    session: AsyncSession, code: str | None, telegram_id: int
) -> User | None:
    if not code:
        return None
    referrer = await session.scalar(
        select(User).where(User.affiliate_code == code)
    )
    if referrer is None and code.isdigit():
        referrer = await session.get(User, int(code))
    if referrer is None:
        return None
    if referrer.telegram_id == telegram_id:
        return None
    return referrer


async def get_user(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    referrer_code: str | None = None,
) -> User:
    user = await get_user(session, telegram_id)
    if user is not None:
        if username is not None:
            user.username = username
        if first_name is not None:
            user.first_name = first_name
        return user

    referrer = await _resolve_referrer(session, referrer_code, telegram_id)
    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        balance=Decimal("0"),
        affiliate_code=await _generate_unique_affiliate_code(session),
        referred_by=referrer.id if referrer else None,
    )
    session.add(user)
    await session.flush()
    return user


async def ensure_affiliate_code(session: AsyncSession, user: User) -> str:
    if not user.affiliate_code:
        user.affiliate_code = await _generate_unique_affiliate_code(session)
        await session.flush()
    return user.affiliate_code


async def save_customer_data(
    session: AsyncSession,
    user: User,
    name: str,
    email: str,
    phone: str,
    document_type: str,
    document_number: str,
) -> User:
    user.customer_name = name
    user.customer_email = email
    user.customer_phone = phone
    user.customer_document_type = document_type
    user.customer_document_number = document_number
    await session.flush()
    return user


async def credit_balance(
    session: AsyncSession,
    user_id: int,
    amount: Decimal,
    tx_type: str,
    description: str | None = None,
    reference_id: str | None = None,
) -> Transaction:
    user = await session.get(User, user_id, with_for_update=True)
    if user is None:
        raise UserNotFound
    user.balance = Decimal(user.balance or 0) + amount
    tx = Transaction(
        user_id=user.id,
        amount=amount,
        type=tx_type,
        description=description,
        reference_id=reference_id,
    )
    session.add(tx)
    await session.flush()
    return tx


async def debit_balance(
    session: AsyncSession,
    user_id: int,
    amount: Decimal,
    tx_type: str,
    description: str | None = None,
    reference_id: str | None = None,
) -> Transaction:
    user = await session.get(User, user_id, with_for_update=True)
    if user is None:
        raise UserNotFound
    if Decimal(user.balance or 0) < amount:
        raise InsufficientBalance
    user.balance = Decimal(user.balance or 0) - amount
    tx = Transaction(
        user_id=user.id,
        amount=-amount,
        type=tx_type,
        description=description,
        reference_id=reference_id,
    )
    session.add(tx)
    await session.flush()
    return tx


async def get_user_stats(session: AsyncSession, user_id: int) -> dict:
    purchases = await session.scalar(
        select(func.count(Purchase.id)).where(
            Purchase.user_id == user_id, Purchase.status == "completed"
        )
    )
    deposited = await session.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.user_id == user_id, Transaction.type == "DEPOSIT"
        )
    )
    return {
        "purchases": purchases or 0,
        "deposited": Decimal(deposited or 0),
    }
