from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.database.models.pix_payment import PixPayment
from app.database.models.transaction import Transaction
from app.database.models.webhook_event import WebhookEvent
from app.exceptions import PaymentError
from app.services import user_service
from app.services.payment.base import PaymentStatus
from app.services.payment.service import PaymentService


async def _customer_user(session, telegram_id: int):
    user = await user_service.get_or_create_user(
        session, telegram_id, f"cliente{telegram_id}", f"Cliente {telegram_id}"
    )
    return user


def _paid_webhook(external_id: str, event_id: str = "evt_1") -> dict:
    return {
        "Id": event_id,
        "Status": "PAID",
        "ExternalId": external_id,
        "Amount": 100,
        "PaidAt": "2025-11-05T21:19:42.3648396",
    }


async def _count(session, model):
    return await session.scalar(select(func.count(model.id)))


async def test_create_deposit_pending(session, provider):
    user = await _customer_user(session, 20001)
    await session.commit()
    service = PaymentService(provider)

    payment = await service.create_deposit(session, user, Decimal("50"))
    await session.commit()

    assert payment.external_id.startswith("pay_")
    assert payment.provider_payment_id == f"txn_{payment.external_id}"
    assert payment.status == PaymentStatus.PENDING.value
    assert payment.amount == Decimal("50")
    assert payment.qr_code == provider.pix_code
    assert payment.pix_copy_paste == provider.pix_code
    assert payment.user_id == user.id
    assert payment.expires_at is not None


async def test_create_deposit_without_customer_data(session, provider):
    user = await user_service.get_or_create_user(session, 20002, "semdados", "SemDados")
    await session.commit()
    service = PaymentService(provider)

    payment = await service.create_deposit(session, user, Decimal("50"))
    await session.commit()

    assert payment.status == PaymentStatus.PENDING.value
    assert payment.user_id == user.id
    assert provider.created[-1][2].document_number is not None


async def test_create_deposit_provider_failure(session, provider):
    user = await _customer_user(session, 20003)
    await session.commit()
    provider.fail_create = True
    service = PaymentService(provider)

    with pytest.raises(PaymentError):
        await service.create_deposit(session, user, Decimal("50"))

    payment = await session.scalar(select(PixPayment).where(PixPayment.user_id == user.id))
    assert payment.status == PaymentStatus.FAILED.value
    assert await _count(session, Transaction) == 0


async def test_webhook_paid_credits_balance(session, provider):
    user = await _customer_user(session, 20004)
    await session.commit()
    service = PaymentService(provider)
    payment = await service.create_deposit(session, user, Decimal("50"))
    await session.commit()

    result, credited = await service.process_webhook(
        session, _paid_webhook(payment.external_id)
    )
    await session.commit()

    assert credited is True
    assert result is not None
    await session.refresh(result)
    assert result.status == PaymentStatus.PAID.value
    await session.refresh(user)
    assert user.balance == Decimal("50")

    deposits = await session.scalar(
        select(func.count(Transaction.id)).where(Transaction.type == "DEPOSIT")
    )
    assert deposits == 1
    webhook_events = await _count(session, WebhookEvent)
    assert webhook_events == 1


async def test_webhook_received_twice_credits_once(session, provider):
    user = await _customer_user(session, 20005)
    await session.commit()
    service = PaymentService(provider)
    payment = await service.create_deposit(session, user, Decimal("50"))
    await session.commit()

    payload = _paid_webhook(payment.external_id)

    _, credited_first = await service.process_webhook(session, payload)
    await session.commit()
    assert credited_first is True

    result_second, credited_second = await service.process_webhook(session, payload)
    await session.commit()
    assert credited_second is False
    assert result_second is None

    await session.refresh(user)
    assert user.balance == Decimal("50")
    deposits = await session.scalar(
        select(func.count(Transaction.id)).where(Transaction.type == "DEPOSIT")
    )
    assert deposits == 1
    webhook_events = await _count(session, WebhookEvent)
    assert webhook_events == 1


async def test_webhook_different_event_same_payment_not_double_credit(session, provider):
    user = await _customer_user(session, 20006)
    await session.commit()
    service = PaymentService(provider)
    payment = await service.create_deposit(session, user, Decimal("50"))
    await session.commit()

    _, credited_first = await service.process_webhook(
        session, _paid_webhook(payment.external_id, "evt_A")
    )
    await session.commit()
    assert credited_first is True

    _, credited_second = await service.process_webhook(
        session, _paid_webhook(payment.external_id, "evt_B")
    )
    await session.commit()
    assert credited_second is False

    await session.refresh(user)
    assert user.balance == Decimal("50")


async def test_webhook_pending_does_not_credit(session, provider):
    user = await _customer_user(session, 20007)
    await session.commit()
    service = PaymentService(provider)
    payment = await service.create_deposit(session, user, Decimal("50"))
    await session.commit()

    payload = {
        "Id": "evt_pending",
        "Status": "PENDING",
        "ExternalId": payment.external_id,
    }
    result, credited = await service.process_webhook(session, payload)
    await session.commit()

    assert credited is False
    assert result.status == PaymentStatus.PENDING.value
    await session.refresh(user)
    assert user.balance == Decimal("0")


async def test_webhook_amount_from_storage_not_payload(session, provider):
    user = await _customer_user(session, 20008)
    await session.commit()
    service = PaymentService(provider)
    payment = await service.create_deposit(session, user, Decimal("50"))
    await session.commit()

    payload = _paid_webhook(payment.external_id, "evt_amount")
    payload["Amount"] = 999999
    result, credited = await service.process_webhook(session, payload)
    await session.commit()

    assert credited is True
    await session.refresh(user)
    assert user.balance == Decimal("50")


async def test_webhook_unmatched_external_id(session, provider):
    await _customer_user(session, 20009)
    await session.commit()
    service = PaymentService(provider)

    result, credited = await service.process_webhook(
        session, _paid_webhook("nao_existe", "evt_unmatched")
    )
    await session.commit()

    assert credited is False
    assert result is None


async def test_check_payment_expired_does_not_credit(session, provider):
    user = await _customer_user(session, 20010)
    await session.commit()
    service = PaymentService(provider)
    payment = await service.create_deposit(session, user, Decimal("50"))
    await session.commit()

    payment.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await session.commit()

    result = await service.check_payment(session, payment)
    await session.commit()

    await session.refresh(result)
    assert result.status == PaymentStatus.EXPIRED.value
    await session.refresh(user)
    assert user.balance == Decimal("0")


async def test_check_payment_manual_paid(session, provider):
    user = await _customer_user(session, 20011)
    await session.commit()
    service = PaymentService(provider)
    payment = await service.create_deposit(session, user, Decimal("50"))
    await session.commit()

    provider.status = PaymentStatus.PAID
    result = await service.check_payment(session, payment)
    await session.commit()

    await session.refresh(result)
    assert result.status == PaymentStatus.PAID.value
    await session.refresh(user)
    assert user.balance == Decimal("50")

    # nova verificação após pago não credita de novo
    provider.status = PaymentStatus.PENDING
    await service.check_payment(session, payment)
    await session.commit()
    await session.refresh(user)
    assert user.balance == Decimal("50")


async def test_two_deposits_same_user_each_credited_once(session, provider):
    user = await _customer_user(session, 20012)
    await session.commit()
    service = PaymentService(provider)

    payment_a = await service.create_deposit(session, user, Decimal("10"))
    await session.commit()
    payment_b = await service.create_deposit(session, user, Decimal("20"))
    await session.commit()

    _, credited_a = await service.process_webhook(
        session, _paid_webhook(payment_a.external_id, "evt_a")
    )
    await session.commit()
    _, credited_b = await service.process_webhook(
        session, _paid_webhook(payment_b.external_id, "evt_b")
    )
    await session.commit()

    assert credited_a is True
    assert credited_b is True
    await session.refresh(user)
    assert user.balance == Decimal("30")
