from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from html import escape


def esc(value) -> str:
    return escape(str(value)) if value is not None else ""


def fmt_money(value) -> str:
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    negative = amount < 0
    raw = f"{abs(amount):.2f}"
    integer_part, decimal_part = raw.split(".")
    grouped = ""
    for index, char in enumerate(integer_part[::-1]):
        if index and index % 3 == 0:
            grouped = "." + grouped
        grouped = char + grouped
    sign = "-" if negative else ""
    return f"R$ {sign}{grouped},{decimal_part}"


def fmt_datetime(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d/%m/%Y %H:%M")


def fmt_date(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d/%m/%Y")


PAYMENT_STATUS_LABELS: dict[str, str] = {
    "PENDING": "⏳ Aguardando pagamento",
    "PAID": "✅ Pago",
    "EXPIRED": "⌛ Expirado",
    "CANCELLED": "❌ Cancelado",
    "FAILED": "❌ Falhou",
    "REFUNDED": "↩️ Estornado",
}


def payment_status_label(status: str | None) -> str:
    if status is None:
        return "—"
    return PAYMENT_STATUS_LABELS.get(status.upper(), status.upper())


TRANSACTION_TYPE_LABELS: dict[str, str] = {
    "DEPOSIT": "💳 Depósito",
    "PURCHASE": "🛒 Compra",
    "AFFILIATE": "🤝 Comissão",
    "REFUND": "↩️ Reembolso",
    "ADJUSTMENT": "⚙️ Ajuste",
}


def transaction_type_label(tx_type: str | None) -> str:
    if tx_type is None:
        return "—"
    return TRANSACTION_TYPE_LABELS.get(tx_type.upper(), tx_type.upper())
