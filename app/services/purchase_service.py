from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.product import Product
from app.database.models.purchase import Purchase
from app.database.models.user import User
from app.exceptions import (
    AlreadyPurchased,
    InsufficientBalance,
    InsufficientStock,
    ProductNotFound,
    UserNotFound,
)
from app.services import affiliate_service, user_service


async def buy_product(
    session: AsyncSession, user_id: int, product_id: int
) -> Purchase:
    product = await session.scalar(
        select(Product).where(Product.id == product_id).with_for_update()
    )
    if product is None or not product.active:
        raise ProductNotFound

    user = await session.get(User, user_id, with_for_update=True)
    if user is None:
        raise UserNotFound

    if int(product.stock or 0) <= 0:
        raise InsufficientStock

    if Decimal(user.balance or 0) < product.price:
        raise InsufficientBalance

    existing = await session.scalar(
        select(Purchase.id).where(
            Purchase.user_id == user_id, Purchase.product_id == product_id
        )
    )
    if existing is not None:
        raise AlreadyPurchased

    await user_service.debit_balance(
        session,
        user_id,
        product.price,
        "PURCHASE",
        description=f"Compra de {product.name}",
        reference_id=f"product:{product_id}",
    )

    product.stock = int(product.stock or 0) - 1

    purchase = Purchase(
        user_id=user_id,
        product_id=product_id,
        amount=product.price,
        status="completed",
    )
    session.add(purchase)
    await session.flush()

    if user.referred_by is not None:
        await affiliate_service.register_commission(
            session, purchase, user.referred_by
        )

    await session.flush()
    return purchase


async def get_user_purchases(
    session: AsyncSession, user_id: int, page: int, per_page: int = 5
) -> tuple[list, int]:
    total = await session.scalar(
        select(func.count(Purchase.id)).where(
            Purchase.user_id == user_id, Purchase.status == "completed"
        )
    )
    result = await session.execute(
        select(Purchase, Product.name, Product.content)
        .join(Product, Purchase.product_id == Product.id)
        .where(Purchase.user_id == user_id, Purchase.status == "completed")
        .order_by(Purchase.created_at.desc())
        .limit(per_page)
        .offset((page - 1) * per_page)
    )
    rows = result.all()
    return rows, total or 0
