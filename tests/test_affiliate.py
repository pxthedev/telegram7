from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.database.models.affiliate import Affiliate
from app.database.models.transaction import Transaction
from app.services import affiliate_service, product_service, purchase_service, user_service


async def _referral_pair(session, referrer_id: int, referred_id: int):
    referrer = await user_service.get_or_create_user(
        session, referrer_id, f"ref{referrer_id}", f"Afiliado {referrer_id}"
    )
    referred = await user_service.get_or_create_user(
        session, referred_id, f"conv{referred_id}", f"Convidado {referred_id}",
        referrer_code=referrer.affiliate_code,
    )
    await user_service.credit_balance(
        session, referred.id, Decimal("100"), "ADJUSTMENT", "Saldo de teste"
    )
    return referrer, referred


async def test_commission_paid_on_referred_purchase(session):
    referrer, referred = await _referral_pair(session, 10000, 10001)
    product = await product_service.create_product(
        session, "Curso", "Conteúdo", Decimal("100.00"), 10
    )
    await session.commit()

    purchase = await purchase_service.buy_product(session, referred.id, product.id)
    await session.commit()

    await session.refresh(referrer)

    # Comissão de 25% de R$ 100,00 = R$ 25,00
    assert referrer.balance == Decimal("25.00")

    commissions = await session.scalars(select(Affiliate))
    records = list(commissions)
    assert len(records) == 1
    assert records[0].commission == Decimal("25.00")
    assert records[0].purchase_id == purchase.id
    assert records[0].affiliate_id == referrer.id

    affiliate_tx = await session.scalar(
        select(Transaction).where(Transaction.type == "AFFILIATE")
    )
    assert affiliate_tx is not None
    assert affiliate_tx.amount == Decimal("25.00")


async def test_commission_percentage_uses_settings(session):
    referrer, referred = await _referral_pair(session, 10010, 10011)
    product = await product_service.create_product(
        session, "Ebook", "Conteúdo", Decimal("50.00"), 10
    )
    await session.commit()

    await purchase_service.buy_product(session, referred.id, product.id)
    await session.commit()

    await session.refresh(referrer)
    # 25% de R$ 50,00 = R$ 12,50
    assert referrer.balance == Decimal("12.50")


async def test_no_commission_without_referrer(session):
    user = await user_service.get_or_create_user(session, 10020, "solo", "Solo")
    await user_service.credit_balance(
        session, user.id, Decimal("100"), "ADJUSTMENT", "Saldo de teste"
    )
    product = await product_service.create_product(
        session, "Curso", "Conteúdo", Decimal("50.00"), 10
    )
    await session.commit()

    await purchase_service.buy_product(session, user.id, product.id)
    await session.commit()

    total = await session.scalar(select(func.count(Affiliate.id)))
    assert total == 0


async def test_commission_only_once_per_purchase(session):
    referrer, referred = await _referral_pair(session, 10030, 10031)
    product = await product_service.create_product(
        session, "Curso", "Conteúdo", Decimal("100.00"), 10
    )
    await session.commit()

    purchase = await purchase_service.buy_product(session, referred.id, product.id)
    await session.commit()
    await session.refresh(referrer)
    first_balance = referrer.balance

    total = await session.scalar(select(func.count(Affiliate.id)))
    assert total == 1

    # Duplicar a comissão do mesmo pedido é bloqueado pela constraint única
    with pytest.raises(Exception):
        await affiliate_service.register_commission(session, purchase, referrer.id)
    await session.rollback()

    await session.refresh(referrer)
    assert referrer.balance == first_balance
    total = await session.scalar(select(func.count(Affiliate.id)))
    assert total == 1


async def test_affiliate_stats_and_history(session):
    referrer, referred = await _referral_pair(session, 10040, 10041)
    product = await product_service.create_product(
        session, "Curso", "Conteúdo", Decimal("100.00"), 10
    )
    await session.commit()
    await purchase_service.buy_product(session, referred.id, product.id)
    await session.commit()

    stats = await affiliate_service.get_affiliate_stats(session, referrer.id)
    assert stats["referrals"] == 1
    assert stats["commission"] == Decimal("25.00")

    rows, total = await affiliate_service.list_affiliate_history(
        session, referrer.id, page=1
    )
    assert total == 1
    assert len(rows) == 1
    record, username, first_name = rows[0]
    assert record.commission == Decimal("25.00")
