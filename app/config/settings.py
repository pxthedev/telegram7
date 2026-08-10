from decimal import Decimal
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        enable_decoding=False,
    )

    bot_token: str = ""
    bot_username: str = ""

    database_url: str = "postgresql+asyncpg://bot:bot@postgres:5432/telegram_bot"
    database_ssl: str = "disable"

    admin_ids: list[int] = Field(default_factory=list)
    admin_usernames: list[str] = Field(default_factory=list)

    affiliate_percentage: Decimal = Decimal("25")
    pix_expiration_minutes: int = 30
    min_deposit_amount: Decimal = Decimal("15")
    max_deposit_amount: Decimal = Decimal("5000")

    freepay_api_url: str = "https://api.freepaybrasil.com"
    freepay_public_key: str = ""
    freepay_secret_key: str = ""
    freepay_webhook_secret: str = ""
    freepay_amount_in_cents: bool = True
    freepay_pix_expires_in_days: int = 1
    freepay_timeout_seconds: float = 15.0
    freepay_retries: int = 1

    pix_customer_name: str = ""
    pix_customer_email: str = ""
    pix_customer_phone: str = ""
    pix_customer_document_type: str = "cpf"
    pix_customer_document_number: str = ""

    webhook_base_url: str = ""
    webhook_host: str = "0.0.0.0"
    webhook_port: int = Field(
        default=8080, validation_alias=AliasChoices("WEBHOOK_PORT", "PORT")
    )

    environment: Literal["development", "production", "test"] = "development"

    rate_limit_max: int = 30
    rate_limit_window: int = 10

    log_level: str = "INFO"

    shop_description: str = (
        "💎 Produtos digitais\n"
        "⚡ Entrega rápida\n"
        "🔒 Pagamento seguro\n"
        "📦 Sistema automatizado"
    )

    benefits_text: str = (
        "📅 Como funciona?\n\n"
        "O sistema contabiliza automaticamente as compras qualificadas.\n\n"
        "Quando o requisito for atingido:\n\n"
        "✅ Benefício desbloqueado."
    )

    @field_validator("shop_description", "benefits_text", mode="before")
    @classmethod
    def _decode_literal_newlines(cls, value):
        if isinstance(value, str) and "\\n" in value:
            return value.replace("\\n", "\n")
        return value

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        if isinstance(value, (int, float)):
            return [int(value)]
        return value

    @field_validator("admin_usernames", mode="before")
    @classmethod
    def _parse_admin_usernames(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [
                item.strip().lstrip("@").lower()
                for item in value.split(",")
                if item.strip()
            ]
        if isinstance(value, (list, tuple)):
            return [str(item).lstrip("@").lower() for item in value]
        return value

    @property
    def freepay_postback_url(self) -> str:
        return f"{self.webhook_base_url.rstrip('/')}/webhooks/freepay"

    @property
    def database_connect_args(self) -> dict:
        ssl = (self.database_ssl or "disable").strip().lower()
        if ssl in ("", "disable", "false", "0", "off", "none"):
            return {}
        return {"ssl": ssl}

    def is_admin(
        self,
        telegram_id: int | None = None,
        username: str | None = None,
    ) -> bool:
        if telegram_id is not None and telegram_id in self.admin_ids:
            return True
        if username:
            return username.strip().lstrip("@").lower() in self.admin_usernames
        return False


settings = Settings()
