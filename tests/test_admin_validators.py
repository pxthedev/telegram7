from __future__ import annotations

from decimal import Decimal

from app.utils.formatting import fmt_money
from app.utils.validators import (
    parse_amount,
    validate_cnpj,
    validate_cpf,
    validate_deposit_amount,
    validate_email,
    validate_phone,
)


def test_admin_ids(test_settings):
    assert test_settings.is_admin(1) is True
    assert test_settings.is_admin(2) is True
    assert test_settings.is_admin(999) is False


def test_parse_amount_formats(test_settings):
    assert parse_amount("10") == Decimal("10.00")
    assert parse_amount("10,50") == Decimal("10.50")
    assert parse_amount("R$ 10,50") == Decimal("10.50")
    assert parse_amount("1.000,50") == Decimal("1000.50")
    assert parse_amount("999") == Decimal("999.00")


def test_parse_amount_invalid(test_settings):
    assert parse_amount("abc") is None
    assert parse_amount("0") is None
    assert parse_amount("") is None
    assert parse_amount("-10") is None
    assert parse_amount("10,555") is None


def test_validate_deposit_amount_bounds(test_settings):
    assert validate_deposit_amount(Decimal("1")) is True
    assert validate_deposit_amount(Decimal("5000")) is True
    assert validate_deposit_amount(Decimal("0.50")) is False
    assert validate_deposit_amount(Decimal("5000.01")) is False
    assert validate_deposit_amount(None) is False


def test_validate_cpf():
    assert validate_cpf("529.982.247-25") is True
    assert validate_cpf("52998224725") is True
    assert validate_cpf("11111111111") is False
    assert validate_cpf("12345678901") is False
    assert validate_cpf("5299822472") is False


def test_validate_cnpj():
    assert validate_cnpj("11.222.333/0001-81") is True
    assert validate_cnpj("11222333000181") is True
    assert validate_cnpj("11111111111111") is False
    assert validate_cnpj("11222333000182") is False


def test_validate_email():
    assert validate_email("teste@exemplo.com") is True
    assert validate_email("a.b@exemplo.com.br") is True
    assert validate_email("invalido") is False
    assert validate_email("sem_arroba.com") is False
    assert validate_email("") is False


def test_validate_phone():
    assert validate_phone("11999999999") is True
    assert validate_phone("(11) 99999-9999") is True
    assert validate_phone("119999") is False
    assert validate_phone("abc") is False


def test_format_money():
    assert fmt_money(Decimal("1000.50")) == "R$ 1.000,50"
    assert fmt_money(Decimal("10")) == "R$ 10,00"
    assert fmt_money(Decimal("0")) == "R$ 0,00"
