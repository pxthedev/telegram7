from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.common import answer, edit_message, ensure_user
from app.keyboards.callbacks import ProfileCB
from app.keyboards.profile import history_kb, profile_kb
from app.services import transaction_service, user_service
from app.utils.formatting import esc, fmt_money

router = Router()


@router.callback_query(ProfileCB.filter(F.action == "view"))
async def cb_profile_view(callback: CallbackQuery, session: AsyncSession) -> None:
    await answer(callback)
    user = await ensure_user(session, callback.from_user)
    stats = await user_service.get_user_stats(session, user.id)
    username = f"@{user.username}" if user.username else "—"
    text = (
        f"✨ Suas Informações\n\n"
        f"👑 Nome: {esc(user.first_name or '—')}\n"
        f"🌐 User: {esc(username)}\n"
        f"🆔 ID: {user.telegram_id}\n\n"
        f"💰 Saldo: {fmt_money(user.balance)}\n\n"
        f"🛒 Compras: {stats['purchases']}\n"
        f"💳 Recargas via PIX: {fmt_money(stats['deposited'])}"
    )
    await edit_message(callback.message, text, profile_kb())


@router.callback_query(ProfileCB.filter(F.action == "rcg"))
async def cb_profile_recharges(
    callback: CallbackQuery,
    callback_data: ProfileCB,
    session: AsyncSession,
) -> None:
    await answer(callback)
    user = await ensure_user(session, callback.from_user)
    rows, total = await transaction_service.list_user_transactions(
        session, user.id, callback_data.page, tx_type="DEPOSIT"
    )
    from app.utils.pagination import paginate

    page_rows, total_pages = paginate(rows, callback_data.page, per_page=5)
    if not page_rows:
        text = "💳 Histórico de recargas\n\nNenhuma recarga encontrada."
    else:
        lines = []
        for tx in page_rows:
            lines.append(
                f"#{tx.id}\n"
                f"Valor: {fmt_money(abs(tx.amount))}\n"
                f"Método: PIX\n"
                f"Status: Pago\n"
                f"Data: {tx.created_at.strftime('%d/%m/%Y')}"
            )
        text = "💳 Histórico de recargas\n\n" + "\n\n".join(lines)
    await edit_message(
        callback.message,
        text,
        history_kb(
            "prof:rcg", callback_data.page, total_pages, ProfileCB(action="view").pack()
        ),
    )
