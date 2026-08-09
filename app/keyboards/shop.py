from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models.product import Product
from app.keyboards.callbacks import ShopCB
from app.utils.formatting import esc, fmt_money


def shop_kb(products: list[Product]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"🛒 {esc(product.name)} — {fmt_money(product.price)}",
                callback_data=ShopCB(action="prod", product_id=product.id).pack(),
            )
        ]
        for product in products
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text="« Voltar", callback_data=ShopCB(action="list").pack()
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_kb(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛒 Comprar",
                    callback_data=ShopCB(action="buy", product_id=product_id).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="« Voltar", callback_data=ShopCB(action="list").pack()
                )
            ],
        ]
    )


def buy_result_kb() -> InlineKeyboardMarkup:
    from app.keyboards.callbacks import BalanceCB, ShopCB

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💰 Adicionar Saldo",
                    callback_data=BalanceCB(action="menu").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🛒 Continuar comprando",
                    callback_data=ShopCB(action="list").pack(),
                )
            ],
        ]
    )
