import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from app.config.settings import settings

_AMOUNT_RE = re.compile(r"^\d{1,9}([.,]\d{1,2})?$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\d{10,11}$")

_CNPJ_WEIGHTS_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_CNPJ_WEIGHTS_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def parse_amount(text: str) -> Decimal | None:
    cleaned = text.strip().replace("R$", "").replace(" ", "").strip()
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    if not _AMOUNT_RE.match(cleaned):
        return None
    try:
        amount = Decimal(cleaned)
        if amount <= 0:
            return None
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def validate_deposit_amount(amount: Decimal | None) -> bool:
    if amount is None:
        return False
    return settings.min_deposit_amount <= amount <= settings.max_deposit_amount


def validate_cpf(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    for index in (9, 10):
        total = sum(int(digits[pos]) * ((index + 1) - pos) for pos in range(index))
        check = (total * 10) % 11
        check = 0 if check == 10 else check
        if int(digits[index]) != check:
            return False
    return True


def validate_cnpj(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if len(digits) != 14 or digits == digits[0] * 14:
        return False

    def calc_digit(payload: str, weights: list[int]) -> int:
        total = sum(int(digits) * weight for digits, weight in zip(payload, weights))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder

    if int(digits[12]) != calc_digit(digits[:12], _CNPJ_WEIGHTS_1):
        return False
    if int(digits[13]) != calc_digit(digits[:13], _CNPJ_WEIGHTS_2):
        return False
    return True


def validate_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value.strip()))


def validate_phone(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    return bool(_PHONE_RE.match(digits))
