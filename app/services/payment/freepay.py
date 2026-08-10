from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

import httpx

from app.config.settings import Settings
from app.exceptions import InvalidWebhook, PaymentError
from app.services.payment.base import (
    PaymentCustomer,
    PaymentProvider,
    PaymentResponse,
    PaymentStatus,
    PaymentWebhookData,
)

logger = logging.getLogger(__name__)

_PROVIDER_STATUS_MAP: dict[str, PaymentStatus] = {
    "PENDING": PaymentStatus.PENDING,
    "PAID": PaymentStatus.PAID,
    "REFUNDED": PaymentStatus.REFUNDED,
    "REFUSED": PaymentStatus.FAILED,
    "FAILED": PaymentStatus.FAILED,
    "EXPIRED": PaymentStatus.EXPIRED,
    "CHARGEBACK": PaymentStatus.FAILED,
    "PRECHARGEBACK": PaymentStatus.FAILED,
    "ERROR": PaymentStatus.FAILED,
}

_NULL_DATE = "0001-01-01"


class FreePayClient(PaymentProvider):
    def __init__(self, settings: Settings) -> None:
        self.api_url = settings.freepay_api_url.rstrip("/")
        self.public_key = settings.freepay_public_key
        self.secret_key = settings.freepay_secret_key
        self.postback_url = settings.freepay_postback_url
        self.timeout = settings.freepay_timeout_seconds
        self.retries = settings.freepay_retries
        self.amount_in_cents = settings.freepay_amount_in_cents
        self.expires_in_days = settings.freepay_pix_expires_in_days
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            credentials = base64.b64encode(
                f"{self.public_key}:{self.secret_key}".encode()
            ).decode()
            transport = httpx.AsyncHTTPTransport(retries=self.retries)
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                timeout=self.timeout,
                transport=transport,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _to_provider_amount(self, amount: Decimal) -> int:
        if self.amount_in_cents:
            return int(amount.quantize(Decimal("0.01")) * 100)
        return int(amount)

    def _from_provider_amount(self, value) -> Decimal:
        return Decimal(str(value))

    def _map_status(self, status: str | None) -> PaymentStatus:
        if status is None:
            return PaymentStatus.PENDING
        return _PROVIDER_STATUS_MAP.get(str(status).upper(), PaymentStatus.PENDING)

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        raw = str(value).strip()
        if raw.startswith(_NULL_DATE):
            return None
        normalized = raw
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            try:
                parsed = datetime.strptime(raw, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                logger.warning("Data inválida da FreePay: %s", raw)
                return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    async def create_pix_payment(
        self,
        amount: Decimal,
        external_id: str,
        description: str,
        customer: PaymentCustomer,
    ) -> PaymentResponse:
        payload = {
            "amount": self._to_provider_amount(amount),
            "payment_method": "pix",
            "postback_url": self.postback_url,
            "customer": {
                "name": customer.name,
                "email": customer.email,
                "phone": customer.phone,
                "document": {
                    "type": customer.document_type,
                    "number": customer.document_number,
                },
            },
            "items": [
                {
                    "title": description or "Recarga de saldo",
                    "unit_price": self._to_provider_amount(amount),
                    "quantity": 1,
                    "tangible": False,
                    "external_ref": external_id,
                }
            ],
            "pix": {"expires_in_days": self.expires_in_days},
            "metadata": {"external_id": external_id, "source": "telegram_bot"},
        }
        try:
            response = await self.client.post(
                "/v1/payment-transaction/create", json=payload
            )
            if response.status_code >= 400:
                logger.error(
                    "FreePay: cobrança PIX rejeitada (external_id=%s) HTTP %s: %s",
                    external_id,
                    response.status_code,
                    response.text[:1000],
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error(
                "FreePay: falha ao criar cobrança PIX (external_id=%s)", external_id
            )
            raise PaymentError("Não foi possível criar a cobrança PIX") from exc

        parsed = self.parse_payment_response(response.json())
        parsed.external_id = external_id
        return parsed

    def parse_payment_response(self, payload: dict) -> PaymentResponse:
        try:
            data = payload["data"]
            pix = data.get("pix") or {}
            qr_code = pix.get("qr_code")
            return PaymentResponse(
                external_id=data.get("external_id") or "",
                provider_id=data["id"],
                status=self._map_status(data.get("status")),
                amount=self._from_provider_amount(data.get("amount") or 0),
                qr_code=qr_code,
                pix_copy_paste=qr_code,
                expires_at=self._parse_datetime(pix.get("expiration_date")),
            )
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            logger.error("FreePay: resposta de criação inválida: %r", payload)
            raise PaymentError("Resposta inválida da FreePay") from exc

    async def get_payment_status(self, provider_id: str) -> PaymentResponse:
        try:
            response = await self.client.get(
                f"/v1/payment-transaction/info/{provider_id}"
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error(
                "FreePay: falha ao consultar status (provider_id=%s)", provider_id
            )
            raise PaymentError("Não foi possível consultar o pagamento") from exc

        data = response.json()["data"]
        return PaymentResponse(
            external_id=data.get("external_id") or "",
            provider_id=data.get("id") or provider_id,
            status=self._map_status(data.get("status")),
            amount=self._from_provider_amount(data.get("amount") or 0),
        )

    async def refund_payment(self, provider_id: str) -> None:
        try:
            response = await self.client.post(
                f"/v1/payment-transaction/{provider_id}/refund"
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("FreePay: falha ao estornar (provider_id=%s)", provider_id)
            raise PaymentError("Não foi possível estornar o pagamento") from exc

    def validate_webhook(self, headers: dict, payload: dict) -> bool:
        if not isinstance(payload, dict):
            return False
        if "Id" not in payload or "Status" not in payload:
            return False
        if str(payload["Status"]).upper() not in _PROVIDER_STATUS_MAP:
            return False
        return True

    def handle_webhook(self, payload: dict) -> PaymentWebhookData:
        if not self.validate_webhook({}, payload):
            raise InvalidWebhook("Webhook da FreePay inválido")
        status = self._map_status(payload.get("Status"))
        return PaymentWebhookData(
            event_id=str(payload["Id"]),
            provider_id=str(payload.get("Id")),
            external_id=str(payload.get("ExternalId"))
            if payload.get("ExternalId")
            else None,
            status=status,
            amount=self._from_provider_amount(payload.get("Amount"))
            if payload.get("Amount") is not None
            else None,
            confirmed_at=self._parse_datetime(payload.get("PaidAt")),
        )
