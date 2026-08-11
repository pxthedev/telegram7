from decimal import Decimal

import pytest
from sqlalchemy import select

from app.database.models.product import Product
from app.services import product_service


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
