from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.models.affiliate import Affiliate
from app.database.models.purchase import Purchase
from app.database.models.user import User


def affiliate_link(bot_username: str, code: str | None) -> str:
    if not code:
        return ""
    return f"https://t.me/{bot_username}?start={code}"


async def get_affiliate_stats(session: AsyncSession, user_id: int) -> dict:
    referrals = await session.scalar(
        select(func.count(User.id)).where(User.referred_by == user_id)
    )
    commission = await session.scalar(
        select(func.coalesce(func.sum(Affiliate.commission), 0)).where(
            Affiliate.affiliate_id == user_id, Affiliate.status == "paid"
        )
    )
    return {
        "referrals": referrals or 0,
        "commission": Decimal(commission or 0),
    }


async def list_affiliate_history(
    session: AsyncSession, user_id: int, page: int, per_page: int = 5
) -> tuple[list, int]:
    total = await session.scalar(
        select(func.count(Affiliate.id)).where(Affiliate.affiliate_id == user_id)
    )
    result = await session.execute(
        select(Affiliate, User.username, User.first_name)
        .join(User, Affiliate.referred_id == User.id)
        .where(Affiliate.affiliate_id == user_id)
        .order_by(Affiliate.created_at.desc())
        .limit(per_page)
        .offset((page - 1) * per_page)
    )
    rows = result.all()
    return rows, total or 0


async def register_commission(
    session: AsyncSession, purchase: Purchase, affiliate_user_id: int
) -> Affiliate | None:
    if affiliate_user_id == purchase.user_id:
        return None
    commission = (
        purchase.amount * settings.affiliate_percentage / 100
    ).quantize(Decimal("0.01"))
    if commission <= 0:
        return None

    record = Affiliate(
        affiliate_id=affiliate_user_id,
        referred_id=purchase.user_id,
        purchase_id=purchase.id,
        commission=commission,
        status="paid",
    )
    session.add(record)

    from app.services import user_service

    await user_service.credit_balance(
        session,
        affiliate_user_id,
        commission,
        "AFFILIATE",
        description=f"Comissão referente ao pedido #{purchase.id}",
        reference_id=f"affiliate:{purchase.id}",
    )
    await session.flush()
    return record
