from __future__ import annotations

from functools import lru_cache

from app.config.settings import settings
from app.services.payment.base import PaymentProvider
from app.services.payment.freepay import FreePayClient


@lru_cache(maxsize=1)
def get_payment_provider() -> PaymentProvider:
    if settings.environment == "test":
        raise RuntimeError("Provider deve ser injetado em testes")
    return FreePayClient(settings)
