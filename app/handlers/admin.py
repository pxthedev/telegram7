from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.models.affiliate import Affiliate
from app.database.models.pix_payment import PixPayment
from app.database.models.product import Product
from app.database.models.purchase import Purchase
from app.database.models.user import User
from app.exceptions import ProductNotFound
from app.handlers.common import answer, edit_message
from app.keyboards.admin import (
    admin_back_kb,
    admin_dashboard_kb,
    admin_list_paginated_kb,
    admin_menu_kb,
    admin_product_kb,
    admin_products_kb,
)
from app.keyboards.callbacks import AdminCB
from app.services import product_service, transaction_service
from app.states.user_states import (
    ProductCommandStates,
    ProductCreateStates,
    ProductEditStates,
)
from app.utils.formatting import (
    esc,
    fmt_datetime,
    fmt_money,
    payment_status_label,
)
from app.utils.logging import memory_log_handler
from app.utils.pagination import paginate
from app.utils.validators import parse_amount

logger = logging.getLogger(__name__)

router = Router()


class AdminAccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        user_id = getattr(user, "id", None)
        if not settings.is_admin(user_id):
            return None
        return await handler(event, data)


def _since_for(period: str) -> datetime | None:
    now = datetime.now(timezone.utc)
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "7d":
        return now - timedelta(days=7)
    if period == "30d":
        return now - timedelta(days=30)
    return None


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession) -> None:
    if not settings.is_admin(message.from_user.id):
        return
    await message.answer("⚙️ Painel Administrativo", reply_markup=admin_menu_kb())


@router.message(Command("addproduto"))
async def cmd_add_product(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(ProductCommandStates.name)
    await message.answer(
        "➕ Novo produto\n\n"
        "Envie o nome:",
        admin_back_kb("products"),
    )


@router.message(ProductCommandStates.name)
async def fsm_cmd_product_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name or len(name) > 255:
        await message.answer("❌ Nome inválido (máx. 255 caracteres). Envie novamente:")
        return
    await state.update_data(product_name=name)
    await state.set_state(ProductCommandStates.description)
    await message.answer("Envie a descrição:")


@router.message(ProductCommandStates.description)
async def fsm_cmd_product_description(message: Message, state: FSMContext) -> None:
    description = (message.text or "").strip()
    if not description or description == "-":
        await message.answer("❌ A descrição é obrigatória. Envie a descrição:")
        return
    await state.update_data(product_description=description)
    await state.set_state(ProductCommandStates.price)
    await message.answer(
        "Envie o preço (ex: 49,90) ou '-' para deixar grátis:"
    )


@router.message(ProductCommandStates.price)
async def fsm_cmd_product_price(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    raw = (message.text or "").strip()
    price = Decimal("0")
    if raw and raw != "-":
        parsed = parse_amount(raw)
        if parsed is None:
            await message.answer(
                "❌ Preço inválido. Envie o preço (ex: 49,90) ou '-' para deixar grátis:"
            )
            return
        price = parsed
    data = await state.get_data()
    async with session.begin():
        await product_service.create_product(
            session,
            name=data["product_name"],
            description=data["product_description"],
            price=price,
            stock=0,
            content=None,
        )
    await state.clear()
    await message.answer("✅ Produto criado com sucesso!", reply_markup=admin_menu_kb())


@router.callback_query(AdminCB.filter(F.action == "menu"))
async def cb_admin_menu(callback: CallbackQuery) -> None:
    await answer(callback)
    await edit_message(
        callback.message, "⚙️ Painel Administrativo", admin_menu_kb()
    )


@router.callback_query(AdminCB.filter(F.action == "dash"))
async def cb_admin_dashboard(
    callback: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    await answer(callback)
    period = callback_data.period or "today"
    since = _since_for(period)

    users_total = await session.scalar(select(func.count(User.id)))
    products_total = await session.scalar(select(func.count(Product.id)))

    purchases_total = await session.scalar(
        select(func.count(Purchase.id)).where(
            Purchase.status == "completed",
            *(Purchase.created_at >= since if since else []),
        )
    )
    sales_total = await session.scalar(
        select(func.coalesce(func.sum(Purchase.amount), 0)).where(
            Purchase.status == "completed",
            *(Purchase.created_at >= since if since else []),
        )
    )
    deposits_total = await transaction_service.sum_by_type(
        session, "DEPOSIT", since
    )
    commissions_total = await session.scalar(
        select(func.coalesce(func.sum(Affiliate.commission), 0)).where(
            Affiliate.status == "paid",
            *(Affiliate.created_at >= since if since else []),
        )
    )

    period_label = {
        "today": "Hoje",
        "7d": "Últimos 7 dias",
        "30d": "Últimos 30 dias",
        "all": "Total geral",
    }.get(period, "Hoje")

    text = (
        f"📊 Dashboard\n\n"
        f"Período: {period_label}\n\n"
        f"👥 Usuários: {users_total or 0}\n"
        f"🛒 Pedidos: {purchases_total or 0}\n"
        f"💰 Vendas: {fmt_money(sales_total or 0)}\n"
        f"💳 PIX recebidos: {fmt_money(deposits_total)}\n"
        f"🤝 Comissões: {fmt_money(commissions_total or 0)}\n"
        f"📦 Produtos: {products_total or 0}"
    )
    await edit_message(callback.message, text, admin_dashboard_kb(period))


@router.callback_query(AdminCB.filter(F.action == "users"))
async def cb_admin_users(
    callback: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    await answer(callback)
    total = await session.scalar(select(func.count(User.id)))
    total_pages = max(1, (total or 0) + 9) // 10
    result = await session.scalars(
        select(User)
        .order_by(User.created_at.desc())
        .limit(10)
        .offset((callback_data.page - 1) * 10)
    )
    users = list(result)
    if not users:
        text = "👥 Usuários\n\nNenhum usuário registrado."
    else:
        lines = []
        for user in users:
            name = user.first_name or user.username or "—"
            lines.append(
                f"👤 {esc(name)}\n"
                f"🆔 {user.telegram_id}\n"
                f"💰 {fmt_money(user.balance)}\n"
                f"📅 {fmt_datetime(user.created_at)}"
            )
        text = "👥 Usuários\n\n" + "\n\n".join(lines)
    await edit_message(
        callback.message,
        text,
        admin_list_paginated_kb("users", callback_data.page, total_pages),
    )


@router.callback_query(AdminCB.filter(F.action == "products"))
async def cb_admin_products(
    callback: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    await answer(callback)
    products = await product_service.list_all_products(session)
    page_items, total_pages = paginate(products, callback_data.page, per_page=5)
    text = "🛒 Produtos\n\n"
    if not page_items:
        text += "Nenhum produto cadastrado.\n\nUse ➕ Novo para criar."
    else:
        text += "\n".join(
            f"{'🟢' if p.active else '🔴'} {esc(p.name)} — "
            f"{fmt_money(p.price)} | Estoque: {p.stock}"
            for p in page_items
        )
    await edit_message(
        callback.message,
        text,
        admin_products_kb(page_items, callback_data.page, total_pages),
    )


@router.callback_query(AdminCB.filter(F.action == "prod"))
async def cb_admin_product(
    callback: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    await answer(callback)
    product = await product_service.get_product(session, callback_data.product_id)
    if product is None:
        await edit_message(
            callback.message, "❌ Produto não encontrado.", admin_back_kb("products")
        )
        return
    sales, sales_total = await product_service.get_product_stats(
        session, product.id
    )
    status = "Ativo" if product.active else "Inativo"
    text = (
        f"🛒 {esc(product.name)}\n\n"
        f"Descrição:\n{esc(product.description or '—')}\n\n"
        f"Preço: {fmt_money(product.price)}\n"
        f"Estoque: {product.stock}\n"
        f"Status: {status}\n"
        f"Criado: {fmt_datetime(product.created_at)}\n\n"
        f"📈 Vendas: {sales} | Total: {fmt_money(sales_total)}"
    )
    await edit_message(callback.message, text, admin_product_kb(product))


@router.callback_query(AdminCB.filter(F.action == "prodnew"))
async def cb_admin_product_new(callback: CallbackQuery, state: FSMContext) -> None:
    await answer(callback)
    await state.clear()
    await state.set_state(ProductCreateStates.name)
    await edit_message(
        callback.message,
        "➕ Novo produto\n\nEnvie o nome:",
        admin_back_kb("products"),
    )


@router.message(ProductCreateStates.name)
async def fsm_product_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name or len(name) > 255:
        await message.answer("❌ Nome inválido (máx. 255 caracteres). Envie novamente:")
        return
    await state.update_data(product_name=name)
    await state.set_state(ProductCreateStates.description)
    await message.answer("Envie a descrição:")


@router.message(ProductCreateStates.description)
async def fsm_product_description(message: Message, state: FSMContext) -> None:
    await state.update_data(
        product_description=(message.text or "").strip() or "Sem descrição."
    )
    await state.set_state(ProductCreateStates.content)
    await message.answer(
        "Envie o conteúdo a ser entregue (chave, link, texto).\n"
        "Envie '-' para pular:"
    )


@router.message(ProductCreateStates.content)
async def fsm_product_content(message: Message, state: FSMContext) -> None:
    content = (message.text or "").strip()
    await state.update_data(product_content=None if content == "-" else content)
    await state.set_state(ProductCreateStates.price)
    await message.answer("Envie o preço (ex: 49,90):")


@router.message(ProductCreateStates.price)
async def fsm_product_price(message: Message, state: FSMContext) -> None:
    price = parse_amount(message.text or "")
    if price is None or price <= 0:
        await message.answer("❌ Preço inválido. Envie o preço (ex: 49,90):")
        return
    await state.update_data(product_price=str(price))
    await state.set_state(ProductCreateStates.stock)
    await message.answer("Envie a quantidade em estoque:")


@router.message(ProductCreateStates.stock)
async def fsm_product_stock(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    try:
        stock = int((message.text or "").strip())
        if stock < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Estoque inválido. Envie um número inteiro:")
        return
    data = await state.get_data()
    async with session.begin():
        await product_service.create_product(
            session,
            name=data["product_name"],
            description=data["product_description"],
            price=Decimal(data["product_price"]),
            stock=stock,
            content=data.get("product_content"),
        )
    await state.clear()
    await message.answer("✅ Produto criado com sucesso!", reply_markup=admin_menu_kb())


@router.callback_query(AdminCB.filter(F.action == "prodprice"))
async def cb_admin_product_price(
    callback: CallbackQuery, callback_data: AdminCB, state: FSMContext
) -> None:
    await answer(callback)
    await state.set_state(ProductEditStates.price)
    await state.update_data(edit_product_id=callback_data.product_id)
    await edit_message(
        callback.message,
        "✏️ Envie o novo preço (ex: 59,90):",
        admin_back_kb("products"),
    )


@router.message(ProductEditStates.price)
async def fsm_product_edit_price(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    price = parse_amount(message.text or "")
    if price is None or price <= 0:
        await message.answer("❌ Preço inválido. Envie novamente:")
        return
    data = await state.get_data()
    try:
        async with session.begin():
            await product_service.set_product_price(
                session, data["edit_product_id"], price
            )
    except ProductNotFound:
        await message.answer("❌ Produto não encontrado.", reply_markup=admin_menu_kb())
        await state.clear()
        return
    await state.clear()
    await message.answer("✅ Preço atualizado.", reply_markup=admin_menu_kb())


@router.callback_query(AdminCB.filter(F.action == "prodstock"))
async def cb_admin_product_stock(
    callback: CallbackQuery, callback_data: AdminCB, state: FSMContext
) -> None:
    await answer(callback)
    await state.set_state(ProductEditStates.stock)
    await state.update_data(edit_product_id=callback_data.product_id)
    await edit_message(
        callback.message,
        "📦 Envie a nova quantidade em estoque:",
        admin_back_kb("products"),
    )


@router.message(ProductEditStates.stock)
async def fsm_product_edit_stock(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    try:
        stock = int((message.text or "").strip())
        if stock < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Estoque inválido. Envie um número inteiro:")
        return
    data = await state.get_data()
    try:
        async with session.begin():
            await product_service.set_product_stock(
                session, data["edit_product_id"], stock
            )
    except ProductNotFound:
        await message.answer("❌ Produto não encontrado.", reply_markup=admin_menu_kb())
        await state.clear()
        return
    await state.clear()
    await message.answer("✅ Estoque atualizado.", reply_markup=admin_menu_kb())


@router.callback_query(AdminCB.filter(F.action == "prodtoggle"))
async def cb_admin_product_toggle(
    callback: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    await answer(callback)
    product = await product_service.get_product(session, callback_data.product_id)
    if product is None:
        await edit_message(
            callback.message, "❌ Produto não encontrado.", admin_back_kb("products")
        )
        return
    async with session.begin():
        product = await product_service.set_product_active(
            session, product.id, not product.active
        )
    await cb_admin_product(callback, callback_data, session)


@router.callback_query(AdminCB.filter(F.action == "proddel"))
async def cb_admin_product_delete(
    callback: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    await answer(callback)
    try:
        async with session.begin():
            await product_service.delete_product(session, callback_data.product_id)
        await edit_message(
            callback.message, "✅ Produto excluído.", admin_back_kb("products")
        )
    except (ProductNotFound, IntegrityError):
        await edit_message(
            callback.message,
            "❌ Não foi possível excluir (produto possui vendas ou não existe).",
            admin_back_kb("products"),
        )


@router.callback_query(AdminCB.filter(F.action == "payments"))
async def cb_admin_payments(
    callback: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    await answer(callback)
    total = await session.scalar(select(func.count(PixPayment.id)))
    total_pages = max(1, ((total or 0) + 9) // 10)
    result = await session.scalars(
        select(PixPayment)
        .order_by(PixPayment.created_at.desc())
        .limit(10)
        .offset((callback_data.page - 1) * 10)
    )
    payments = list(result)
    if not payments:
        text = "💳 Pagamentos\n\nNenhum pagamento registrado."
    else:
        lines = []
        for payment in payments:
            lines.append(
                f"#{payment.id} • Usuário {payment.user_id}\n"
                f"Valor: {fmt_money(payment.amount)} | {payment_status_label(payment.status)}\n"
                f"Data: {fmt_datetime(payment.created_at)}"
            )
        text = "💳 Pagamentos\n\n" + "\n\n".join(lines)
    await edit_message(
        callback.message,
        text,
        admin_list_paginated_kb("payments", callback_data.page, total_pages),
    )


@router.callback_query(AdminCB.filter(F.action == "affiliates"))
async def cb_admin_affiliates(
    callback: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    await answer(callback)
    total = await session.scalar(select(func.count(Affiliate.id)))
    total_pages = max(1, ((total or 0) + 9) // 10)
    result = await session.execute(
        select(Affiliate, User.username, User.first_name)
        .join(User, Affiliate.affiliate_id == User.id)
        .order_by(Affiliate.created_at.desc())
        .limit(10)
        .offset((callback_data.page - 1) * 10)
    )
    rows = result.all()
    if not rows:
        text = "🤝 Afiliados\n\nNenhuma comissão registrada."
    else:
        lines = []
        for record, username, first_name in rows:
            name = first_name or username or "—"
            lines.append(
                f"🤝 {esc(name)} | Comissão: {fmt_money(record.commission)}\n"
                f"Indicado: {record.referred_id} | Data: {fmt_datetime(record.created_at)}"
            )
        text = "🤝 Afiliados\n\n" + "\n\n".join(lines)
    await edit_message(
        callback.message,
        text,
        admin_list_paginated_kb("affiliates", callback_data.page, total_pages),
    )


@router.callback_query(AdminCB.filter(F.action == "stock"))
async def cb_admin_stock(
    callback: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    await answer(callback)
    total = await session.scalar(select(func.count(Product.id)))
    total_pages = max(1, ((total or 0) + 9) // 10)
    result = await session.scalars(
        select(Product)
        .order_by(Product.stock.asc())
        .limit(10)
        .offset((callback_data.page - 1) * 10)
    )
    products = list(result)
    if not products:
        text = "📦 Estoque\n\nNenhum produto cadastrado."
    else:
        lines = []
        for product in products:
            icon = "🟢" if product.stock > 0 else "🔴"
            lines.append(
                f"{icon} {esc(product.name)} — Estoque: {product.stock}"
            )
        text = "📦 Estoque\n\n" + "\n".join(lines)
    await edit_message(
        callback.message,
        text,
        admin_list_paginated_kb("stock", callback_data.page, total_pages),
    )


@router.callback_query(AdminCB.filter(F.action == "orders"))
async def cb_admin_orders(
    callback: CallbackQuery, callback_data: AdminCB, session: AsyncSession
) -> None:
    await answer(callback)
    total = await session.scalar(select(func.count(Purchase.id)))
    total_pages = max(1, ((total or 0) + 9) // 10)
    result = await session.execute(
        select(Purchase, Product.name, User.first_name, User.username)
        .join(Product, Purchase.product_id == Product.id)
        .join(User, Purchase.user_id == User.id)
        .order_by(Purchase.created_at.desc())
        .limit(10)
        .offset((callback_data.page - 1) * 10)
    )
    rows = result.all()
    if not rows:
        text = "📋 Pedidos\n\nNenhum pedido registrado."
    else:
        lines = []
        for purchase, product_name, first_name, username in rows:
            customer = first_name or username or "—"
            lines.append(
                f"#{purchase.id} • {esc(product_name)}\n"
                f"Cliente: {esc(customer)} | {fmt_money(purchase.amount)}\n"
                f"Data: {fmt_datetime(purchase.created_at)}"
            )
        text = "📋 Pedidos\n\n" + "\n\n".join(lines)
    await edit_message(
        callback.message,
        text,
        admin_list_paginated_kb("orders", callback_data.page, total_pages),
    )


@router.callback_query(AdminCB.filter(F.action == "logs"))
async def cb_admin_logs(callback: CallbackQuery) -> None:
    await answer(callback)
    recent = ""
    if memory_log_handler is not None:
        recent = memory_log_handler.recent(40)
    text = "📜 Logs recentes\n\n" + (f"<code>{esc(recent)}</code>" if recent else "Sem logs.")
    await edit_message(callback.message, text, admin_back_kb("menu"))


@router.callback_query(AdminCB.filter(F.action == "config"))
async def cb_admin_config(callback: CallbackQuery) -> None:
    await answer(callback)
    text = (
        f"⚙️ Configurações\n\n"
        f"🌐 Bot: @{settings.bot_username or '—'}\n"
        f"⚙️ Ambiente: {settings.environment}\n"
        f"👥 Admins: {len(settings.admin_ids)}\n\n"
        f"💵 Comissão de afiliados: {settings.affiliate_percentage}%\n"
        f"⏳ Expiração do PIX: {settings.pix_expiration_minutes} min\n"
        f"💰 Depósito mínimo: {fmt_money(settings.min_deposit_amount)}\n"
        f"💰 Depósito máximo: {fmt_money(settings.max_deposit_amount)}\n\n"
        f"🔌 Gateway: FreePay\n"
        f"🌐 API: {settings.freepay_api_url}\n"
        f"💵 Amount em centavos: {'sim' if settings.freepay_amount_in_cents else 'não'}\n"
        f"🔗 Webhook: {settings.freepay_postback_url or '—'}"
    )
    await edit_message(callback.message, text, admin_back_kb("menu"))
