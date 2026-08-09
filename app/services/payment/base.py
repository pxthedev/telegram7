from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


@dataclass
class PaymentCustomer:
    name: str
    email: str
    phone: str
    document_type: str
    document_number: str


@dataclass
class PaymentResponse:
    external_id: str
    provider_id: str
    status: PaymentStatus
    amount: Decimal
    qr_code: str | None = None
    pix_copy_paste: str | None = None
    expires_at: datetime | None = None


@dataclass
class PaymentWebhookData:
    event_id: str
    provider_id: str | None = None
    external_id: str | None = None
    status: PaymentStatus = PaymentStatus.PENDING
    amount: Decimal | None = None
    confirmed_at: datetime | None = None


class PaymentProvider(ABC):
    @abstractmethod
    async def create_pix_payment(
        self,
        amount: Decimal,
        external_id: str,
        description: str,
        customer: PaymentCustomer,
    ) -> PaymentResponse:
        raise NotImplementedError

    @abstractmethod
    async def get_payment_status(self, provider_id: str) -> PaymentResponse:
        raise NotImplementedError

    @abstractmethod
    def parse_payment_response(self, payload: dict) -> PaymentResponse:
        raise NotImplementedError

    @abstractmethod
    def validate_webhook(self, headers: dict, payload: dict) -> bool:
        raise NotImplementedError

    @abstractmethod
    def handle_webhook(self, payload: dict) -> PaymentWebhookData:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
