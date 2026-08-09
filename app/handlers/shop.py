from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import (
    AlreadyPurchased,
    InsufficientBalance,
    InsufficientStock,
    ProductNotFound,
)
from app.handlers.common import answer, edit_message
from app.keyboards.callbacks import ShopCB
from app.keyboards.main import back_to_menu_kb
from app.keyboards.shop import buy_result_kb, product_kb, shop_kb
from app.services import product_service, purchase_service
from app.utils.formatting import esc, fmt_money

router = Router()


def _product_detail_text(product) -> str:
    stock = product.stock if product.stock is not None else 0
    description = product.description or "Sem descrição."
    return (
        f"🛒 {esc(product.name)}\n\n"
        f"Descrição:\n{esc(description)}\n\n"
        f"Preço:\n{fmt_money(product.price)}\n\n"
        f"Estoque:\n{stock}"
    )


@router.callback_query(ShopCB.filter(F.action == "list"))
async def cb_shop_list(callback: CallbackQuery, session: AsyncSession) -> None:
    await answer(callback)
    products = await product_service.list_active_products(session)
    if not products:
        await edit_message(
            callback.message,
            "🛒 Produtos disponíveis\n\nNenhum produto disponível no momento.",
            back_to_menu_kb(),
        )
        return
    lines = "\n".join(
        f"• {esc(p.name)} — {fmt_money(p.price)}" for p in products
    )
    await edit_message(
        callback.message,
        f"🛒 Produtos disponíveis\n\n{lines}\n\nSelecione um produto:",
        shop_kb(products),
    )


@router.callback_query(ShopCB.filter(F.action == "prod"))
async def cb_shop_product(
    callback: CallbackQuery,
    callback_data: ShopCB,
    session: AsyncSession,
) -> None:
    await answer(callback)
    product = await product_service.get_product(session, callback_data.product_id)
    if product is None or not product.active:
        await edit_message(
            callback.message,
            "❌ Este produto não está mais disponível.",
            back_to_menu_kb(),
        )
        return
    await edit_message(
        callback.message, _product_detail_text(product), product_kb(product.id)
    )


@router.callback_query(ShopCB.filter(F.action == "buy"))
async def cb_shop_buy(
    callback: CallbackQuery,
    callback_data: ShopCB,
    session: AsyncSession,
) -> None:
    await answer(callback)
    user_id = callback.from_user.id

    try:
        async with session.begin():
            purchase = await purchase_service.buy_product(
                session, user_id, callback_data.product_id
            )
    except ProductNotFound:
        await edit_message(
            callback.message,
            "❌ Produto não encontrado ou indisponível.",
            back_to_menu_kb(),
        )
        return
    except InsufficientBalance:
        await edit_message(
            callback.message,
            "❌ Saldo insuficiente para esta compra.\n\n"
            "Adicione saldo para continuar. 👇",
            buy_result_kb(),
        )
        return
    except InsufficientStock:
        await edit_message(
            callback.message,
            "❌ Produto sem estoque no momento.",
            back_to_menu_kb(),
        )
        return
    except AlreadyPurchased:
        await edit_message(
            callback.message,
            "ℹ️ Você já possui este produto.",
            back_to_menu_kb(),
        )
        return

    product = await product_service.get_product(session, callback_data.product_id)
    content = product.content if product else None
    receipt = (
        f"✅ Compra realizada com sucesso!\n\n"
        f"🛒 {esc(product.name) if product else ''}\n"
        f"💰 Valor: {fmt_money(purchase.amount)}\n"
        f"📦 Código do pedido: #{purchase.id}\n\n"
    )
    if content:
        receipt += f"📦 Seu produto:\n\n{esc(content)}"
    else:
        receipt += "📦 Entrega automatizada concluída."
    await callback.message.answer(receipt)
    await edit_message(
        callback.message,
        _product_detail_text(product) if product else "✅ Compra concluída.",
        product_kb(callback_data.product_id) if product else None,
    )
