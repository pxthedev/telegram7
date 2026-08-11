from decimal import Decimal

import pytest
from sqlalchemy import select

from app.database.models.product import Product
from app.database.models.purchase import Purchase
from app.database.models.user import User
from app.services import product_service, purchase_service, user_service


@pytest.mark.asyncio
async def test_zero_all_stock(session):
    await product_service.create_product(session, "A", "d", Decimal("10"), 3)
    await product_service.create_product(session, "B", "d", Decimal("20"), 0)
    await product_service.create_product(session, "C", "d", Decimal("30"), 8)
    await session.commit()

    updated = await product_service.zero_all_stock(session)

    assert updated == 3
    stocks = (await session.scalars(select(Product.stock))).all()
    assert stocks == [0, 0, 0]


@pytest.mark.asyncio
async def test_delete_all_products(session):
    await product_service.create_product(session, "A", "d", Decimal("10"), 3)
    await product_service.create_product(session, "B", "d", Decimal("20"), 0)
    await session.commit()

    deleted, skipped = await product_service.delete_all_products(session)

    assert (deleted, skipped) == (2, 0)
    remaining = await session.scalars(select(Product))
    assert list(remaining) == []


@pytest.mark.asyncio
async def test_delete_all_keeps_products_with_sales(session):
    await product_service.create_product(session, "A", "d", Decimal("10"), 3)
    await session.commit()

    user = await user_service.get_or_create_user(session, 9001, "comprador", "Comprador")
    await user_service.credit_balance(
        session, user.id, Decimal("100"), "ADJUSTMENT", description="teste"
    )
    product = (await session.scalars(select(Product))).first()
    await purchase_service.buy_product(session, user.id, product.id)
    await session.commit()

    deleted, skipped = await product_service.delete_all_products(session)

    assert (deleted, skipped) == (0, 1)
    remaining = await session.scalars(select(Product))
    assert list(remaining) != []
