from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config.settings import Settings
from app.database.database import Base
from app.exceptions import PaymentError
from app.services.payment.base import (
    PaymentProvider,
    PaymentResponse,
    PaymentStatus,
    PaymentWebhookData,
)

_CONFIG_MODULES = (
    "app.config.settings",
    "app.services.affiliate_service",
    "app.services.payment.service",
    "app.utils.validators",
)


def _build_test_settings(**overrides) -> Settings:
    values = {
        "bot_token": "test:token",
        "bot_username": "test_bot",
        "database_url": "sqlite+aiosqlite://",
        "admin_ids": [1, 2],
        "affiliate_percentage": Decimal("25"),
        "pix_expiration_minutes": 30,
        "min_deposit_amount": Decimal("1"),
        "max_deposit_amount": Decimal("5000"),
        "webhook_base_url": "https://example.com",
        "freepay_public_key": "public_key_test",
        "freepay_secret_key": "secret_key_test",
        "environment": "test",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
def test_settings(monkeypatch):
    settings = _build_test_settings()
    for module_name in _CONFIG_MODULES:
        monkeypatch.setattr(importlib.import_module(module_name), "settings", settings)
    return settings


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s


class FakeProvider(PaymentProvider):
    def __init__(self) -> None:
        self.created: list[tuple] = []
        self.status = PaymentStatus.PENDING
        self.pix_code = "00020126580014br.gov.bcb.pix...FAKE"
        self.fail_create = False
        self.fail_status = False

    async def create_pix_payment(self, amount, external_id, description, customer):
        if self.fail_create:
            raise PaymentError("provider fora do ar")
        self.created.append((external_id, amount, customer))
        return PaymentResponse(
            external_id=external_id,
            provider_id=f"txn_{external_id}",
            status=PaymentStatus.PENDING,
            amount=amount,
            qr_code=self.pix_code,
            pix_copy_paste=self.pix_code,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )

    async def get_payment_status(self, provider_id):
        if self.fail_status:
            raise PaymentError("provider fora do ar")
        return PaymentResponse(
            external_id="",
            provider_id=provider_id,
            status=self.status,
            amount=Decimal("0"),
        )

    def parse_payment_response(self, payload):
        raise NotImplementedError

    def validate_webhook(self, headers, payload):
        return (
            isinstance(payload, dict)
            and "Id" in payload
            and "Status" in payload
        )

    def handle_webhook(self, payload):
        return PaymentWebhookData(
            event_id=str(payload["Id"]),
            provider_id=str(payload.get("Id")),
            external_id=payload.get("ExternalId"),
            status=PaymentStatus(payload["Status"]),
            amount=Decimal(str(payload.get("Amount", 0))),
        )

    async def close(self):
        return None


@pytest.fixture
def provider():
    return FakeProvider()
