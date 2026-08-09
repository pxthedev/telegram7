from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.models.pix_payment import PixPayment
from app.database.models.user import User
from app.database.models.webhook_event import WebhookEvent
from app.exceptions import CustomerDataRequired, PaymentError, PaymentNotFound
from app.services import user_service
from app.services.payment.base import (
    PaymentCustomer,
    PaymentProvider,
    PaymentResponse,
    PaymentStatus,
    PaymentWebhookData,
)

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self, provider: PaymentProvider) -> None:
        self.provider = provider

    @staticmethod
    def _new_external_id() -> str:
        return f"pay_{uuid4().hex}"

    async def create_deposit(
        self,
        session: AsyncSession,
        user: User,
        amount: Decimal,
        description: str = "Recarga de saldo",
    ) -> PixPayment:
        amount = amount.quantize(Decimal("0.01"))
        if not user.customer_email or not user.customer_phone or not user.customer_document_number:
            raise CustomerDataRequired

        external_id = self._new_external_id()
        payment = PixPayment(
            user_id=user.id,
            external_id=external_id,
            amount=amount,
            status=PaymentStatus.PENDING.value,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.pix_expiration_minutes),
        )
        session.add(payment)
        await session.flush()

        customer = PaymentCustomer(
            name=user.customer_name or user.first_name or "Usuário",
            email=user.customer_email,
            phone=user.customer_phone,
            document_type=(user.customer_document_type or "cpf"),
            document_number=user.customer_document_number,
        )
        try:
            response: PaymentResponse = await self.provider.create_pix_payment(
                amount, external_id, description, customer
            )
        except PaymentError:
            payment.status = PaymentStatus.FAILED.value
            await session.flush()
            raise

        payment.provider_payment_id = response.provider_id
        payment.status = response.status.value
        payment.qr_code = response.qr_code
        payment.pix_copy_paste = response.pix_copy_paste
        if response.expires_at is not None:
            payment.expires_at = response.expires_at
        await session.flush()
        return payment

    async def get_payment(
        self, session: AsyncSession, payment_id: int
    ) -> PixPayment | None:
        return await session.get(PixPayment, payment_id)

    async def credit_if_paid(
        self, session: AsyncSession, payment_id: int
    ) -> bool:
        payment = await session.scalar(
            select(PixPayment)
            .where(PixPayment.id == payment_id)
            .with_for_update()
        )
        if payment is None:
            raise PaymentNotFound

        if payment.status == PaymentStatus.PAID.value:
            return False

        payment.status = PaymentStatus.PAID.value
        payment.paid_at = datetime.now(timezone.utc)
        await user_service.credit_balance(
            session,
            payment.user_id,
            payment.amount,
            "DEPOSIT",
            description=f"Recarga PIX #{payment.id}",
            reference_id=f"pix:{payment.id}",
        )
        await session.flush()
        return True

    async def check_payment(
        self, session: AsyncSession, payment: PixPayment
    ) -> PixPayment:
        now = datetime.now(timezone.utc)
        if (
            payment.status == PaymentStatus.PENDING.value
            and payment.expires_at is not None
            and now > payment.expires_at
        ):
            payment.status = PaymentStatus.EXPIRED.value
            await session.flush()
            return payment

        if payment.status != PaymentStatus.PENDING.value:
            return payment

        if not payment.provider_payment_id:
            raise PaymentError("Pagamento sem identificador no gateway")

        response = await self.provider.get_payment_status(
            payment.provider_payment_id
        )
        if response.status is PaymentStatus.PAID:
            await self.credit_if_paid(session, payment.id)
        elif response.status is not PaymentStatus.PENDING:
            payment.status = response.status.value
            if response.status is PaymentStatus.PAID:
                payment.paid_at = datetime.now(timezone.utc)
        await session.flush()
        return payment

    async def process_webhook(
        self, session: AsyncSession, payload: dict
    ) -> tuple[PixPayment | None, bool]:
        data: PaymentWebhookData = self.provider.handle_webhook(payload)

        event, already_recorded = await self._record_webhook_event(
            session, data.event_id, payload
        )
        if already_recorded and event.processed:
            return None, False

        payment = await self._find_payment(session, data)
        if payment is None:
            logger.warning(
                "Webhook sem correspondência no banco (event_id=%s external_id=%s)",
                data.event_id,
                data.external_id,
            )
            event.processed = True
            event.processed_at = datetime.now(timezone.utc)
            await session.flush()
            return None, False

        if data.status is PaymentStatus.PAID:
            credited = await self.credit_if_paid(session, payment.id)
        else:
            payment.status = data.status.value
            credited = False

        event.processed = True
        event.processed_at = datetime.now(timezone.utc)
        await session.flush()
        return payment, credited

    async def _record_webhook_event(
        self, session: AsyncSession, event_id: str, payload: dict
    ) -> tuple[WebhookEvent, bool]:
        try:
            async with session.begin_nested():
                event = WebhookEvent(
                    event_id=event_id,
                    provider="freepay",
                    payload=payload,
                    processed=False,
                )
                session.add(event)
                await session.flush()
            return event, False
        except IntegrityError:
            event = await session.scalar(
                select(WebhookEvent)
                .where(WebhookEvent.event_id == event_id)
                .with_for_update()
            )
            return event, True

    async def _find_payment(
        self, session: AsyncSession, data: PaymentWebhookData
    ) -> PixPayment | None:
        if data.external_id:
            payment = await session.scalar(
                select(PixPayment).where(
                    PixPayment.external_id == data.external_id
                )
            )
            if payment is not None:
                return payment
        if data.provider_id:
            payment = await session.scalar(
                select(PixPayment).where(
                    PixPayment.provider_payment_id == data.provider_id
                )
            )
            if payment is not None:
                return payment
        return None
