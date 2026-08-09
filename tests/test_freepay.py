from __future__ import annotations

from decimal import Decimal

import pytest

from app.config.settings import Settings
from app.exceptions import InvalidWebhook, PaymentError
from app.services.payment.base import PaymentStatus
from app.services.payment.freepay import FreePayClient


def _client(**overrides) -> FreePayClient:
    values = {
        "bot_token": "test:token",
        "bot_username": "test_bot",
        "database_url": "sqlite+aiosqlite://",
        "admin_ids": [1, 2],
        "affiliate_percentage": Decimal("25"),
        "webhook_base_url": "https://example.com",
        "freepay_api_url": "https://api.freepaybrasil.com",
        "freepay_public_key": "public_key_test",
        "freepay_secret_key": "secret_key_test",
        "freepay_amount_in_cents": True,
        "environment": "test",
    }
    values.update(overrides)
    return FreePayClient(Settings(_env_file=None, **values))


def test_parse_create_response_pending():
    client = _client()
    payload = {
        "data": [
            {
                "id": "abc123",
                "status": "PENDING",
                "amount": 5000,
                "payment_method": "pix",
                "pix": [
                    {
                        "expiration_date": "2026-08-09T10:00:00Z",
                        "qr_code": "00020126580014BR.GOV.BCB.PIX...",
                    }
                ],
            }
        ]
    }
    response = client.parse_payment_response(payload)
    assert response.provider_id == "abc123"
    assert response.status is PaymentStatus.PENDING
    assert response.amount == Decimal("5000")
    assert response.qr_code == "00020126580014BR.GOV.BCB.PIX..."
    assert response.pix_copy_paste == "00020126580014BR.GOV.BCB.PIX..."
    assert response.expires_at is not None
    assert response.expires_at.tzinfo is not None


def test_parse_create_response_paid():
    client = _client()
    payload = {
        "data": [
            {
                "id": "xyz",
                "status": "PAID",
                "amount": 1000,
                "pix": [{"expiration_date": None, "qr_code": "abc"}],
            }
        ]
    }
    response = client.parse_payment_response(payload)
    assert response.status is PaymentStatus.PAID
    assert response.expires_at is None


def test_parse_create_response_invalid():
    client = _client()
    with pytest.raises(PaymentError):
        client.parse_payment_response({"data": []})
    with pytest.raises(PaymentError):
        client.parse_payment_response({})


def test_status_mapping():
    client = _client()
    assert client._map_status("PAID") is PaymentStatus.PAID
    assert client._map_status("pending") is PaymentStatus.PENDING
    assert client._map_status("REFUSED") is PaymentStatus.FAILED
    assert client._map_status("FAILED") is PaymentStatus.FAILED
    assert client._map_status("EXPIRED") is PaymentStatus.EXPIRED
    assert client._map_status("CHARGEBACK") is PaymentStatus.FAILED
    assert client._map_status("PRECHARGEBACK") is PaymentStatus.FAILED
    assert client._map_status("REFUNDED") is PaymentStatus.REFUNDED
    assert client._map_status("ERROR") is PaymentStatus.FAILED
    assert client._map_status(None) is PaymentStatus.PENDING
    assert client._map_status("DESCONHECIDO") is PaymentStatus.PENDING


def test_validate_webhook_structural():
    client = _client()
    assert client.validate_webhook({}, {"Id": "1", "Status": "PAID"}) is True
    assert client.validate_webhook({}, {"Id": "1", "Status": "PENDING"}) is True
    assert client.validate_webhook({}, {"Id": "1", "Status": "DESCONHECIDO"}) is False
    assert client.validate_webhook({}, {"Status": "PAID"}) is False
    assert client.validate_webhook({}, {"Id": "1"}) is False
    assert client.validate_webhook({}, "texto") is False
    assert client.validate_webhook({}, None) is False


def test_handle_webhook_paid():
    client = _client()
    data = client.handle_webhook(
        {
            "Id": "evt1",
            "Status": "PAID",
            "ExternalId": "pay_1",
            "Amount": 5000,
            "PaidAt": "2026-08-09T10:00:00Z",
        }
    )
    assert data.event_id == "evt1"
    assert data.provider_id == "evt1"
    assert data.external_id == "pay_1"
    assert data.status is PaymentStatus.PAID
    assert data.amount == Decimal("5000")
    assert data.confirmed_at is not None


def test_handle_webhook_invalid():
    client = _client()
    with pytest.raises(InvalidWebhook):
        client.handle_webhook({"Id": "evt1", "Status": "FOO"})


def test_amount_in_cents():
    client = _client(freepay_amount_in_cents=True)
    assert client._to_provider_amount(Decimal("120.50")) == 12050
    assert client._to_provider_amount(Decimal("10")) == 1000


def test_amount_in_reais():
    client = _client(freepay_amount_in_cents=False)
    assert client._to_provider_amount(Decimal("120.50")) == 120
    assert client._to_provider_amount(Decimal("10")) == 10
