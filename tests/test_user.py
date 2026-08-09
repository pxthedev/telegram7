from __future__ import annotations

from sqlalchemy import func, select

from app.database.models.affiliate import Affiliate
from app.database.models.user import User
from app.services import user_service


async def test_create_user(session):
    user = await user_service.get_or_create_user(
        session, 111, username="joao", first_name="João"
    )
    assert user.telegram_id == 111
    assert user.username == "joao"
    assert user.balance == 0
    assert user.affiliate_code
    assert user.referred_by is None


async def test_get_or_create_user_is_idempotent(session):
    first = await user_service.get_or_create_user(session, 222, "maria", "Maria")
    second = await user_service.get_or_create_user(session, 222, "maria", "Maria")
    assert first.id == second.id
    total = await session.scalar(select(func.count(User.id)))
    assert total == 1


async def test_referral_flow(session):
    referrer = await user_service.get_or_create_user(session, 100, "ref", "Referral")
    assert referrer.affiliate_code

    referred = await user_service.get_or_create_user(
        session, 101, "novo", "Novo", referrer_code=referrer.affiliate_code
    )
    assert referred.referred_by == referrer.id
    assert referred.affiliate_code
    assert referred.affiliate_code != referrer.affiliate_code


async def test_referral_by_numeric_user_id(session):
    referrer = await user_service.get_or_create_user(session, 200, "ref2", "Referral2")
    referred = await user_service.get_or_create_user(
        session, 201, "novo2", "Novo2", referrer_code=str(referrer.id)
    )
    assert referred.referred_by == referrer.id


async def test_self_referral_not_allowed(session):
    user = await user_service.get_or_create_user(session, 300, "self", "Self")
    again = await user_service.get_or_create_user(
        session, 300, "self", "Self", referrer_code=user.affiliate_code
    )
    assert again.referred_by is None


async def test_referral_does_not_credit_balance_on_signup(session):
    referrer = await user_service.get_or_create_user(session, 400, "ref3", "Referral3")
    await user_service.get_or_create_user(
        session, 401, "novo3", "Novo3", referrer_code=referrer.affiliate_code
    )
    total = await session.scalar(select(func.count(Affiliate.id)))
    assert total == 0
    assert referrer.balance == 0


async def test_referral_not_duplicated_or_changed(session):
    referrer_a = await user_service.get_or_create_user(session, 500, "a", "A")
    referrer_b = await user_service.get_or_create_user(session, 501, "b", "B")
    referred = await user_service.get_or_create_user(
        session, 502, "novo4", "Novo4", referrer_code=referrer_a.affiliate_code
    )
    assert referred.referred_by == referrer_a.id

    again = await user_service.get_or_create_user(
        session, 502, "novo4", "Novo4", referrer_code=referrer_b.affiliate_code
    )
    assert again.referred_by == referrer_a.id
    total = await session.scalar(select(func.count(User.id)).where(User.telegram_id == 502))
    assert total == 1
