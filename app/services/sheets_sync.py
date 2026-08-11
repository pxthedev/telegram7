from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.product import Product

logger = logging.getLogger(__name__)

_KEY_MAP = {
    "name": "name",
    "nome": "name",
    "produto": "name",
    "price": "price",
    "preco": "price",
    "preço": "price",
    "valor": "price",
    "stock": "stock",
    "estoque": "stock",
    "qtd": "stock",
    "quantidade": "stock",
}

_UNWRAP_KEYS = ("data", "produtos", "rows", "items", "products")


class ProductSourceError(Exception):
    pass


async def fetch_rows(webhook_url: str) -> list[list]:
    """Busca os produtos no webhook do site e normaliza para lista de linhas."""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(webhook_url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        raise ProductSourceError(f"Falha ao acessar {webhook_url}: {exc}") from exc

    return _normalize(data)


def _normalize(data) -> list[list]:
    if isinstance(data, dict):
        for key in _UNWRAP_KEYS:
            value = data.get(key)
            if isinstance(value, list):
                data = value
                break
        else:
            return [_dict_to_row(data)]
    if not isinstance(data, list):
        raise ProductSourceError("Resposta do webhook não contém uma lista de produtos")

    rows: list[list] = []
    for item in data:
        if isinstance(item, list):
            rows.append(item)
        elif isinstance(item, dict):
            rows.append(_dict_to_row(item))
        else:
            raise ProductSourceError("Item da resposta em formato inválido")
    return rows


def _dict_to_row(item: dict) -> list:
    mapped = {}
    for key, value in item.items():
        normalized = str(key).strip().lower()
        field = _KEY_MAP.get(normalized)
        if field is not None:
            mapped[field] = value
    return [
        str(mapped.get("name", "")),
        mapped.get("price", ""),
        mapped.get("stock", ""),
    ]


def parse_product_rows(rows: list[list]) -> list[dict]:
    """Converte linhas [nome, preço, estoque] em dicionários limpos."""
    products: list[dict] = []
    for row in rows:
        if not row or not str(row[0]).strip():
            continue
        name = str(row[0]).strip()
        price_raw = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        stock_raw = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""

        price: Decimal | None = None
        if price_raw:
            try:
                price = Decimal(str(price_raw).replace(",", "."))
            except InvalidOperation:
                logger.warning("Webhook: preço inválido para %s: %r", name, price_raw)

        stock = 0
        if stock_raw:
            try:
                stock = int(float(stock_raw))
            except ValueError:
                logger.warning("Webhook: estoque inválido para %s: %r", name, stock_raw)

        products.append({"name": name, "price": price, "stock": stock})
    return products


async def apply_sheet_to_db(
    session: AsyncSession, rows: list[list]
) -> tuple[int, int]:
    """Atualiza estoque (e preço) por nome de produto. Cria produtos que faltam."""
    existing = {
        p.name: p for p in (await session.scalars(select(Product))).all()
    }
    created = 0
    updated = 0
    for item in parse_product_rows(rows):
        product = existing.get(item["name"])
        if product is None:
            if item["price"] is None:
                logger.warning(
                    "Webhook: sem preço válido, produto não criado: %s", item["name"]
                )
                continue
            product = Product(
                name=item["name"],
                description="",
                price=item["price"],
                stock=item["stock"],
                active=True,
            )
            session.add(product)
            existing[item["name"]] = product
            created += 1
        else:
            product.stock = item["stock"]
            if item["price"] is not None:
                product.price = item["price"]
            updated += 1
    await session.commit()
    return created, updated
