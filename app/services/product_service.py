from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.product import Product
from app.database.models.purchase import Purchase
from app.exceptions import ProductNotFound


async def list_active_products(session: AsyncSession) -> list[Product]:
    result = await session.scalars(
        select(Product)
        .where(Product.active.is_(True))
        .order_by(Product.created_at.asc())
    )
    return list(result)


async def list_all_products(session: AsyncSession) -> list[Product]:
    result = await session.scalars(
        select(Product).order_by(Product.created_at.asc())
    )
    return list(result)


async def get_product(
    session: AsyncSession, product_id: int, for_update: bool = False
) -> Product | None:
    stmt = select(Product).where(Product.id == product_id)
    if for_update:
        stmt = stmt.with_for_update()
    return await session.scalar(stmt)


async def create_product(
    session: AsyncSession,
    name: str,
    description: str,
    price: Decimal,
    stock: int,
    content: str | None = None,
) -> Product:
    product = Product(
        name=name,
        description=description,
        price=price,
        stock=stock,
        active=True,
        content=content,
    )
    session.add(product)
    await session.flush()
    return product


async def set_product_price(
    session: AsyncSession, product_id: int, price: Decimal
) -> Product:
    product = await get_product(session, product_id)
    if product is None:
        raise ProductNotFound
    product.price = price
    await session.flush()
    return product


async def set_product_stock(
    session: AsyncSession, product_id: int, stock: int
) -> Product:
    product = await get_product(session, product_id)
    if product is None:
        raise ProductNotFound
    product.stock = stock
    await session.flush()
    return product


async def zero_all_stock(session: AsyncSession) -> int:
    result = await session.execute(update(Product).values(stock=0))
    await session.commit()
    return result.rowcount or 0


async def set_product_active(
    session: AsyncSession, product_id: int, active: bool
) -> Product:
    product = await get_product(session, product_id)
    if product is None:
        raise ProductNotFound
    product.active = active
    await session.flush()
    return product


async def delete_product(session: AsyncSession, product_id: int) -> None:
    product = await get_product(session, product_id)
    if product is None:
        raise ProductNotFound
    await session.delete(product)
    await session.flush()


async def get_product_stats(
    session: AsyncSession, product_id: int
) -> tuple[int, Decimal]:
    result = await session.execute(
        select(
            func.count(Purchase.id),
            func.coalesce(func.sum(Purchase.amount), 0),
        ).where(
            Purchase.product_id == product_id, Purchase.status == "completed"
        )
    )
    row = result.one()
    return row[0] or 0, Decimal(row[1] or 0)
