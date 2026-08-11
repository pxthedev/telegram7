from decimal import Decimal

import pytest
from sqlalchemy import select

from app.database.models.product import Product
from app.services.sheets_sync import _normalize, apply_sheet_to_db, parse_product_rows


async def _get_product(session, name: str) -> Product | None:
    return (await session.scalars(select(Product).where(Product.name == name))).first()


class TestParseProductRows:
    def test_skips_blank_rows(self):
        rows = [["", "", ""], ["  ", None, None], ["Produto A", "10,50", "3"]]
        parsed = parse_product_rows(rows)
        assert len(parsed) == 1
        assert parsed[0]["name"] == "Produto A"

    def test_parses_price_and_stock(self):
        parsed = parse_product_rows([["Produto A", "10,50", "3"]])
        assert parsed[0]["price"] == Decimal("10.50")
        assert parsed[0]["stock"] == 3

    def test_price_with_dot(self):
        parsed = parse_product_rows([["Produto B", "19.99", "0"]])
        assert parsed[0]["price"] == Decimal("19.99")

    def test_missing_columns_default(self):
        parsed = parse_product_rows([["Produto C"]])
        assert parsed[0]["price"] is None
        assert parsed[0]["stock"] == 0

    def test_invalid_price_becomes_none(self):
        parsed = parse_product_rows([["Produto D", "nao-e-numero", "1"]])
        assert parsed[0]["price"] is None
        assert parsed[0]["stock"] == 1


class TestNormalize:
    def test_list_of_lists_passes_through(self):
        assert _normalize([["Produto", "10", "2"]]) == [["Produto", "10", "2"]]

    def test_dict_with_data_key(self):
        assert _normalize({"data": [["Produto", "10", "2"]]}) == [
            ["Produto", "10", "2"]
        ]

    def test_list_of_dicts_maps_fields(self):
        rows = _normalize([{"nome": "A", "preco": "10,50", "estoque": "3"}])
        assert rows == [["A", "10,50", "3"]]

    def test_english_keys(self):
        rows = _normalize([{"name": "B", "price": "5", "stock": 1}])
        assert rows == [["B", "5", 1]]

    def test_single_object(self):
        rows = _normalize({"name": "C", "price": "7", "stock": "2"})
        assert rows == [["C", "7", "2"]]


@pytest.mark.asyncio
class TestApplySheetToDb:
    async def test_creates_missing_product(self, session):
        created, updated = await apply_sheet_to_db(
            session, [["Produto X", "9,90", "5"]]
        )
        assert (created, updated) == (1, 0)

    async def test_updates_existing_stock_and_price(self, session):
        session.add(Product(name="Produto Y", price=Decimal("1"), stock=1, active=True))
        await session.commit()

        created, updated = await apply_sheet_to_db(
            session, [["Produto Y", "15.00", "7"]]
        )
        assert (created, updated) == (0, 1)

        product = await _get_product(session, "Produto Y")
        assert product.stock == 7
        assert product.price == Decimal("15.00")

    async def test_does_not_create_without_valid_price(self, session):
        created, updated = await apply_sheet_to_db(session, [["Sem Preço", "abc", "2"]])
        assert (created, updated) == (0, 0)

    async def test_zeroes_stock_from_sheet(self, session):
        session.add(Product(name="Produto Z", price=Decimal("5"), stock=10, active=True))
        await session.commit()

        await apply_sheet_to_db(session, [["Produto Z", "5", "0"]])
        product = await _get_product(session, "Produto Z")
        assert product.stock == 0
