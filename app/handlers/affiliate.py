from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.handlers.common import answer, edit_message, ensure_user
from app.keyboards.affiliate import (
    affiliate_back_kb,
    affiliate_history_kb,
    affiliate_kb,
)
from app.keyboards.callbacks import AffiliateCB
from app.services import affiliate_service, user_service
from app.utils.formatting import esc, fmt_money
from app.utils.pagination import paginate

router = Router()


async def _affiliate_panel_text(
    session: AsyncSession, user
) -> str:
    await user_service.ensure_affiliate_code(session, user)
    stats = await affiliate_service.get_affiliate_stats(session, user.id)
    link = affiliate_service.affiliate_link(
        settings.bot_username, user.affiliate_code
    )
    return (
        f"🤝 Programa de Afiliados\n\n"
        f"📊 Seu painel\n\n"
        f"• Indicados: {stats['referrals']}\n"
        f"• Saldo acumulado: {fmt_money(stats['commission'])}\n\n"
        f"🔗 Seu link:\n<code>{esc(link)}</code>\n\n"
        f"💵 Comissão: {settings.affiliate_percentage}% por compra qualificada."
    )


@router.callback_query(AffiliateCB.filter(F.action == "panel"))
async def cb_affiliate_panel(callback: CallbackQuery, session: AsyncSession) -> None:
    await answer(callback)
    user = await ensure_user(session, callback.from_user)
    text = await _affiliate_panel_text(session, user)
    await edit_message(callback.message, text, affiliate_kb())


@router.callback_query(AffiliateCB.filter(F.action == "share"))
async def cb_affiliate_share(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    await answer(callback)
    user = await ensure_user(session, callback.from_user)
    await user_service.ensure_affiliate_code(session, user)
    await session.commit()
    link = affiliate_service.affiliate_link(settings.bot_username, user.affiliate_code)
    text = (
        f"🔗 Compartilhe seu link de afiliado:\n\n"
        f"<code>{esc(link)}</code>\n\n"
        f"Você recebe {settings.affiliate_percentage}% de comissão "
        f"em cada compra feita pelos seus indicados."
    )
    await edit_message(callback.message, text, affiliate_back_kb())


@router.callback_query(AffiliateCB.filter(F.action == "history"))
async def cb_affiliate_history(
    callback: CallbackQuery,
    callback_data: AffiliateCB,
    session: AsyncSession,
) -> None:
    await answer(callback)
    user = await ensure_user(session, callback.from_user)
    rows, total = await affiliate_service.list_affiliate_history(
        session, user.id, callback_data.page
    )
    page_rows, total_pages = paginate(rows, callback_data.page, per_page=5)
    if not page_rows:
        text = "💰 Histórico de comissões\n\nNenhuma comissão registrada."
    else:
        lines = []
        for record, username, first_name in page_rows:
            referred = f"@{username}" if username else (first_name or "usuário")
            lines.append(
                f"🤝 {esc(referred)}\n"
                f"Comissão: {fmt_money(record.commission)}\n"
                f"Data: {record.created_at.strftime('%d/%m/%Y %H:%M')}"
            )
        text = "💰 Histórico de comissões\n\n" + "\n\n".join(lines)
    await edit_message(
        callback.message,
        text,
        affiliate_history_kb(callback_data.page, total_pages),
    )
