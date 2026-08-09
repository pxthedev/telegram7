from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.database.models.product import Product
from app.database.models.purchase import Purchase
from app.database.models.transaction import Transaction
from app.exceptions import (
    AlreadyPurchased,
    InsufficientBalance,
    InsufficientStock,
    ProductNotFound,
)
from app.services import product_service, purchase_service, user_service


async def _setup_balance(session, user_id: int, amount: str) -> None:
    await user_service.credit_balance(
        session,
        user_id,
        Decimal(amount),
        "ADJUSTMENT",
        description="Crédito de teste",
    )


async def test_buy_product_success(session):
    user = await user_service.get_or_create_user(session, 9001, "comprador", "Comprador")
    await _setup_balance(session, user.id, "100")
    product = await product_service.create_product(
        session, "Curso Teste", "Conteúdo", Decimal("40.00"), 5
    )
    await session.commit()

    purchase = await purchase_service.buy_product(session, user.id, product.id)
    await session.commit()

    assert purchase.status == "completed"
    assert purchase.amount == Decimal("40.00")
    assert purchase.user_id == user.id
    assert purchase.product_id == product.id

    await session.refresh(user)
    assert user.balance == Decimal("60.00")

    purchases = await session.scalar(
        select(func.count(Purchase.id)).where(Purchase.user_id == user.id)
    )
    assert purchases == 1

    transaction = await session.scalar(
        select(Transaction).where(Transaction.type == "PURCHASE")
    )
    assert transaction is not None
    assert transaction.amount == Decimal("-40.00")


async def test_buy_product_insufficient_balance(session):
    user = await user_service.get_or_create_user(session, 9002, "pobre", "Pobre")
    await _setup_balance(session, user.id, "10")
    product = await product_service.create_product(
        session, "Curso Teste", "Conteúdo", Decimal("40.00"), 5
    )
    await session.commit()

    with pytest.raises(InsufficientBalance):
        await purchase_service.buy_product(session, user.id, product.id)

    await session.refresh(user)
    assert user.balance == Decimal("10")
    purchases = await session.scalar(select(func.count(Purchase.id)))
    assert purchases == 0


async def test_buy_product_insufficient_stock(session):
    user = await user_service.get_or_create_user(session, 9003, "semestoque", "SemEstoque")
    await _setup_balance(session, user.id, "100")
    product = await product_service.create_product(
        session, "Curso Teste", "Conteúdo", Decimal("10.00"), 0
    )
    await session.commit()

    with pytest.raises(InsufficientStock):
        await purchase_service.buy_product(session, user.id, product.id)

    await session.refresh(user)
    assert user.balance == Decimal("100")


async def test_buy_product_duplicate_not_allowed(session):
    user = await user_service.get_or_create_user(session, 9004, "dup", "Dup")
    await _setup_balance(session, user.id, "100")
    product = await product_service.create_product(
        session, "Curso Teste", "Conteúdo", Decimal("10.00"), 5
    )
    await session.commit()

    await purchase_service.buy_product(session, user.id, product.id)
    await session.commit()

    with pytest.raises(AlreadyPurchased):
        await purchase_service.buy_product(session, user.id, product.id)

    await session.refresh(user)
    assert user.balance == Decimal("90.00")
    purchases = await session.scalar(
        select(func.count(Purchase.id)).where(Purchase.user_id == user.id)
    )
    assert purchases == 1


async def test_buy_product_inactive(session):
    user = await user_service.get_or_create_user(session, 9005, "inativo", "Inativo")
    await _setup_balance(session, user.id, "100")
    product = await product_service.create_product(
        session, "Curso Teste", "Conteúdo", Decimal("10.00"), 5
    )
    await product_service.set_product_active(session, product.id, False)
    await session.commit()

    with pytest.raises(ProductNotFound):
        await purchase_service.buy_product(session, user.id, product.id)


async def test_buy_product_never_negative_balance(session):
    user = await user_service.get_or_create_user(session, 9006, "negativo", "Negativo")
    await _setup_balance(session, user.id, "5")
    product = await product_service.create_product(
        session, "Curso Teste", "Conteúdo", Decimal("10.00"), 5
    )
    await session.commit()

    with pytest.raises(InsufficientBalance):
        await purchase_service.buy_product(session, user.id, product.id)

    await session.refresh(user)
    assert user.balance == Decimal("5")


async def test_stock_never_negative(session):
    user = await user_service.get_or_create_user(session, 9007, "estoque", "Estoque")
    await _setup_balance(session, user.id, "100")
    product = await product_service.create_product(
        session, "Curso Teste", "Conteúdo", Decimal("10.00"), 1
    )
    await session.commit()

    await purchase_service.buy_product(session, user.id, product.id)
    await session.commit()

    user2 = await user_service.get_or_create_user(session, 9008, "estoque2", "Estoque2")
    await _setup_balance(session, user2.id, "100")
    await session.commit()

    with pytest.raises(InsufficientStock):
        await purchase_service.buy_product(session, user2.id, product.id)

    await session.refresh(product)
    assert product.stock == 0
